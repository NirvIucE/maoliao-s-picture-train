"""
公共图库路由
"""
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User
from src.routers.users import get_current_user, get_current_user_optional
from src.schemas.public_image import (
    AddTagsRequest,
    AISearchRequest,
    PublicImageDetailResponse,
    PublicImageListResponse,
    PublicImageResponse,
    PublicImageSubmitRequest,
    RemoveRequest,
    ReviewRequest,
    SetVisibilityRequest,
)
from src.services import public_service

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
    """提交图片到公共图库（仅限自己图库已有图片，可选携带标签）"""
    return public_service.submit_to_public(db, req.image_id, current_user, req.tags)


@router.get("", response_model=PublicImageListResponse)
async def list_public(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="按图片名称搜索"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """浏览公共图库（匿名看 approved+visible，登录后角色感知过滤，支持按名称搜索）"""
    return public_service.get_public_images(db, current_user, skip, limit, search)


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


@router.post("/ai-search")
async def ai_search(
    req: AISearchRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """AI 搜索公共图库（语义：标题+标签 / 识图：视觉模型），匿名可用"""
    return await public_service.ai_search(db, req.query, req.mode, current_user)


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


@router.get("/{public_id}", response_model=PublicImageDetailResponse)
async def detail(
    public_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """公共图库图片详情（含当前用户权限判断，匿名可访问 approved+visible）"""
    return public_service.get_public_detail(db, public_id, current_user)


@router.get("/{public_id}/download")
def download_public_image(
    public_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """下载公共图库图片（需登录）"""
    pi = public_service._get_public_record(db, public_id)
    if pi.status != "approved" or not pi.is_visible:
        raise HTTPException(status_code=404, detail="图片不存在或不可见")
    from src.models.image import Image
    image = db.query(Image).filter(Image.id == pi.image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="原图不存在")
    if not os.path.exists(image.file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        image.file_path,
        filename=image.original_name,
        media_type="application/octet-stream",
    )


@router.post("/{public_id}/visibility")
async def visibility(
    public_id: int,
    req: SetVisibilityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """切换可见性（管理员或上传者）"""
    public_service.set_visibility(db, public_id, req.visible, current_user)
    return {"message": "已更新可见性"}


@router.post("/{public_id}/tags")
async def add_tags(
    public_id: int,
    req: AddTagsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """给公共图库图片添加标签（上传者本人或管理员）"""
    tags = public_service.add_tags_to_public(db, public_id, req.tags, current_user)
    return {"message": "标签已更新", "tags": tags}


@router.delete("/{public_id}/tags/{tag_name}")
async def remove_tag(
    public_id: int,
    tag_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从公共图库图片移除标签（上传者本人或管理员）"""
    public_service.remove_tag_from_public(db, public_id, tag_name, current_user)
    return {"message": "标签已删除"}


@router.delete("/{public_id}")
async def delete(
    public_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除公共库记录（上传者本人或管理员）"""
    public_service.delete_public_image(db, public_id, current_user)
    return {"message": "删除成功"}
