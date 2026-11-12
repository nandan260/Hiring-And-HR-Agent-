"""End-to-end HTTP integration tests across all 7 HR agents, file upload -> RAG, HITL approvals, and cross-tenant isolation."""

from __future__ import annotations


def _login(client, email: str, password: str, tenant_slug: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "tenant_slug": tenant_slug},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_end_to_end_all_7_hr_agents_rag_hitl_and_isolation(client):
    acme_hdr = _login(client, "ananya@acmecloud.io", "AcmeOwner!2026", "acme-cloud")
    nova_hdr = _login(client, "priya@novabio.io", "NovaOwner!2026", "novabio-healthtech")

    # 1. Agent specs endpoint returns all 7 independently configured HR agents
    specs_resp = client.get("/api/v1/agents/specs")
    assert specs_resp.status_code == 200
    specs = specs_resp.json()
    assert len(specs) == 7
    slugs = {s["agent_id"] for s in specs}
    assert slugs == {
        "recruitment-screening",
        "jd-generator",
        "candidate-shortlisting",
        "interview-scheduling",
        "employee-onboarding",
        "hr-policy-support",
        "hr-analytics",
    }

    # Fetch Acme's existing rentals and rent the remaining 4 specialists on demo starter plan cleanly
    acme_rentals = client.get("/api/v1/rentals", headers=acme_hdr).json()
    by_slug = {r["agent_slug"]: r for r in acme_rentals}

    for slug in ["jd-generator", "candidate-shortlisting", "interview-scheduling", "hr-analytics"]:
        if slug not in by_slug:
            rent_res = client.post(
                "/api/v1/rentals",
                headers=acme_hdr,
                json={
                    "agent_slug": slug,
                    "plan_slug": "starter",
                    "display_name": f"Acme {slug}",
                },
            )
            assert rent_res.status_code == 201, rent_res.text
            by_slug[slug] = rent_res.json()

    # 2. Conversation message -> live Recruitment Screening Agent via POST /conversations/{id}/messages
    rec_rid = by_slug["recruitment-screening"]["id"]
    conv_res = client.post(
        f"/api/v1/rentals/{rec_rid}/conversations",
        headers=acme_hdr,
        json={"title": "Live Recruitment Batch"},
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    msg_res = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=acme_hdr,
        json={"content": "Screen candidates for Senior Backend Engineer with Python, FastAPI, PostgreSQL skills."},
    )
    assert msg_res.status_code == 201, msg_res.text
    msg_data = msg_res.json()
    assert msg_data["classifier_result"] == "in_domain"
    assert msg_data["assistant_message"]["metadata_json"]["is_foundation_stub"] is False
    assert msg_data["assistant_message"]["metadata_json"]["agent_id"] == "recruitment-screening"

    # 3. Execute JD Generator, Candidate Shortlisting, Interview Scheduling, HR Analytics via /execute
    jd_res = client.post(
        f"/api/v1/rentals/{by_slug['jd-generator']['id']}/execute",
        headers=acme_hdr,
        json={
            "prompt": "Generate a job description for Staff Platform Engineer with Python, PostgreSQL, Docker skills.",
            "structured_input": {"job_title": "Staff Platform Engineer", "required_skills": ["Python", "PostgreSQL", "Docker"]},
        },
    )
    assert jd_res.status_code == 200, jd_res.text
    assert jd_res.json()["structured_output"]["job_title"] == "Staff Platform Engineer"

    short_res = client.post(
        f"/api/v1/rentals/{by_slug['candidate-shortlisting']['id']}/execute",
        headers=acme_hdr,
        json={"prompt": "Shortlist top Backend candidates with Python, FastAPI, and PostgreSQL."},
    )
    assert short_res.status_code == 200, short_res.text
    assert len(short_res.json()["structured_output"]["comparison_matrix"]) >= 2

    sched_res = client.post(
        f"/api/v1/rentals/{by_slug['interview-scheduling']['id']}/execute",
        headers=acme_hdr,
        json={
            "prompt": "Schedule technical interview for Elena Rostova.",
            "structured_input": {"candidate_name": "Elena Rostova", "role_title": "Senior Backend Engineer"},
        },
    )
    assert sched_res.status_code == 200, sched_res.text
    assert sched_res.json()["execution_status"] == "paused_hitl"

    ana_res = client.post(
        f"/api/v1/rentals/{by_slug['hr-analytics']['id']}/execute",
        headers=acme_hdr,
        json={"prompt": "Generate full HR pipeline analytics report and charts."},
    )
    assert ana_res.status_code == 200, ana_res.text
    assert len(ana_res.json()["charts"]) == 3

    # 4. Upload new HR Policy document -> auto-indexed into pgvector -> Employee Support cites it immediately
    pol_rid = by_slug["hr-policy-support"]["id"]
    up_res = client.post(
        f"/api/v1/rentals/{pol_rid}/knowledge",
        headers=acme_hdr,
        data={"title": "Acme Relocation Bonus Addendum", "source_type": "policy", "min_role_access": "business_employee"},
        files={"file": ("relocation_addendum.md", b"# Relocation Stipend\nAcme provides $7,500 relocation reimbursement for engineering hires.", "text/markdown")},
    )
    assert up_res.status_code == 201, up_res.text

    rag_res = client.post(
        f"/api/v1/rentals/{pol_rid}/execute",
        headers=acme_hdr,
        json={"prompt": "What is the relocation stipend reimbursement policy for engineering hires?"},
    )
    assert rag_res.status_code == 200, rag_res.text
    rag_json = rag_res.json()
    assert rag_json["structured_output"]["grounded_in_tenant_docs"] is True
    assert "$7,500" in rag_json["structured_output"]["answer"]
    assert any("Relocation" in c for c in rag_json["citations"])

    # 5. Onboarding Agent creates HITL approvals -> Resolve HITL approval -> updates OnboardingWorkflow live
    onb_rid = by_slug["employee-onboarding"]["id"]
    onb_res = client.post(
        f"/api/v1/rentals/{onb_rid}/execute",
        headers=acme_hdr,
        json={
            "prompt": "Onboard Priya Iyer as DevOps Engineer in Engineering.",
            "structured_input": {
                "employee_name": "Priya Iyer",
                "role_title": "DevOps Engineer",
                "department": "Engineering",
                "submitted_documents": ["aadhar_card", "degree_certificate", "offer_letter_signed", "bank_details"],
            },
        },
    )
    assert onb_res.status_code == 200, onb_res.text
    onb_json = onb_res.json()
    assert onb_json["execution_status"] == "paused_hitl"
    hitl_reqs = onb_json["hitl_requests"]
    assert len(hitl_reqs) == 2

    # Verify NovaBio cannot see or resolve Acme's HITL approvals!
    first_approval_id = hitl_reqs[0]["approval_id"]
    nova_hitl = client.get("/api/v1/hitl/approvals", headers=nova_hdr).json()
    assert all(item["id"] != first_approval_id for item in nova_hitl)
    nova_resolve = client.post(
        f"/api/v1/hitl/approvals/{first_approval_id}/resolve",
        headers=nova_hdr,
        json={"decision": "approved"},
    )
    assert nova_resolve.status_code == 404

    # Acme Owner approves both onboarding HITL approvals cleanly
    for req in hitl_reqs:
        ap_res = client.post(
            f"/api/v1/hitl/approvals/{req['approval_id']}/resolve",
            headers=acme_hdr,
            json={"decision": "approved", "resolution_note": "Approved by HR Owner"},
        )
        assert ap_res.status_code == 200, ap_res.text
        assert ap_res.json()["status"] == "approved"

    wfs = client.get("/api/v1/onboarding", headers=acme_hdr).json()
    priya_wf = next(w for w in wfs if w["employee_name"] == "Priya Iyer")
    assert priya_wf["progress_percent"] == 100
    assert priya_wf["current_stage"] == "onboarding_ready"
    assert priya_wf["it_provisioning"]["scim_status"] == "provisioned"
    assert priya_wf["team_allocation"]["status"] == "confirmed"
