"""Comprehensive end-to-end verification of all 7 HR workflows, agent behavior, 8 error-handling modes, and 9 real Dashboard KPIs."""

from __future__ import annotations

import io
import time
import uuid
import zipfile

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from agents.framework import workflow as workflow_mod
from agents.framework.llm_provider import llm_provider
from agents.framework.optimizer import tenant_response_cache
from agents.framework.tools import AgentToolBox
from agents.registry import agent_registry
from app.core.rate_limiter import rate_limiter
from app.db.models import AgentConfiguration, ExecutionLog
from app.db.session import get_session_factory
from app.runtime.docker_sandbox import SandboxTimeoutError, sandbox_manager
from app.runtime.mcp_client import mcp_manager
from app.runtime.playwright_browser import browser_manager


@pytest.fixture(autouse=True)
def _reset_rate_and_cache():
    rate_limiter.reset()
    tenant_response_cache.clear()
    yield
    rate_limiter.reset()
    tenant_response_cache.clear()


def _login(client: TestClient, email: str, password: str, org_slug: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "organization_slug": org_slug},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _register_fresh_org(client: TestClient, tag: str) -> tuple[dict[str, str], str]:
    slug = f"e2e-{tag}-{uuid.uuid4().hex[:6]}"
    email = f"owner-{uuid.uuid4().hex[:6]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": f"E2E Org {tag}",
            "organization_slug": slug,
            "industry": "Technology",
            "full_name": "E2E Owner",
            "email": email,
            "password": "StrongPassword!2026",
        },
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, slug


def _make_empty_docx_bytes() -> bytes:
    """Create a valid ZIP/DOCX container with empty document XML (no readable text)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document><w:body><w:p/></w:body></w:document>")
    return buf.getvalue()


def test_all_7_hr_workflows_grounded_data_and_9_dashboard_metrics(client: TestClient):
    owner_hdr, _slug = _register_fresh_org(client, "fullflow")

    # Initial workspace snapshot & verify all 9 KPI keys exist cleanly on /workspace
    ws0 = client.get("/api/v1/hr-agent/workspace", headers=owner_hdr)
    assert ws0.status_code == 200, ws0.text
    metrics0 = ws0.json()["metrics"]
    for key in [
        "total_jobs_count",
        "candidate_count",
        "resumes_analyzed_count",
        "interview_count",
        "scheduled_interviews_count",
        "pending_onboarding_count",
        "completed_executions",
        "failed_executions",
        "estimated_ai_cost_usd",
    ]:
        assert key in metrics0
    assert "tokens_used_this_month" in ws0.json()["quota"]

    # Workflow 6 precondition: Upload realistic HR Policy document
    policy_txt = (
        b"Acme Global Benefits Policy 2026\n"
        b"Home Office Ergonomics Allowance: Full-time employees receive $1,200 reimbursement every 24 months "
        b"for ergonomic desks, monitors, and seating upon manager approval.\n"
        b"Parental Leave Policy: Primary caregivers receive 16 weeks of 100% paid bonding leave.\n"
    )
    pol_up = client.post(
        "/api/v1/hr-agent/knowledge",
        headers=owner_hdr,
        files={"file": ("ergonomics_benefits_2026.txt", policy_txt, "text/plain")},
        data={
            "title": "Ergonomics & Benefits Policy 2026",
            "source_type": "handbook",
            "min_role_access": "business_employee",
            "workflow_slug": "hr-policy-support",
        },
    )
    assert pol_up.status_code == 201, pol_up.text

    # Workflow 1 (Recruitment / Resume Screening): Upload realistic resume + run screening
    resume_txt = (
        b"Vikram Deshmukh\n"
        b"Email: vikram.deshmukh@example.org | Phone: +1-555-0148\n"
        b"Summary: Principal Backend Engineer with 8 years of experience building Python, FastAPI, PostgreSQL, "
        b"Docker, and Kubernetes microservices.\n"
    )
    res_up = client.post(
        "/api/v1/hr-agent/knowledge",
        headers=owner_hdr,
        files={"file": ("vikram_deshmukh_cv.txt", resume_txt, "text/plain")},
        data={
            "title": "Vikram Deshmukh Resume",
            "source_type": "resume",
            "min_role_access": "business_admin",
            "workflow_slug": "recruitment-screening",
        },
    )
    assert res_up.status_code == 201, res_up.text
    resume_doc_id = res_up.json()["id"]

    wf1 = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "Screen uploaded candidate resume for Principal Backend Engineer requiring Python, FastAPI, PostgreSQL, Kubernetes.",
            "workflow_hint": "recruitment-screening",
            "attachments": [resume_doc_id],
            "structured_input": {"blind_screening": True, "persist_new_resumes": True},
        },
    )
    assert wf1.status_code == 200, wf1.text
    b1 = wf1.json()
    assert b1["routed_workflow"] == "recruitment-screening"
    evaluated = b1["structured_output"].get("evaluated_candidates", [])
    assert len(evaluated) >= 1
    assert any("Python" in (c.get("matched_required_skills") or []) for c in evaluated)
    assert b1["structured_output"]["blind_screening_applied"] is True

    # Also test seeded inline resume ingestion
    wf1b = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "Screen inline candidate for Staff ML Engineer requiring Python, PyTorch, SQL.",
            "workflow_hint": "recruitment-screening",
            "structured_input": {
                "resume_texts": [
                    "Sneha Kapoor\nEmail: sneha@example.com\n6 years experience in Python, PyTorch, SQL pipelines."
                ],
                "persist_new_resumes": True,
            },
        },
    )
    assert wf1b.status_code == 200, wf1b.text

    # Workflow 2 (JD Generator): Generate grounded JD
    wf2 = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "Create a detailed inclusive job description for Principal Data Platform Architect requiring Kafka, PostgreSQL, Python, dbt.",
            "workflow_hint": "jd-generator",
        },
    )
    assert wf2.status_code == 200, wf2.text
    b2 = wf2.json()
    assert b2["routed_workflow"] == "jd-generator"
    jd_text = (b2["structured_output"].get("formatted_job_description_markdown") or b2["final_response_text"]).lower()
    assert "kafka" in jd_text or "postgresql" in jd_text
    assert b2["structured_output"].get("inclusive_language_score") is not None

    # Workflow 3 (Candidate Shortlisting): Rank grounded candidates
    wf3 = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "Shortlist top candidates in our database for Principal Backend Engineer requiring Python and PostgreSQL.",
            "workflow_hint": "candidate-shortlisting",
        },
    )
    assert wf3.status_code == 200, wf3.text
    b3 = wf3.json()
    assert b3["routed_workflow"] == "candidate-shortlisting"
    assert len(b3["structured_output"].get("comparison_matrix", [])) >= 1
    assert len(b3["structured_output"].get("suggested_shortlist", [])) >= 1

    # Workflow 4 (Interview Scheduling) + HITL approval
    wf4 = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "Schedule a technical panel interview for Vikram Deshmukh for Principal Backend Engineer next Tuesday.",
            "workflow_hint": "interview-scheduling",
        },
    )
    assert wf4.status_code == 200, wf4.text
    b4 = wf4.json()
    assert b4["routed_workflow"] == "interview-scheduling"
    assert b4["execution_status"] in {"paused_hitl", "completed"}
    if b4["hitl_requests"]:
        appr_id = b4["hitl_requests"][0]["approval_id"]
        res_hitl = client.post(
            f"/api/v1/hitl/approvals/{appr_id}/resolve",
            headers=owner_hdr,
            json={"decision": "approved", "notes": "Verified panel availability"},
        )
        assert res_hitl.status_code == 200, res_hitl.text
        assert res_hitl.json()["status"] == "approved"

    # Workflow 5 (Employee Onboarding) + HITL resolution
    wf5 = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "Initiate employee onboarding for Neha Kulkarni joining Engineering as Senior DevOps Engineer starting 2026-12-01.",
            "workflow_hint": "employee-onboarding",
        },
    )
    assert wf5.status_code == 200, wf5.text
    b5 = wf5.json()
    assert b5["routed_workflow"] == "employee-onboarding"
    assert len(b5["structured_output"].get("checklist", [])) >= 1

    # Workflow 6 (HR Policy Support): Grounded answer citing $1,200 / 24 months
    wf6 = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "What is our home office ergonomics allowance amount and renewal cycle?",
            "workflow_hint": "hr-policy-support",
        },
    )
    assert wf6.status_code == 200, wf6.text
    b6 = wf6.json()
    assert b6["routed_workflow"] == "hr-policy-support"
    combined_answer = f"{b6['final_response_text']} {' '.join(b6['citations'])}"
    assert "1,200" in combined_answer or "Ergonomics" in combined_answer
    assert len(b6["citations"]) >= 1

    # Workflow 7 (HR Analytics): Pipeline charts & SQL metrics
    wf7 = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "Show hiring funnel analytics, candidate counts, and interview metrics.",
            "workflow_hint": "hr-analytics",
        },
    )
    assert wf7.status_code == 200, wf7.text
    b7 = wf7.json()
    assert b7["routed_workflow"] == "hr-analytics"
    assert len(b7["charts"]) >= 1 or b7["structured_output"].get("kpis") is not None

    # Verify Dashboard Analytics reflects REAL DB updates across all 9 required KPIs!
    # Also insert one real failed ExecutionLog row to verify failed_executions counter accurately.
    SessionFactory = get_session_factory()
    with SessionFactory() as db_sess:
        any_log = db_sess.scalars(select(ExecutionLog)).first()
        # Look up an execution from this fresh org via workspace rental
        ws_now = client.get("/api/v1/hr-agent/workspace", headers=owner_hdr).json()
        jd_rental_id = uuid.UUID(
            next(w["rental_id"] for w in ws_now["workflows"] if w["slug"] == "jd-generator")
        )
        tenant_uuid = uuid.UUID(ws_now["tenant_id"])
        assert jd_rental_id is not None and any_log is not None
        failed_log = ExecutionLog(
            tenant_id=tenant_uuid,
            rental_id=jd_rental_id,
            prompt_preview="Simulated failed upstream execution test",
            classifier_result="in_domain",
            status="failed",
            latency_ms=42,
            model_tier_used="tier_1_fast",
            steps_json=[],
            citations_json=[],
            browser_activity_json={"status": "not_used"},
            runtime_telemetry_json={"error": "upstream_timeout"},
        )
        db_sess.add(failed_log)
        db_sess.commit()

    ws_final = client.get("/api/v1/hr-agent/workspace", headers=owner_hdr)
    assert ws_final.status_code == 200
    m = ws_final.json()["metrics"]
    q = ws_final.json()["quota"]
    assert m["total_jobs_count"] >= 2
    assert m["candidate_count"] >= 2
    assert m["resumes_analyzed_count"] >= 2
    assert m["interview_count"] >= 1
    assert m["scheduled_interviews_count"] >= 1
    assert m["pending_onboarding_count"] >= 1
    assert m["completed_executions"] >= 7
    assert m["failed_executions"] >= 1
    assert q["tokens_used_this_month"] > 0
    assert isinstance(m["estimated_ai_cost_usd"], float) and m["estimated_ai_cost_usd"] >= 0.0

    # Also verify seeded Acme Cloud workspace has rich live metrics too
    acme_hdr = _login(client, "ananya@acmecloud.io", "AcmeOwner!2026", "acme-cloud")
    acme_ws = client.get("/api/v1/hr-agent/workspace", headers=acme_hdr).json()
    assert acme_ws["metrics"]["candidate_count"] >= 1
    assert acme_ws["metrics"]["total_jobs_count"] >= 1


def test_agent_behavior_clarification_domain_block_and_invalid_resumes(client: TestClient):
    owner_hdr, _ = _register_fresh_org(client, "behavior")

    # 1. Underspecified prompt lacking context -> clarification mode
    clar = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={"prompt": "help"},
    )
    assert clar.status_code == 200, clar.text
    clar_body = clar.json()
    assert clar_body["classifier_result"] == "needs_clarification"
    assert len(clar_body["clarification_questions"]) >= 1

    # 2. Out-of-domain restriction -> zero tools called
    ood = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={"prompt": "Write a crypto trading bot for Bitcoin arbitrage and prescribe aspirin dosage."},
    )
    assert ood.status_code == 200, ood.text
    ood_body = ood.json()
    assert ood_body["classifier_result"] == "rejected_out_of_domain"
    assert ood_body["execution_status"] == "rejected"
    assert not any(s["step"] == "execute_tools" for s in ood_body["trace_steps"])

    # 3. Error Handling (c): Corrupted PDF, empty/corrupted DOCX, whitespace/binary TXT upload rejections (400)
    bad_files = [
        ("corrupt_resume.pdf", b"%PDF-1.4\n\x00\xff\xfe\x80\x81CORRUPT", "application/pdf"),
        ("empty_text_resume.docx", _make_empty_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("blank_resume.txt", b"   \n\t   ", "text/plain"),
        ("binary_resume.txt", b"\x00\xff\xfe\xfd\x80\x81\x82binary", "text/plain"),
    ]
    for fname, content, ctype in bad_files:
        bad_resp = client.post(
            "/api/v1/hr-agent/knowledge",
            headers=owner_hdr,
            files={"file": (fname, content, ctype)},
            data={"title": f"Bad {fname}", "source_type": "resume", "workflow_slug": "recruitment-screening"},
        )
        assert bad_resp.status_code == 400, f"Expected 400 for {fname}, got {bad_resp.status_code}: {bad_resp.text}"

    # 4. Inline corrupted resume alongside valid resume in recruitment screening -> surfaces invalid_resumes warning without crashing
    mixed = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "Screen candidates for Backend Engineer requiring Python and PostgreSQL.",
            "workflow_hint": "recruitment-screening",
            "structured_input": {
                "resume_texts": [
                    "\x00\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd",
                    "Anika Rao\nEmail: anika@example.com\n6 years Python, FastAPI, PostgreSQL, Docker experience.",
                ]
            },
        },
    )
    assert mixed.status_code == 200, mixed.text
    mixed_body = mixed.json()
    invalid_list = mixed_body["structured_output"].get("invalid_resumes", [])
    assert len(invalid_list) >= 1
    assert "unreadable/corrupt resume" in mixed_body["structured_output"].get("explanation", "").lower()
    assert len(mixed_body["structured_output"].get("evaluated_candidates", [])) >= 1


def test_all_remaining_error_handling_modes(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path):
    owner_hdr, _ = _register_fresh_org(client, "errors")

    # (a) LLM provider failure & secret redaction -> deterministic fallback telemetry
    monkeypatch.setattr(llm_provider, "resolve_provider", lambda override=None: "gemini")

    def _boom_llm(**kwargs):
        raise TimeoutError("Upstream Gemini 504 with leaked key AIzaSyD9876543210SecretKeyValue")

    monkeypatch.setattr(llm_provider, "_invoke_live_provider", _boom_llm)
    llm_fail = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "Generate job description for QA Automation Engineer using Python and Playwright.",
            "workflow_hint": "jd-generator",
            "model_provider_override": "gemini",
        },
    )
    assert llm_fail.status_code == 200, llm_fail.text
    lf_body = llm_fail.json()
    assert lf_body["llm_provider_used"] == "deterministic_fallback_on_error"
    assert "llm_provider_fallback" in lf_body["guardrail_flags"]
    assert "AIzaSyD9876543210SecretKeyValue" not in llm_fail.text
    monkeypatch.undo()

    # (b) Database errors -> clean 503 OperationalError & 500 SQLAlchemyError without DB DSN leakage
    from app.api.v1 import hr_agent as hr_agent_mod
    from app.main import app

    no_raise_client = TestClient(app, raise_server_exceptions=False)
    monkeypatch.setattr(
        hr_agent_mod,
        "ensure_tenant_hr_workflows",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OperationalError("FATAL postgresql://pguser:SuperSecretPgPass@10.0.0.5/hrdb", None, None)
        ),
    )
    db_down = no_raise_client.get("/api/v1/hr-agent/workspace", headers=owner_hdr)
    assert db_down.status_code == 503
    assert db_down.json()["error_code"] == "database_unavailable"
    assert "SuperSecretPgPass" not in db_down.text
    assert "postgresql://" not in db_down.text

    monkeypatch.setattr(
        hr_agent_mod,
        "ensure_tenant_hr_workflows",
        lambda *args, **kwargs: (_ for _ in ()).throw(SQLAlchemyError("Internal constraint error")),
    )
    db_err = no_raise_client.get("/api/v1/hr-agent/workspace", headers=owner_hdr)
    assert db_err.status_code == 500
    assert db_err.json()["error_code"] == "database_error"
    assert "Internal constraint error" not in db_err.text
    monkeypatch.undo()

    # (d) Browser failures & timeouts -> 403 SSRF, 504 Timeout, 502 redacted crash
    ssrf = client.post(
        "/api/v1/hr-agent/browser/inspect",
        headers=owner_hdr,
        json={"url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert ssrf.status_code == 403

    monkeypatch.setattr(
        browser_manager,
        "navigate_and_extract",
        lambda **kwargs: (_ for _ in ()).throw(TimeoutError("Playwright navigation timed out")),
    )
    b_timeout = client.post(
        "/api/v1/hr-agent/browser/inspect",
        headers=owner_hdr,
        json={"url": "https://boards.greenhouse.io/acme/jobs/1"},
    )
    assert b_timeout.status_code == 504

    monkeypatch.setattr(
        browser_manager,
        "navigate_and_extract",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Crash at https://admin:SecretToken@internal/")),
    )
    b_crash = client.post(
        "/api/v1/hr-agent/browser/inspect",
        headers=owner_hdr,
        json={"url": "https://boards.greenhouse.io/acme/jobs/1"},
    )
    assert b_crash.status_code == 502
    assert "SecretToken" not in b_crash.text
    monkeypatch.undo()

    # (e) Sandbox failures -> 403 disallowed task, 404 unknown runtime, 504 timeout, 400 ValueError, 502 RuntimeError
    rt_resp = client.post("/api/v1/hr-agent/runtimes", headers=owner_hdr, json={"timeout_seconds": 5})
    assert rt_resp.status_code == 201
    rt_id = rt_resp.json()["id"]

    assert client.post(
        f"/api/v1/hr-agent/runtimes/{rt_id}/execute",
        headers=owner_hdr,
        json={"task_name": "sh", "payload": {"cmd": "id"}},
    ).status_code == 403
    assert client.post(
        f"/api/v1/hr-agent/runtimes/{uuid.uuid4()}/execute",
        headers=owner_hdr,
        json={"task_name": "noop_ping", "payload": {}},
    ).status_code == 404

    monkeypatch.setattr(
        sandbox_manager,
        "execute_in_runtime",
        lambda *args, **kwargs: (_ for _ in ()).throw(SandboxTimeoutError("Exceeded timeout")),
    )
    assert client.post(
        f"/api/v1/hr-agent/runtimes/{rt_id}/execute",
        headers=owner_hdr,
        json={"task_name": "noop_ping", "payload": {}},
    ).status_code == 504

    monkeypatch.setattr(
        sandbox_manager,
        "execute_in_runtime",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Malformed base64 payload")),
    )
    assert client.post(
        f"/api/v1/hr-agent/runtimes/{rt_id}/execute",
        headers=owner_hdr,
        json={"task_name": "noop_ping", "payload": {}},
    ).status_code == 400

    monkeypatch.setattr(
        sandbox_manager,
        "execute_in_runtime",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("OOMKilled exit code 137")),
    )
    assert client.post(
        f"/api/v1/hr-agent/runtimes/{rt_id}/execute",
        headers=owner_hdr,
        json={"task_name": "noop_ping", "payload": {}},
    ).status_code == 502
    monkeypatch.undo()

    # (f) MCP disconnections & timeouts
    missing_script = tmp_path / "missing_mcp_server.py"
    reg = client.post(
        "/api/v1/hr-agent/mcp/servers",
        headers=owner_hdr,
        json={
            "slug": "e2e-err-mcp",
            "name": "E2E Error MCP",
            "transport": "stdio",
            "command_or_url": "python",
            "args": [str(missing_script)],
        },
    )
    assert reg.status_code == 201
    srv_id = reg.json()["id"]

    # Unapproved MCP blocked with 403
    assert client.post(f"/api/v1/hr-agent/mcp/servers/{srv_id}/discover", headers=owner_hdr).status_code == 403

    # Approve then test unreachable discovery + simulated execution timeout/disconnect
    assert client.post(
        f"/api/v1/hr-agent/mcp/servers/{srv_id}/approval",
        headers=owner_hdr,
        json={"approved": True},
    ).status_code == 200
    monkeypatch.setattr(
        mcp_manager,
        "_discover_async",
        lambda **kwargs: (_ for _ in ()).throw(TimeoutError("MCP discovery timed out")),
    )
    disc = client.post(f"/api/v1/hr-agent/mcp/servers/{srv_id}/discover", headers=owner_hdr)
    assert disc.status_code == 200
    assert disc.json()["ok"] is False
    assert disc.json()["connection_status"] == "unreachable"

    monkeypatch.setattr(
        mcp_manager,
        "execute_tool",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("MCP tool execution timed out")),
    )
    assert client.post(
        f"/api/v1/hr-agent/mcp/servers/{srv_id}/execute",
        headers=owner_hdr,
        json={"tool_name": "any_tool", "arguments": {}},
    ).status_code == 504

    monkeypatch.setattr(
        mcp_manager,
        "execute_tool",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("MCP stdio broken pipe")),
    )
    assert client.post(
        f"/api/v1/hr-agent/mcp/servers/{srv_id}/execute",
        headers=owner_hdr,
        json={"tool_name": "any_tool", "arguments": {}},
    ).status_code == 502
    monkeypatch.undo()

    # (g) Tool execution error caught gracefully in LangGraph workflow without server 500
    orig_run_tool = AgentToolBox.run_tool

    def _failing_inclusive_lint(self, *, slug, ctx, args, agent_allowed_tools, rental_allowed_tools):
        if slug == "inclusive_language_linter":
            return {"tool": slug, "status": "error", "duration_ms": 2, "error": "Simulated linter crash"}
        return orig_run_tool(
            self,
            slug=slug,
            ctx=ctx,
            args=args,
            agent_allowed_tools=agent_allowed_tools,
            rental_allowed_tools=rental_allowed_tools,
        )

    monkeypatch.setattr(AgentToolBox, "run_tool", _failing_inclusive_lint)
    tool_err_exec = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "Generate job description for Site Reliability Engineer requiring Terraform and Kubernetes.",
            "workflow_hint": "jd-generator",
        },
    )
    assert tool_err_exec.status_code == 200, tool_err_exec.text
    assert "tool_execution_error" in tool_err_exec.json()["guardrail_flags"]
    monkeypatch.undo()

    # (h) Request / execution timeout cap enforced cleanly in workflow engine
    tick = {"n": 0}

    def _fast_forward_perf():
        tick["n"] += 1
        return tick["n"] * 200.0

    monkeypatch.setattr(workflow_mod.time, "perf_counter", _fast_forward_perf)
    timeout_exec = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "Draft a technical job description for Platform Security Lead requiring AWS and Python.",
            "workflow_hint": "jd-generator",
        },
    )
    assert timeout_exec.status_code == 200, timeout_exec.text
    assert "execution_timeout_enforced" in timeout_exec.json()["guardrail_flags"]
    monkeypatch.undo()
