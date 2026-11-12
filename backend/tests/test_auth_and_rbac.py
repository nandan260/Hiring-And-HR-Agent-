from sqlalchemy import select

from app.db.models import User
from app.db.session import get_session_factory


def test_business_register_login_and_logout_revocation(client):
    reg_payload = {
        "full_name": "Rohan Verma",
        "email": "rohan.auth@vertexhr.io",
        "password": "StrongPassword!2026",
        "organization_name": "Vertex Talent Labs",
        "industry": "SaaS & Tech",
    }
    resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    token = data["access_token"]
    assert data["user"]["role"] == "business_owner"
    assert data["user"]["organization_name"] == "Vertex Talent Labs"

    # Duplicate email must return 409 Conflict
    dup = client.post("/api/v1/auth/register", json=reg_payload)
    assert dup.status_code == 409

    # Password stored as Argon2id hash, never plaintext
    SessionFactory = get_session_factory()
    with SessionFactory() as db:
        db_user = db.scalars(select(User).where(User.email == "rohan.auth@vertexhr.io")).first()
        assert db_user is not None
        assert db_user.password_hash.startswith("$argon2")
        assert "StrongPassword!2026" not in db_user.password_hash

    # Invalid password rejected
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": "rohan.auth@vertexhr.io", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401

    # Valid login succeeds
    good_login = client.post(
        "/api/v1/auth/login",
        json={"email": "rohan.auth@vertexhr.io", "password": "StrongPassword!2026"},
    )
    assert good_login.status_code == 200
    login_token = good_login.json()["access_token"]

    # /me succeeds before logout
    headers = {"Authorization": f"Bearer {login_token}"}
    me_ok = client.get("/api/v1/auth/me", headers=headers)
    assert me_ok.status_code == 200
    assert me_ok.json()["email"] == "rohan.auth@vertexhr.io"

    # Logout revokes JTI immediately
    out = client.post("/api/v1/auth/logout", headers=headers)
    assert out.status_code == 200
    assert out.json()["status"] == "logged_out"

    # Reusing revoked token must fail with 401
    me_revoked = client.get("/api/v1/auth/me", headers=headers)
    assert me_revoked.status_code == 401
    # Original registration token remains valid until logged out
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_role_based_access_control(client):
    owner_reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Neha Owner",
            "email": "neha.owner@rbaccorp.io",
            "password": "OwnerPassword!2026",
            "organization_name": "RBAC Corp",
            "industry": "Enterprise",
        },
    ).json()
    owner_hdr = {"Authorization": f"Bearer {owner_reg['access_token']}"}

    # Owner invites Business Admin and Business Employee
    inv_admin = client.post(
        "/api/v1/organizations/members",
        headers=owner_hdr,
        json={
            "full_name": "Arjun Admin",
            "email": "arjun.admin@rbaccorp.io",
            "password": "AdminPassword!2026",
            "role": "business_admin",
        },
    )
    assert inv_admin.status_code == 201, inv_admin.text

    inv_emp = client.post(
        "/api/v1/organizations/members",
        headers=owner_hdr,
        json={
            "full_name": "Sana Employee",
            "email": "sana.emp@rbaccorp.io",
            "password": "EmpPassword!2026",
            "role": "business_employee",
        },
    )
    assert inv_emp.status_code == 201, inv_emp.text
    emp_member_id = inv_emp.json()["member_id"]

    admin_token = client.post(
        "/api/v1/auth/login",
        json={"email": "arjun.admin@rbaccorp.io", "password": "AdminPassword!2026"},
    ).json()["access_token"]
    emp_token = client.post(
        "/api/v1/auth/login",
        json={"email": "sana.emp@rbaccorp.io", "password": "EmpPassword!2026"},
    ).json()["access_token"]

    admin_hdr = {"Authorization": f"Bearer {admin_token}"}
    emp_hdr = {"Authorization": f"Bearer {emp_token}"}

    # Business Employee is denied administrative endpoints
    assert (
        client.post(
            "/api/v1/rentals",
            headers=emp_hdr,
            json={"agent_slug": "hr-policy-support", "subscription_plan_slug": "starter"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/organizations/members",
            headers=emp_hdr,
            json={
                "full_name": "Rogue Invite",
                "email": "rogue@rbaccorp.io",
                "password": "RoguePassword!2026",
                "role": "business_admin",
            },
        ).status_code
        == 403
    )
    assert client.get("/api/v1/audit-logs", headers=emp_hdr).status_code == 403

    # Business Admin cannot promote an employee to business_owner
    promote_owner = client.patch(
        f"/api/v1/organizations/members/{emp_member_id}/role",
        headers=admin_hdr,
        json={"role": "business_owner", "is_active": True},
    )
    assert promote_owner.status_code == 403

    # Business Admin CAN rent an agent and read audit logs
    admin_rent = client.post(
        "/api/v1/rentals",
        headers=admin_hdr,
        json={"agent_slug": "hr-policy-support", "subscription_plan_slug": "starter"},
    )
    assert admin_rent.status_code == 201
    rental_id = admin_rent.json()["id"]
    assert client.get("/api/v1/audit-logs", headers=admin_hdr).status_code == 200

    # Employee CAN view organization's rentals & chat inside workspace, but CANNOT pause/cancel
    assert client.get("/api/v1/rentals", headers=emp_hdr).status_code == 200
    assert client.post(f"/api/v1/rentals/{rental_id}/pause", headers=emp_hdr).status_code == 403
    conv = client.post(
        f"/api/v1/rentals/{rental_id}/conversations",
        headers=emp_hdr,
        json={"title": "Employee PTO Question"},
    )
    assert conv.status_code == 201
    turn = client.post(
        f"/api/v1/conversations/{conv.json()['id']}/messages",
        headers=emp_hdr,
        json={"content": "What is our PTO and holiday handbook policy?"},
    )
    assert turn.status_code == 201
