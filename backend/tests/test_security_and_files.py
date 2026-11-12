from sqlalchemy import select

from app.core.security import decrypt_secret
from app.db.models import ToolPermission
from app.db.session import get_session_factory


def test_encrypted_tool_credentials_and_protected_file_uploads(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Tara Security",
            "email": "tara@secvault.io",
            "password": "SecPassword!2026",
            "organization_name": "SecVault HR",
            "industry": "Enterprise",
        },
    ).json()
    hdr = {"Authorization": f"Bearer {reg['access_token']}"}

    # Invite a business_employee for min_role_access document RBAC test
    client.post(
        "/api/v1/organizations/members",
        headers=hdr,
        json={
            "full_name": "Junior Staff",
            "email": "staff@secvault.io",
            "password": "StaffPassword!2026",
            "role": "business_employee",
        },
    )
    emp_token = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@secvault.io", "password": "StaffPassword!2026"},
    ).json()["access_token"]
    emp_hdr = {"Authorization": f"Bearer {emp_token}"}

    rental = client.post(
        "/api/v1/rentals",
        headers=hdr,
        json={"agent_slug": "hr-policy-support", "subscription_plan_slug": "starter"},
    ).json()
    rid = rental["id"]
    tool_id = rental["tool_permissions"][0]["tool_id"]

    raw_secret = "sk-confluence-live-token-99887766"
    bind = client.post(
        f"/api/v1/rentals/{rid}/tools/{tool_id}/credentials",
        headers=hdr,
        json={"api_key_or_token": raw_secret},
    )
    assert bind.status_code == 200
    body = bind.json()
    assert body["credential_status"] == "bound_encrypted"
    assert raw_secret not in body["masked_secret_ref"]
    assert raw_secret not in bind.text

    # Confirm ciphertext at rest in DB decrypts properly & is NOT plaintext
    SessionFactory = get_session_factory()
    with SessionFactory() as db:
        perm = db.scalars(select(ToolPermission).where(ToolPermission.rental_id == rid, ToolPermission.tool_id == tool_id)).first()
        assert perm is not None
        assert perm.encrypted_secret is not None
        assert raw_secret not in perm.encrypted_secret
        assert decrypt_secret(perm.encrypted_secret) == raw_secret

    # Reject executable upload extension
    bad_ext = client.post(
        f"/api/v1/rentals/{rid}/knowledge",
        headers=hdr,
        files={"file": ("payload.exe", b"MZbinary", "application/octet-stream")},
    )
    assert bad_ext.status_code == 400

    # Reject spoofed PDF without %PDF magic header
    bad_pdf = client.post(
        f"/api/v1/rentals/{rid}/knowledge",
        headers=hdr,
        files={"file": ("fake.pdf", b"not actually a pdf file", "application/pdf")},
    )
    assert bad_pdf.status_code == 400

    # Accept valid handbook with path-traversal filename safely sanitized & stored in tenant dir
    pdf_bytes = b"%PDF-1.4\nSecVault Executive Compensation Policy\n%%EOF"
    up_ok = client.post(
        f"/api/v1/rentals/{rid}/knowledge",
        headers=hdr,
        files={"file": ("../../etc/passwd/handbook.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Exec Comp Policy", "source_type": "policy", "min_role_access": "business_admin"},
    )
    assert up_ok.status_code == 201, up_ok.text
    doc = up_ok.json()
    assert ".." not in doc["original_filename"]
    assert doc["original_filename"] == "handbook.pdf"

    # Owner can download exact file bytes
    dl_owner = client.get(f"/api/v1/rentals/{rid}/knowledge/{doc['id']}/download", headers=hdr)
    assert dl_owner.status_code == 200
    assert dl_owner.content == pdf_bytes

    # Employee is filtered from restricted business_admin doc list & denied direct download (403)
    emp_list = client.get(f"/api/v1/rentals/{rid}/knowledge", headers=emp_hdr).json()
    assert all(d["id"] != doc["id"] for d in emp_list)
    assert client.get(f"/api/v1/rentals/{rid}/knowledge/{doc['id']}/download", headers=emp_hdr).status_code == 403
