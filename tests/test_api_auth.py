"""认证接口测试：注册 / 登录 / 登出 / 鉴权边界。"""
from __future__ import annotations

import pytest

TEACHER_CREDS = {"username": "jiangxl", "password": "123456"}
ADMIN_CREDS = {"username": "admin", "password": "admin123"}


def _data(resp):
    body = resp.get_json()
    assert body["ok"] is True, body
    return body["data"]


# --------------------------------------------------------------------------- #
# 鉴权边界
# --------------------------------------------------------------------------- #
PROTECTED = [
    ("get", "/api/state"),
    ("get", "/api/stats"),
    ("get", "/api/collections/projects"),
    ("get", "/api/profile"),
    ("get", "/api/search?q=雷达"),
    ("get", "/api/export"),
    ("get", "/api/tools/specs"),
    ("get", "/api/admin/overview"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_requires_login(anon_client, method, path):
    resp = getattr(anon_client, method)(path)
    assert resp.status_code == 401
    assert resp.get_json()["code"] == "unauthenticated"


def test_me_anonymous(anon_client):
    resp = anon_client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_after_login(client):
    data = _data(client.get("/api/auth/me"))
    assert data["user"]["username"] == "jiangxl"
    assert data["user"]["role"] == "teacher"
    assert data["user"]["roleLabel"] == "教师"


def test_logout_revokes_access(client):
    assert client.get("/api/state").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/state").status_code == 401


# --------------------------------------------------------------------------- #
# 登录
# --------------------------------------------------------------------------- #
def test_login_ok(anon_client):
    data = _data(anon_client.post("/api/auth/login", json=TEACHER_CREDS))
    assert data["user"]["name"] == "江老师"
    assert data["user"]["role"] == "teacher"


def test_login_admin(anon_client):
    data = _data(anon_client.post("/api/auth/login", json=ADMIN_CREDS))
    assert data["user"]["role"] == "admin"
    assert data["user"]["roleLabel"] == "管理员"


def test_login_username_is_case_insensitive(anon_client):
    resp = anon_client.post("/api/auth/login", json={"username": "JiangXL", "password": "123456"})
    assert resp.status_code == 200


@pytest.mark.parametrize("creds", [
    {"username": "jiangxl", "password": "wrong"},
    {"username": "nobody", "password": "123456"},
    {"username": "", "password": ""},
])
def test_login_failures(anon_client, creds):
    resp = anon_client.post("/api/auth/login", json=creds)
    assert resp.status_code == 401
    assert "不正确" in resp.get_json()["error"]


def test_password_never_leaks(anon_client):
    data = _data(anon_client.post("/api/auth/login", json=TEACHER_CREDS))
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


# --------------------------------------------------------------------------- #
# 注册
# --------------------------------------------------------------------------- #
def _register(client, **over) -> dict:
    payload = {"username": "newteacher", "password": "abc123", "name": "新教师",
               "title": "讲师", "dept": "计算机科学与技术学院", "withDemo": False}
    payload.update(over)
    resp = client.post("/api/auth/register", json=payload)
    return resp


def test_register_creates_teacher_and_logs_in(anon_client, clean_users):
    resp = _register(anon_client)
    assert resp.status_code == 201
    user = resp.get_json()["data"]["user"]
    assert user["role"] == "teacher"
    assert user["name"] == "新教师"

    # 已处于登录态，且数据空间为空（withDemo=False）
    state = _data(anon_client.get("/api/state"))
    assert state["profile"]["name"] == "新教师"
    assert state["projects"] == []
    assert state["tools"], "工具清单应始终存在"
    assert anon_client.get("/api/admin/overview").status_code == 403


def test_register_with_demo_data(anon_client, clean_users):
    _register(anon_client, username="demoteacher", name="演示教师", withDemo=True)
    state = _data(anon_client.get("/api/state"))
    assert len(state["projects"]) > 0
    assert state["profile"]["name"] == "演示教师"


@pytest.mark.parametrize("over,keyword", [
    ({"username": "ab"}, "用户名"),
    ({"username": "1abc"}, "用户名"),
    ({"username": "has space"}, "用户名"),
    ({"password": "123"}, "密码至少"),
    ({"name": "   "}, "姓名"),
])
def test_register_validation(anon_client, clean_users, over, keyword):
    resp = _register(anon_client, **over)
    assert resp.status_code == 400
    assert keyword in resp.get_json()["error"]


def test_register_duplicate_username(anon_client, clean_users):
    assert _register(anon_client, username="jiangxl").status_code == 409
    resp = _register(anon_client, username="dupuser")
    assert resp.status_code == 201
    anon_client.post("/api/auth/logout")
    assert _register(anon_client, username="dupuser").status_code == 409


def test_registered_teacher_data_is_isolated(anon_client, clean_users):
    _register(anon_client, username="isolated1", name="甲教师", withDemo=False)
    anon_client.post("/api/auth/logout")
    _register(anon_client, username="isolated2", name="乙教师", withDemo=True)

    # 乙有演示数据
    assert len(_data(anon_client.get("/api/state"))["projects"]) > 0
    anon_client.post("/api/auth/logout")
    anon_client.post("/api/auth/login", json={"username": "isolated1", "password": "abc123"})
    # 甲的库仍为空 —— 两位教师互不影响
    assert _data(anon_client.get("/api/state"))["projects"] == []


def test_teacher_cannot_reach_admin_api(client):
    assert client.get("/api/admin/overview").status_code == 403
    assert client.get("/api/admin/teachers").status_code == 403
