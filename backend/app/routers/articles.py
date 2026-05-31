import math
from typing import Optional
import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Article
from app.schemas.article import ArticleRead, ArticleListResponse

router = APIRouter()


@router.get("/", response_model=ArticleListResponse)
def list_articles(
    tenant_id: int,
    source_id: Optional[int] = None,
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    from_date: Optional[datetime.date] = None,
    to_date: Optional[datetime.date] = None,
    is_read: Optional[bool] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = (db.query(Article)
         .filter(Article.tenant_id == tenant_id,
                 Article.duplicate_of_id.is_(None)))

    if source_id:
        q = q.filter(Article.source_id == source_id)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            (Article.title.ilike(like)) |
            (Article.excerpt.ilike(like)) |
            (Article.summary.ilike(like))
        )
    if category:
        q = q.filter(Article.category == category)
    if from_date:
        q = q.filter(Article.scraped_at >= datetime.datetime.combine(
            from_date, datetime.time.min))
    if to_date:
        q = q.filter(Article.scraped_at <= datetime.datetime.combine(
            to_date, datetime.time.max))
    if is_read is not None:
        q = q.filter(Article.is_read == is_read)

    total = q.count()
    items = (q.order_by(Article.relevance_score.desc(), Article.scraped_at.desc())
             .offset((page - 1) * size)
             .limit(size)
             .all())

    return ArticleListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 0,
    )


@router.get("/{article_id}", response_model=ArticleRead)
def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return article


@router.patch("/{article_id}/read", response_model=ArticleRead)
def mark_read(article_id: int, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    article.is_read = True
    db.commit()
    db.refresh(article)
    return article


@router.patch("/read-all")
def mark_all_read(tenant_id: int, db: Session = Depends(get_db)):
    count = (db.query(Article)
             .filter(Article.tenant_id == tenant_id, Article.is_read == False)
             .update({"is_read": True}))
    db.commit()
    return {"marked_read": count}


@router.delete("/{article_id}", status_code=204)
def delete_article(article_id: int, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    db.delete(article)
    db.commit()
