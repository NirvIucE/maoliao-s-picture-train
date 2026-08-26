"""auth 模块接口测试：注册 / 登录 / JWT 失效（见计划 3.1 节）

状态码依据实际路由：
- register 成功 201，重复用户名/邮箱 409，缺字段/非法邮箱 422
- login 成功 200，错密码/不存在用户 401，用 JSON 而非 form 422
- /me 无 token/篡改 token 401
"""


class TestRegister:
    def test_register_success(self, client):
        """正常注册 → 201 + uid + role=user"""
        r = client.post(
            "/api/auth/register",
            json={"username": "newuser", "email": "new@test.com", "password": "pass1234"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["username"] == "newuser"
        assert data["uid"]
        assert data["role"] == "user"

    def test_register_duplicate_username(self, client, registered_user):
        """重复用户名 → 400"""
        r = client.post(
            "/api/auth/register",
            json={
                "username": registered_user["username"],
                "email": "other@test.com",
                "password": "pass1234",
            },
        )
        assert r.status_code == 409

    def test_register_duplicate_email(self, client, registered_user):
        """重复邮箱 → 400"""
        r = client.post(
            "/api/auth/register",
            json={
                "username": "otheruser",
                "email": registered_user["email"],
                "password": "pass1234",
            },
        )
        assert r.status_code == 409

    def test_register_missing_field(self, client):
        """缺字段（无 email/password）→ 422"""
        r = client.post("/api/auth/register", json={"username": "x"})
        assert r.status_code == 422

    def test_register_invalid_email(self, client):
        """非法邮箱 → 422"""
        r = client.post(
            "/api/auth/register",
            json={"username": "x", "email": "not-an-email", "password": "pass1234"},
        )
        assert r.status_code == 422


class TestLogin:
    def test_login_success(self, client, registered_user):
        """正常登录 → 200 + access_token + bearer"""
        r = client.post(
            "/api/auth/login",
            data={
                "username": registered_user["username"],
                "password": registered_user["password"],
            },
        )
        assert r.status_code == 200
        assert r.json()["access_token"]
        assert r.json()["token_type"] == "bearer"

    def test_login_wrong_password(self, client, registered_user):
        """错密码 → 401"""
        r = client.post(
            "/api/auth/login",
            data={"username": registered_user["username"], "password": "wrongpass"},
        )
        assert r.status_code == 401

    def test_login_nonexistent_user(self, client):
        """用户不存在 → 401"""
        r = client.post(
            "/api/auth/login",
            data={"username": "ghost", "password": "whatever"},
        )
        assert r.status_code == 401

    def test_login_json_instead_of_form(self, client, registered_user):
        """用 JSON 而非 OAuth2 form 提交 → 422（缺 form 字段）"""
        r = client.post(
            "/api/auth/login",
            json={
                "username": registered_user["username"],
                "password": registered_user["password"],
            },
        )
        assert r.status_code == 422


class TestJWT:
    def test_me_without_token(self, client):
        """无 token → 401"""
        r = client.get("/api/users/me")
        assert r.status_code == 401

    def test_me_tampered_token(self, client):
        """篡改 token → 401"""
        r = client.get(
            "/api/users/me", headers={"Authorization": "Bearer abc.def.ghi"}
        )
        assert r.status_code == 401

    def test_me_valid_token(self, client, auth_headers):
        """有效 token → 200 + 当前用户 alice"""
        r = client.get("/api/users/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["username"] == "alice"
