from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.db.models import AgentSandboxRuntime
from app.runtime.redaction import redact_secrets_in_text, sanitize_structured_payload
from app.runtime.sandbox_worker import ALLOWED_TASKS

DISALLOWED_SHELL_TASKS = {
    "shell",
    "bash",
    "sh",
    "cmd",
    "powershell",
    "pwsh",
    "exec",
    "eval",
    "system",
    "subprocess",
}


class SandboxSecurityError(PermissionError):
    """Raised when an operation attempts cross-tenant access, shell execution, or host escape."""


class SandboxTimeoutError(TimeoutError):
    """Raised when sandbox execution exceeds the configured timeout."""


class SandboxNotFoundError(LookupError):
    """Raised when the requested runtime cannot be found for the tenant."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _worker_script_path() -> Path:
    return (BACKEND_DIR / "app" / "runtime" / "sandbox_worker.py").resolve()


def _minimal_subprocess_env(workspace_dir: Path) -> dict[str, str]:
    """Build a strictly stripped environment so API keys / DB secrets never reach sandbox workers."""
    env: dict[str, str] = {
        "SANDBOX_WORKSPACE": str(workspace_dir),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
    }
    for safe_key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC"):
        if safe_key in os.environ and safe_key not in {"COMSPEC"}:
            env[safe_key] = os.environ[safe_key]
    return env


def _kill_process_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except psutil.Error:
                pass
        parent.kill()
    except psutil.Error:
        pass


class DockerSandboxManager:
    """Manages per-tenant isolated HR Agent sandbox runtimes.

    Uses hardened Docker containers when a Docker daemon is present, and otherwise
    uses a clearly labelled `development_fallback` isolated child Python worker
    inside a tenant-scoped workspace directory (never disguised as Docker isolation).
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def detect_docker_daemon(self) -> tuple[bool, str | None, str | None]:
        """Return (available, docker_bin_path, detail)."""
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return False, None, "Docker CLI is not installed on host; using development_fallback"
        try:
            proc = subprocess.run(
                [docker_bin, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=3,
                shell=False,
            )
            if proc.returncode == 0:
                version = proc.stdout.strip() or "unknown"
                return True, docker_bin, f"Docker daemon active (v{version})"
            err = redact_secrets_in_text(proc.stderr or proc.stdout, max_len=240)
            return False, docker_bin, f"Docker daemon unreachable ({err}); using development_fallback"
        except Exception as exc:
            return False, docker_bin, f"Docker check failed ({type(exc).__name__}); using development_fallback"

    def _tenant_workspace_root(self, tenant_id: uuid.UUID) -> Path:
        root = (self.settings.sandbox_root_path / str(tenant_id)).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _validate_workspace_path(self, tenant_id: uuid.UUID, workspace_path: str) -> Path:
        tenant_root = self._tenant_workspace_root(tenant_id)
        candidate = Path(workspace_path).resolve()
        if not candidate.is_relative_to(tenant_root):
            raise SandboxSecurityError("Cross-tenant or host workspace escape blocked")
        return candidate

    def _get_runtime_row(self, db: Session, tenant_id: uuid.UUID, runtime_id: uuid.UUID) -> AgentSandboxRuntime:
        row = db.scalar(
            select(AgentSandboxRuntime).where(
                AgentSandboxRuntime.id == runtime_id,
                AgentSandboxRuntime.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise SandboxNotFoundError(f"Sandbox runtime {runtime_id} not found for tenant")
        self._validate_workspace_path(tenant_id, row.workspace_path)
        return row

    def _append_log(
        self,
        row: AgentSandboxRuntime,
        *,
        event: str,
        status: str,
        detail: str,
        duration_ms: int = 0,
        meta: dict[str, Any] | None = None,
    ) -> None:
        logs = list(row.execution_logs_json or [])
        logs.append(
            {
                "timestamp": _utcnow().isoformat(),
                "event": event,
                "status": status,
                "duration_ms": duration_ms,
                "detail": redact_secrets_in_text(detail, max_len=400),
                "meta": sanitize_structured_payload(meta or {}, max_str_len=250),
            }
        )
        row.execution_logs_json = logs[-50:]

    def _collect_resource_stats(self, row: AgentSandboxRuntime) -> dict[str, Any]:
        ws = Path(row.workspace_path)
        ws_bytes = 0
        file_count = 0
        if ws.exists():
            for item in ws.rglob("*"):
                if item.is_file():
                    file_count += 1
                    try:
                        ws_bytes += item.stat().st_size
                    except OSError:
                        pass

        health: dict[str, Any] = {
            "checked_at": _utcnow().isoformat(),
            "backend_mode": row.backend_mode,
            "is_container_isolated": row.is_container_isolated,
            "network_mode": row.network_mode,
            "workspace_bytes": ws_bytes,
            "workspace_files": file_count,
            "cpu_limit": row.cpu_limit,
            "memory_limit_mb": row.memory_limit_mb,
            "memory_used_mb": 0.0,
            "cpu_percent": 0.0,
            "pids": 0,
        }

        if row.is_container_isolated and row.container_id and row.status == "running":
            docker_ok, docker_bin, _ = self.detect_docker_daemon()
            if docker_ok and docker_bin:
                try:
                    proc = subprocess.run(
                        [
                            docker_bin,
                            "stats",
                            "--no-stream",
                            "--format",
                            "{{.CPUPerc}}|{{.MemUsage}}|{{.PIDs}}",
                            row.container_id,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=3,
                        shell=False,
                    )
                    if proc.returncode == 0 and proc.stdout.strip():
                        parts = proc.stdout.strip().split("|")
                        health["cpu_percent_raw"] = parts[0] if len(parts) > 0 else "0%"
                        health["memory_usage_raw"] = parts[1] if len(parts) > 1 else "0MiB"
                        health["pids"] = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
                except Exception:
                    pass
        else:
            try:
                proc = psutil.Process(os.getpid())
                health["host_worker_memory_mb"] = round(proc.memory_info().rss / (1024 * 1024), 2)
                health["host_cpu_percent"] = round(psutil.cpu_percent(interval=None), 1)
            except psutil.Error:
                pass
        return health

    def _build_docker_run_cmd(
        self,
        *,
        docker_bin: str,
        container_name: str,
        workspace_dir: Path,
        image_name: str,
        cpu_limit: float,
        memory_limit_mb: int,
    ) -> list[str]:
        """Build hardened, non-root, no-network, read-only rootfs Docker CLI args (no docker.sock!)."""
        return [
            docker_bin,
            "run",
            "-d",
            "--name",
            container_name,
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--user=10001:10001",
            f"--cpus={cpu_limit}",
            f"--memory={memory_limit_mb}m",
            "--pids-limit=64",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=64m",
            "--entrypoint=sleep",
            "-v",
            f"{workspace_dir}:/sandbox/workspace:rw",
            "-e",
            "SANDBOX_WORKSPACE=/sandbox/workspace",
            image_name,
            "infinity",
        ]

    def create_runtime(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        *,
        rental_id: uuid.UUID | None = None,
        cpu_limit: float | None = None,
        memory_limit_mb: int | None = None,
        timeout_seconds: int | None = None,
        auto_start: bool = True,
    ) -> AgentSandboxRuntime:
        agent_runtime_id = f"hr-rt-{uuid.uuid4().hex[:12]}"
        workspace_dir = (self._tenant_workspace_root(tenant_id) / agent_runtime_id / "workspace").resolve()
        workspace_dir.mkdir(parents=True, exist_ok=True)

        docker_available, docker_bin, docker_detail = self.detect_docker_daemon()
        eff_cpu = float(cpu_limit or self.settings.SANDBOX_DEFAULT_CPU_LIMIT)
        eff_mem = int(memory_limit_mb or self.settings.SANDBOX_DEFAULT_MEMORY_MB)
        eff_timeout = int(timeout_seconds or self.settings.SANDBOX_DEFAULT_TIMEOUT_SEC)

        backend_mode = "docker" if docker_available else "development_fallback"
        is_container_isolated = docker_available

        row = AgentSandboxRuntime(
            tenant_id=tenant_id,
            agent_runtime_id=agent_runtime_id,
            rental_id=rental_id,
            backend_mode=backend_mode,
            is_container_isolated=is_container_isolated,
            status="created",
            container_id=None,
            image_name=self.settings.SANDBOX_DOCKER_IMAGE,
            workspace_path=str(workspace_dir),
            cpu_limit=eff_cpu,
            memory_limit_mb=eff_mem,
            timeout_seconds=eff_timeout,
            network_mode="none",
            last_health_json={"note": docker_detail},
            execution_logs_json=[],
        )
        self._append_log(
            row,
            event="create",
            status="ok",
            detail=f"Runtime {agent_runtime_id} created ({backend_mode}): {docker_detail}",
            meta={"network_mode": "none", "cpu_limit": eff_cpu, "memory_limit_mb": eff_mem},
        )
        db.add(row)
        db.flush()

        if auto_start:
            return self.start_runtime(db, tenant_id, row.id)
        row.last_health_json = self._collect_resource_stats(row)
        db.flush()
        return row

    def start_runtime(self, db: Session, tenant_id: uuid.UUID, runtime_id: uuid.UUID) -> AgentSandboxRuntime:
        row = self._get_runtime_row(db, tenant_id, runtime_id)
        if row.status == "destroyed":
            raise ValueError("Cannot start a destroyed runtime; create a new runtime instead")
        workspace_dir = self._validate_workspace_path(tenant_id, row.workspace_path)
        workspace_dir.mkdir(parents=True, exist_ok=True)

        docker_available, docker_bin, docker_detail = self.detect_docker_daemon()
        if docker_available and docker_bin:
            if row.container_id:
                proc = subprocess.run(
                    [docker_bin, "start", row.container_id],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    shell=False,
                )
                if proc.returncode != 0:
                    raise RuntimeError(f"Docker start failed: {redact_secrets_in_text(proc.stderr)}")
            else:
                container_name = f"hireflow-{row.agent_runtime_id}"
                cmd = self._build_docker_run_cmd(
                    docker_bin=docker_bin,
                    container_name=container_name,
                    workspace_dir=workspace_dir,
                    image_name=row.image_name,
                    cpu_limit=row.cpu_limit,
                    memory_limit_mb=row.memory_limit_mb,
                )
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20, shell=False)
                if proc.returncode != 0:
                    raise RuntimeError(f"Docker run failed: {redact_secrets_in_text(proc.stderr)}")
                row.container_id = (proc.stdout or container_name).strip()[:64]
            row.backend_mode = "docker"
            row.is_container_isolated = True
            mode_note = "Docker container started with --network=none --read-only --cap-drop=ALL --user=10001:10001"
        else:
            row.backend_mode = "development_fallback"
            row.is_container_isolated = False
            mode_note = (
                f"Started in development_fallback (isolated Python child subprocess + tenant temp dir; "
                f"NOT a Linux container). {docker_detail}"
            )

        row.status = "running"
        row.last_started_at = _utcnow()
        row.last_health_json = self._collect_resource_stats(row)
        row.last_health_json["mode_notice"] = mode_note
        self._append_log(row, event="start", status="ok", detail=mode_note)
        db.flush()
        return row

    def stop_runtime(self, db: Session, tenant_id: uuid.UUID, runtime_id: uuid.UUID) -> AgentSandboxRuntime:
        row = self._get_runtime_row(db, tenant_id, runtime_id)
        if row.status == "destroyed":
            raise ValueError("Cannot stop a destroyed runtime")

        if row.is_container_isolated and row.container_id:
            docker_available, docker_bin, _ = self.detect_docker_daemon()
            if docker_available and docker_bin:
                subprocess.run(
                    [docker_bin, "stop", "-t", "5", row.container_id],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    shell=False,
                )

        row.status = "stopped"
        row.last_stopped_at = _utcnow()
        row.last_health_json = self._collect_resource_stats(row)
        self._append_log(row, event="stop", status="ok", detail=f"Runtime {row.agent_runtime_id} stopped cleanly")
        db.flush()
        return row

    def restart_runtime(self, db: Session, tenant_id: uuid.UUID, runtime_id: uuid.UUID) -> AgentSandboxRuntime:
        row = self._get_runtime_row(db, tenant_id, runtime_id)
        if row.status == "destroyed":
            raise ValueError("Cannot restart a destroyed runtime")
        self.stop_runtime(db, tenant_id, runtime_id)
        return self.start_runtime(db, tenant_id, runtime_id)

    def destroy_runtime(self, db: Session, tenant_id: uuid.UUID, runtime_id: uuid.UUID) -> AgentSandboxRuntime:
        row = self._get_runtime_row(db, tenant_id, runtime_id)
        if row.container_id:
            docker_available, docker_bin, _ = self.detect_docker_daemon()
            if docker_available and docker_bin:
                subprocess.run(
                    [docker_bin, "rm", "-f", row.container_id],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    shell=False,
                )

        workspace_dir = self._validate_workspace_path(tenant_id, row.workspace_path)
        runtime_dir = workspace_dir.parent
        tenant_root = self._tenant_workspace_root(tenant_id)
        if runtime_dir.is_relative_to(tenant_root) and runtime_dir.exists():
            shutil.rmtree(runtime_dir, ignore_errors=True)

        row.status = "destroyed"
        row.container_id = None
        row.destroyed_at = _utcnow()
        row.last_health_json = {
            "checked_at": _utcnow().isoformat(),
            "backend_mode": row.backend_mode,
            "is_container_isolated": False,
            "workspace_bytes": 0,
            "workspace_files": 0,
            "note": "Workspace purged and runtime destroyed",
        }
        self._append_log(row, event="destroy", status="ok", detail="Runtime destroyed and isolated workspace purged")
        db.flush()
        return row

    def get_runtime_status(self, db: Session, tenant_id: uuid.UUID, runtime_id: uuid.UUID) -> AgentSandboxRuntime:
        row = self._get_runtime_row(db, tenant_id, runtime_id)
        if row.status != "destroyed":
            row.last_health_json = self._collect_resource_stats(row)
            db.flush()
        return row

    def list_runtimes(self, db: Session, tenant_id: uuid.UUID) -> list[AgentSandboxRuntime]:
        return list(
            db.scalars(
                select(AgentSandboxRuntime)
                .where(AgentSandboxRuntime.tenant_id == tenant_id)
                .order_by(AgentSandboxRuntime.created_at.desc())
            ).all()
        )

    def ensure_tenant_runtime(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        *,
        rental_id: uuid.UUID | None = None,
    ) -> AgentSandboxRuntime:
        row = db.scalar(
            select(AgentSandboxRuntime)
            .where(
                AgentSandboxRuntime.tenant_id == tenant_id,
                AgentSandboxRuntime.status != "destroyed",
            )
            .order_by(AgentSandboxRuntime.created_at.desc())
        )
        if row is None:
            return self.create_runtime(db, tenant_id, rental_id=rental_id, auto_start=True)
        if row.status != "running":
            return self.start_runtime(db, tenant_id, row.id)
        return row

    def execute_in_runtime(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        runtime_id: uuid.UUID,
        *,
        task_name: str,
        payload: dict[str, Any],
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        normalized_task = (task_name or "").strip().lower()
        if normalized_task in DISALLOWED_SHELL_TASKS or normalized_task not in ALLOWED_TASKS:
            raise SandboxSecurityError(f"Disallowed sandbox task '{task_name}'. Arbitrary shell execution is forbidden.")

        row = self._get_runtime_row(db, tenant_id, runtime_id)
        if row.status == "destroyed":
            raise SandboxSecurityError("Cannot execute inside a destroyed runtime")
        if row.status != "running":
            row = self.start_runtime(db, tenant_id, runtime_id)

        workspace_dir = self._validate_workspace_path(tenant_id, row.workspace_path)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        eff_timeout = int(timeout_seconds or row.timeout_seconds or self.settings.SANDBOX_DEFAULT_TIMEOUT_SEC)

        worker_input = json.dumps({"task": normalized_task, "payload": payload})
        t0 = time.perf_counter()

        try:
            if row.is_container_isolated and row.container_id:
                _, docker_bin, _ = self.detect_docker_daemon()
                if not docker_bin:
                    raise RuntimeError("Docker runtime selected but docker CLI is missing")
                cmd = [docker_bin, "exec", "-i", row.container_id, "python", "-I", "/sandbox/sandbox_worker.py"]
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=False,
                )
            else:
                import sys

                worker = _worker_script_path()
                cmd = [sys.executable, "-I", str(worker)]
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(workspace_dir),
                    env=_minimal_subprocess_env(workspace_dir),
                    text=True,
                    shell=False,
                )

            try:
                stdout_data, stderr_data = proc.communicate(input=worker_input, timeout=eff_timeout)
            except subprocess.TimeoutExpired as exc:
                _kill_process_tree(proc.pid)
                proc.wait(timeout=2)
                elapsed_ms = round((time.perf_counter() - t0) * 1000)
                self._append_log(
                    row,
                    event=f"exec:{normalized_task}",
                    status="timeout",
                    duration_ms=elapsed_ms,
                    detail=f"Sandbox task '{normalized_task}' timed out after {eff_timeout}s",
                )
                db.flush()
                raise SandboxTimeoutError(
                    f"Sandbox task '{normalized_task}' exceeded timeout ({eff_timeout}s)"
                ) from exc

            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            if proc.returncode != 0:
                err_msg = redact_secrets_in_text(stderr_data or stdout_data or f"exit={proc.returncode}", max_len=400)
                self._append_log(
                    row,
                    event=f"exec:{normalized_task}",
                    status="blocked" if proc.returncode == 3 else "error",
                    duration_ms=elapsed_ms,
                    detail=f"Task blocked/failed: {err_msg}",
                )
                db.flush()
                if proc.returncode == 3:
                    raise SandboxSecurityError(f"Sandbox security violation: {err_msg}")
                raise RuntimeError(f"Sandbox execution failed: {err_msg}")

            parsed = json.loads(stdout_data or "{}")
            row.last_health_json = self._collect_resource_stats(row)
            self._append_log(
                row,
                event=f"exec:{normalized_task}",
                status="ok" if parsed.get("ok", True) else "error",
                duration_ms=elapsed_ms,
                detail=f"Executed {normalized_task} in {row.backend_mode}",
                meta={"backend_mode": row.backend_mode, "is_container_isolated": row.is_container_isolated},
            )
            db.flush()
            return {
                "runtime_id": str(row.id),
                "agent_runtime_id": row.agent_runtime_id,
                "backend_mode": row.backend_mode,
                "is_container_isolated": row.is_container_isolated,
                "duration_ms": elapsed_ms,
                "result": parsed,
            }
        except SandboxTimeoutError:
            raise
        except Exception:
            db.flush()
            raise


sandbox_manager = DockerSandboxManager()
