import math
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.sent_digest import SentDigest

router = APIRouter()


@router.get("/")
def list_digests(
    tenant_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(SentDigest).filter_by(tenant_id=tenant_id)
    total = q.count()
    items = (q.order_by(SentDigest.sent_at.desc())
             .offset((page - 1) * size)
             .limit(size)
             .all())
    return {
        "items": [
            {
                "id": d.id,
                "tenant_id": d.tenant_id,
                "sent_at": d.sent_at.isoformat() + "Z",
                "subject": d.subject,
                "article_count": d.article_count,
                "digest_type": d.digest_type,
            }
            for d in items
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total else 0,
    }
