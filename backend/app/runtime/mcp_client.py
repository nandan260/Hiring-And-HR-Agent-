from __future__ import annotations

import asyncio
import concurrent.futures
import ipaddress
import re
import socket
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import jsonschema
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AuditLog, McpExecutionLog, McpServerRecord, ToolPermission
from app.runtime.redaction import redact_secrets_in_text, sanitize_structured_payload
from app.core.security import decrypt_secret

BLOCKED_SHELL_COMMANDS = {
    "sh",
    "bash",
    "zsh",
    "fish",
    "dash",
    "cmd",
    "cmd.exe",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
    "osascript",
    "wscript",
    "cscript",
}

SHELL_META_RE = re.compile(r"[;&|`$<>]")
TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,78}$")


class McpSecurityError(PermissionError):
    """Raised when an MCP server configuration or invocation violates security policy."""


class McpValidationError(ValueError):
    """Raised when MCP tool arguments or schemas fail validation."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _run_coro_sync(coro):
    try:
        asyncio.get_running_loop()
        in_async = True
    except RuntimeError:
        in_async = False

    if not in_async:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _validate_stdio_command(command: str, args: list[str]) -> tuple[str, list[str]]:
    cmd = (command or "").strip()
    if not cmd:
        raise McpValidationError("Stdio command cannot be empty")
    if SHELL_META_RE.search(cmd):
        raise McpSecurityError("Shell metacharacters are forbidden in MCP stdio command")
    base = cmd.replace("\\", "/").split("/")[-1].lower()
    if base in BLOCKED_SHELL_COMMANDS:
        raise McpSecurityError(f"Shell wrapper '{base}' is forbidden for MCP stdio servers")
    cleaned_args: list[str] = []
    for arg in args:
        s = str(arg)
        if SHELL_META_RE.search(s):
            raise McpSecurityError("Shell metacharacters are forbidden in MCP stdio arguments")
        cleaned_args.append(s)
    return cmd, cleaned_args


def _validate_sse_url(url: str) -> str:
    raw = (url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() not in {"https", "http"}:
        raise McpSecurityError("MCP SSE transport supports only http/https URLs")
    if parsed.username or parsed.password:
        raise McpSecurityError("URL credentials are forbidden for MCP SSE endpoints")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise McpValidationError("MCP SSE URL is missing a valid hostname")
    if host in {"localhost", "localhost.localdomain", "metadata.google.internal"} or host.endswith(
        (".local", ".internal", ".localhost")
    ):
        raise McpSecurityError(f"Blocked internal/local hostname for MCP SSE: '{host}'")
    try:
        ip_obj = ipaddress.ip_address(host)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
            raise McpSecurityError(f"Blocked restricted IP literal for MCP SSE: '{host}'")
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        for _, _, _, _, sockaddr in infos:
            ip_obj = ipaddress.ip_address(sockaddr[0].split("%")[0])
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
                raise McpSecurityError(f"SSRF blocked: MCP SSE host '{host}' resolved to restricted IP")
    except socket.gaierror:
        # DNS may fail offline at registration time; enforce strictly at connect time as well.
        pass
    return raw


def _validate_discovered_tool(raw_tool: Any) -> tuple[dict[str, Any] | None, str | None]:
    name = getattr(raw_tool, "name", None) or (raw_tool.get("name") if isinstance(raw_tool, dict) else "")
    description = getattr(raw_tool, "description", None) or (
        raw_tool.get("description") if isinstance(raw_tool, dict) else ""
    )
    schema = getattr(raw_tool, "input_schema", None)
    if schema is None:
        schema = getattr(raw_tool, "inputSchema", None)
    if schema is None and isinstance(raw_tool, dict):
        schema = raw_tool.get("input_schema") or raw_tool.get("inputSchema")

    if not isinstance(name, str) or not TOOL_NAME_RE.match(name):
        return None, f"Invalid MCP tool name '{name}'"
    if not isinstance(schema, dict):
        return None, f"Tool '{name}' missing object inputSchema"
    if schema.get("type") not in (None, "object"):
        return None, f"Tool '{name}' inputSchema must define object parameters"

    normalized_schema = {"type": "object", **schema} if "type" not in schema else schema
    try:
        jsonschema.Draft202012Validator.check_schema(normalized_schema)
    except jsonschema.SchemaError as exc:
        return None, f"Tool '{name}' has invalid JSON Schema: {exc.message}"

    return {
        "name": name,
        "description": redact_secrets_in_text(str(description or ""), max_len=400),
        "inputSchema": sanitize_structured_payload(normalized_schema, max_str_len=500),
    }, None


class McpClientManager:
    """Manages external MCP server registrations, approvals, discovery, permissions, and execution."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def _get_server(self, db: Session, tenant_id: uuid.UUID, server_id: uuid.UUID) -> McpServerRecord:
        row = db.scalar(
            select(McpServerRecord).where(
                McpServerRecord.id == server_id,
                McpServerRecord.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise LookupError(f"MCP server {server_id} not found for tenant")
        return row

    def list_servers(self, db: Session, tenant_id: uuid.UUID) -> list[McpServerRecord]:
        return list(
            db.scalars(
                select(McpServerRecord)
                .where(McpServerRecord.tenant_id == tenant_id)
                .order_by(McpServerRecord.created_at.desc())
            ).all()
        )

    def list_logs(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        *,
        server_id: uuid.UUID | None = None,
        limit: int = 40,
    ) -> list[McpExecutionLog]:
        stmt = select(McpExecutionLog).where(McpExecutionLog.tenant_id == tenant_id)
        if server_id is not None:
            stmt = stmt.where(McpExecutionLog.server_id == server_id)
        return list(db.scalars(stmt.order_by(McpExecutionLog.created_at.desc()).limit(limit)).all())

    def register_server(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None,
        slug: str,
        name: str,
        transport: str,
        command_or_url: str,
        args: list[str] | None = None,
        env_keys: list[str] | None = None,
        description: str = "",
    ) -> McpServerRecord:
        norm_slug = slug.strip().lower()
        if not SLUG_RE.match(norm_slug):
            raise McpValidationError("MCP server slug must match ^[a-z0-9][a-z0-9_-]{1,78}$")

        norm_transport = transport.strip().lower()
        if norm_transport not in {"stdio", "sse"}:
            raise McpValidationError("Transport must be 'stdio' or 'sse'")

        existing = db.scalar(
            select(McpServerRecord).where(
                McpServerRecord.tenant_id == tenant_id,
                McpServerRecord.slug == norm_slug,
            )
        )
        if existing is not None:
            raise McpValidationError(f"MCP server with slug '{norm_slug}' already exists")

        clean_args = [str(a) for a in (args or [])]
        if norm_transport == "stdio":
            clean_target, clean_args = _validate_stdio_command(command_or_url, clean_args)
        else:
            clean_target = _validate_sse_url(command_or_url)
            clean_args = []

        safe_env_keys = [str(k).strip() for k in (env_keys or []) if str(k).strip() and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(k).strip())]

        # SECURITY INVARIANT: newly registered MCP servers are NEVER automatically trusted.
        row = McpServerRecord(
            tenant_id=tenant_id,
            slug=norm_slug,
            name=name.strip(),
            description=description.strip(),
            transport=norm_transport,
            command_or_url=clean_target,
            args_json=clean_args,
            env_keys_json=safe_env_keys,
            is_approved=False,
            approval_status="pending_approval",
            approved_by_user_id=None,
            approved_at=None,
            connection_status="pending_approval",
            last_error=None,
            discovered_tools_json=[],
            tool_permissions_json={},
        )
        db.add(row)
        db.flush()
        db.add(
            AuditLog(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action="mcp.server_registered",
                resource_type="mcp_server",
                resource_id=str(row.id),
                metadata_json={"slug": norm_slug, "transport": norm_transport, "is_approved": False},
            )
        )
        db.flush()
        return row

    def set_server_approval(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        server_id: uuid.UUID,
        *,
        approved: bool,
        actor_user_id: uuid.UUID | None,
    ) -> McpServerRecord:
        row = self._get_server(db, tenant_id, server_id)
        if approved:
            row.is_approved = True
            row.approval_status = "approved"
            row.approved_by_user_id = actor_user_id
            row.approved_at = _utcnow()
            if row.connection_status in {"pending_approval", "blocked"}:
                row.connection_status = "not_checked"
        else:
            row.is_approved = False
            row.approval_status = "blocked"
            row.connection_status = "blocked"
        row.last_error = None
        db.add(
            AuditLog(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action="mcp.server_approved" if approved else "mcp.server_blocked",
                resource_type="mcp_server",
                resource_id=str(row.id),
                metadata_json={"slug": row.slug, "approved": approved},
            )
        )
        db.flush()
        return row

    def configure_tool_permissions(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        server_id: uuid.UUID,
        *,
        tool_name: str,
        allowed: bool,
        requires_hitl: bool = False,
        allowed_roles: list[str] | None = None,
        timeout_seconds: int | None = None,
        actor_user_id: uuid.UUID | None = None,
    ) -> McpServerRecord:
        row = self._get_server(db, tenant_id, server_id)
        perms = dict(row.tool_permissions_json or {})
        perms[tool_name] = {
            "allowed": bool(allowed),
            "requires_hitl": bool(requires_hitl),
            "allowed_roles": list(allowed_roles or ["business_owner", "business_admin"]),
            "timeout_seconds": int(timeout_seconds or self.settings.MCP_EXECUTION_TIMEOUT_SEC),
        }
        row.tool_permissions_json = perms
        db.add(
            AuditLog(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action="mcp.tool_permission_updated",
                resource_type="mcp_server",
                resource_id=str(row.id),
                metadata_json={"slug": row.slug, "tool_name": tool_name, "allowed": allowed},
            )
        )
        db.flush()
        return row

    def _resolve_server_env(self, db: Session, tenant_id: uuid.UUID, row: McpServerRecord) -> dict[str, str]:
        """Inject ONLY explicitly bound tenant credentials for listed env_keys — never leak platform secrets."""
        env: dict[str, str] = {"PYTHONUNBUFFERED": "1", "PYTHONNOUSERSITE": "1"}
        if not row.env_keys_json:
            return env

        secret_map: dict[str, str] = {}
        perm_rows = db.scalars(
            select(ToolPermission).where(ToolPermission.tenant_id == tenant_id, ToolPermission.is_allowed.is_(True))
        ).all()
        for perm in perm_rows:
            if perm.encrypted_secret:
                try:
                    raw = decrypt_secret(perm.encrypted_secret)
                    if "=" in raw:
                        k, v = raw.split("=", 1)
                        secret_map[k.strip()] = v.strip()
                    elif perm.tool is not None:
                        env_key = f"{perm.tool.slug.upper().replace('-', '_')}_SECRET"
                        secret_map[env_key] = raw
                except Exception:
                    pass

        for key in row.env_keys_json:
            if key in secret_map and secret_map[key]:
                env[key] = secret_map[key]
        return env

    async def _discover_async(
        self,
        *,
        transport: str,
        target: str,
        args: list[str],
        env: dict[str, str],
        timeout_seconds: int,
    ) -> list[Any]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.sse import sse_client
        from mcp.client.stdio import stdio_client

        async def _inner():
            if transport == "stdio":
                server_params = StdioServerParameters(command=target, args=args, env=env)
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_resp = await session.list_tools()
                        return list(tools_resp.tools)
            else:
                _validate_sse_url(target)
                async with sse_client(target, timeout=timeout_seconds) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_resp = await session.list_tools()
                        return list(tools_resp.tools)

        return await asyncio.wait_for(_inner(), timeout=timeout_seconds)

    async def _call_tool_async(
        self,
        *,
        transport: str,
        target: str,
        args: list[str],
        env: dict[str, str],
        tool_name: str,
        arguments: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.sse import sse_client
        from mcp.client.stdio import stdio_client

        async def _inner():
            if transport == "stdio":
                server_params = StdioServerParameters(command=target, args=args, env=env)
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments=arguments)
                        return result
            else:
                _validate_sse_url(target)
                async with sse_client(target, timeout=timeout_seconds) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments=arguments)
                        return result

        result = await asyncio.wait_for(_inner(), timeout=timeout_seconds)
        content_items: list[dict[str, Any]] = []
        for item in getattr(result, "content", []) or []:
            item_type = getattr(item, "type", "text")
            text_val = getattr(item, "text", None)
            content_items.append(
                {
                    "type": str(item_type),
                    "text": redact_secrets_in_text(str(text_val or ""), max_len=4000) if text_val is not None else "",
                }
            )
        structured = getattr(result, "structured_content", None)
        if structured is None:
            structured = getattr(result, "structuredContent", None)
        is_err = bool(getattr(result, "is_error", False) or getattr(result, "isError", False))
        return {
            "is_error": is_err,
            "content": content_items,
            "structured_content": sanitize_structured_payload(structured) if structured is not None else None,
        }

    def check_connection_and_discover(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        server_id: uuid.UUID,
        *,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        row = self._get_server(db, tenant_id, server_id)
        if not row.is_approved or row.approval_status != "approved":
            raise McpSecurityError(
                f"MCP server '{row.slug}' is untrusted/unapproved (status={row.approval_status}); approve it before connecting"
            )

        if row.transport == "stdio":
            target, args = _validate_stdio_command(row.command_or_url, list(row.args_json or []))
        else:
            target = _validate_sse_url(row.command_or_url)
            args = []

        env = self._resolve_server_env(db, tenant_id, row)
        eff_timeout = int(timeout_seconds or self.settings.MCP_EXECUTION_TIMEOUT_SEC)

        try:
            raw_tools = _run_coro_sync(
                self._discover_async(
                    transport=row.transport,
                    target=target,
                    args=args,
                    env=env,
                    timeout_seconds=eff_timeout,
                )
            )
        except Exception as exc:
            err_msg = redact_secrets_in_text(f"{type(exc).__name__}: {exc}", max_len=350)
            row.connection_status = "unreachable"
            row.last_error = err_msg
            row.last_checked_at = _utcnow()
            db.flush()
            return {
                "ok": False,
                "server_id": str(row.id),
                "connection_status": "unreachable",
                "error": err_msg,
                "discovered_tools": row.discovered_tools_json,
                "schema_warnings": [],
            }

        valid_tools: list[dict[str, Any]] = []
        schema_warnings: list[str] = []
        perms = dict(row.tool_permissions_json or {})
        for raw_t in raw_tools:
            parsed_tool, warn = _validate_discovered_tool(raw_t)
            if parsed_tool is None:
                if warn:
                    schema_warnings.append(warn)
                continue
            valid_tools.append(parsed_tool)
            if parsed_tool["name"] not in perms:
                perms[parsed_tool["name"]] = {
                    "allowed": False,
                    "requires_hitl": False,
                    "allowed_roles": ["business_owner", "business_admin"],
                    "timeout_seconds": eff_timeout,
                }

        row.discovered_tools_json = valid_tools
        row.tool_permissions_json = perms
        row.connection_status = "connected"
        row.last_error = "; ".join(schema_warnings) if schema_warnings else None
        row.last_checked_at = _utcnow()
        db.flush()
        return {
            "ok": True,
            "server_id": str(row.id),
            "connection_status": "connected",
            "error": row.last_error,
            "discovered_tools": valid_tools,
            "schema_warnings": schema_warnings,
        }

    def execute_tool(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        server_id: uuid.UUID,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        actor_user_id: uuid.UUID | None,
        actor_role: str = "business_admin",
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        row = self._get_server(db, tenant_id, server_id)
        t0 = time.perf_counter()

        def _record(status: str, resp: dict[str, Any] | None = None, error_msg: str | None = None):
            duration = round((time.perf_counter() - t0) * 1000)
            log_row = McpExecutionLog(
                tenant_id=tenant_id,
                server_id=row.id,
                actor_user_id=actor_user_id,
                tool_name=tool_name,
                status=status,
                duration_ms=duration,
                request_summary_json=sanitize_structured_payload(arguments),
                response_summary_json=sanitize_structured_payload(resp or {}),
                error_message=redact_secrets_in_text(error_msg, max_len=400) if error_msg else None,
            )
            db.add(log_row)
            db.flush()
            return duration

        if not row.is_approved or row.approval_status != "approved":
            _record("blocked", error_msg="MCP server is not approved")
            raise McpSecurityError(f"MCP server '{row.slug}' is not approved for execution")

        tool_def = next((t for t in (row.discovered_tools_json or []) if t.get("name") == tool_name), None)
        if tool_def is None:
            _record("blocked", error_msg=f"Unknown or unvalidated MCP tool '{tool_name}'")
            raise McpValidationError(f"MCP tool '{tool_name}' is not in discovered validated tools")

        perm = (row.tool_permissions_json or {}).get(tool_name) or {}
        if perm.get("allowed") is not True:
            _record("blocked", error_msg=f"Tool '{tool_name}' is not enabled in server permissions")
            raise McpSecurityError(f"MCP tool '{tool_name}' is disabled in permissions")

        allowed_roles = perm.get("allowed_roles") or ["business_owner", "business_admin"]
        if actor_role not in allowed_roles and not actor_role == "platform_admin":
            _record("blocked", error_msg=f"Role '{actor_role}' not authorized for MCP tool '{tool_name}'")
            raise McpSecurityError(f"Role '{actor_role}' is not authorized to invoke MCP tool '{tool_name}'")

        try:
            jsonschema.validate(instance=arguments, schema=tool_def["inputSchema"])
        except jsonschema.ValidationError as exc:
            _record("schema_error", error_msg=exc.message)
            raise McpValidationError(f"MCP argument schema validation failed: {exc.message}") from exc

        eff_timeout = int(timeout_seconds or perm.get("timeout_seconds") or self.settings.MCP_EXECUTION_TIMEOUT_SEC)
        if row.transport == "stdio":
            target, args = _validate_stdio_command(row.command_or_url, list(row.args_json or []))
        else:
            target = _validate_sse_url(row.command_or_url)
            args = []
        env = self._resolve_server_env(db, tenant_id, row)

        try:
            res = _run_coro_sync(
                self._call_tool_async(
                    transport=row.transport,
                    target=target,
                    args=args,
                    env=env,
                    tool_name=tool_name,
                    arguments=arguments,
                    timeout_seconds=eff_timeout,
                )
            )
            status = "error" if res.get("is_error") else "success"
            duration = _record(status, resp=res, error_msg="Tool reported error" if res.get("is_error") else None)
            row.connection_status = "connected"
            row.last_checked_at = _utcnow()
            db.flush()
            return {"ok": not res.get("is_error"), "tool_name": tool_name, "duration_ms": duration, **res}
        except (TimeoutError, asyncio.TimeoutError) as exc:
            _record("timeout", error_msg=f"Timed out after {eff_timeout}s")
            raise TimeoutError(f"MCP tool '{tool_name}' timed out after {eff_timeout}s") from exc
        except Exception as exc:
            msg = redact_secrets_in_text(f"{type(exc).__name__}: {exc}", max_len=350)
            _record("connection_error", error_msg=msg)
            row.connection_status = "unreachable"
            row.last_error = msg
            db.flush()
            raise RuntimeError(f"MCP tool execution failed: {msg}") from exc


mcp_manager = McpClientManager()
