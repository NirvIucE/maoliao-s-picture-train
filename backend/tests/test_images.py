"""images 模块接口测试：上传 / 列表 / 详情 / 下载 / 删除 / 改名 / 编辑 / 替换 / AI编辑（见计划 3.1 节）

状态码依据实际路由 + image_service：
- upload 成功 200，无 token 401，非法格式 400
- upload-url 成功 200，不支持类型 400（respx mock httpx）
- list 成功 200，支持分页 + 搜索
- detail 成功 200，不存在/非本人 404
- download 成功 200，不存在 404
- delete 成功 200，不存在/非本人 404
- rename 成功 200，空串恢复原名，不存在 404
- edit（rotate/crop）overwrite 200 同 id，new 200 新 id，不存在 404
- replace 成功 200，非法格式 400
- ai-edit 提交 200（返回 task_id），不存在/非本人 404（任务执行见 test_tasks.py）
"""

from io import BytesIO

import httpx
import pytest
import respx
from fastapi import HTTPException
from PIL import Image as PILImage

from src.services import image_service


# ── 辅助 fixture：第二个用户 bob 的 auth headers（用于所有权隔离测试）──
@pytest.fixture
def other_user_headers(client):
    client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "bob@test.com", "password": "pass1234"},
    )
    r = client.post("/api/auth/login", data={"username": "bob", "password": "pass1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_png(width=10, height=10, color=(255, 0, 0)):
    """生成一张 PNG BytesIO"""
    buf = BytesIO()
    PILImage.new("RGB", (width, height), color).save(buf, format="PNG")
    buf.seek(0)
    return buf


class TestUpload:
    def test_upload_success(self, client, auth_headers):
        """上传 PNG → 200 + id + image_url + thumbnail_url"""
        r = client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": ("test.png", _make_png(), "image/png")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"]
        assert data["original_name"] == "test.png"
        assert data["image_url"]
        assert data["thumbnail_url"]
        assert data["width"] == 10
        assert data["height"] == 10

    def test_upload_with_custom_name(self, client, auth_headers):
        """带 custom_name 上传 → 200，display_name == custom_name"""
        r = client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": ("test.png", _make_png(), "image/png")},
            data={"custom_name": "我的图"},
        )
        assert r.status_code == 200
        assert r.json()["display_name"] == "我的图"

    def test_upload_unauthorized(self, client):
        """无 token → 401"""
        r = client.post(
            "/api/images/upload",
            files={"file": ("test.png", _make_png(), "image/png")},
        )
        assert r.status_code == 401

    def test_upload_invalid_format(self, client, auth_headers):
        """非法格式（.txt）→ 400"""
        r = client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": ("bad.txt", BytesIO(b"not image"), "text/plain")},
        )
        assert r.status_code == 400


class TestUploadFromUrl:
    @respx.mock
    def test_upload_url_success(self, client, auth_headers):
        """URL 上传（mock httpx 返回 PNG）→ 200"""
        png_bytes = _make_png().getvalue()
        respx.get("https://example.com/img.png").mock(
            return_value=httpx.Response(
                200,
                content=png_bytes,
                headers={"content-type": "image/png"},
            )
        )
        r = client.post(
            "/api/images/upload-url",
            headers=auth_headers,
            json={"url": "https://example.com/img.png"},
        )
        assert r.status_code == 200
        assert r.json()["original_name"] == "img.png"

    @respx.mock
    def test_upload_url_unsupported_type(self, client, auth_headers):
        """URL 内容非图片（text/html）→ 400"""
        respx.get("https://example.com/doc.html").mock(
            return_value=httpx.Response(
                200,
                content=b"<html></html>",
                headers={"content-type": "text/html"},
            )
        )
        r = client.post(
            "/api/images/upload-url",
            headers=auth_headers,
            json={"url": "https://example.com/doc.html"},
        )
        assert r.status_code == 400


class TestListImages:
    def test_list_empty(self, client, auth_headers):
        """无图片 → total=0, items=[]"""
        r = client.get("/api/images", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["items"] == []

    def test_list_with_images(self, client, auth_headers, test_image):
        """有图片 → total>=1"""
        r = client.get("/api/images", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_pagination(self, client, auth_headers):
        """上传 3 张，limit=2 → total=3, items=2"""
        for _ in range(3):
            client.post(
                "/api/images/upload",
                headers=auth_headers,
                files={"file": ("p.png", _make_png(), "image/png")},
            )
        r = client.get("/api/images", headers=auth_headers, params={"limit": 2})
        assert r.status_code == 200
        assert r.json()["total"] == 3
        assert len(r.json()["items"]) == 2

    def test_list_search(self, client, auth_headers, test_image):
        """搜索 custom_name 关键词 → 过滤结果"""
        r = client.get("/api/images", headers=auth_headers, params={"search": "fixture"})
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["custom_name"] == "fixture 图"


class TestGetImageDetail:
    def test_get_detail_success(self, client, auth_headers, test_image):
        """获取详情 → 200 + 正确 id"""
        r = client.get(f"/api/images/{test_image}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["id"] == test_image

    def test_get_detail_not_found(self, client, auth_headers):
        """不存在 → 404"""
        r = client.get("/api/images/9999", headers=auth_headers)
        assert r.status_code == 404

    def test_get_detail_other_user(self, client, auth_headers, other_user_headers, test_image):
        """他人图片 → 404（所有权隔离）"""
        r = client.get(f"/api/images/{test_image}", headers=other_user_headers)
        assert r.status_code == 404


class TestImageTags:
    """阶段 19：个人图库标签 API（增 / 删 / 详情返回 / 权限 / 规范化 / 校验）"""

    def test_add_tags_owner(self, client, auth_headers, test_image):
        """owner 加标签 → 200 + 返回当前全部标签"""
        r = client.post(
            f"/api/images/{test_image}/tags",
            headers=auth_headers,
            json={"tags": ["猫", "#风景"]},
        )
        assert r.status_code == 200
        assert r.json()["tags"] == ["猫", "风景"]

    def test_add_tags_normalize_and_dedupe(self, client, auth_headers, test_image):
        """规范化：去 # 前缀 / 去首尾空白 / 去空 / 去重（保序）"""
        r = client.post(
            f"/api/images/{test_image}/tags",
            headers=auth_headers,
            json={"tags": [" 猫 ", "#猫", "", "  ", "风景"]},
        )
        assert r.status_code == 200
        assert r.json()["tags"] == ["猫", "风景"]

    def test_add_tags_idempotent(self, client, auth_headers, test_image):
        """重复提交同一标签 → 幂等，不产生重复项"""
        client.post(f"/api/images/{test_image}/tags", headers=auth_headers, json={"tags": ["猫"]})
        r = client.post(
            f"/api/images/{test_image}/tags", headers=auth_headers, json={"tags": ["猫"]}
        )
        assert r.status_code == 200
        assert r.json()["tags"] == ["猫"]

    def test_detail_returns_tags(self, client, auth_headers, test_image):
        """详情接口返回个人标签（阶段 19 新增字段）"""
        client.post(f"/api/images/{test_image}/tags", headers=auth_headers, json={"tags": ["猫"]})
        r = client.get(f"/api/images/{test_image}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["tags"] == ["猫"]

    def test_detail_without_tags(self, client, auth_headers, test_image):
        """无标签 → tags 为空列表（而非缺字段）"""
        r = client.get(f"/api/images/{test_image}", headers=auth_headers)
        assert r.json()["tags"] == []

    def test_list_does_not_include_tags(self, client, auth_headers, test_image):
        """列表接口保持 ImageResponse（无 tags）：列表走 Redis 缓存，不加字段"""
        client.post(f"/api/images/{test_image}/tags", headers=auth_headers, json={"tags": ["猫"]})
        r = client.get("/api/images", headers=auth_headers)
        assert r.status_code == 200
        assert "tags" not in r.json()["items"][0]

    def test_remove_tag_owner(self, client, auth_headers, test_image):
        """owner 删标签 → 200；重复删 → 404"""
        client.post(f"/api/images/{test_image}/tags", headers=auth_headers, json={"tags": ["猫"]})
        r = client.delete(f"/api/images/{test_image}/tags/猫", headers=auth_headers)
        assert r.status_code == 200
        r2 = client.delete(f"/api/images/{test_image}/tags/猫", headers=auth_headers)
        assert r2.status_code == 404

    def test_remove_nonexistent_tag(self, client, auth_headers, test_image):
        """删不存在的标签 → 404"""
        r = client.delete(f"/api/images/{test_image}/tags/不存在", headers=auth_headers)
        assert r.status_code == 404

    def test_add_tags_other_user_404(self, client, other_user_headers, test_image):
        """bob 给 alice 的图打标签 → 404（个人图库严格按所有权隔离）"""
        r = client.post(
            f"/api/images/{test_image}/tags",
            headers=other_user_headers,
            json={"tags": ["x"]},
        )
        assert r.status_code == 404

    def test_remove_tag_other_user_404(self, client, other_user_headers, test_image):
        """bob 删 alice 的标签 → 404"""
        r = client.delete(f"/api/images/{test_image}/tags/猫", headers=other_user_headers)
        assert r.status_code == 404

    def test_tag_too_long_400(self, client, auth_headers, test_image):
        """单标签 > 50 字 → 400（在入口拦截，不让 DB 抛 IntegrityError 变 500）"""
        r = client.post(
            f"/api/images/{test_image}/tags",
            headers=auth_headers,
            json={"tags": ["猫" * 51]},
        )
        assert r.status_code == 400

    def test_tag_length_boundary_ok(self, client, auth_headers, test_image):
        """边界：恰好 50 字合法"""
        r = client.post(
            f"/api/images/{test_image}/tags",
            headers=auth_headers,
            json={"tags": ["猫" * 50]},
        )
        assert r.status_code == 200

    def test_too_many_tags_400(self, client, auth_headers, test_image):
        """一次提交 > 20 个标签 → 400"""
        r = client.post(
            f"/api/images/{test_image}/tags",
            headers=auth_headers,
            json={"tags": [f"标签{i}" for i in range(21)]},
        )
        assert r.status_code == 400


class TestDownloadImage:
    def test_download_success(self, client, auth_headers, test_image):
        """下载原图 → 200 + octet-stream"""
        r = client.get(f"/api/images/{test_image}/download", headers=auth_headers)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/octet-stream"


class TestDeleteImage:
    def test_delete_success(self, client, auth_headers, test_image):
        """删除成功 → 200"""
        r = client.delete(f"/api/images/{test_image}", headers=auth_headers)
        assert r.status_code == 200
        assert "删除成功" in r.json()["message"]
        # 删除后查不到
        r = client.get(f"/api/images/{test_image}", headers=auth_headers)
        assert r.status_code == 404

    def test_delete_not_found(self, client, auth_headers):
        """删除不存在 → 404"""
        r = client.delete("/api/images/9999", headers=auth_headers)
        assert r.status_code == 404

    def test_delete_other_user(self, client, auth_headers, other_user_headers, test_image):
        """删除他人图片 → 404"""
        r = client.delete(f"/api/images/{test_image}", headers=other_user_headers)
        assert r.status_code == 404


class TestRenameImage:
    def test_rename_success(self, client, auth_headers, test_image):
        """改名成功 → 200 + custom_name 更新"""
        r = client.patch(
            f"/api/images/{test_image}/name",
            headers=auth_headers,
            json={"custom_name": "新名字"},
        )
        assert r.status_code == 200
        assert r.json()["custom_name"] == "新名字"

    def test_rename_empty_restore(self, client, auth_headers, test_image):
        """空串 → 恢复原文件名，custom_name=null"""
        r = client.patch(
            f"/api/images/{test_image}/name",
            headers=auth_headers,
            json={"custom_name": ""},
        )
        assert r.status_code == 200
        assert r.json()["custom_name"] is None
        assert r.json()["display_name"] == r.json()["original_name"]


class TestEditImage:
    def test_edit_rotate_overwrite(self, client, auth_headers, test_image):
        """旋转覆盖 → 200 + 同 id"""
        r = client.post(
            f"/api/images/{test_image}/edit",
            headers=auth_headers,
            json={
                "operations": [{"type": "rotate", "angle": 90}],
                "save_mode": "overwrite",
            },
        )
        assert r.status_code == 200
        assert r.json()["id"] == test_image

    def test_edit_crop_save_as_new(self, client, auth_headers, test_image):
        """裁剪另存 → 200 + 新 id + 自定义名"""
        r = client.post(
            f"/api/images/{test_image}/edit",
            headers=auth_headers,
            json={
                "operations": [{"type": "crop", "left": 0, "top": 0, "right": 5, "bottom": 5}],
                "save_mode": "new",
                "custom_name": "裁剪副本",
            },
        )
        assert r.status_code == 200
        assert r.json()["id"] != test_image
        assert r.json()["display_name"] == "裁剪副本"


class TestReplaceImage:
    def test_replace_success(self, client, auth_headers, test_image):
        """替换图片 → 200 + 新尺寸"""
        r = client.post(
            f"/api/images/{test_image}/replace",
            headers=auth_headers,
            files={"file": ("replaced.png", _make_png(20, 20, (0, 0, 255)), "image/png")},
        )
        assert r.status_code == 200
        assert r.json()["width"] == 20
        assert r.json()["height"] == 20

    def test_replace_invalid_format(self, client, auth_headers, test_image):
        """替换非法格式 → 400"""
        r = client.post(
            f"/api/images/{test_image}/replace",
            headers=auth_headers,
            files={"file": ("bad.txt", BytesIO(b"not image"), "text/plain")},
        )
        assert r.status_code == 400


class TestAIEdit:
    """阶段 16：AI 编辑执行已下沉到 task_service 后台协程，
    这里只测提交入口的归属校验 + call_image_edit 本身（prompt 约束 / 多形态解析）"""

    def test_ai_edit_not_found(self, client, auth_headers):
        """AI 编辑不存在的图片 → 404（提交时校验归属）"""
        r = client.post(
            "/api/images/9999/ai-edit",
            headers=auth_headers,
            json={"prompt": "换成星空", "image_base64": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert r.status_code == 404

    @respx.mock
    async def test_prompt_has_protection_constraints(self, monkeypatch):
        """阶段 15：编辑请求体 prompt 含目标区域/区域外保护/边缘融合/冲突优先 4 类约束"""
        monkeypatch.setattr(image_service, "PROVIDER_CONFIG", {
            "siliconflow": {"api_key": "fake-key", "base_url": "https://api.siliconflow.cn/v1"}
        })
        result_png = _make_png(color=(0, 255, 0)).getvalue()
        route = respx.post("https://api.siliconflow.cn/v1/images/generations").mock(
            return_value=httpx.Response(
                200, json={"images": [{"url": "https://cdn.example.com/result.png"}]}
            )
        )
        respx.get("https://cdn.example.com/result.png").mock(
            return_value=httpx.Response(200, content=result_png)
        )
        result = await image_service.call_image_edit(
            "换成星空", "data:image/png;base64,iVBORw0KGgo="
        )
        assert result.startswith("data:image/png;base64,")
        content = route.calls.last.request.content.decode("utf-8")
        assert "唯一可修改" in content  # 目标区域限定
        assert "完全不变" in content  # 区域外保护
        assert "自然融合" in content  # 边缘融合
        assert "优先保证" in content  # 冲突优先

    @respx.mock
    async def test_b64_json_response_shape(self, monkeypatch):
        """阶段 15：编辑响应为 b64_json 形状 → 返回 data URL（兼容解析器）"""
        monkeypatch.setattr(image_service, "PROVIDER_CONFIG", {
            "siliconflow": {"api_key": "fake-key", "base_url": "https://api.siliconflow.cn/v1"}
        })
        respx.post("https://api.siliconflow.cn/v1/images/generations").mock(
            return_value=httpx.Response(200, json={"images": [{"b64_json": "aGVsbG8="}]})
        )
        result = await image_service.call_image_edit(
            "换成星空", "data:image/png;base64,iVBORw0KGgo="
        )
        assert result == "data:image/png;base64,aGVsbG8="

    @respx.mock
    async def test_no_image_in_response_502(self, monkeypatch):
        """阶段 15：编辑响应未含图片 → 502（而非 IndexError）"""
        monkeypatch.setattr(image_service, "PROVIDER_CONFIG", {
            "siliconflow": {"api_key": "fake-key", "base_url": "https://api.siliconflow.cn/v1"}
        })
        respx.post("https://api.siliconflow.cn/v1/images/generations").mock(
            return_value=httpx.Response(200, json={"error": "no image"})
        )
        with pytest.raises(HTTPException) as exc:
            await image_service.call_image_edit("换成星空", "data:image/png;base64,iVBORw0KGgo=")
        assert exc.value.status_code == 502


class TestExtractResultImage:
    """阶段 15：多形态图片响应解析器（纯函数）"""

    def test_images_url(self):
        assert image_service._extract_result_image({"images": [{"url": "https://x/y.png"}]}) == "https://x/y.png"

    def test_data_b64_json(self):
        assert image_service._extract_result_image({"data": [{"b64_json": "abc"}]}) == "abc"

    def test_data_url_shape(self):
        expected = "data:image/png;base64,abc"
        assert image_service._extract_result_image({"data_url": expected}) == expected

    def test_invalid_returns_none(self):
        assert image_service._extract_result_image({"error": "x"}) is None
        assert image_service._extract_result_image(None) is None
        assert image_service._extract_result_image({"images": [{"url": ""}]}) is None
