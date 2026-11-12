import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.db.session import apply_tenant_rls, get_session_factory


def test_cross_tenant_api_and_postgres_rls_isolation(client):
    # Register Tenant A (Alpha) & Tenant B (Beta)
    alpha = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Alpha Owner",
            "email": "alpha.owner@alphaiso.io",
            "password": "AlphaPassword!2026",
            "organization_name": "Alpha Isolation Corp",
            "industry": "Finance",
        },
    ).json()
    beta = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Beta Owner",
            "email": "beta.owner@betaiso.io",
            "password": "BetaPassword!2026",
            "organization_name": "Beta Isolation Labs",
            "industry": "Healthcare",
        },
    ).json()

    alpha_tenant_id = uuid.UUID(alpha["user"]["tenant_id"])
    beta_tenant_id = uuid.UUID(beta["user"]["tenant_id"])
    alpha_hdr = {"Authorization": f"Bearer {alpha['access_token']}"}
    # Beta even tries passing malicious tenant spoofing headers
    beta_hdr = {
        "Authorization": f"Bearer {beta['access_token']}",
        "X-Tenant-Id": str(alpha_tenant_id),
    }

    # Alpha rents an agent, uploads a secret file, binds an encrypted API key, chats
    rental = client.post(
        "/api/v1/rentals",
        headers=alpha_hdr,
        json={
            "agent_slug": "recruitment-screening",
            "subscription_plan_slug": "growth",
            "display_name": "Alpha Secret Screener",
        },
    ).json()
    alpha_rental_id = rental["id"]
    tool_id = next(t["tool_id"] for t in rental["tool_permissions"] if t["tool_slug"] == "ats_post_scorecard")

    bind = client.post(
        f"/api/v1/rentals/{alpha_rental_id}/tools/{tool_id}/credentials",
        headers=alpha_hdr,
        json={"api_key_or_token": "alpha-greenhouse-secret-xyz"},
    )
    assert bind.status_code == 200

    upload = client.post(
        f"/api/v1/rentals/{alpha_rental_id}/knowledge",
        headers=alpha_hdr,
        files={"file": ("alpha_secret_comp.txt", b"Senior L6 base range: $210k-$245k", "text/plain")},
        data={"title": "Alpha Secret Compensation Guide", "source_type": "rubric", "min_role_access": "business_employee"},
    )
    assert upload.status_code == 201
    alpha_doc_id = upload.json()["id"]

    conv = client.post(
        f"/api/v1/rentals/{alpha_rental_id}/conversations",
        headers=alpha_hdr,
        json={"title": "Alpha Confidential Thread"},
    ).json()
    alpha_conv_id = conv["id"]

    msg = client.post(
        f"/api/v1/conversations/{alpha_conv_id}/messages",
        headers=alpha_hdr,
        json={"content": "Screen this candidate resume against our Backend rubric."},
    )
    assert msg.status_code == 201

    # --- Company B MUST NEVER ACCESS Company A resources ---
    beta_rentals = client.get("/api/v1/rentals", headers=beta_hdr).json()
    assert all(r["id"] != alpha_rental_id for r in beta_rentals)

    assert client.get(f"/api/v1/rentals/{alpha_rental_id}", headers=beta_hdr).status_code == 404
    assert client.post(f"/api/v1/rentals/{alpha_rental_id}/pause", headers=beta_hdr).status_code == 404
    assert (
        client.patch(
            f"/api/v1/rentals/{alpha_rental_id}/configuration",
            headers=beta_hdr,
            json={"custom_persona_prompt": "Tampered by Beta"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/rentals/{alpha_rental_id}/tools/{tool_id}/credentials",
            headers=beta_hdr,
            json={"api_key_or_token": "tampered"},
        ).status_code
        == 404
    )
    assert client.get(f"/api/v1/rentals/{alpha_rental_id}/knowledge", headers=beta_hdr).status_code == 404
    assert client.get(f"/api/v1/rentals/{alpha_rental_id}/knowledge/{alpha_doc_id}/download", headers=beta_hdr).status_code == 404
    assert client.delete(f"/api/v1/rentals/{alpha_rental_id}/knowledge/{alpha_doc_id}", headers=beta_hdr).status_code == 404

    assert client.get(f"/api/v1/conversations/{alpha_conv_id}", headers=beta_hdr).status_code == 404
    assert (
        client.post(
            f"/api/v1/conversations/{alpha_conv_id}/messages",
            headers=beta_hdr,
            json={"content": "Try stealing alpha thread"},
        ).status_code
        == 404
    )

    assert all(x["rental_id"] != alpha_rental_id for x in client.get("/api/v1/execution-logs", headers=beta_hdr).json())
    assert all(x["rental_id"] != alpha_rental_id for x in client.get("/api/v1/usage/tokens", headers=beta_hdr).json())
    assert all(x["rental_id"] != alpha_rental_id for x in client.get("/api/v1/billing/records", headers=beta_hdr).json())
    assert all(x["rental_id"] != alpha_rental_id for x in client.get("/api/v1/audit-logs", headers=beta_hdr).json())

    # --- Verify PostgreSQL FORCE ROW LEVEL SECURITY at raw SQL engine level ---
    SessionFactory = get_session_factory()
    with SessionFactory() as db:
        apply_tenant_rls(db, beta_tenant_id)
        for table in [
            "agent_rentals",
            "agent_configurations",
            "agent_conversations",
            "messages",
            "tool_permissions",
            "knowledge_documents",
            "execution_logs",
            "token_usage",
            "billing_records",
            "audit_logs",
        ]:
            count = db.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id = :alpha_tid"),
                {"alpha_tid": str(alpha_tenant_id)},
            ).scalar_one()
            assert count == 0, f"PostgreSQL RLS failed to isolate table {table}"

        # Also prove runtime role cannot INSERT a row claiming Alpha's tenant_id while bound to Beta
        with pytest.raises(ProgrammingError):
            db.execute(
                text(
                    "INSERT INTO agent_conversations (id, tenant_id, rental_id, title, status, summary_memory) "
                    "VALUES (:id, :alpha_tid, :rid, 'forged', 'active', '')"
                ),
                {"id": str(uuid.uuid4()), "alpha_tid": str(alpha_tenant_id), "rid": alpha_rental_id},
            )
        db.rollback()

        # And prove runtime role cannot UPDATE/DELETE audit_logs (append-only enforcement)
        apply_tenant_rls(db, alpha_tenant_id)
        with pytest.raises(ProgrammingError):
            db.execute(text("DELETE FROM audit_logs WHERE tenant_id = :tid"), {"tid": str(alpha_tenant_id)})
        db.rollback()
