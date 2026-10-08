"""核心层单测：工具函数、文档仓库、种子数据自洽性。

这些用例不经过 HTTP，直接验证后端内部行为（数据层与工具注册表），
用于在接口层之外提供更细的回归保护。
"""
from __future__ import annotations

import copy
import re

import pytest

from backend import config
from backend.seed import COLLECTION_SEED, full_seed
from backend.tools import KEY_BY_URL, TOOL_IMPLS
from backend.utils import (
    barrier, cn_date, csv_bytes, day_offset, days_until, due_text,
    parse_ymd, safe_name, today, uid,
)


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
def test_uid_is_unique_and_prefixed():
    # 2000 个连续 ID：仅靠毫秒时间戳 + 随机后缀会撞生日问题，序号保证唯一
    ids = [uid("p") for _ in range(2000)]
    assert len(set(ids)) == 2000
    assert all(i.startswith("p_") for i in ids)


@pytest.mark.parametrize("raw,expected", [
    ("结题材料汇编", "结题材料汇编"),
    ("a/b\\c:d*e?f", "a-b-c-d-e-f"),
    ("  多  空格  ", "多-空格"),
    ("V1.0 版", "V1.0-版"),          # 保留扩展名分隔点，仅折叠连续点
    ("结题材料汇编.pdf", "结题材料汇编.pdf"),
    ("../../etc/passwd", "etc-passwd"),
    ("..\\..\\x.txt", "x.txt"),
    ("...", "output"),
    ("", "output"),
    ("<>|\"", "output"),
])
def test_safe_name(raw, expected):
    assert safe_name(raw) == expected


def test_safe_name_has_no_path_separators():
    for raw in ("../../etc/passwd", "..\\..\\windows\\system32", "/abs/path", "...//..\\x"):
        out = safe_name(raw)
        assert "/" not in out and "\\" not in out and ".." not in out


def test_safe_name_respects_limit():
    assert len(safe_name("长" * 200, 48)) == 48


def test_date_helpers():
    assert parse_ymd("2026/3/7").isoformat() == "2026-03-07"
    assert parse_ymd("2026-3-7 14:00") is not None
    assert parse_ymd("不是日期") is None
    assert parse_ymd("") is None
    assert days_until(today()) == 0
    assert days_until(day_offset(10)) == 10
    assert days_until(day_offset(-3)) == -3
    assert due_text(day_offset(0)) == "今天截止"
    assert due_text(day_offset(1)) == "明天截止"
    assert due_text(day_offset(6)) == "剩 6 天"
    assert due_text(day_offset(-2)) == "已逾期 2 天"
    assert due_text("") == "无截止日期"
    assert cn_date("2026-03-07") == "3月7日 周六"


def test_csv_bytes_has_bom_and_crlf():
    raw = csv_bytes(["姓名", "分数"], [["李明", 87.1]])
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in raw
    assert "李明,87.1" in raw.decode("utf-8-sig")


def test_barrier_clamps_out_of_range():
    assert barrier(0, 10, 20) == ""
    assert barrier(10, 10, 20) == "█" * 20
    assert barrier(20, 10, 20) == "█" * 20
    assert barrier(5, 0, 20) == ""


# --------------------------------------------------------------------------- #
# 种子数据自洽性
# --------------------------------------------------------------------------- #
def test_seed_covers_every_collection():
    seed = full_seed()
    for coll in config.COLLECTIONS:
        assert coll in seed, coll
        assert isinstance(seed[coll], list)
    assert seed["profile"]["name"] == "江先亮"


def test_seed_ids_unique_within_collection():
    for coll, items in COLLECTION_SEED.items():
        ids = [x["id"] for x in items]
        assert len(ids) == len(set(ids)), coll


def test_seed_is_deep_copied():
    a = full_seed()
    a["projects"][0]["phases"][0]["name"] = "被改坏了"
    assert "被改坏了" not in str(full_seed()["projects"][0])


def test_seed_nested_structures_present():
    seed = full_seed()
    assert all(p.get("phases") for p in seed["projects"])
    assert all(s.get("milestones") and s.get("logs") for s in seed["students"])
    assert all(c.get("syllabus") and c.get("materials") for c in seed["courses"])
    assert all(g.get("tasks") for g in seed["teachings"])
    assert all(d.get("metrics") for d in seed["developments"])


def test_tool_urls_match_registry():
    """种子里的工具 url 必须与后端工具注册表一一对应，否则前端点了没反应。"""
    seed = full_seed()
    urls = {t["url"] for t in seed["tools"]}
    assert urls == set(KEY_BY_URL)
    assert set(KEY_BY_URL.values()) == set(TOOL_IMPLS)


def test_all_seed_events_have_type_and_date():
    for e in full_seed()["events"]:
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", e["date"]), e
        assert e["type"]


# --------------------------------------------------------------------------- #
# 文档仓库（Store）
# --------------------------------------------------------------------------- #
def test_add_get_update_remove(store):
    created = store.add("todos", {"title": "整理下周组会材料", "done": False})
    assert created["id"]
    assert store.exists("todos", created["id"])

    assert store.get("todos", created["id"])["title"] == "整理下周组会材料"

    updated = store.update("todos", created["id"], {"done": True})
    assert updated["done"] is True
    assert updated["title"] == "整理下周组会材料"

    assert store.remove("todos", created["id"]) is True
    assert store.remove("todos", created["id"]) is False
    assert store.get("todos", created["id"]) is None


def test_update_missing_returns_none(store):
    assert store.update("todos", "ghost-id", {"done": True}) is None


def test_list_is_newest_first(store):
    base = len(store.list("literature"))
    first = store.add("literature", {"title": "第一篇"})
    second = store.add("literature", {"title": "第二篇"})
    titles = [x["title"] for x in store.list("literature")]
    assert len(titles) == base + 2
    assert titles[0] == "第二篇"      # 最新在前
    assert titles.index("第一篇") == 1
    assert second["id"] != first["id"]


def test_seed_display_order_is_preserved(store):
    """种子首条应排在首位 —— 与前端数组顺序、导出顺序一致（回归保护）。"""
    for coll in ("literature", "projects", "todos", "events"):
        assert store.list(coll)[0]["id"] == COLLECTION_SEED[coll][0]["id"], coll


def test_export_import_keeps_order(store):
    before = {c: [x["id"] for x in store.list(c)] for c in ("projects", "todos", "tools")}
    store.replace_all(store.export())
    after = {c: [x["id"] for x in store.list(c)] for c in ("projects", "todos", "tools")}
    assert after == before


def test_nested_payload_survives_roundtrip(store):
    payload = {
        "name": "嵌套结构验证项目",
        "phases": [{"name": "阶段一", "tasks": [{"name": "任务 A", "done": True}]}],
        "metrics": {"ratio": 0.75, "tags": ["a", "b"]},
    }
    created = store.add("projects", payload)
    got = store.get("projects", created["id"])
    assert got["phases"][0]["tasks"][0]["name"] == "任务 A"
    assert got["metrics"]["ratio"] == 0.75
    assert got["metrics"]["tags"] == ["a", "b"]


def test_profile_defaults_and_update(store):
    profile = store.get_profile()
    assert profile["name"] == "江先亮"
    store.set_profile({"dept": "计算机科学与技术学院（新）"})
    assert store.get_profile()["dept"] == "计算机科学与技术学院（新）"
    assert store.get_profile()["name"] == "江先亮"      # 其它字段保留


def test_set_profile_ignores_none(store):
    store.set_profile({"office": None, "title": "教授"})
    profile = store.get_profile()
    assert profile["title"] == "教授"
    assert profile["office"] == "信息楼 A-513"


def test_export_shape(store):
    data = store.export()
    assert set(data) == {"profile"} | set(config.COLLECTIONS)
    assert isinstance(data["profile"], dict)


def test_migrate_fills_missing_collections(store):
    migrated = store.migrate({"profile": {"name": "某教师"}, "projects": [{"id": "x"}]})
    for coll in config.COLLECTIONS:
        assert isinstance(migrated[coll], list)
    assert migrated["projects"] == [{"id": "x"}]            # 已有数据不动
    assert len(migrated["students"]) == len(COLLECTION_SEED["students"])
    assert migrated["profile"]["name"] == "某教师"


def test_replace_all_restores_seed(store):
    store.add("todos", {"title": "临时", "done": False})
    store.replace_all(full_seed())
    assert len(store.list("todos")) == len(COLLECTION_SEED["todos"])
    assert len(store.list("projects")) == len(COLLECTION_SEED["projects"])


def test_replace_all_tolerates_partial_payload(store):
    store.replace_all({"profile": {"name": "只有个人信息"}})
    assert store.get_profile()["name"] == "只有个人信息"
    assert len(store.list("projects")) == len(COLLECTION_SEED["projects"])


def test_ensure_seed_is_idempotent(store):
    store.ensure_seed()
    first = len(store.list("todos"))
    store.ensure_seed()
    assert len(store.list("todos")) == first


def test_stats_and_derived_views(store):
    stats = store.stats()
    assert stats["students"] == 4
    assert stats["papers"] == len(store.list("literature"))
    assert stats["activeProjects"] == sum(
        1 for p in store.list("projects") if p["status"] != "已结题"
    )

    ach = store.achievement_stats()
    assert ach["total"] == len(store.list("achievements"))
    assert ach["score"] == sum(a.get("score", 0) for a in store.list("achievements"))

    load = store.teaching_load()
    assert load["courses"] == len(store.list("teachings"))
    assert load["students"] == sum(g["students"] for g in store.list("teachings"))

    assert 0 <= store.development_progress() <= 100
    assert sum(c[1] for c in store.tool_categories()) == len(store.list("tools"))


def test_upcoming_events_window(store):
    events = store.upcoming_events(7)
    assert events == sorted(events, key=lambda e: (e["date"], e.get("start", "")))
    for e in events:
        assert today() <= e["date"] <= day_offset(7)


def test_tool_runs_sorted_newest_first(store):
    store.record_tool_run("grade_calc", "成绩批量计算", "第 1 次")
    store.record_tool_run("student_board", "研究生培养进度看板", "第 2 次")
    runs = store.tool_runs_for()
    assert len(runs) == 2
    assert store.tool_runs_for("grade_calc")[0]["tool"] == "grade_calc"
    assert len(store.tool_runs_for("nope")) == 0


def test_bump_tool_freq(store):
    tool = store.list("tools")[0]
    before = tool["freq"]
    store.bump_tool_freq(tool["id"])
    assert store.get("tools", tool["id"])["freq"] == before + 1
    store.bump_tool_freq("not-exist")      # 不应抛错


def test_unknown_collection_reads_as_empty(store):
    assert store.list("nope") == []
    assert store.get("nope", "x") is None


def test_deep_copy_of_seed_independent_of_store(store):
    snapshot = copy.deepcopy(store.list("projects"))
    store.update("projects", snapshot[0]["id"], {"name": "改名了"})
    assert full_seed()["projects"][0]["name"] != "改名了"
