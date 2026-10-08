"""个人简历 —— 领域模块与接口用例。

覆盖：固定链接令牌（生成 / 幂等 / 轮换失效）、区块开关校验、
头像（双路径校验 / 类型嗅探 / 旧文件清理 / 越权防护）、
聚合投影的隐私白名单（业绩分 / 内部备注 / 学生邮箱 / 审核状态不下发）、
统计口径（学位论文不计入教师荣誉）、公开页三种状态（404 / 403 / 200）
与教师端全部接口。
"""
from __future__ import annotations

import io

import pytest

from backend import config, cv as cv_util
from backend.store import open_store

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
UID = config.DEFAULT_TENANT_ID


def _public_payload(client, token: str):
    resp = client.get(f"/api/public/cv/{token}")
    body = resp.get_json()
    return resp, (body or {}).get("data") or {}


def _token_of(client) -> str:
    resp = client.get("/api/cv")
    return resp.get_json()["data"]["token"]


# --------------------------------------------------------------------------- #
# 令牌：生成 / 幂等 / 轮换
# --------------------------------------------------------------------------- #
def test_new_token_shape():
    tok = cv_util.new_token()
    assert cv_util.CV_TOKEN_RE.fullmatch(tok), tok
    assert len(cv_util.new_token()) == 16


def test_ensure_token_is_idempotent(store):
    a = cv_util.ensure_token(store)
    b = cv_util.ensure_token(store)
    assert a == b
    assert cv_util.CV_TOKEN_RE.fullmatch(a)


def test_rotate_token_invalidates_old(store):
    old = cv_util.ensure_token(store)
    new = cv_util.rotate_token(store)
    assert new != old
    assert cv_util.ensure_token(store) == new      # 轮换后再次读取保持稳定
    profile, _ = cv_util.find_anywhere(old)
    assert profile is None                          # 旧令牌查不到任何教师


def test_find_anywhere_finds_right_teacher(store):
    tok = cv_util.ensure_token(store)
    profile, user = cv_util.find_anywhere(tok)
    assert profile is not None and user is not None
    assert user["id"] == UID
    assert user["username"] == "jiangxl"


# --------------------------------------------------------------------------- #
# 区块开关
# --------------------------------------------------------------------------- #
def test_sections_defaults_and_filtering(store):
    secs = cv_util.sections_of(store.get_profile())
    assert set(secs) == set(cv_util.DEFAULT_SECTIONS)
    assert all(v is True for v in secs.values())

    # 未知区块直接丢弃；已知区块取布尔值
    patched = dict(secs)
    patched["papers"] = False
    patched["hack"] = True
    store.set_profile({"cvSections": patched})
    secs2 = cv_util.sections_of(store.get_profile())
    assert "hack" not in secs2 and secs2["papers"] is False

    # 缺失的键回落为 True
    store.set_profile({"cvSections": {"papers": False}})
    secs3 = cv_util.sections_of(store.get_profile())
    assert secs3["papers"] is False and secs3["bio"] is True


# --------------------------------------------------------------------------- #
# 头像
# --------------------------------------------------------------------------- #
def test_avatar_path_requires_uid_prefix_and_confines_to_dir(app):
    with app.app_context():
        # 不带 <uid>/ 前缀：拒绝（防止越权指向别的教师的文件）
        assert cv_util.avatar_path(UID, "u_zhangwei/a.png") is None
        assert cv_util.avatar_path(UID, "a.png") is None
        # 目录穿越：拒绝
        assert cv_util.avatar_path(UID, f"{UID}/../../secret.key") is None
        # 未设置：None
        assert cv_util.avatar_path(UID, "") is None


def test_save_avatar_sniffs_and_prunes(app):
    with app.app_context():
        first = cv_util.save_avatar(UID, io.BytesIO(PNG))
        assert first["ext"] == "png"
        assert first["stored"].startswith(f"{UID}/")
        name1 = first["stored"].split("/", 1)[1]
        assert (cv_util.avatar_dir(UID) / name1).is_file()

        # 再传一张：旧文件被清理，目录里只剩新文件
        second = cv_util.save_avatar(UID, io.BytesIO(PNG))
        names = [p.name for p in cv_util.avatar_dir(UID).iterdir() if p.is_file()]
        assert names == [second["stored"].split("/", 1)[1]]
        cv_util.drop_avatar(UID)
        assert not cv_util.avatar_dir(UID).exists()


def test_save_avatar_rejects_non_image(app):
    with app.app_context():
        with pytest.raises(ValueError):
            cv_util.save_avatar(UID, io.BytesIO(b"<html>not an image</html>"))
        with pytest.raises(ValueError):
            cv_util.save_avatar(UID, io.BytesIO(b""))


def test_resolve_avatar_forms(app):
    with app.app_context():
        store = open_store(UID)
        # 未设置
        assert cv_util.resolve_avatar(store.get_profile(), "/api/cv") == \
            {"url": "", "external": False, "set": False}
        # 外链原样返回
        ext = cv_util.resolve_avatar({"avatar": "https://cdn.example.com/me.png"}, "/api/cv")
        assert ext == {"url": "https://cdn.example.com/me.png", "external": True, "set": True}
        # 上传文件拼成接口地址
        saved = cv_util.save_avatar(UID, io.BytesIO(PNG))
        store.set_profile({"avatar": saved["stored"]})
        got = cv_util.resolve_avatar(store.get_profile(), "/api/cv")
        assert got["set"] is True and got["external"] is False
        assert got["url"].startswith("/api/cv/avatar?t=")
        cv_util.drop_avatar(UID)
        store.set_profile({"avatar": ""})


# --------------------------------------------------------------------------- #
# 聚合与隐私白名单
# --------------------------------------------------------------------------- #
def test_build_cv_seed_counts(store):
    data = cv_util.build_cv(store)
    assert data["name"] == "江先亮"
    assert len(data["projects"]) == 4
    assert len(data["papers"]) == 4
    assert len(data["patents"]) == 2
    assert len(data["honors"]) == 1        # 学位论文是学生成果，不计入教师荣誉
    assert len(data["services"]) == 6
    assert len(data["students"]) == 4
    assert len(data["teachings"]) == 4
    assert len(data["educations"]) == 3
    assert data["stats"]["hours"] == 152
    assert set(data["sections"]) == set(cv_util.DEFAULT_SECTIONS)


def test_build_cv_privacy_whitelist(store):
    data = cv_util.build_cv(store)
    for key in ("papers", "patents", "honors"):
        for row in data[key]:
            assert "score" not in row and "note" not in row
            assert "projectId" not in row and "auditStatus" not in row
    for row in data["students"]:
        assert "email" not in row
    # 公开 profile 只含白名单字段（+ directions / avatar 两个附加键）
    assert set(data["profile"]) <= set(cv_util.PROFILE_FIELDS) | {"directions", "avatar"}


def test_build_cv_live_projects_first(store):
    projects = cv_util.build_cv(store)["projects"]
    assert projects[0]["status"] != "已结题"     # 在研排最前


def test_directions_fallback_from_literature_and_projects(store):
    keep = store.get_profile().get("directions")
    store.set_profile({"directions": []})
    try:
        data = cv_util.build_cv(store)
        assert 0 < len(data["directions"]) <= 6
    finally:
        store.set_profile({"directions": keep or []})


def test_funding_tolerant_parse():
    assert cv_util._funding("62") == 62.0
    assert cv_util._funding("62.5") == 62.5
    assert cv_util._funding("62万") == 62.0
    assert cv_util._funding("—") == 0.0
    assert cv_util._funding(None) == 0.0


# --------------------------------------------------------------------------- #
# 教师端接口
# --------------------------------------------------------------------------- #
def test_cv_endpoints_require_login(anon_client):
    for method, path in (("GET", "/api/cv"), ("POST", "/api/cv/visibility"),
                         ("POST", "/api/cv/sections"), ("POST", "/api/cv/token"),
                         ("GET", "/api/cv/avatar")):
        resp = anon_client.open(path, method=method)
        assert resp.status_code == 401, path


def test_cv_overview(client):
    resp = client.get("/api/cv")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert cv_util.CV_TOKEN_RE.fullmatch(data["token"])
    assert data["path"] == f"/cv/{data['token']}"
    assert data["url"].endswith(data["path"])
    assert data["published"] is True
    assert data["counts"]["papers"] == 4
    assert data["sectionLabels"]["papers"] == "论文发表"
    assert set(data["sections"]) == set(cv_util.DEFAULT_SECTIONS)


def test_cv_visibility_roundtrip(client):
    resp = client.post("/api/cv/visibility", json={"published": False})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["published"] is False

    # 未公开时，公开接口 403
    pub, _ = _public_payload(client, data["token"])
    assert pub.status_code == 403
    assert pub.get_json()["state"] == "private"

    # 缺字段 → 400
    assert client.post("/api/cv/visibility", json={}).status_code == 400


def test_cv_sections_validation(client):
    resp = client.post("/api/cv/sections", json={"papers": False, "evil": True})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["sections"]["papers"] is False
    assert "evil" not in data["sections"]
    # 没有可识别键 → 400
    assert client.post("/api/cv/sections", json={"evil": True}).status_code == 400
    # 恢复
    client.post("/api/cv/sections", json={"papers": True})


def test_cv_rotate_token_endpoint(client):
    old = _token_of(client)
    resp = client.post("/api/cv/token", json={})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["token"] != old


def test_cv_avatar_endpoints(client):
    # 上传
    resp = client.post("/api/cv/avatar", data={"file": (io.BytesIO(PNG), "me.png")},
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["avatar"]["set"] is True and data["avatar"]["external"] is False
    assert data["ext"] == "png"

    # 读取（教师端预览）
    got = client.get("/api/cv/avatar")
    assert got.status_code == 200
    assert got.headers["Content-Type"].startswith("image/png")

    # 公开侧也能读到（简历处于公开状态）
    token = _token_of(client)
    pub = client.get(f"/api/public/cv/{token}/avatar")
    assert pub.status_code == 200

    # 非图片拒绝
    bad = client.post("/api/cv/avatar", data={"file": (io.BytesIO(b"<html/>"), "x.png")},
                      content_type="multipart/form-data")
    assert bad.status_code == 400

    # 删除后：教师端 404，公开侧 404
    dele = client.delete("/api/cv/avatar")
    assert dele.status_code == 200
    assert dele.get_json()["data"]["avatar"]["set"] is False
    assert client.get("/api/cv/avatar").status_code == 404
    assert client.get(f"/api/public/cv/{token}/avatar").status_code == 404


def test_public_cv_invalid_token(anon_client):
    resp, _ = _public_payload(anon_client, "deadbeefdeadbeef")
    assert resp.status_code == 404
    resp2, _ = _public_payload(anon_client, "not-a-token")
    assert resp2.status_code == 404


def test_public_cv_published_shape(client):
    token = _token_of(client)
    resp, data = _public_payload(client, token)
    assert resp.status_code == 200
    assert data["name"] == "江先亮"
    assert data["sections"]["bio"] is True
    assert len(data["papers"]) == 4
    # 学生邮箱绝不下发
    for row in data["students"]:
        assert "email" not in row


def test_public_avatar_cannot_reach_other_teachers_file(client, app, clean_users):
    """profile.avatar 被改成别人的路径时必须 404（双路径校验兜底）。"""
    from backend import auth, seed_teachers

    other = [u for u in seed_teachers.all_users()
             if u["id"] != UID and u["role"] == "teacher"][0]
    with app.app_context():
        auth.create_user(user_id="u_tmp_cv", username="tmpcv", password="tmpcv01",
                         role="teacher", name="临时教师", seed=None)
        store = open_store("u_tmp_cv")
        saved = cv_util.save_avatar("u_tmp_cv", io.BytesIO(PNG))
        store.set_profile({"avatar": saved["stored"], "cvToken": cv_util.new_token()})
        token = store.get_profile()["cvToken"]

        # 本人头像：200
        assert client.get(f"/api/public/cv/{token}/avatar").status_code == 200
        # 指向别的教师的文件：404
        open_store("u_tmp_cv").set_profile({"avatar": f"{other['id']}/hack.png"})
        assert client.get(f"/api/public/cv/{token}/avatar").status_code == 404

        cv_util.drop_avatar("u_tmp_cv")


def test_cv_page_route_served(client):
    resp = client.get(f"/cv/{_token_of(client)}")
    assert resp.status_code == 200
    assert b'id="cv"' in resp.data


def test_cv_preview_matches_public_shape(client):
    prev = client.get("/api/cv/preview").get_json()["data"]
    token = _token_of(client)
    _, pub = _public_payload(client, token)
    assert prev["name"] == pub["name"]
    assert len(prev["papers"]) == len(pub["papers"])
    assert prev["published"] is True
    assert prev["url"].endswith(f"/cv/{token}")
