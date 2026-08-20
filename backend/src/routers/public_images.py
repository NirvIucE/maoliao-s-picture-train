"""
公共图库路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User
from src.schemas.public_image import (
    PublicImageSubmitRequest,
    PublicImageResponse,
    PublicImageListResponse,
    ReviewRequest,
    RemoveRequest,
)
from src.services import public_service
from src.routers.users import get_current_user

router = APIRouter(prefix="/api/public/images", tags=["公共图库"])


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """管理员权限依赖：先鉴权，再校验角色"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


@router.post("", response_model=PublicImageResponse)
async def submit(
    req: PublicImageSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交图片到公共图库（仅限自己图库已有图片）"""
    return public_service.submit_to_public(db, req.image_id, current_user)


@router.get("", response_model=PublicImageListResponse)
async def list_public(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """浏览公共图库（仅审核通过的图片）"""
    return public_service.get_public_images(db, skip, limit)


@router.get("/my", response_model=PublicImageListResponse)
async def my_submissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """我的提交记录（含各状态）"""
    return public_service.get_my_public_images(db, current_user, skip, limit)


@router.get("/pending", response_model=PublicImageListResponse)
async def pending_list(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """待审核列表（管理员）"""
    return public_service.get_pending_public_images(db, skip, limit)


@router.post("/{public_id}/review")
async def review(
    public_id: int,
    req: ReviewRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """审核（通过/拒绝）"""
    public_service.review_public_image(db, public_id, req.action, req.comment, admin)
    return {"message": "审核完成"}


@router.post("/{public_id}/remove")
async def remove(
    public_id: int,
    req: RemoveRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """管理员下架（approved → rejected）"""
    public_service.remove_public_image(db, public_id, req.comment, admin)
    return {"message": "已下架"}


@router.delete("/{public_id}")
async def delete(
    public_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """作者删除自己的公共库记录（撤回 pending / 主动删除 approved）"""
    public_service.delete_public_image(db, public_id, current_user)
    return {"message": "删除成功"}
