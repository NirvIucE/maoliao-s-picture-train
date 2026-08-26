"""users 模块接口测试：改名 / 改密码 / 头像 / uid 不可改（见计划 3.1 节）

状态码依据实际路由 + auth_service：
- PATCH /me：成功 200，空用户名 400，重复 409
- POST /me/password：成功 200，旧密码错 400，新密码<6位 400
- POST /me/avatar：成功 200，非法扩展名 400，>2MB 400
- uid 不可改：PATCH 携带 uid 字段，uid 不变（无 mass-assignment 漏洞）
"""
from io import BytesIO

from PIL import Image as PILImage


class TestUpdateUsername:
    def test_update_username_success(self, client, auth_headers):
        """改名成功 → 200 + 新用户名"""
        r = client.patch("/api/users/me", headers=auth_headers, json={"username": "newname"})
        assert r.status_code == 200
        assert r.json()["username"] == "newname"

    def test_update_username_duplicate(self, client, auth_headers):
        """改成已存在用户名 → 409"""
        client.post(
            "/api/auth/register",
            json={"username": "bob", "email": "bob@test.com", "password": "pass1234"},
        )
        r = client.patch("/api/users/me", headers=auth_headers, json={"username": "bob"})
        assert r.status_code == 409

    def test_update_username_empty(self, client, auth_headers):
        """空用户名（空白）→ 400"""
        r = client.patch("/api/users/me", headers=auth_headers, json={"username": "   "})
        assert r.status_code == 400

    def test_uid_immutable(self, client, auth_headers, registered_user):
        """PATCH 携带 uid 字段 → uid 不变（无 mass-assignment 漏洞）"""
        original_uid = registered_user["uid"]
        r = client.patch(
            "/api/users/me",
            headers=auth_headers,
            json={"username": "newname2", "uid": "hacked-uid"},
        )
        assert r.status_code == 200
        r = client.get("/api/users/me", headers=auth_headers)
        assert r.json()["uid"] == original_uid
        assert r.json()["username"] == "newname2"


class TestChangePassword:
    def test_change_password_success(self, client, registered_user, auth_headers):
        """改密码成功 → 200，新密码可登录、旧密码不可"""
        r = client.post(
            "/api/users/me/password",
            headers=auth_headers,
            json={"old_password": registered_user["password"], "new_password": "newpass123"},
        )
        assert r.status_code == 200
        # 新密码可登录
        r = client.post(
            "/api/auth/login",
            data={"username": registered_user["username"], "password": "newpass123"},
        )
        assert r.status_code == 200
        # 旧密码不可登录
        r = client.post(
            "/api/auth/login",
            data={"username": registered_user["username"], "password": registered_user["password"]},
        )
        assert r.status_code == 401

    def test_change_password_wrong_old(self, client, auth_headers):
        """旧密码错 → 400"""
        r = client.post(
            "/api/users/me/password",
            headers=auth_headers,
            json={"old_password": "wrongold", "new_password": "newpass123"},
        )
        assert r.status_code == 400

    def test_change_password_short_new(self, client, auth_headers, registered_user):
        """新密码 <6 位 → 400"""
        r = client.post(
            "/api/users/me/password",
            headers=auth_headers,
            json={"old_password": registered_user["password"], "new_password": "123"},
        )
        assert r.status_code == 400


class TestAvatar:
    def test_upload_avatar_success(self, client, auth_headers):
        """上传 PNG 头像 → 200 + avatar_url"""
        buf = BytesIO()
        PILImage.new("RGB", (50, 50), (0, 255, 0)).save(buf, format="PNG")
        buf.seek(0)
        r = client.post(
            "/api/users/me/avatar",
            headers=auth_headers,
            files={"file": ("avatar.png", buf, "image/png")},
        )
        assert r.status_code == 200
        assert r.json()["avatar_url"]

    def test_upload_avatar_bad_ext(self, client, auth_headers):
        """非法扩展名（.txt）→ 400"""
        buf = BytesIO(b"not an image")
        r = client.post(
            "/api/users/me/avatar",
            headers=auth_headers,
            files={"file": ("avatar.txt", buf, "text/plain")},
        )
        assert r.status_code == 400

    def test_upload_avatar_too_large(self, client, auth_headers):
        """超过 2MB → 400"""
        buf = BytesIO(b"x" * (3 * 1024 * 1024))  # 3MB
        r = client.post(
            "/api/users/me/avatar",
            headers=auth_headers,
            files={"file": ("big.png", buf, "image/png")},
        )
        assert r.status_code == 400
