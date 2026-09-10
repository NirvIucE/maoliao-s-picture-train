"""清理 uploads 目录中的孤儿文件（阶段 17）

背景：pytest / E2E 此前只隔离了数据库，没有隔离磁盘 —— 测试上传的图片会真实
落到 backend/src/uploads/<日期>/，而 DB 记录随事务回滚，于是文件成了孤儿：
用户在页面上看不到、也删不掉，只能白占磁盘。

本脚本用于清理这些历史孤儿文件。

保留集（四处并集，缺一不可）：
  1. images.file_path        原图
  2. images.thumbnail_path   缩略图
  3. users.avatar_url        头像
  4. ai_tasks.result_path    AI 编辑结果图（前端「取结果」仍需读取）
  ⚠️ 教训：2026-08-27 曾因只按 images 表判定，误删了真实用户头像
     （os.remove 不进回收站，无法恢复），故头像必须纳入保留集。

安全设计：
  - 默认 dry-run，只打印清单、不动磁盘；加 --apply 才真删
  - 删除前先把待删清单写入日志文件，便于事后追溯
  - 保留集为空时直接中止（防止 DB 查询异常导致全量误删）

用法（backend 目录下）：
    uv run python scripts/cleanup_orphan_uploads.py            # 预演，只看不删
    uv run python scripts/cleanup_orphan_uploads.py --apply    # 真正删除
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# 让脚本能找到 src 包（backend 目录加入 sys.path）
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from src.config import UPLOAD_ROOT  # noqa: E402
from src.database import SessionLocal  # noqa: E402
from src.models.ai_task import AITask  # noqa: E402
from src.models.image import Image  # noqa: E402
from src.models.user import User  # noqa: E402

# users.avatar_url 存的是 URL（/static/uploads/avatars/xxx.png），需还原成磁盘路径
AVATAR_URL_PREFIX = "/static/uploads/"


def _norm(path: str) -> str:
    """统一成绝对路径 + 平台大小写规范，用于集合比较"""
    return os.path.normcase(os.path.abspath(path))


def build_keep_set(db) -> set[str]:
    """汇总所有被数据库引用的文件（四处并集）"""
    keep: set[str] = set()

    for file_path, thumbnail_path in db.query(Image.file_path, Image.thumbnail_path).all():
        if file_path:
            keep.add(_norm(file_path))
        if thumbnail_path:
            keep.add(_norm(thumbnail_path))

    for (avatar_url,) in db.query(User.avatar_url).all():
        if avatar_url and avatar_url.startswith(AVATAR_URL_PREFIX):
            keep.add(_norm(os.path.join(UPLOAD_ROOT, avatar_url[len(AVATAR_URL_PREFIX):])))

    for (result_path,) in db.query(AITask.result_path).all():
        if result_path:
            keep.add(_norm(result_path))

    return keep


def scan_files(root: str) -> list[str]:
    """递归列出 root 下所有文件"""
    found = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            found.append(os.path.join(dirpath, filename))
    return found


def write_log(root: str, orphans: list[str], keep_count: int) -> str:
    """把待删清单落盘，便于事后追溯"""
    log_dir = BACKEND_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"cleanup_orphans_{datetime.now():%Y%m%d_%H%M%S}.log"

    lines = [
        f"时间: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"上传根目录: {root}",
        f"保留文件数: {keep_count}",
        f"待删孤儿数: {len(orphans)}",
        "-" * 60,
    ]
    lines += [os.path.relpath(p, root) for p in orphans]
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return str(log_path)


def prune_empty_dirs(root: str) -> int:
    """自底向上删除空目录（保留 root 本身）"""
    removed = 0
    for dirpath, _dirnames, _filenames in os.walk(root, topdown=False):
        if os.path.abspath(dirpath) == os.path.abspath(root):
            continue
        try:
            os.rmdir(dirpath)
            removed += 1
        except OSError:
            pass  # 非空则跳过
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="清理 uploads 目录中的孤儿文件")
    parser.add_argument("--apply", action="store_true", help="真正删除（默认只预演）")
    args = parser.parse_args()

    root = os.path.abspath(UPLOAD_ROOT)
    print(f"[cleanup] 上传根目录: {root}")
    if not os.path.isdir(root):
        print("[cleanup] 目录不存在，无需清理")
        return 0

    db = SessionLocal()
    try:
        keep = build_keep_set(db)
    finally:
        db.close()

    if not keep:
        print("[cleanup] 保留集为空，疑似数据库连接/查询异常，已中止以免误删")
        return 1

    all_files = scan_files(root)
    orphans = sorted(f for f in all_files if _norm(f) not in keep)
    print(
        f"[cleanup] 磁盘文件 {len(all_files)} 个 / 数据库引用 {len(keep)} 个 / "
        f"孤儿 {len(orphans)} 个"
    )

    if not orphans:
        print("[cleanup] 没有孤儿文件，无需清理")
        return 0

    log_path = write_log(root, orphans, len(keep))

    if not args.apply:
        print("[cleanup] === 预演模式，未删除任何文件 ===")
        print("[cleanup] 待删清单已写入: " + log_path)
        print("[cleanup] 前 10 个示例:")
        for path in orphans[:10]:
            print("   " + os.path.relpath(path, root))
        print("[cleanup] 确认无误后加 --apply 真正删除")
        return 0

    removed = 0
    for path in orphans:
        try:
            os.remove(path)
            removed += 1
        except OSError as exc:
            print(f"[cleanup] 删除失败 {path}: {exc}")

    dirs = prune_empty_dirs(root)
    print(f"[cleanup] 已删除孤儿文件 {removed} 个、空目录 {dirs} 个")
    print("[cleanup] 清单留存: " + log_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
