"""课程开放与学生可见性 —— 接口用例。

覆盖：可见性四态与时间窗口边界、开放设置校验、资料上传/下载/删除、
磁盘文件清理、跨租户路径防护、公开接口的免登录准入与未开放拦截。
"""
from __future__ import annotations

import io
from datetime import date, datetime, timedelta

import pytest

from backend import courses as courses_util
from backend.store import open_store

from conftest import TEACHER_ID

C1 = "c1"          # 计算机网络：长期开放
C3 = "c3"          # Python 程序设计：种子中默认关闭


# --------------------------------------------------------------------------- #
# 可见性判定（纯函数，注入 now）
# --------------------------------------------------------------------------- #
def test_visibility_four_states():
    today = date(2026, 10, 8)
    open_course = {"published": True}
    assert courses_util.visibility(open_course, now=today)["state"] == "open"

    closed = {"published": False}
    v = courses_util.visibility(closed, now=today)
    assert v["state"] == "closed" and not v["visible"]

    scheduled = {"published": True, "openFrom": "2026-11-01"}
    v = courses_util.visibility(scheduled, now=today)
    assert v["state"] == "scheduled" and not v["visible"]
    assert "2026-11-01" in v["detail"]

    expired = {"published": True, "openUntil": "2026-09-30"}
    v = courses_util.visibility(expired, now=today)
    assert v["state"] == "expired" and not v["visible"]
    assert "2026-09-30" in v["detail"]


def test_visibility_window_boundaries_are_inclusive():
    today = date(2026, 10, 8)
    course = {"published": True, "openFrom": "2026-10-08", "openUntil": "2026-10-08"}
    assert courses_util.visibility(course, now=today)["visible"] is True
    assert courses_util.visibility(course, now=today - timedelta(days=1))["state"] == "scheduled"
    assert courses_util.visibility(course, now=today + timedelta(days=1))["state"] == "expired"


def test_visibility_accepts_datetime_and_keeps_dates_in_payload():
    v = courses_util.visibility({"published": True, "openFrom": "2026-09-01"},
                                now=datetime(2026, 10, 8, 23, 59))
    assert v["visible"] is True
    assert v["openFrom"] == "2026-09-01" and v["openUntil"] == ""


def test_human_size():
    assert courses_util.human_size(0) == "0 B"
    assert courses_util.human_size(158) == "158 B"
    assert courses_util.human_size(40960) == "40.0 KB"
    assert courses_util.human_size(8.4 * 1024 * 1024) == "8.4 MB"
    assert courses_util.human_size("abc") == ""
    assert courses_util.human_size(None) == ""


# --------------------------------------------------------------------------- #
# 种子与回填
# --------------------------------------------------------------------------- #
def test_seed_courses_carry_open_fields(store):
    items = {c["id"]: c for c in store.list("courses")}
    assert set(items) >= {C1, "c2", C3}
    for c in items.values():
        assert courses_util.SHARE_TOKEN_RE.match(c["shareToken"]), "访问令牌已生成"
        assert c["materials"], "种子资料齐全"
        assert all(courses_util.MATERIAL_ID_RE.match(m["id"]) for m in c["materials"])
    assert items[C1]["published"] is True
    assert items[C3]["published"] is False, "种子保留一门关闭课程用于演示"


def test_resources_seed_is_normalized_into_materials():
    """早期种子的 ``resources``（type 存文件格式）应被 normalize 转换为 ``materials``。"""
    from backend import seed_teachers
    data = seed_teachers.initial_data(seed_teachers.TEACHER_BY_ID["u_zhangwei"])
    course = data["courses"][0]
    assert course.get("resources"), "原始种子仍保留 resources 登记"
    assert "materials" not in course, "转换发生在 normalize，而非种子本身"

    patch = courses_util.normalize(dict(course))
    mats = patch["materials"]
    assert mats and all(m["type"] in ("教学大纲", "课件", "案例", "实验", "习题", "参考书", "其他")
                        for m in mats)
    assert all(m["name"] for m in mats)


# --------------------------------------------------------------------------- #
# 分享信息与开放设置
# --------------------------------------------------------------------------- #
def test_share_endpoint_returns_token_and_visibility(client):
    data = client.get(f"/api/courses/{C1}/share").get_json()["data"]
    assert data["course"]["id"] == C1
    assert courses_util.SHARE_TOKEN_RE.match(data["token"])
    assert data["path"] == f"/c/{data['token']}"
    assert data["visibility"]["visible"] is True
    assert data["published"] is True


def test_share_is_idempotent(client, store):
    first = client.get(f"/api/courses/{C1}/share").get_json()["data"]["token"]
    second = client.get(f"/api/courses/{C1}/share").get_json()["data"]["token"]
    assert first == second, "令牌在多次读取间保持稳定"
    assert store.get("courses", C1)["shareToken"] == first


def test_share_requires_login(anon_client):
    assert anon_client.get(f"/api/courses/{C1}/share").status_code == 401


def test_share_unknown_course_404(client):
    assert client.get("/api/courses/nope/share").status_code == 404


def test_set_visibility_toggle(client, store):
    data = client.post(f"/api/courses/{C1}/visibility",
                       json={"published": False}).get_json()["data"]
    assert data["published"] is False
    assert data["visibility"]["state"] == "closed"
    assert store.get("courses", C1)["published"] is False

    data = client.post(f"/api/courses/{C1}/visibility",
                       json={"published": True}).get_json()["data"]
    assert data["visibility"]["visible"] is True


def test_set_visibility_window_and_clear(client, store):
    client.post(f"/api/courses/{C1}/visibility",
                json={"openFrom": "2026-09-01", "openUntil": "2027-01-15"})
    doc = store.get("courses", C1)
    assert doc["openFrom"] == "2026-09-01" and doc["openUntil"] == "2027-01-15"

    client.post(f"/api/courses/{C1}/visibility", json={"openFrom": "", "openUntil": ""})
    doc = store.get("courses", C1)
    assert doc["openFrom"] == "" and doc["openUntil"] == ""


def test_set_visibility_rejects_inverted_range(client):
    resp = client.post(f"/api/courses/{C1}/visibility",
                       json={"openFrom": "2026-12-01", "openUntil": "2026-01-01"})
    assert resp.status_code == 400
    assert "不能晚于" in resp.get_json()["error"]


def test_set_visibility_rejects_bad_date(client):
    resp = client.post(f"/api/courses/{C1}/visibility", json={"openFrom": "明天"})
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# 学生公开接口
# --------------------------------------------------------------------------- #
def _public_token(client) -> str:
    return client.get(f"/api/courses/{C1}/share").get_json()["data"]["token"]


def test_public_course_visible_without_login(anon_client, client):
    token = _public_token(client)
    resp = anon_client.get(f"/api/public/courses/{token}")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["name"] == "计算机网络"
    assert data["teacher"]["name"] == "江老师"
    assert len(data["syllabus"]) == 8
    # 未上传文件的种子资料不下发
    assert data["materials"] == []
    # 教师私有字段不得泄漏
    for key in ("published", "shareToken", "students", "materials_raw"):
        assert key not in data


def test_public_course_hidden_when_closed(anon_client, client):
    client.post(f"/api/courses/{C1}/visibility", json={"published": False})
    token = _public_token(client)
    resp = anon_client.get(f"/api/public/courses/{token}")
    assert resp.status_code == 403
    body = resp.get_json()
    assert body["visibility"]["state"] == "closed"
    assert body["error"] == "本课程暂未开放，请联系任课教师。"
    # 只回显足以确认课程的元信息，正文不下发
    assert body["course"]["name"] == "计算机网络"
    assert "syllabus" not in body["course"] and "materials" not in body["course"]


def test_public_course_scheduled_and_expired(anon_client, client):
    client.post(f"/api/courses/{C1}/visibility", json={"openFrom": "2099-01-01"})
    body = anon_client.get(f"/api/public/courses/{_public_token(client)}").get_json()
    assert body["visibility"]["state"] == "scheduled" and "2099-01-01" in body["error"]

    client.post(f"/api/courses/{C1}/visibility",
                json={"openFrom": "", "openUntil": "2000-01-01"})
    body = anon_client.get(f"/api/public/courses/{_public_token(client)}").get_json()
    assert body["visibility"]["state"] == "expired" and "2000-01-01" in body["error"]


def test_public_course_rejects_bad_tokens(anon_client):
    assert anon_client.get("/api/public/courses/deadbeefdeadbeef").status_code == 404
    assert anon_client.get("/api/public/courses/xyz").status_code == 404
    assert anon_client.get("/api/public/courses/" + "g" * 16).status_code == 404


def test_public_page_route_serves_html(anon_client):
    resp = anon_client.get("/c/deadbeefdeadbeef")
    assert resp.status_code == 200
    assert b"course-public.js" in resp.data


def test_public_material_download(anon_client, client):
    """上传 → 学生可下载；内容与上传一致。"""
    payload = b"demo material body\n" * 10
    resp = client.post(f"/api/courses/{C1}/materials", data={
        "files": (io.BytesIO(payload), "lecture05.pptx"),
        "type": "课件", "date": "2026-10-08",
    }, content_type="multipart/form-data")
    assert resp.status_code == 200
    added = resp.get_json()["data"]["materials"][-1]
    token = _public_token(client)

    dl = anon_client.get(f"/api/public/courses/{token}/materials/{added['id']}/download")
    assert dl.status_code == 200
    assert dl.data == payload


def test_public_download_blocked_when_course_closed(anon_client, client):
    payload = b"secret"
    resp = client.post(f"/api/courses/{C1}/materials", data={
        "files": (io.BytesIO(payload), "secret.txt")}, content_type="multipart/form-data")
    mid = resp.get_json()["data"]["materials"][-1]["id"]
    token = _public_token(client)
    client.post(f"/api/courses/{C1}/visibility", json={"published": False})

    resp = anon_client.get(f"/api/public/courses/{token}/materials/{mid}/download")
    assert resp.status_code == 403, "关闭课程后直链也必须被拦截"


def test_public_download_unknown_material_404(anon_client, client):
    token = _public_token(client)
    assert anon_client.get(
        f"/api/public/courses/{token}/materials/m_none/download").status_code == 404


def test_public_download_rejects_cross_tenant_path(client, store):
    """教师可整体 PATCH 课程文档，``stored`` 指向他人目录时必须拒绝。"""
    payload = b"other teacher's file"
    resp = client.post(f"/api/courses/{C1}/materials", data={
        "files": (io.BytesIO(payload), "mine.txt")}, content_type="multipart/form-data")
    mid = resp.get_json()["data"]["materials"][-1]["id"]
    token = _public_token(client)

    rogue_rel = "u_admin/c1/m_rogue.txt"
    rogue = courses_util.COURSE_FILES_DIR / rogue_rel
    rogue.parent.mkdir(parents=True, exist_ok=True)
    rogue.write_bytes(payload)
    try:
        doc = store.get("courses", C1)
        for m in doc["materials"]:
            if m["id"] == mid:
                m["stored"] = rogue_rel
        store.update("courses", C1, {"materials": doc["materials"]})

        resp = client.get(f"/api/courses/{C1}/materials/{mid}/download")
        assert resp.status_code == 404, "跨租户 stored 不得被下载"
        resp = client.get(f"/api/public/courses/{token}/materials/{mid}/download")
        assert resp.status_code == 404
    finally:
        import shutil
        shutil.rmtree(rogue.parent, ignore_errors=True)


# --------------------------------------------------------------------------- #
# 资料上传 / 下载 / 删除
# --------------------------------------------------------------------------- #
def test_upload_material_persists_file(client, store):
    payload = "课程作业模板内容".encode("utf-8")
    resp = client.post(f"/api/courses/{C1}/materials", data={
        "files": (io.BytesIO(payload), "作业模板.txt"),
        "type": "习题", "date": "2026-10-08",
    }, content_type="multipart/form-data")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["added"] == 1

    doc = store.get("courses", C1)
    mat = doc["materials"][-1]
    assert mat["name"] == "作业模板.txt"
    assert mat["type"] == "习题" and mat["date"] == "2026-10-08"
    assert mat["bytes"] == len(payload)
    assert mat["size"] == courses_util.human_size(len(payload))
    assert mat["stored"].startswith(f"{TEACHER_ID}/{C1}/")
    assert mat["uploadedBy"] == "江老师"
    assert (courses_util.COURSE_FILES_DIR / mat["stored"]).read_bytes() == payload


def test_upload_material_defaults_type_and_date(client, store):
    resp = client.post(f"/api/courses/{C1}/materials", data={
        "files": (io.BytesIO(b"x"), "note.md"),
    }, content_type="multipart/form-data")
    mat = store.get("courses", C1)["materials"][-1]
    assert mat["type"] == "课件", "未指定类型时默认课件"
    assert mat["date"] == date.today().isoformat()
    assert resp.status_code == 200


def test_upload_material_requires_files(client):
    resp = client.post(f"/api/courses/{C1}/materials", data={"type": "课件"},
                       content_type="multipart/form-data")
    assert resp.status_code == 400
    assert "没有收到文件" in resp.get_json()["error"]


def test_upload_material_rejects_too_many(client):
    files = {"files": [(io.BytesIO(b"x"), f"f{i}.txt") for i in range(11)]}
    resp = client.post(f"/api/courses/{C1}/materials", data=files,
                       content_type="multipart/form-data")
    assert resp.status_code == 400


def test_upload_material_rejects_bad_date(client):
    resp = client.post(f"/api/courses/{C1}/materials", data={
        "files": (io.BytesIO(b"x"), "a.txt"), "date": "昨天",
    }, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_teacher_download_material(client):
    payload = b"teacher download"
    resp = client.post(f"/api/courses/{C1}/materials", data={
        "files": (io.BytesIO(payload), "handout.pdf")}, content_type="multipart/form-data")
    mid = resp.get_json()["data"]["materials"][-1]["id"]

    dl = client.get(f"/api/courses/{C1}/materials/{mid}/download")
    assert dl.status_code == 200 and dl.data == payload


def test_teacher_download_unstored_material_404(client):
    """种子资料只有登记信息没有文件，下载应提示未上传。"""
    course = client.get("/api/state").get_json()["data"]["courses"]
    mid = [c for c in course if c["id"] == C1][0]["materials"][0]["id"]
    dl = client.get(f"/api/courses/{C1}/materials/{mid}/download")
    assert dl.status_code == 404
    assert "尚未上传" in dl.get_json()["error"]


def test_delete_material_removes_file(client, store):
    resp = client.post(f"/api/courses/{C1}/materials", data={
        "files": (io.BytesIO(b"to be removed"), "tmp.bin")}, content_type="multipart/form-data")
    mat = store.get("courses", C1)["materials"][-1]
    path = courses_util.COURSE_FILES_DIR / mat["stored"]
    assert path.exists()

    resp = client.delete(f"/api/courses/{C1}/materials/{mat['id']}")
    assert resp.status_code == 200
    assert not path.exists()
    assert all(m["id"] != mat["id"] for m in store.get("courses", C1)["materials"])


def test_delete_unknown_material_404(client):
    assert client.delete(f"/api/courses/{C1}/materials/m_none").status_code == 404


def test_course_delete_purges_files(client, app):
    """删除课程后其资料目录一并清理。"""
    payload = b"course file"
    resp = client.post(f"/api/courses/{C1}/materials", data={
        "files": (io.BytesIO(payload), "keep.bin")}, content_type="multipart/form-data")
    stored = resp.get_json()["data"]["materials"][-1]["stored"]
    folder = (courses_util.COURSE_FILES_DIR / stored).parent
    assert folder.exists()

    assert client.delete(f"/api/collections/courses/{C1}").status_code == 200
    assert not folder.exists()


def test_materials_endpoints_require_login(anon_client):
    assert anon_client.post(f"/api/courses/{C1}/materials").status_code == 401
    assert anon_client.get(f"/api/courses/{C1}/materials/m1/download").status_code == 401
    assert anon_client.delete(f"/api/courses/{C1}/materials/m1").status_code == 401
    assert anon_client.post(f"/api/courses/{C1}/visibility", json={}).status_code == 401


def test_other_teacher_cannot_touch_foreign_course(app):
    """教师 A 不能操作教师 B 的课程（租户库物理隔离 + 课程 id 不存在）。"""
    from backend import db
    from backend.store import Store

    with app.app_context():
        Store(db.connect_tenant("u_zhangwei"))
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["uid"] = "u_zhangwei"
        assert c.get(f"/api/courses/{C1}/share").status_code == 404
        assert c.post(f"/api/courses/{C1}/visibility", json={}).status_code == 404
        assert c.delete(f"/api/courses/{C1}/materials/m1").status_code == 404
