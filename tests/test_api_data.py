"""数据接口测试：状态、CRUD、个人信息、搜索、导入导出与重置。"""
from __future__ import annotations

from backend import config


def _data(resp):
    payload = resp.get_json()
    assert payload["ok"] is True, payload
    return payload["data"]


# --------------------------------------------------------------------------- #
# 状态
# --------------------------------------------------------------------------- #
def test_state_contains_all_collections(client):
    data = _data(client.get("/api/state"))
    for coll in config.COLLECTIONS:
        assert coll in data, coll
    assert data["profile"]["name"] == "江老师"
    assert len(data["projects"]) == 4
    assert data["meta"]["schemaVersion"] == config.SCHEMA_VERSION
    assert data["stats"]["students"] == 4


def test_stats_derived_fields(client):
    data = _data(client.get("/api/stats"))
    assert set(data) == {"overview", "achievements", "teaching", "development", "toolCategories"}
    assert data["overview"]["papers"] == 6
    assert data["teaching"]["courses"] == 4
    assert data["achievements"]["total"] == 8
    assert 0 <= data["development"] <= 100
    # toolCategories: [[分类, 数量], ...] 且按数量降序
    counts = [c[1] for c in data["toolCategories"]]
    assert counts == sorted(counts, reverse=True)


# --------------------------------------------------------------------------- #
# 集合 CRUD
# --------------------------------------------------------------------------- #
def test_list_collection(client):
    items = _data(client.get("/api/collections/literature"))
    assert len(items) == 6
    # 最新写入的排在最前（seq 降序 == 前端 unshift 语义）
    assert items[0]["id"] == "l1"


def test_list_unknown_collection(client):
    resp = client.get("/api/collections/nope")
    assert resp.status_code == 404
    assert resp.get_json()["ok"] is False


def test_create_update_delete_roundtrip(client):
    created = _data(client.post("/api/collections/todos", json={
        "title": "撰写国家基金年度进展报告", "due": "2026-12-01",
        "priority": "high", "done": False, "tag": "科研项目",
    }))
    assert created["id"]
    assert created["title"] == "撰写国家基金年度进展报告"

    # 新记录出现在列表首位
    items = _data(client.get("/api/collections/todos"))
    assert items[0]["id"] == created["id"]

    patched = _data(client.patch(f"/api/collections/todos/{created['id']}", json={"done": True}))
    assert patched["done"] is True
    assert patched["title"] == "撰写国家基金年度进展报告"  # 未传字段保留

    assert client.delete(f"/api/collections/todos/{created['id']}").status_code == 200
    ids = [t["id"] for t in _data(client.get("/api/collections/todos"))]
    assert created["id"] not in ids


def test_create_rejects_empty_body(client):
    resp = client.post("/api/collections/todos", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"]


def test_patch_missing_record(client):
    resp = client.patch("/api/collections/todos/not-exist", json={"done": True})
    assert resp.status_code == 404


def test_delete_missing_record(client):
    assert client.delete("/api/collections/todos/not-exist").status_code == 404


# --------------------------------------------------------------------------- #
# 个人信息
# --------------------------------------------------------------------------- #
def test_profile_get_and_put(client):
    profile = _data(client.get("/api/profile"))
    assert profile["dept"] == "计算机科学与技术学院"

    updated = _data(client.put("/api/profile", json={
        "name": "江老师", "title": "教授", "dept": "计算机学院",
        "office": "信息楼 A-513", "email": "jiangxl@university.edu.cn",
    }))
    assert updated["dept"] == "计算机学院"
    assert _data(client.get("/api/profile"))["dept"] == "计算机学院"


def test_profile_requires_name(client):
    resp = client.put("/api/profile", json={"name": "   "})
    assert resp.status_code == 400
    assert "姓名" in resp.get_json()["error"]


# --------------------------------------------------------------------------- #
# 全局搜索
# --------------------------------------------------------------------------- #
def test_search_hits_multiple_collections(client):
    hits = _data(client.get("/api/search?q=雷达"))
    assert len(hits) >= 4
    colls = {h["collection"] for h in hits}
    assert {"projects", "literature", "students"} & colls
    for h in hits:
        assert h["label"] and h["page"] and h["title"]


def test_search_empty_query(client):
    assert _data(client.get("/api/search?q=")) == []


def test_search_limit(client):
    hits = _data(client.get("/api/search?q=江老师"))
    assert len(hits) <= 60


# --------------------------------------------------------------------------- #
# 导入 / 导出 / 重置
# --------------------------------------------------------------------------- #
def test_export_then_reset_then_import(client):
    backup = client.get("/api/export").get_json()
    assert backup["profile"]["name"] == "江老师"
    assert len(backup["projects"]) == 4

    # 改动数据后重置，应恢复演示数据
    client.post("/api/collections/todos", json={"title": "临时待办", "done": False})
    assert len(_data(client.get("/api/collections/todos"))) == 7
    _data(client.post("/api/reset"))
    assert len(_data(client.get("/api/collections/todos"))) == 6

    # 用备份覆盖导入
    backup["profile"]["dept"] = "导入后的学院"
    assert _data(client.post("/api/import", json=backup))["imported"] is True
    assert _data(client.get("/api/profile"))["dept"] == "导入后的学院"


def test_import_rejects_foreign_json(client):
    resp = client.post("/api/import", json={"foo": "bar"})
    assert resp.status_code == 400
    assert "备份" in resp.get_json()["error"]


# --------------------------------------------------------------------------- #
# 错误处理
# --------------------------------------------------------------------------- #
def test_unknown_route_returns_json(client):
    resp = client.get("/api/definitely-not-here")
    assert resp.status_code == 404
    assert resp.get_json()["ok"] is False


def test_index_page_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "教师工作台" in resp.get_data(as_text=True)
