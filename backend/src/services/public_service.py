"""
公共图库业务逻辑
"""
import base64
import json
import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from src.config import AI_SEARCH_BATCH_SIZE, AI_SEARCH_VISION_TOP_N, MODEL_REGISTRY
from src.models.image import Image
from src.models.public_image import PublicImage
from src.models.tag import Tag, public_image_tags
from src.models.user import User
from src.services.agent_service import complete_llm
from src.services.image_service import get_image_detail
from src.services.tag_service import set_tags, tag_names


def _can_manage(pi: PublicImage, user: User) -> bool:
    """标签管理权限：上传者本人或管理员"""
    return pi.user_id == user.id or user.role == "admin"


def _build_item(pi: PublicImage, image: Image, submitter: User) -> dict:
    """组装公共图库条目（展平图片信息 + 提交者用户名 + 标签）"""
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
        # 阶段 19：公共图库展示的是「公开标签」（public_image_tags），
        # 与个人图库的 image_tags 分离，互不影响
        "tags": tag_names(pi),
    }


def submit_to_public(db: Session, image_id: int, user: User, tags: list[str] | None = None) -> dict:
    """提交图片到公共图库（仅限自己图库已有图片），可选携带标签

    阶段 19：传入的标签写入「公开标签」（public_image_tags），是**复制**而非共享——
    之后用户在个人图库增删标签不会影响这条已提交记录。
    """
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
    if tags:
        set_tags(db, pi, tags)
    db.commit()
    db.refresh(pi)
    return _build_item(pi, image, user)


def _apply_visibility(query, user: User | None):
    """公共图库可见性过滤（阶段 22：收敛为单一实现）

    调用前 query 须已限定 `PublicImage.status == "approved"`：
    - 匿名：只看 is_visible
    - 普通用户：is_visible 或本人上传的（自己能看到自己提交但未公开的）
    - admin：不加额外过滤（可见全部已审核）

    阶段 22 前这套规则在 `get_public_images` 与 `ai_search` 里各写了一遍，
    标签聚合若再写第三遍，改一处漏两处就会越权/泄露，故统一到这里。
    """
    if user is None:
        return query.filter(PublicImage.is_visible == True)  # noqa: E712
    if user.role != "admin":
        return query.filter(
            or_(
                PublicImage.is_visible == True,  # noqa: E712
                PublicImage.user_id == user.id,
            )
        )
    return query


def get_public_images(
    db: Session,
    user: User | None,
    skip: int = 0,
    limit: int = 20,
    search: str | None = None,
    tag: str | None = None,
) -> dict:
    """浏览公共图库（角色感知可见性 + 名称/标签搜索）

    - `search`：#标签 → 严格匹配公开标签；否则按自定义名称模糊匹配
    - `tag`：按公开标签精确筛选（与 `search` 同时给出取 AND）
    """
    query = (
        db.query(PublicImage, Image, User)
        .join(Image, PublicImage.image_id == Image.id)
        .join(User, PublicImage.user_id == User.id)
        .filter(PublicImage.status == "approved")
    )
    query = _apply_visibility(query, user)
    if search:
        if search.startswith("#"):
            # #标签 → 严格匹配标签名（非模糊）：搜 #猫 只命中标签恰好为"猫"的图片
            # 阶段 19：搜的是「公开标签」，个人图库的私人标签不会出现在公共搜索里
            tag_name = search[1:].strip()
            if tag_name:
                query = query.filter(PublicImage.tags.any(Tag.name == tag_name))
        else:
            pattern = f"%{search}%"
            # 普通关键词：只匹配自定义名称（用户要求：不搜原始文件名）
            query = query.filter(Image.custom_name.ilike(pattern))
    if tag:
        # 阶段 22：独立标签筛选项，精确匹配公开标签；与 search 同时给出时取 AND
        query = query.filter(PublicImage.tags.any(Tag.name == tag))
    total = query.count()
    rows = query.order_by(PublicImage.created_at.desc()).offset(skip).limit(limit).all()
    items = [_build_item(pi, img, u) for pi, img, u in rows]
    return {"total": total, "items": items}


def get_public_tag_stats(db: Session, user: User | None) -> list[dict]:
    """公共图库的标签使用统计（阶段 22：筛选条数据源）

    与列表**复用同一套可见性口径**（`_apply_visibility`）：匿名访客的筛选条里
    不能出现不可见或未审核记录的标签名，否则等于泄露。
    按使用次数降序、标签名升序；不缓存（结果随角色与可见性变化）。
    """
    query = (
        db.query(Tag.name, func.count(public_image_tags.c.public_image_id).label("count"))
        .join(public_image_tags, public_image_tags.c.tag_id == Tag.id)
        .join(PublicImage, PublicImage.id == public_image_tags.c.public_image_id)
        .filter(PublicImage.status == "approved")
    )
    query = _apply_visibility(query, user)
    rows = (
        query.group_by(Tag.name)
        .order_by(
            func.count(public_image_tags.c.public_image_id).desc(),
            Tag.name.asc(),
        )
        .all()
    )
    return [{"name": name, "count": count} for name, count in rows]


def _pick_model(model_type: str) -> str | None:
    """从模型注册表选一个指定类型的模型 id（text/vision），无可用返回 None"""
    for m in MODEL_REGISTRY:
        if m.get("type") == model_type:
            model_id = m.get("id")
            if isinstance(model_id, str):
                return model_id
    return None


def _parse_id_list(text: str) -> set[int]:
    """从 AI 返回文本中解析 id 列表（容错：剥离代码块围栏、提取 JSON 数组，非法则空）"""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\[[^\]]*\]", cleaned)
        if not m:
            return set()
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return set()
    if not isinstance(data, list):
        return set()

    def _is_id(x: object) -> bool:
        return isinstance(x, (int, str)) and str(x).strip().lstrip("-").isdigit()

    return {int(x) for x in data if _is_id(x)}


async def _ai_search_semantic(rows, query: str, model_id: str) -> set[int]:
    """语义通道：候选元数据（id/标题/标签）分批送文本模型，返回匹配的 public_id 集合"""
    candidates = [
        {"id": pi.id, "title": img.display_name, "tags": tag_names(pi)}
        for pi, img, _ in rows
    ]
    matched: set[int] = set()
    for i in range(0, len(candidates), AI_SEARCH_BATCH_SIZE):
        batch = candidates[i:i + AI_SEARCH_BATCH_SIZE]
        prompt = (
            "你是图片检索助手。下面是公共图库中的图片清单（id, 标题, 标签）。\n"
            f"用户查询：「{query}」\n"
            "请根据标题和标签的语义相关性，返回与查询匹配的图片 id 列表。\n"
            f"清单：{json.dumps(batch, ensure_ascii=False)}\n"
            "只返回 JSON 数组，例如 [1, 5]。没有匹配返回 []。不要输出其他内容。"
        )
        text = await complete_llm(model_id, [{"role": "user", "content": prompt}])
        matched |= _parse_id_list(text)
    return matched


async def _ai_search_vision(rows, query: str, model_id: str) -> set[int]:
    """识图通道：对候选图片限量逐张视觉判断"与查询是否相关"，返回匹配的 public_id 集合"""
    matched: set[int] = set()
    for pi, img, _ in rows[:AI_SEARCH_VISION_TOP_N]:
        image_path = img.thumbnail_path or img.file_path
        if not image_path:
            continue
        try:
            with open(image_path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
        except OSError:
            continue
        text_prompt = f"这张图片与查询「{query}」相关吗？只回答「是」或「否」。"
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": text_prompt},
                {"type": "image_url", "image_url": {"url": f"data:{img.mime_type};base64,{data}"}},
            ],
        }]
        text = await complete_llm(model_id, messages)
        if text.strip().startswith("是"):
            matched.add(pi.id)
    return matched


async def ai_search(db: Session, query: str, mode: str, user: User | None) -> dict:
    """AI 搜索公共图库：语义通道（标题+标签）或识图通道（视觉模型）
    - 候选集与列表浏览一致的可见性规则（approved + 角色过滤）
    - 严格校验 AI 返回的 id 存在且可见（幻觉过滤）
    - AI 不可用/失败 → 抛出 5xx 友好错误（前端提示后可回退普通搜索）
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="搜索词不能为空")

    q = (
        db.query(PublicImage, Image, User)
        .join(Image, PublicImage.image_id == Image.id)
        .join(User, PublicImage.user_id == User.id)
        .filter(PublicImage.status == "approved")
    )
    # 阶段 22：候选集可见性与列表同源，避免两处规则漂移
    q = _apply_visibility(q, user)
    rows = q.order_by(PublicImage.created_at.desc()).all()
    if not rows:
        return {"total": 0, "items": [], "note": "没有可搜索的公共图片"}

    model_id = _pick_model("vision" if mode == "vision" else "text")
    if model_id is None:
        raise HTTPException(status_code=503, detail="未配置 AI 模型，无法使用 AI 搜索")

    try:
        if mode == "vision":
            matched_ids = await _ai_search_vision(rows, query, model_id)
        else:
            matched_ids = await _ai_search_semantic(rows, query, model_id)
    except HTTPException:
        raise HTTPException(status_code=502, detail="AI 搜索暂不可用，请稍后重试或使用普通搜索")

    # 幻觉过滤：只保留 AI 返回且仍在候选集中的 id
    valid_ids = {pi.id for pi, _, _ in rows}
    matched = [t for t in rows if t[0].id in matched_ids and t[0].id in valid_ids]
    items = [_build_item(pi, img, u) for pi, img, u in matched]
    return {"total": len(items), "items": items, "note": None}


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


def review_public_image(
    db: Session, public_id: int, action: str, comment: str | None, admin: User
) -> None:
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


def get_public_detail(db: Session, public_id: int, user: User | None) -> dict:
    """公共图库详情（含当前用户是否为上传者/管理员，匿名可访问 approved+visible）"""
    pi = _get_public_record(db, public_id)
    # 匿名用户只能看 approved + visible
    if user is None and (pi.status != "approved" or not pi.is_visible):
        raise HTTPException(status_code=404, detail="记录不存在")
    image = db.query(Image).filter(Image.id == pi.image_id).first()
    submitter = db.query(User).filter(User.id == pi.user_id).first()
    item = _build_item(pi, image, submitter)
    if user is None:
        item["is_owner"] = False
        item["is_admin"] = False
    else:
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


def add_tags_to_public(db: Session, public_id: int, raw_tags: list[str], user: User) -> list[str]:
    """给公共图库图片添加标签（上传者本人或管理员），返回该记录当前全部公开标签

    阶段 19：只写公开标签（public_image_tags），不回写 image_tags——
    否则用户在公共图库删掉一个预填标签，个人图库的标签也会跟着消失。
    """
    pi = _get_public_record(db, public_id)
    if not _can_manage(pi, user):
        raise HTTPException(status_code=403, detail="无权操作")
    set_tags(db, pi, raw_tags)
    db.commit()
    return tag_names(pi)


def remove_tag_from_public(db: Session, public_id: int, tag_name: str, user: User) -> None:
    """从公共图库图片移除标签（上传者本人或管理员），只影响公开标签"""
    pi = _get_public_record(db, public_id)
    if not _can_manage(pi, user):
        raise HTTPException(status_code=403, detail="无权操作")
    tag = next((t for t in pi.tags if t.name == tag_name), None)
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    pi.tags.remove(tag)
    db.commit()
