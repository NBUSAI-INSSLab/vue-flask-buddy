"""管理端接口测试：总览 / 教师列表 / 四类统计 / 账号管理。"""
from __future__ import annotations

import pytest

from backend import config

ADMIN_CREDS = {"username": "admin", "password": "admin123"}
SEED_TEACHER_NAMES = {"江老师", "张伟", "李敏", "王强", "陈静"}


def _data(resp):
    body = resp.get_json()
    assert body["ok"] is True, body
    return body["data"]


def _teacher_id(admin_client, name: str) -> str:
    for t in _data(admin_client.get("/api/admin/teachers")):
        if t["name"] == name:
            return t["id"]
    raise AssertionError(f"未找到教师 {name}")


# --------------------------------------------------------------------------- #
# 总览与列表
# --------------------------------------------------------------------------- #
def test_overview_shape(admin_client):
    data = _data(admin_client.get("/api/admin/overview"))
    totals, teachers = data["totals"], data["teachers"]
    assert totals["teachers"] == len(teachers) == 5
    for key in ("projects", "papers", "students", "teachings", "hours",
                "achievements", "score", "exchanges"):
        assert key in totals
    assert totals["projects"] == sum(t["summary"]["counts"]["projects"] for t in teachers)
    assert totals["students"] == sum(t["summary"]["counts"]["students"] for t in teachers)
    # 审核概况随总览一并下发，供导航徽标使用
    assert set(data["audit"]) >= {"total", "pending", "approved", "rejected", "pendingScore"}


def test_overview_totals_match_seed(admin_client):
    totals = _data(admin_client.get("/api/admin/overview"))["totals"]
    # 江老师(4) + 张伟(3) + 李敏(2) + 王强(1) + 陈静(3)
    assert totals["projects"] == 13
    assert totals["students"] == 14
    assert totals["papers"] == 20


def test_teacher_list_carries_summary(admin_client):
    teachers = _data(admin_client.get("/api/admin/teachers"))
    names = {t["name"] for t in teachers}
    assert names == SEED_TEACHER_NAMES
    for t in teachers:
        assert t["role"] == config.ROLE_TEACHER
        assert t["summary"]["counts"]["projects"] >= 0
        assert "password_hash" not in t


def test_teacher_list_sorted_stably(admin_client):
    first = [t["id"] for t in _data(admin_client.get("/api/admin/teachers"))]
    second = [t["id"] for t in _data(admin_client.get("/api/admin/teachers"))]
    assert first == second


# --------------------------------------------------------------------------- #
# 教师详情统计
# --------------------------------------------------------------------------- #
def test_teacher_detail_sections(admin_client):
    tid = _teacher_id(admin_client, "江老师")
    data = _data(admin_client.get(f"/api/admin/teachers/{tid}"))
    assert data["user"]["name"] == "江老师"
    assert data["profile"]["name"] == "江老师"

    detail = data["detail"]
    assert set(detail) == {"research", "exchanges", "teaching", "students", "audit"}
    assert detail["audit"]["total"] == 8

    research = detail["research"]
    assert research["projects"]["total"] == 4
    assert research["projects"]["leading"] >= 1
    assert research["achievements"]["total"] == 8
    assert research["achievements"]["published"] >= 1
    assert research["achievements"]["score"] > 0
    assert research["literature"]["total"] == 6

    teaching = detail["teaching"]
    assert teaching["tasks"] == 4
    assert teaching["hours"] > 0
    assert teaching["students"] > 0
    assert 0 <= teaching["outlineProgress"] <= 100
    assert teaching["evalAvg"] is not None

    students = detail["students"]
    assert students["total"] == 4
    assert students["master"] + students["phd"] == students["total"]
    assert 0 <= students["milestones"]["rate"] <= 100

    exchanges = detail["exchanges"]
    assert exchanges["total"] == 5
    assert sum(exchanges["byKind"].values()) == 5


def test_teacher_detail_differs_between_teachers(admin_client):
    rows = _data(admin_client.get("/api/admin/teachers"))
    counts = {t["name"]: t["summary"]["counts"]["projects"] for t in rows}
    assert counts["王强"] < counts["江老师"]
    assert len(set(counts.values())) > 1, "各教师数据规模应有差异"


def test_teacher_detail_404_for_unknown(admin_client):
    assert admin_client.get("/api/admin/teachers/u_nobody").status_code == 404


def test_teacher_detail_404_for_admin_account(admin_client):
    admin_id = _data(admin_client.get("/api/auth/me"))["user"]["id"]
    assert admin_client.get(f"/api/admin/teachers/{admin_id}").status_code == 404


# --------------------------------------------------------------------------- #
# 账号管理
# --------------------------------------------------------------------------- #
def test_create_teacher_can_login(admin_client, anon_client, clean_users):
    resp = admin_client.post("/api/admin/teachers", json={
        "username": "newbie", "password": "pass123", "name": "新入职教师",
        "title": "讲师", "dept": "人工智能学院",
    })
    assert resp.status_code == 201
    assert resp.get_json()["data"]["user"]["role"] == "teacher"

    # 新账号可登录，且初始为空白工作台
    anon_client.post("/api/auth/login", json={"username": "newbie", "password": "pass123"})
    state = _data(anon_client.get("/api/state"))
    assert state["profile"]["name"] == "新入职教师"
    assert state["projects"] == []


def test_create_admin_requires_password(admin_client, clean_users):
    resp = admin_client.post("/api/admin/teachers", json={
        "username": "admin2", "password": "", "name": "第二管理员", "role": "admin",
    })
    assert resp.status_code == 400
    assert "密码" in resp.get_json()["error"]


def test_update_teacher_profile(admin_client, clean_users):
    tid = _teacher_id(admin_client, "张伟")
    data = _data(admin_client.patch(f"/api/admin/teachers/{tid}",
                                    json={"title": "教授", "office": "信息楼 C-301"}))
    assert data["user"]["title"] == "教授"
    assert data["user"]["office"] == "信息楼 C-301"


def test_update_rejects_empty_name(admin_client, clean_users):
    tid = _teacher_id(admin_client, "张伟")
    assert admin_client.patch(f"/api/admin/teachers/{tid}", json={"name": "  "}).status_code == 400


def test_reset_password_then_login(admin_client, anon_client, clean_users):
    tid = _teacher_id(admin_client, "李敏")
    assert admin_client.post(f"/api/admin/teachers/{tid}/password",
                             json={"password": "newpass9"}).status_code == 200
    assert anon_client.post("/api/auth/login",
                            json={"username": "limin", "password": "newpass9"}).status_code == 200


def test_reset_password_too_short(admin_client, clean_users):
    tid = _teacher_id(admin_client, "李敏")
    resp = admin_client.post(f"/api/admin/teachers/{tid}/password", json={"password": "123"})
    assert resp.status_code == 400


def test_disable_account_blocks_login(admin_client, anon_client, clean_users):
    tid = _teacher_id(admin_client, "王强")
    assert admin_client.patch(f"/api/admin/teachers/{tid}", json={"active": False}).status_code == 200
    resp = anon_client.post("/api/auth/login", json={"username": "wangqiang", "password": "123456"})
    assert resp.status_code == 401
    assert "停用" in resp.get_json()["error"]


def test_disable_self_rejected(admin_client):
    admin_id = _data(admin_client.get("/api/auth/me"))["user"]["id"]
    resp = admin_client.patch(f"/api/admin/teachers/{admin_id}", json={"active": False})
    assert resp.status_code == 400


def test_delete_teacher_removes_data(app, admin_client, anon_client, clean_users):
    tid = _teacher_id(admin_client, "王强")
    assert config.tenant_db_path(tid).exists()

    assert admin_client.delete(f"/api/admin/teachers/{tid}").status_code == 200
    assert not config.tenant_db_path(tid).exists(), "租户库文件应一并删除"
    assert anon_client.post("/api/auth/login",
                            json={"username": "wangqiang", "password": "123456"}).status_code == 401

    teachers = _data(admin_client.get("/api/admin/teachers"))
    assert "王强" not in {t["name"] for t in teachers}
    assert len(teachers) == 4


def test_cannot_delete_self(admin_client):
    admin_id = _data(admin_client.get("/api/auth/me"))["user"]["id"]
    resp = admin_client.delete(f"/api/admin/teachers/{admin_id}")
    assert resp.status_code == 400
    assert "当前登录账号" in resp.get_json()["error"]


def test_cannot_downgrade_last_admin(admin_client):
    admin_id = _data(admin_client.get("/api/auth/me"))["user"]["id"]
    resp = admin_client.patch(f"/api/admin/teachers/{admin_id}", json={"role": "teacher"})
    assert resp.status_code == 400
    assert "管理员" in resp.get_json()["error"]


def test_create_teacher_rejects_bad_role(admin_client, clean_users):
    resp = admin_client.post("/api/admin/teachers", json={
        "username": "badrole", "password": "abc123", "name": "角色错误", "role": "root",
    })
    assert resp.status_code == 400


@pytest.mark.parametrize("path,method", [
    ("/api/admin/overview", "get"),
    ("/api/admin/teachers", "get"),
    ("/api/admin/teachers/u_zhangwei", "get"),
    ("/api/admin/achievements", "get"),
])
def test_admin_endpoints_forbidden_for_teacher(client, path, method):
    assert getattr(client, method)(path).status_code == 403
