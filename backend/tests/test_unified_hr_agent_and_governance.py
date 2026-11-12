"""Phase 4 verification suite for unified HireFlow AI HR Agent routing, RBAC, quota locking, and governance."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import uuid

from fastapi.testclient import TestClient

from agents.framework.classifier import classify_domain_boundary
from agents.registry import agent_registry
from app.main import app


def _login(client: TestClient, email: str, password: str, tenant_slug: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "tenant_slug": tenant_slug},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _register_owner(client: TestClient, suffix: str) -> tuple[dict[str, str], str]:
    slug = f"hr-test-{suffix}"
    email = f"owner-{suffix}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": f"HR Test Org {suffix}",
            "organization_slug": slug,
            "industry": "Technology",
            "full_name": f"Owner {suffix}",
            "email": email,
            "password": "TestOwner!2026",
        },
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, slug


def test_unified_hr_agent_routes_all_7_workflows_without_hint(client: TestClient):
    owner_hdr = _login(client, "ananya@acmecloud.io", "AcmeOwner!2026", "acme-cloud")

    ws_resp = client.get("/api/v1/hr-agent/workspace", headers=owner_hdr)
    assert ws_resp.status_code == 200, ws_resp.text
    ws_data = ws_resp.json()
    assert ws_data["product_name"] == "HireFlow AI — Hiring & HR AI Agent"
    assert len(ws_data["workflows"]) == 7
    assert all(w["allowed_for_current_role"] is True for w in ws_data["workflows"])

    routing_cases = [
        (
            "Screen this resume for a Senior Python Backend Engineer with FastAPI and PostgreSQL skills.",
            "recruitment-screening",
        ),
        (
            "Write a complete job description for a Staff DevOps Engineer with Kubernetes and Terraform experience.",
            "jd-generator",
        ),
        (
            "Compare and rank the shortlisted candidates and show missing skills for the Backend role.",
            "candidate-shortlisting",
        ),
        (
            "Schedule a technical interview panel for Elena Rostova next Thursday and propose calendar slots.",
            "interview-scheduling",
        ),
        (
            "Create a day-1 employee onboarding checklist, workstation provisioning, and orientation tasks for a new hire.",
            "employee-onboarding",
        ),
        (
            "What is the company bereavement and parental leave policy in our employee handbook?",
            "hr-policy-support",
        ),
        (
            "Show our quarterly hiring funnel conversion metrics, time to hire, and DEI analytics report.",
            "hr-analytics",
        ),
    ]

    for prompt, expected_slug in routing_cases:
        res = client.post(
            "/api/v1/hr-agent/execute",
            headers=owner_hdr,
            json={"prompt": prompt},
        )
        assert res.status_code == 200, f"Prompt '{prompt}' failed: {res.text}"
        body = res.json()
        assert body["classifier_result"] == "in_domain", body
        assert body["routed_workflow"] == expected_slug, (
            f"Expected {expected_slug}, got {body['routed_workflow']} for '{prompt}'"
        )
        assert "marketplace" not in body["final_response_text"].lower()
        assert "rent-an-agent" not in body["final_response_text"].lower()


def test_cross_hr_internal_routing_replaces_old_boundary_rejection(client: TestClient):
    # Direct unit test of classify_domain_boundary across HR sub-workflows
    recruitment_agent = agent_registry.get_agent("recruitment-screening")
    boundary = classify_domain_boundary(
        prompt="Schedule a panel interview for Elena Rostova next week",
        agent_id="recruitment-screening",
        domain=recruitment_agent.domain,
        guardrails=recruitment_agent.guardrails,
    )
    assert boundary.allowed is True
    assert boundary.classifier_result == "in_domain"
    assert boundary.suggested_agent_slug == "interview-scheduling"

    # End-to-end API test passing workflow_hint='recruitment-screening' with an onboarding/analytics request
    owner_hdr = _login(client, "ananya@acmecloud.io", "AcmeOwner!2026", "acme-cloud")
    res = client.post(
        "/api/v1/hr-agent/execute",
        headers=owner_hdr,
        json={
            "prompt": "Generate our Q2 time to hire and hiring funnel analytics report.",
            "workflow_hint": "recruitment-screening",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["classifier_result"] == "in_domain"
    assert body["routed_workflow"] == "hr-analytics"


def test_multiturn_conversation_switching_and_followup_continuity(client: TestClient):
    owner_hdr = _login(client, "ananya@acmecloud.io", "AcmeOwner!2026", "acme-cloud")

    conv_res = client.post(
        "/api/v1/hr-agent/conversations",
        headers=owner_hdr,
        json={"title": "Unified Cross-HR Hiring Pipeline"},
    )
    assert conv_res.status_code == 201, conv_res.text
    conv_id = conv_res.json()["id"]

    turn1 = client.post(
        f"/api/v1/hr-agent/conversations/{conv_id}/messages",
        headers=owner_hdr,
        json={"content": "Screen candidates for Senior Backend Engineer with Python, FastAPI, PostgreSQL."},
    )
    assert turn1.status_code == 201, turn1.text
    assert turn1.json()["workflow_slug"] == "recruitment-screening"

    turn2 = client.post(
        f"/api/v1/hr-agent/conversations/{conv_id}/messages",
        headers=owner_hdr,
        json={"content": "Now shortlist and compare the top candidates and highlight missing skills."},
    )
    assert turn2.status_code == 201, turn2.text
    assert turn2.json()["workflow_slug"] == "candidate-shortlisting"

    turn3 = client.post(
        f"/api/v1/hr-agent/conversations/{conv_id}/messages",
        headers=owner_hdr,
        json={"content": "Schedule a technical interview for Elena Rostova next Wednesday."},
    )
    assert turn3.status_code == 201, turn3.text
    assert turn3.json()["workflow_slug"] == "interview-scheduling"

    # Follow-up phrase lacking explicit new keywords should stay in HR context rather than failing out-of-domain
    turn4 = client.post(
        f"/api/v1/hr-agent/conversations/{conv_id}/messages",
        headers=owner_hdr,
        json={"content": "Please refine that for the same candidate and proceed."},
    )
    assert turn4.status_code == 201, turn4.text
    t4_body = turn4.json()
    assert t4_body["classifier_result"] == "in_domain"
    assert t4_body["execution_status"] in {"completed", "paused_hitl"}

    msgs_res = client.get(f"/api/v1/hr-agent/conversations/{conv_id}/messages", headers=owner_hdr)
    assert msgs_res.status_code == 200
    msgs = msgs_res.json()
    assert len(msgs) == 8
    assert msgs[1]["metadata_json"]["workflow_slug"] == "recruitment-screening"
    assert msgs[3]["metadata_json"]["workflow_slug"] == "candidate-shortlisting"
    assert msgs[5]["metadata_json"]["workflow_slug"] == "interview-scheduling"


def test_non_hr_queries_rejected_without_marketplace_wording(client: TestClient):
    owner_hdr = _login(client, "ananya@acmecloud.io", "AcmeOwner!2026", "acme-cloud")

    non_hr_prompts = [
        "Diagnose my chest pain and prescribe antibiotic medication dosage.",
        "Give me stock options trading strategies and portfolio tax optimization advice.",
        "Draft a patent infringement lawsuit defense brief for federal court.",
        "Give me a sourdough bread and chocolate cake baking recipe.",
    ]

    for prompt in non_hr_prompts:
        res = client.post(
            "/api/v1/hr-agent/execute",
            headers=owner_hdr,
            json={"prompt": prompt},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["execution_status"] == "rejected", (prompt, body)
        assert body["classifier_result"] == "rejected_out_of_domain", (prompt, body)
        combined = f"{body['final_response_text']} {body.get('rejection_reason') or ''}".lower()
        assert "marketplace" not in combined
        assert "rent-an-agent" not in combined
        assert "suggested marketplace category" not in combined


def test_rbac_enforcement_employee_vs_admin_and_owner(client: TestClient):
    emp_hdr = _login(client, "maya@acmecloud.io", "AcmeUser!2026", "acme-cloud")
    admin_hdr = _login(client, "vikram@acmecloud.io", "AcmeAdmin!2026", "acme-cloud")
    owner_hdr = _login(client, "ananya@acmecloud.io", "AcmeOwner!2026", "acme-cloud")

    # Workspace metadata accurately flags permitted workflows per role
    ws_emp = client.get("/api/v1/hr-agent/workspace", headers=emp_hdr)
    assert ws_emp.status_code == 200
    emp_wf_map = {w["slug"]: w["allowed_for_current_role"] for w in ws_emp.json()["workflows"]}
    assert emp_wf_map["hr-policy-support"] is True
    for restricted in [
        "recruitment-screening",
        "jd-generator",
        "candidate-shortlisting",
        "interview-scheduling",
        "employee-onboarding",
        "hr-analytics",
    ]:
        assert emp_wf_map[restricted] is False

    # Employee CAN use HR Policy Support self-service
    ok_policy = client.post(
        "/api/v1/hr-agent/execute",
        headers=emp_hdr,
        json={"prompt": "What is our PTO and parental leave policy in the handbook?"},
    )
    assert ok_policy.status_code == 200, ok_policy.text
    assert ok_policy.json()["routed_workflow"] == "hr-policy-support"

    # Employee receives 403 on all 6 sensitive hiring/HR/analytics workflows
    restricted_prompts = [
        ("recruitment-screening", "Screen resumes for Senior Python Engineer."),
        ("jd-generator", "Generate a job description for Staff Backend Engineer."),
        ("candidate-shortlisting", "Shortlist and rank top engineering candidates."),
        ("interview-scheduling", "Schedule technical interview panel for Elena Rostova."),
        ("employee-onboarding", "Start day-1 IT and HR onboarding checklist for new hire."),
        ("hr-analytics", "Generate executive time to hire and DEI attrition metrics report."),
    ]
    for hint, prompt in restricted_prompts:
        denied = client.post(
            "/api/v1/hr-agent/execute",
            headers=emp_hdr,
            json={"prompt": prompt, "workflow_hint": hint},
        )
        assert denied.status_code == 403, f"Expected 403 for employee on {hint}, got {denied.status_code}: {denied.text}"

    # Employee cannot alter workspace settings or tool permissions
    assert client.patch("/api/v1/hr-agent/settings", headers=emp_hdr, json={"blind_screening_mode": False}).status_code == 403
    perms = client.get("/api/v1/hr-agent/integrations", headers=owner_hdr).json()
    assert len(perms) > 0
    assert client.patch(
        f"/api/v1/hr-agent/integrations/{perms[0]['id']}",
        headers=emp_hdr,
        json={"is_allowed": False},
    ).status_code == 403

    # Business Admin can execute restricted workflows cleanly
    admin_jd = client.post(
        "/api/v1/hr-agent/execute",
        headers=admin_hdr,
        json={"prompt": "Generate a job description for Principal Cloud Architect with AWS and Kubernetes."},
    )
    assert admin_jd.status_code == 200, admin_jd.text
    assert admin_jd.json()["routed_workflow"] == "jd-generator"


def test_quota_enforcement_and_concurrency_locking(client: TestClient):
    # 1. Sequential quota enforcement on an isolated freshly-registered tenant
    hdr1, _ = _register_owner(client, uuid.uuid4().hex[:8])
    ws1 = client.get("/api/v1/hr-agent/workspace", headers=hdr1)
    assert ws1.status_code == 200

    prompt = "Explain our parental leave and remote work reimbursement handbook policy."
    used_total = 0
    while used_total < 200:
        r = client.post("/api/v1/hr-agent/execute", headers=hdr1, json={"prompt": prompt})
        assert r.status_code == 200, r.text
        used_total += r.json()["input_tokens"] + r.json()["output_tokens"]

    cap_res = client.patch(
        "/api/v1/hr-agent/settings",
        headers=hdr1,
        json={"monthly_token_quota": used_total},
    )
    assert cap_res.status_code == 200, cap_res.text
    assert cap_res.json()["monthly_token_quota"] == used_total

    blocked = client.post("/api/v1/hr-agent/execute", headers=hdr1, json={"prompt": prompt})
    assert blocked.status_code == 429, blocked.text
    assert "quota" in blocked.json()["detail"].lower()

    usage_after_block = client.get("/api/v1/hr-agent/usage", headers=hdr1).json()
    assert usage_after_block["tokens_used_this_month"] == used_total

    # Raising quota restores execution
    raise_res = client.patch(
        "/api/v1/hr-agent/settings",
        headers=hdr1,
        json={"monthly_token_quota": used_total + 50_000},
    )
    assert raise_res.status_code == 200
    restored = client.post("/api/v1/hr-agent/execute", headers=hdr1, json={"prompt": prompt})
    assert restored.status_code == 200

    # 2. Concurrent execution test proving SELECT FOR UPDATE prevents double-spend past quota
    hdr2, _ = _register_owner(client, f"conc-{uuid.uuid4().hex[:6]}")
    base_used = 0
    last_tokens = 0
    while base_used < 200:
        r = client.post("/api/v1/hr-agent/execute", headers=hdr2, json={"prompt": prompt})
        assert r.status_code == 200, r.text
        last_tokens = r.json()["input_tokens"] + r.json()["output_tokens"]
        base_used += last_tokens

    # Tight cap permits exactly ONE more execution of `last_tokens` and rejects a simultaneous 2nd request
    tight_cap = base_used + last_tokens
    patch_cap = client.patch(
        "/api/v1/hr-agent/settings",
        headers=hdr2,
        json={"monthly_token_quota": tight_cap},
    )
    assert patch_cap.status_code == 200, patch_cap.text

    def _run_concurrent_call() -> int:
        # Instantiate TestClient without 'with' so thread exit does not shut down session-wide lifespan pgserver
        local_client = TestClient(app)
        res = local_client.post("/api/v1/hr-agent/execute", headers=hdr2, json={"prompt": prompt})
        return res.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_run_concurrent_call)
        f2 = pool.submit(_run_concurrent_call)
        statuses = sorted([f1.result(), f2.result()])

    assert statuses == [200, 429], f"Expected strict [200, 429] under FOR UPDATE lock, got {statuses}"
    final_usage = client.get("/api/v1/hr-agent/usage", headers=hdr2).json()
    assert final_usage["tokens_used_this_month"] <= tight_cap


def test_unified_kb_integrations_settings_and_tenant_isolation(client: TestClient):
    acme_hdr = _login(client, "ananya@acmecloud.io", "AcmeOwner!2026", "acme-cloud")
    emp_hdr = _login(client, "maya@acmecloud.io", "AcmeUser!2026", "acme-cloud")
    nova_hdr = _login(client, "priya@novabio.io", "NovaOwner!2026", "novabio-healthtech")

    # 1. Knowledge base upload -> list -> download -> cross-tenant 404 -> owner delete
    sample_text = b"Acme Hybrid Work Stipend Policy: Employees receive $750 annual ergonomic setup budget."
    up_res = client.post(
        "/api/v1/hr-agent/knowledge",
        headers=acme_hdr,
        data={
            "title": "Acme Stipend Addendum",
            "source_type": "policy",
            "min_role_access": "business_employee",
            "workflow_slug": "hr-policy-support",
        },
        files={"file": ("stipend_addendum.txt", sample_text, "text/plain")},
    )
    assert up_res.status_code == 201, up_res.text
    doc = up_res.json()
    doc_id = doc["id"]
    assert doc["status"] == "indexed"

    list_res = client.get("/api/v1/hr-agent/knowledge", headers=emp_hdr)
    assert list_res.status_code == 200
    assert any(d["id"] == doc_id for d in list_res.json())

    dl_res = client.get(f"/api/v1/hr-agent/knowledge/{doc_id}/download", headers=emp_hdr)
    assert dl_res.status_code == 200
    assert b"ergonomic setup budget" in dl_res.content

    # Tenant B cannot see or download Tenant A's document
    nova_dl = client.get(f"/api/v1/hr-agent/knowledge/{doc_id}/download", headers=nova_hdr)
    assert nova_dl.status_code == 404

    # Employee cannot delete, Owner can delete
    assert client.delete(f"/api/v1/hr-agent/knowledge/{doc_id}", headers=emp_hdr).status_code == 403
    assert client.delete(f"/api/v1/hr-agent/knowledge/{doc_id}", headers=acme_hdr).status_code == 204

    # 2. Integrations toggle + encrypted credential masking + cross-tenant 404
    integrations = client.get("/api/v1/hr-agent/integrations", headers=acme_hdr).json()
    assert len(integrations) > 0
    perm_id = integrations[0]["id"]
    orig_allowed = integrations[0]["is_allowed"]

    toggle = client.patch(
        f"/api/v1/hr-agent/integrations/{perm_id}",
        headers=acme_hdr,
        json={"is_allowed": not orig_allowed, "apply_to_all_workflows": False},
    )
    assert toggle.status_code == 200
    assert toggle.json()["is_allowed"] == (not orig_allowed)

    raw_secret = "ghp_super_secret_demo_token_987654"
    cred = client.post(
        f"/api/v1/hr-agent/integrations/{perm_id}/credentials",
        headers=acme_hdr,
        json={"api_key_or_token": raw_secret, "apply_to_all_workflows": False},
    )
    assert cred.status_code == 200, cred.text
    cred_data = cred.json()
    assert cred_data["credential_status"] == "bound_encrypted"
    assert raw_secret not in (cred_data.get("masked_secret_ref") or "")
    assert "7654" in (cred_data.get("masked_secret_ref") or "")
    assert (cred_data.get("masked_secret_ref") or "").startswith("vault://")

    # Restore toggle cleanly
    client.patch(
        f"/api/v1/hr-agent/integrations/{perm_id}",
        headers=acme_hdr,
        json={"is_allowed": orig_allowed, "apply_to_all_workflows": False},
    )

    # NovaBio cannot access Acme's permission ID
    assert client.patch(
        f"/api/v1/hr-agent/integrations/{perm_id}",
        headers=nova_hdr,
        json={"is_allowed": False},
    ).status_code == 404

    # 3. Telemetry endpoints return executions & usage cleanly
    execs = client.get("/api/v1/hr-agent/executions", headers=acme_hdr)
    assert execs.status_code == 200
    assert len(execs.json()) >= 1

    usage = client.get("/api/v1/hr-agent/usage", headers=acme_hdr)
    assert usage.status_code == 200
    assert usage.json()["tokens_used_this_month"] > 0
