from typing import Any, Optional
import uuid

from sqlalchemy.orm import Session

from ..db.models import AuditLog


def record_audit(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: Optional[uuid.UUID],
    action: str,
    resource_type: str,
    resource_id: str,
    rental_id: Optional[uuid.UUID] = None,
    status: str = "success",
    ip_address: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        rental_id=rental_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        status=status,
        ip_address=ip_address,
        metadata_json=metadata or {},
    )
    db.add(entry)
    return entry
