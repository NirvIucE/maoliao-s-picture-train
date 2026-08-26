"""
公共图库业务逻辑
"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.models.image import Image
from src.models.public_image import PublicImage
from src.models.user import User
from src.services.image_service import get_image_detail


def _build_item(pi: PublicImage, image: Image, submitter: User) -> dict:
    """组装公共图库条目（展平图片信息 + 提交者用户名）"""
    return {
        "id": pi.id,
        "image_id": pi.image_id,
        "user_id": pi.user_id,
        "username": submitter.username if submitter else None,
        "status": pi.status,
        "review_comment": pi.review_comment,
        "reviewed_by": pi.reviewed_by,
        "reviewed_at": pi.reviewed_at,
        "created_at": pi.created_at,
        "display_name": image.display_name,
        "thumbnail_url": image.thumbnail_url,
        "image_url": image.image_url,
        "is_visible": pi.is_visible,
    }


def submit_to_public(db: Session, image_id: int, user: User) -> dict:
    """提交图片到公共图库（仅限自己图库已有图片）"""
    image = get_image_detail(db, image_id, user)

    # 防重复提交：同一图片已有 pending/approved 记录则拒绝
    existing = db.query(PublicImage).filter(
        PublicImage.image_id == image_id,
        PublicImage.status.in_(["pending", "approved"]),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该图片已提交过公共图库")

    pi = PublicImage(image_id=image_id, user_id=user.id, status="pending")
    db.add(pi)
    db.commit()
    db.refresh(pi)
    return _build_item(pi, image, user)


def get_public_images(db: Session, user: User, skip: int = 0, limit: int = 20) -> dict:
    """浏览公共图库（管理员看全部 approved；普通用户看可见 + 自己上传的全部）"""
    query = (
        db.query(PublicImage, Image, User)
        .join(Image, PublicImage.image_id == Image.id)
        .join(User, PublicImage.user_id == User.id)
        .filter(PublicImage.status == "approved")
    )
    if user.role != "admin":
        query = query.filter(
            or_(
                PublicImage.is_visible == True,  # noqa: E712
                PublicImage.user_id == user.id,
            )
        )
    total = query.count()
    rows = query.order_by(PublicImage.created_at.desc()).offset(skip).limit(limit).all()
    items = [_build_item(pi, img, u) for pi, img, u in rows]
    return {"total": total, "items": items}


def get_my_public_images(db: Session, user: User, skip: int = 0, limit: int = 20) -> dict:
    """我的提交记录（含各状态）"""
    query = (
        db.query(PublicImage, Image, User)
        .join(Image, PublicImage.image_id == Image.id)
        .join(User, PublicImage.user_id == User.id)
        .filter(PublicImage.user_id == user.id)
    )
    total = query.count()
    rows = query.order_by(PublicImage.created_at.desc()).offset(skip).limit(limit).all()
    items = [_build_item(pi, img, u) for pi, img, u in rows]
    return {"total": total, "items": items}


def get_pending_public_images(db: Session, skip: int = 0, limit: int = 20) -> dict:
    """待审核列表（管理员）"""
    query = (
        db.query(PublicImage, Image, User)
        .join(Image, PublicImage.image_id == Image.id)
        .join(User, PublicImage.user_id == User.id)
        .filter(PublicImage.status == "pending")
    )
    total = query.count()
    rows = query.order_by(PublicImage.created_at.asc()).offset(skip).limit(limit).all()
    items = [_build_item(pi, img, u) for pi, img, u in rows]
    return {"total": total, "items": items}


def _get_public_record(db: Session, public_id: int) -> PublicImage:
    pi = db.query(PublicImage).filter(PublicImage.id == public_id).first()
    if not pi:
        raise HTTPException(status_code=404, detail="记录不存在")
    return pi


def review_public_image(db: Session, public_id: int, action: str, comment: str | None, admin: User) -> None:
    """审核（通过/拒绝）"""
    pi = _get_public_record(db, public_id)
    if pi.status != "pending":
        raise HTTPException(status_code=400, detail="该记录不在待审核状态")
    pi.status = "approved" if action == "approve" else "rejected"
    pi.review_comment = comment
    pi.reviewed_by = admin.id
    pi.reviewed_at = datetime.now()
    db.commit()


def remove_public_image(db: Session, public_id: int, comment: str | None, admin: User) -> None:
    """管理员下架（approved → rejected）"""
    pi = _get_public_record(db, public_id)
    if pi.status != "approved":
        raise HTTPException(status_code=400, detail="该记录不在已公开状态")
    pi.status = "rejected"
    pi.review_comment = comment or "管理员下架"
    pi.reviewed_by = admin.id
    pi.reviewed_at = datetime.now()
    db.commit()


def delete_public_image(db: Session, public_id: int, user: User) -> None:
    """删除公共库记录（上传者本人或管理员）"""
    pi = _get_public_record(db, public_id)
    if pi.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="无权操作")
    db.delete(pi)
    db.commit()


def get_public_detail(db: Session, public_id: int, user: User) -> dict:
    """公共图库详情（含当前用户是否为上传者/管理员）"""
    pi = _get_public_record(db, public_id)
    image = db.query(Image).filter(Image.id == pi.image_id).first()
    submitter = db.query(User).filter(User.id == pi.user_id).first()
    item = _build_item(pi, image, submitter)
    item["is_owner"] = pi.user_id == user.id
    item["is_admin"] = user.role == "admin"
    return item


def set_visibility(db: Session, public_id: int, visible: bool, user: User) -> None:
    """切换可见性（管理员或上传者）"""
    pi = _get_public_record(db, public_id)
    if pi.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="无权操作")
    pi.is_visible = visible
    db.commit()
