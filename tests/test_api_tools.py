"""工具接口测试：字段规格、上传、运行、产物下载、留痕。

覆盖 12 个内置工具，其中 PDF 工具用 pypdf 现场生成真实文件做合并/拆分验证。
"""
from __future__ import annotations

import io
import json

import pytest

from backend.utils import day_offset, today

pypdf = pytest.importorskip("pypdf", reason="PDF 工具测试需要 pypdf")

TOOL_KEYS = [
    "teaching_calendar", "grade_calc", "cite_convert", "budget_calc",
    "submission_track", "student_board", "duty_log", "meeting_note",
    "pdf_toolkit", "achievement_export", "ppt_theme", "device_lend",
]


def _data(resp, code=200):
    assert resp.status_code == code, resp.get_data(as_text=True)[:400]
    payload = resp.get_json()
    assert payload["ok"] is True, payload
    return payload["data"]


def _run(client, key, params=None, files=None):
    return client.post(f"/api/tools/{key}/run", json={"params": params or {}, "files": files or []})


def _pdf_bytes(pages: int = 2) -> bytes:
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# 字段规格
# --------------------------------------------------------------------------- #
def test_specs_all_covers_12_tools(client):
    specs = _data(client.get("/api/tools/specs"))
    assert set(specs) == set(TOOL_KEYS)
    for key, fields in specs.items():
        assert fields, f"{key} 字段规格为空"
        for f in fields:
            assert {"name", "label", "type"} <= set(f), (key, f)


def test_specs_one_tool(client):
    fields = _data(client.get("/api/tools/grade_calc/specs"))
    names = [f["name"] for f in fields]
    assert names[:2] == ["raw", "w_usual"]
    assert next(f for f in fields if f["name"] == "raw")["req"] is True


def test_specs_unknown_tool(client):
    assert client.get("/api/tools/nope/specs").status_code == 404


def test_budget_specs_are_generated_from_rules(client):
    fields = _data(client.get("/api/tools/budget_calc/specs"))
    subjects = [f["name"] for f in fields if f["name"].startswith("_")]
    assert len(subjects) == 9
    assert "_设备费" in subjects


# --------------------------------------------------------------------------- #
# 运行：参数校验
# --------------------------------------------------------------------------- #
def test_run_unknown_tool(client):
    assert _run(client, "no_such_tool").status_code == 404


def test_run_requires_mandatory_params(client):
    resp = _run(client, "grade_calc", {})
    assert resp.status_code == 400
    assert "请填写" in resp.get_json()["error"]


def test_run_rejects_bad_params_type(client):
    resp = client.post("/api/tools/grade_calc/run", json={"params": "oops"})
    assert resp.status_code == 400


def test_file_field_required_without_upload(client):
    resp = _run(client, "pdf_toolkit", {"mode": "合并多个 PDF"})
    assert resp.status_code == 400
    assert "请选择" in resp.get_json()["error"]


# --------------------------------------------------------------------------- #
# 运行：逐个工具
# --------------------------------------------------------------------------- #
def test_teaching_calendar(client):
    data = _data(_run(client, "teaching_calendar", {
        "course_label": "CS301 计算机网络", "start_date": day_offset(7),
        "sessions_per_week": "2", "weekdays": "1,3",
        "holidays": day_offset(20), "skip_holidays": True, "hours_per_session": "2",
    }))
    assert "计算机网络" in data["summary"]
    assert data["ok"] is True
    assert data["table"]["header"]
    assert data["files"][0]["url"].startswith("/api/tools/download/")


def test_grade_calc(client):
    data = _data(_run(client, "grade_calc", {
        "raw": "李明 85 78 92\n王雪 90 88 95\n张伟 72 65 70",
        "w_usual": "30", "w_mid": "20", "w_final": "50", "fail_line": "60", "curve": "0",
    }))
    assert "3 名学生" in data["summary"]
    assert "82.93" in data["summary"]
    assert data["metrics"][0] == ["学生数", "3", "人"]
    assert data["files"][0]["name"].endswith(".csv")


def test_cite_convert_bibtex_to_gbt(client):
    data = _data(_run(client, "cite_convert", {
        "raw": "@article{li2024radar,\n  author = {Li, Xin and He, Yuan},\n"
               "  title  = {Radar-based Human Activity Recognition},\n"
               "  journal= {IEEE Sensors Journal},\n  year   = {2024}\n}",
        "src_format": "自动识别", "dst_format": "GB/T 7714", "sort_by": "保持原顺序",
    }))
    assert data["metrics"][1] == ["源格式", "BibTeX", ""]
    assert "[1]" in data["text"]
    assert "2024" in data["text"]


def test_budget_calc_flags_over_limit(client):
    data = _data(_run(client, "budget_calc", {
        "total": "62", "allocated": "10",
        "_设备费": "20", "_材料费": "5", "_差旅费": "8", "_劳务费": "10",
    }))
    assert "超限" in data["summary"]
    assert any("超限" in row[4] for row in data["table"]["rows"])


def test_submission_track(client):
    data = _data(_run(client, "submission_track", {"only_paper": "仅期刊论文", "warn_days": "90"}))
    assert "篇" in data["summary"]
    assert data["table"]["header"]
    assert "逾期提醒" in data["text"] or "在审" in data["text"]


def test_student_board(client):
    data = _data(_run(client, "student_board", {"scope": "全部学生"}))
    assert data["metrics"][0] == ["学生数", "4", "人"]
    assert "平均论文进度" in data["text"]


def test_duty_log_writes_event(client):
    before = len(_data(client.get("/api/collections/events")))
    data = _data(_run(client, "duty_log", {
        "kind": "调课", "course": "计算机网络（第 03 讲）",
        "orig_date": day_offset(1), "orig_time": "10:00",
        "new_date": day_offset(3), "new_time": "14:00",
        "room": "一教 302", "reason": "参加学术会议",
        "audience": "全班", "notify": "写入日程并生成通知",
    }))
    assert "调课" in data["summary"]
    assert len(_data(client.get("/api/collections/events"))) == before + 1


def test_meeting_note_pushes_todo(client):
    before = len(_data(client.get("/api/collections/todos")))
    data = _data(_run(client, "meeting_note", {
        "title": "课题组第 12 次例会", "when": today(), "place": "信息楼 A-513",
        "host": "江老师", "attendees": "李明,王雪",
        "agenda": "1 汇报进展", "conclusion": "继续推进",
        "actions": "补充实验 | 李明 | " + day_offset(10), "push_todo": True,
    }))
    assert "会议纪要" in data["summary"]
    todos = _data(client.get("/api/collections/todos"))
    assert len(todos) == before + 1
    # 待办标题带会议前缀，便于回溯来源
    assert todos[0]["title"].endswith("补充实验（李明）")
    assert "第 12 次例会" in todos[0]["title"]


def test_achievement_export_csv(client):
    data = _data(_run(client, "achievement_export", {
        "year": "全部年度", "type": "全部类型",
        "format": "CSV（Excel 可直接打开）", "with_score": "含业绩分",
    }))
    assert data["metrics"][0] == ["成果项数", "8", "项"]
    f = data["files"][0]
    assert f["name"].endswith(".csv")
    # CSV 用 utf-8-sig（带 BOM），Excel 双击不乱码
    raw = _download(client, f["url"])
    assert raw[:3] == b"\xef\xbb\xbf"


def test_ppt_theme_without_upload(client):
    data = _data(_run(client, "ppt_theme", {
        "preset": "薄荷绿学术（默认）", "font": "微软雅黑", "size": "28",
    }))
    assert "样式规范" in data["summary"]
    assert "#189d5b" in data["text"]


def test_device_lend_borrow_then_return(client):
    borrow = _data(_run(client, "device_lend", {
        "action": "借出登记", "device": "毫米波雷达开发板 TI-AWR1843", "person": "张伟",
        "contact": "13800000000", "borrow_date": today(), "due_date": day_offset(14),
        "back_date": "", "condition_out": "完好", "condition_back": "",
        "overdue_days": "0", "purpose": "跌倒检测数据采集",
    }))
    assert borrow["metrics"][2] == ["台账在借", "1", "台"]

    back = _data(_run(client, "device_lend", {
        "action": "归还登记", "device": "毫米波雷达开发板 TI-AWR1843", "person": "张伟",
        "borrow_date": today(), "due_date": day_offset(14), "back_date": today(),
        "condition_out": "完好", "condition_back": "完好", "purpose": "跌倒检测数据采集",
    }))
    assert back["ok"] is True
    assert "归还" in back["summary"]


# --------------------------------------------------------------------------- #
# 上传 / 下载
# --------------------------------------------------------------------------- #
def _upload(client, files):
    payload = {"files": [(io.BytesIO(blob), name) for name, blob in files]}
    return _data(client.post("/api/tools/upload", data=payload, content_type="multipart/form-data"))


def _download(client, url):
    resp = client.get(url)
    assert resp.status_code == 200, url
    return resp.get_data()


def test_upload_and_download_roundtrip(client):
    up = _upload(client, [("申报材料.pdf", _pdf_bytes(1))])
    assert up["token"]
    assert up["files"][0]["name"] == "申报材料.pdf"

    # 上传 ID 可直接作为文件字段传入
    data = _data(_run(client, "pdf_toolkit", {
        "mode": "仅统计信息", "ranges": "", "chunk": "1", "out_name": "",
    }, files=[up["files"][0]["id"]]))
    assert data["ok"] is True


def test_pdf_merge_and_split(client):
    up = _upload(client, [
        ("part-a.pdf", _pdf_bytes(2)),
        ("part-b.pdf", _pdf_bytes(3)),
    ])
    ids = [f["id"] for f in up["files"]]

    merged = _data(_run(client, "pdf_toolkit", {
        "mode": "合并多个 PDF", "out_name": "结题材料汇编", "ranges": "", "chunk": "1",
    }, files=ids))
    assert "合并" in merged["summary"]
    merged_file = merged["files"][0]
    assert merged_file["name"].endswith(".pdf")
    blob = _download(client, merged_file["url"])
    assert len(pypdf.PdfReader(io.BytesIO(blob)).pages) == 5

    split = _data(_run(client, "pdf_toolkit", {
        "mode": "拆分 PDF", "out_name": "", "ranges": "", "chunk": "2",
    }, files=[ids[1]]))
    assert len(split["files"]) == 2
    assert all(f["name"].endswith(".pdf") for f in split["files"])


def test_upload_without_files(client):
    resp = client.post("/api/tools/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_upload_filename_is_sanitized(client):
    up = _upload(client, [("../../evil<>.pdf", _pdf_bytes(1))])
    saved = up["files"][0]["id"]
    assert ".." not in saved and "<" not in saved and ">" not in saved


def test_download_rejects_bad_token(client):
    assert client.get("/api/tools/download/not-a-token/x.pdf").status_code == 400


def test_download_missing_file(client):
    up = _upload(client, [("a.pdf", _pdf_bytes(1))])
    resp = client.get(f"/api/tools/download/{up['token']}/ghost.pdf")
    assert resp.status_code == 404


def test_download_rejects_path_traversal(client):
    up = _upload(client, [("a.pdf", _pdf_bytes(1))])
    resp = client.get(f"/api/tools/download/{up['token']}/..%2F..%2Fworkbench.db")
    assert resp.status_code in (400, 404)


# --------------------------------------------------------------------------- #
# 留痕
# --------------------------------------------------------------------------- #
def test_successful_run_bumps_freq_and_records(client):
    tools_before = {t["id"]: t.get("freq", 0) for t in _data(client.get("/api/collections/tools"))}
    _data(_run(client, "student_board", {"scope": "全部学生"}))

    tools_after = {t["id"]: t.get("freq", 0) for t in _data(client.get("/api/collections/tools"))}
    bumped = [k for k in tools_before if tools_after[k] == tools_before[k] + 1]
    assert len(bumped) == 1

    runs = _data(client.get("/api/collections/tool_runs"))
    assert runs and runs[0]["tool"] == "student_board"
    assert runs[0]["created"] == today()


def test_failed_run_is_not_recorded(client):
    before = len(_data(client.get("/api/collections/tool_runs")))
    resp = _run(client, "grade_calc", {})  # 缺必填 -> 400
    assert resp.status_code == 400
    assert len(_data(client.get("/api/collections/tool_runs"))) == before


# --------------------------------------------------------------------------- #
# 异常路径：既不 5xx，也不静默失败
# --------------------------------------------------------------------------- #
def test_unparsable_grade_rows_gives_friendly_hint(client):
    """全部行无法解析时返回提示语（与原 JS / 桌面版行为一致）。"""
    data = _data(_run(client, "grade_calc", {
        "raw": "这不是成绩数据", "w_usual": "30", "w_mid": "20",
        "w_final": "50", "fail_line": "60", "curve": "0",
    }))
    assert "没有解析到有效数据行" in data["summary"]
    assert data["files"] == []


def test_partially_invalid_rows_are_reported(client):
    data = _data(_run(client, "grade_calc", {
        "raw": "李明 85 78 92\n这一行坏了\n王雪 90 88 95",
        "w_usual": "30", "w_mid": "20", "w_final": "50", "fail_line": "60", "curve": "0",
    }))
    assert data["metrics"][0] == ["学生数", "2", "人"]
    assert "未能解析的行" in data["text"]


def test_corrupt_pdf_is_handled(client):
    """上传损坏的 PDF 不应 500，而是给出可读的失败说明。"""
    up = _upload(client, [("broken.pdf", b"not a real pdf at all")])
    data = _data(_run(client, "pdf_toolkit", {
        "mode": "合并多个 PDF", "out_name": "", "ranges": "", "chunk": "1",
    }, files=[f["id"] for f in up["files"]]))
    assert data["summary"]
    assert data["files"] == []


def test_internal_exception_is_caught(monkeypatch):
    """工具内部抛异常时 run_tool 统一兜底为 ok=False，不向上冒泡。"""
    from backend.tools import TOOL_IMPLS, ToolContext, run_tool

    def boom(ctx):  # noqa: ARG001
        raise RuntimeError("模拟内部故障")

    monkeypatch.setitem(TOOL_IMPLS, "student_board", boom)
    with pytest.raises(RuntimeError):
        TOOL_IMPLS["student_board"](ToolContext(store=None, params={}))
    result = run_tool("student_board", ToolContext(store=None, params={}))
    assert result.ok is False
    assert "模拟内部故障" in result.summary


def test_export_json_is_valid_backup_shape(client):
    raw = client.get("/api/export").get_data(as_text=True)
    payload = json.loads(raw)
    assert payload["profile"]["name"] == "江老师"
    assert len(payload["tools"]) == 12
