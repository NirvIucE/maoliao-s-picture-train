"""
标签业务通用逻辑（阶段 19）

个人图库标签（`Image.tags`）与公共图库标签（`PublicImage.tags`）用的是同一套
「规范化 + 挂载」逻辑，只是挂载目标不同。抽到此处的原因：`public_service` 已经
从 `image_service` 导入 `get_image_detail`，若把这段共享逻辑放在任一方的模块里，
另一方导入就会形成循环依赖。

注意：本模块只关心「标签名 → Tag 对象 → 挂到 owner 上」，不关心业务权限
（谁有资格改），权限判断留在各自的 service 里。
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.models.tag import Tag

# 对齐 tags.name 的 String(50)：超长标签若不拦，会直接打到 DB 层报错（500）
MAX_TAG_LENGTH = 50
# 单次请求允许提交的标签数量上限
MAX_TAGS = 20


def normalize_tags(raw_tags: list[str] | None) -> list[str]:
    """标签规范化：去 # 前缀、去首尾空白、去空、去重（保序）；超限抛 400

    为什么在这里校验：`tags.name` 只有 50 字符宽，个人图库开放标签后输入面
    变大（提交弹窗 + 详情页两处），必须在入口拦住而不是让 DB 抛 IntegrityError。
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in raw_tags or []:
        name = raw.strip().lstrip("#").strip()
        if not name or name in seen:
            continue
        if len(name) > MAX_TAG_LENGTH:
            raise HTTPException(
                status_code=400, detail=f"单个标签不能超过 {MAX_TAG_LENGTH} 个字符"
            )
        seen.add(name)
        result.append(name)
    if len(result) > MAX_TAGS:
        raise HTTPException(status_code=400, detail=f"一次最多提交 {MAX_TAGS} 个标签")
    return result


def set_tags(db: Session, owner: object, raw_tags: list[str] | None) -> list[str]:
    """把标签挂到 owner（Image 或 PublicImage）上

    已存在的 Tag 复用，不存在的新建；已挂过的跳过（幂等）。返回规范化后的标签名列表。
    """
    names = normalize_tags(raw_tags)
    if not names:
        return []
    existing = {t.name: t for t in db.query(Tag).filter(Tag.name.in_(names)).all()}
    for name in names:
        tag = existing.get(name)
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
        if tag not in owner.tags:  # type: ignore[attr-defined]
            owner.tags.append(tag)  # type: ignore[attr-defined]
    return names


def tag_names(owner: object) -> list[str]:
    """读取 owner 当前的全部标签名"""
    return [t.name for t in owner.tags]  # type: ignore[attr-defined]
