"""
AI 助手可调用的工具（阶段 20：tool-calling）

三个工具都围绕「当前登录用户的个人图库」：

| 工具 | 类型 | 作用 |
|---|---|---|
| `search_images` | 只读 | 按标签（精确）或名称（模糊）检索个人图库 |
| `get_image_info` | 只读 | 单张图片详情 + 它在公共图库的状态 |
| `submit_to_public` | 写 | **只校验、不写库**，返回待确认参数 |

关于 `submit_to_public`：它刻意不做任何写操作。工具的职责是「理解意图 + 抽取参数 + 前置校验」，
真正的写动作由前端确认卡片触发既有的 `POST /api/public/images`。
这样「AI 误提交」在结构上不可能发生，而不是靠在 prompt 里叮嘱模型别乱来。

本模块单独成文件（而非塞进 `agent_service`）有两个原因：一是 `agent_service` 已承担
「模型调用 + 上下文裁剪」，再堆工具会失焦；二是工具要依赖 `image_service` / `tag_service` /
各类模型，放在第三方模块可避免与 `agent_service` 形成循环依赖（与阶段 19 抽 `tag_service` 同理）。
"""

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.config import AGENT_TOOL_RESULT_LIMIT
from src.models.image import Image
from src.models.public_image import PublicImage
from src.models.tag import Tag
from src.models.user import User
from src.services.tag_service import normalize_tags, tag_names

logger = logging.getLogger(__name__)


# ── 工具参数模型（Pydantic 校验，模型给的 JSON 不可信）──

class SearchImagesArgs(BaseModel):
    """search_images 入参"""
    keyword: str | None = Field(default=None, description="图片名称关键词（模糊匹配）")
    tag: str | None = Field(default=None, description="标签名（精确匹配，不带 #）")
    limit: int | None = Field(default=None, description="返回条数上限")


class GetImageInfoArgs(BaseModel):
    """get_image_info 入参"""
    image_id: int


class SubmitToPublicArgs(BaseModel):
    """submit_to_public 入参"""
    image_id: int
    tags: list[str] | None = Field(default=None, description="要带上的公开标签，不传则沿用个人标签")


# ── 工具声明（发给模型的 JSON Schema）──

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_images",
            "description": (
                "检索当前用户的个人图库。按标签精确匹配或按名称模糊匹配，两者可同时给出（取交集）。"
                "用户提到「我的图」「图库里的」「那张猫的图」等时，先用本工具找到候选图片。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "标签名，例如「猫猫」，不要带 # 前缀"},
                    "keyword": {"type": "string", "description": "图片名称关键词，例如「麦当劳」"},
                    "limit": {"type": "integer", "description": "返回条数上限，默认 10"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_image_info",
            "description": (
                "查看个人图库中某张图片的详细信息，包含标签与它在公共图库的提交状态"
                "（none/pending/approved/rejected）。用于确认图片身份，或判断是否已提交过。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {"type": "integer", "description": "search_images 返回的图片 id"},
                },
                "required": ["image_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_to_public",
            "description": (
                "为用户准备的「提交到公共图库」操作。本工具不会真正提交，"
                "只是校验并把待确认信息返回给界面，由用户点击确认后才真正提交。"
                "因此用户表达提交意图时应调用本工具，然后告知用户「请在卡片上确认」。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {"type": "integer", "description": "要提交的图片 id"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "公开标签，不传则沿用该图的个人标签",
                    },
                },
                "required": ["image_id"],
            },
        },
    },
]

TOOL_NAMES = [schema["function"]["name"] for schema in TOOL_SCHEMAS]


def _ok(summary: str, data: Any = None, **extra: Any) -> dict:
    """成功结果（summary 给用户看，data 给模型看）"""
    return {"ok": True, "summary": summary, "data": data, **extra}


def _error(message: str) -> dict:
    """失败结果——统一转成可读文本回灌给模型，让它自己向用户解释，而不是抛 500"""
    return {"ok": False, "summary": message, "error": message, "data": None}


def _fmt_date(value: object) -> str | None:
    """日期格式化为 YYYY-MM-DD（模型不需要秒级精度）

    参数用 `object` + `isinstance` 而非 `datetime | None`：ORM 属性在类型上表现为
    `Column[datetime]`，直接标注 datetime 会与 SQLAlchemy 的模型注解冲突。
    """
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return None


def _find_own_image(db: Session, user: User, image_id: int) -> Image | None:
    """查「属于当前用户」的图片——越权在查询条件里天然阻断，不依赖工具自觉"""
    return db.query(Image).filter(Image.id == image_id, Image.user_id == user.id).first()


def _search_images(db: Session, user: User, args: SearchImagesArgs) -> dict:
    """按标签 / 名称检索个人图库"""
    tag = (args.tag or "").strip().lstrip("#")
    keyword = (args.keyword or "").strip()
    limit = args.limit if args.limit and args.limit > 0 else AGENT_TOOL_RESULT_LIMIT
    limit = min(limit, AGENT_TOOL_RESULT_LIMIT)

    query = db.query(Image).filter(Image.user_id == user.id)
    if tag:
        query = query.filter(Image.tags.any(Tag.name == tag))
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(Image.custom_name.ilike(pattern), Image.original_name.ilike(pattern))
        )

    total = query.count()
    rows = query.order_by(Image.created_at.desc()).limit(limit).all()
    items = [
        {
            "id": row.id,
            "display_name": row.display_name,
            "tags": tag_names(row),
            "created_at": _fmt_date(row.created_at),
            # 供前端步骤行展示缩略图（模型也会看到，但 URL 很短，可接受）
            "thumbnail_url": row.thumbnail_url,
        }
        for row in rows
    ]
    if not items:
        return _ok("没有找到符合条件的图片", [])
    summary = f"找到 {total} 张" + (f"，返回前 {len(items)} 张" if total > len(items) else "")
    return _ok(summary, items)


def _get_image_info(db: Session, user: User, args: GetImageInfoArgs) -> dict:
    """单张图片详情 + 公共图库状态"""
    image = _find_own_image(db, user, args.image_id)
    if image is None:
        return _error(f"图片 {args.image_id} 不存在，或者不属于当前用户")

    record = (
        db.query(PublicImage)
        .filter(PublicImage.image_id == image.id)
        .order_by(PublicImage.id.desc())
        .first()
    )
    public_status = str(record.status) if record else "none"
    data = {
        "id": image.id,
        "display_name": image.display_name,
        "tags": tag_names(image),
        "created_at": _fmt_date(image.created_at),
        "public_status": public_status,
        "public_id": record.id if record else None,
    }
    status_cn = {
        "none": "未提交公共图库",
        "pending": "已提交、审核中",
        "approved": "已在公共图库展示",
        "rejected": "曾被拒绝",
    }.get(public_status, public_status)
    return _ok(f"《{image.display_name}》{status_cn}", data)


def _prepare_public_submit(db: Session, user: User, args: SubmitToPublicArgs) -> dict:
    """校验「提交公共图库」的可行性并返回待确认参数——**不写库**"""
    image = _find_own_image(db, user, args.image_id)
    if image is None:
        return _error(f"图片 {args.image_id} 不存在，或者不属于当前用户")

    if args.tags:
        try:
            tags = normalize_tags(args.tags)
        except HTTPException as exc:
            return _error(str(exc.detail))
    else:
        # 与前端提交面板一致的体验：不指定就用该图的个人标签预填
        tags = tag_names(image)

    existing = (
        db.query(PublicImage)
        .filter(
            PublicImage.image_id == image.id,
            PublicImage.status.in_(["pending", "approved"]),
        )
        .first()
    )
    if existing:
        status_cn = "审核中" if existing.status == "pending" else "已通过审核"
        return _error(f"《{image.display_name}》已提交过公共图库（{status_cn}），无需重复提交")

    return _ok(
        f"已准备提交《{image.display_name}》，等待用户确认",
        {"image_id": image.id, "display_name": image.display_name, "tags": tags},
        requires_confirmation=True,
    )


def _load_arguments(raw_arguments: str) -> tuple[dict, dict | None]:
    """解析模型给的参数 JSON，返回 (参数字典, 错误结果)"""
    text = (raw_arguments or "").strip()
    if not text:
        return {}, None
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return {}, _error("工具参数不是合法 JSON，请按 schema 重新调用")
    if not isinstance(raw, dict):
        return {}, _error("工具参数必须是 JSON 对象")
    return raw, None


def execute_tool(name: str, raw_arguments: str, db: Session, user: User) -> dict:
    """执行工具：解析参数 → Pydantic 校验 → 调用实现

    任何失败都转成 `{"ok": False, "error": ...}` 交给模型组织语言，
    **不让工具异常中断整段对话**（工具出事不该等于聊天报废）。
    """
    raw, arg_error = _load_arguments(raw_arguments)
    if arg_error is not None:
        return arg_error

    try:
        if name == "search_images":
            return _search_images(db, user, SearchImagesArgs(**raw))
        if name == "get_image_info":
            return _get_image_info(db, user, GetImageInfoArgs(**raw))
        if name == "submit_to_public":
            return _prepare_public_submit(db, user, SubmitToPublicArgs(**raw))
        return _error(f"未知工具：{name}")
    except ValidationError as exc:
        first = exc.errors()[0].get("msg", "") if exc.errors() else ""
        return _error(f"工具参数校验失败：{first}")
    except HTTPException as exc:
        return _error(str(exc.detail))
    except Exception as exc:  # noqa: BLE001 - 兜底：工具失败不能中断对话
        logger.exception("工具 %s 执行失败", name)
        return _error(f"工具执行失败：{exc}")
