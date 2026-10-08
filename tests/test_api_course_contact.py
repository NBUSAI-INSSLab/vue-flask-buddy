"""课程助教 / 联系方式与教学日历 —— 接口用例。

覆盖：日历与助教名单清洗（白名单 / 去空行 / 自动补周次 / 截断）、
QQ 群号清洗、补丁只改显式传入的键、群二维码上传与内容嗅探、
读取与公开下发、跨课程路径越权防护、删除清理、未开放课程不下发二维码。
"""
from __future__ import annotations

import io
import struct
import zlib

import pytest

from backend import courses as courses_util
from backend.store import open_store

from conftest import TEACHER_ID

C1 = "c1"          # 计算机网络：种子默认长期开放
C3 = "c3"          # Python 程序设计：种子默认关闭


def _png() -> bytes:
    """最小但可解码的 1×1 PNG（服务端按内容嗅探类型）。"""
    def chunk(tag: bytes, data: bytes) -> bytes:
        blob = struct.pack(">I", len(data)) + tag + data
        return blob + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _share_token(store, course_id: str) -> str:
    return store.get("courses", course_id)["shareToken"]


# --------------------------------------------------------------------------- #
# 清洗函数
# --------------------------------------------------------------------------- #
def test_clean_calendar_keeps_whitelist_and_drops_empty():
    rows = [
        {"week": "第 1 周", "date": "2026-08-13", "topic": "导论", "hours": "4",
         "type": "讲授", "note": "", "hacker": "<script>"},
        {"week": "", "date": "", "topic": "", "hours": "", "type": "", "note": ""},
        {"topic": "实验课", "hours": 2},
        "not-a-dict",
    ]
    out = courses_util.clean_calendar(rows)
    assert len(out) == 2
    assert out[0] == {"week": "第 1 周", "date": "2026-08-13", "topic": "导论",
                      "hours": "4", "type": "讲授", "note": ""}
    assert "hacker" not in out[0]
    assert out[1]["week"] == "第 2 周", "周次缺失时按顺序自动补齐"
    assert out[1]["hours"] == "2"


def test_clean_calendar_rejects_non_list_and_caps_rows():
    assert courses_util.clean_calendar(None) == []
    assert courses_util.clean_calendar("abc") == []
    many = [{"topic": f"w{i}"} for i in range(200)]
    assert len(courses_util.clean_calendar(many)) == courses_util.CAL_MAX_ROWS


def test_sanitize_contact_trims_qq():
    patch = courses_util.sanitize_contact({"qqGroup": "  736285914  ", "calendar": []})
    assert patch == {"qqGroup": "736285914", "calendar": []}
    assert courses_util.sanitize_contact({"note": "x"}) == {}


def test_sanitize_contact_only_touches_given_keys():
    """只改助教时不能顺带清空 QQ 群与日历（补丁语义）。"""
    patch = courses_util.sanitize_contact({"assistants": [{"name": "李明"}]})
    assert set(patch) == {"assistants"}


# --------------------------------------------------------------------------- #
# 助教名单清洗
# --------------------------------------------------------------------------- #
def test_clean_assistants_keeps_whitelist_and_drops_empty():
    rows = [
        {"name": "李明", "role": "博士生助教", "phone": "138 0000 2417",
         "email": "liming@university.edu.cn", "qq": "402178536", "note": "实验课答疑",
         "hacker": "<script>alert(1)</script>"},
        {"name": "", "role": "", "phone": "", "email": "", "qq": "", "note": ""},
        {"name": "  王雪  ", "phone": " 139 0000 5521 "},
        "not-a-dict",
        {"name": "只留电话也算有效", "phone": "13700000000"},
    ]
    out = courses_util.clean_assistants(rows)
    assert len(out) == 3, "全空占位行与非字典项被丢弃"
    assert out[0] == {"name": "李明", "role": "博士生助教", "phone": "138 0000 2417",
                      "email": "liming@university.edu.cn", "qq": "402178536",
                      "note": "实验课答疑"}
    assert "hacker" not in out[0], "非白名单字段不下发"
    assert out[1]["name"] == "王雪" and out[1]["phone"] == "139 0000 5521"
    assert out[1]["role"] == "" and out[1]["note"] == ""


def test_clean_assistants_rejects_non_list_and_caps():
    assert courses_util.clean_assistants(None) == []
    assert courses_util.clean_assistants({"name": "李明"}) == []
    many = [{"name": f"助教{i}"} for i in range(40)]
    assert len(courses_util.clean_assistants(many)) == courses_util.TA_MAX


def test_clean_assistants_truncates_long_text():
    out = courses_util.clean_assistants([{"name": "名" * 200, "note": "备" * 400}])
    assert len(out[0]["name"]) == courses_util.TA_TEXT_MAX
    assert len(out[0]["note"]) == courses_util.TA_NOTE_MAX


# --------------------------------------------------------------------------- #
# 教师端接口
# --------------------------------------------------------------------------- #
def test_contact_roundtrip(client, store):
    r = client.get(f"/api/courses/{C1}/contact")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["courseId"] == C1
    assert isinstance(data["calendar"], list) and isinstance(data["qqGroup"], str)

    payload = {"qqGroup": " 98765 ",
               "calendar": [{"topic": "导论", "hours": "4", "type": "讲授", "note": ""}]}
    r = client.post(f"/api/courses/{C1}/contact", json=payload)
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["qqGroup"] == "98765"
    assert len(data["calendar"]) == 1 and data["calendar"][0]["week"] == "第 1 周"
    assert store.get("courses", C1)["qqGroup"] == "98765"


def test_contact_requires_payload(client):
    assert client.post(f"/api/courses/{C1}/contact", json={}).status_code == 400
    assert client.post(f"/api/courses/{C1}/contact", json={"qqGroup": "123"}).status_code == 200


def test_contact_unknown_course(client):
    assert client.get("/api/courses/nope/contact").status_code == 404
    assert client.post("/api/courses/nope/contact", json={"qqGroup": "1"}).status_code == 404


def test_contact_returns_seed_assistants(client):
    """种子课程自带助教名单，读取接口原样返回（清洗后）。"""
    data = client.get(f"/api/courses/{C1}/contact").get_json()["data"]
    names = [t["name"] for t in data["assistants"]]
    assert names == ["李明", "王雪"]
    assert set(data["assistants"][0]) == set(courses_util.TA_FIELDS)
    assert data["assistants"][0]["phone"] != ""


def test_contact_saves_assistants_and_keeps_other_fields(client, store):
    """保存助教名单：空行丢弃、首尾空格裁剪，且不连带清空 QQ 群与日历。"""
    payload = {"assistants": [
        {"name": "  赵一  ", "role": "实验助教", "phone": "138 0000 0001",
         "email": "zhaoyi@university.edu.cn", "qq": "123456", "note": "周三值班"},
        {"name": "", "role": "", "phone": "", "email": "", "qq": "", "note": ""},
    ]}
    r = client.post(f"/api/courses/{C1}/contact", json=payload)
    assert r.status_code == 200
    out = r.get_json()["data"]["assistants"]
    assert len(out) == 1 and out[0]["name"] == "赵一"
    assert store.get("courses", C1)["assistants"] == out
    doc = store.get("courses", C1)
    assert doc["qqGroup"] == "736285914", "未传入的字段保持原值"
    assert len(doc.get("calendar") or []) >= 1, "教学日历不被清空"


def test_contact_clears_assistants_with_empty_list(client, store):
    r = client.post(f"/api/courses/{C1}/contact", json={"assistants": []})
    assert r.status_code == 200 and r.get_json()["data"]["assistants"] == []
    assert store.get("courses", C1)["assistants"] == []


def test_contact_rejects_non_list_assistants(client, store):
    """非法类型不报错，按空名单清洗（不会把文档写成非列表）。"""
    r = client.post(f"/api/courses/{C1}/contact", json={"assistants": {"name": "李明"}})
    assert r.status_code == 200 and r.get_json()["data"]["assistants"] == []
    assert store.get("courses", C1)["assistants"] == []


def test_qr_upload_sniff_and_replace(client, store):
    # 非图片内容应被拒绝
    r = client.post(f"/api/courses/{C1}/qr",
                    data={"file": (io.BytesIO(b"plain text"), "x.png")},
                    content_type="multipart/form-data")
    assert r.status_code == 400

    r = client.post(f"/api/courses/{C1}/qr",
                    data={"file": (io.BytesIO(_png()), "qr.png")},
                    content_type="multipart/form-data")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["hasQr"] is True
    assert store.get("courses", C1)["qqQr"].startswith(f"{TEACHER_ID}/{C1}/qr.")

    # 再次上传 → 覆盖（不残留多份 qr.*）
    client.post(f"/api/courses/{C1}/qr",
                data={"file": (io.BytesIO(_png()), "qr.png")},
                content_type="multipart/form-data")
    folder = courses_util.material_dir(TEACHER_ID, C1)
    assert len(list(folder.glob("qr.*"))) == 1


def test_qr_read_and_delete(client, store):
    client.post(f"/api/courses/{C1}/qr",
                data={"file": (io.BytesIO(_png()), "qr.png")},
                content_type="multipart/form-data")
    r = client.get(f"/api/courses/{C1}/qr")
    assert r.status_code == 200 and r.content_type == "image/png"
    assert len(r.data) > 0, "读取响应体以关闭 send_file 句柄（Windows 文件占用）"

    r = client.delete(f"/api/courses/{C1}/qr")
    assert r.status_code == 200 and r.get_json()["data"]["hasQr"] is False
    assert store.get("courses", C1)["qqQr"] == ""
    assert client.get(f"/api/courses/{C1}/qr").status_code == 404


def test_qr_cross_course_path_blocked(client, store):
    """把 c1 的 qqQr 指到 c2 的目录 → 归属校验应拦截。"""
    client.post(f"/api/courses/c2/qr",
                data={"file": (io.BytesIO(_png()), "qr.png")},
                content_type="multipart/form-data")
    store.update("courses", C1, {"qqQr": f"{TEACHER_ID}/c2/qr.png"})
    assert client.get(f"/api/courses/{C1}/qr").status_code == 404
    # 公开侧同样拦截
    token = _share_token(store, C1)
    assert client.get(f"/api/public/courses/{token}/qr").status_code == 404
    # 清理
    store.update("courses", C1, {"qqQr": ""})
    client.delete("/api/courses/c2/qr")


# --------------------------------------------------------------------------- #
# 公开侧
# --------------------------------------------------------------------------- #
def test_public_payload_includes_contact_and_calendar(client, store):
    client.post(f"/api/courses/{C1}/qr",
                data={"file": (io.BytesIO(_png()), "qr.png")},
                content_type="multipart/form-data")
    token = _share_token(store, C1)
    r = client.get(f"/api/public/courses/{token}")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["qqGroup"] == "736285914"
    assert data["hasQr"] is True
    assert len(data["calendar"]) >= 1
    assert set(data["calendar"][0]) == {"week", "date", "topic", "hours", "type", "note"}
    # 助教名单：只下发白名单字段
    assert [t["name"] for t in data["assistants"]] == ["李明", "王雪"]
    assert set(data["assistants"][0]) == {"name", "role", "phone", "email", "qq", "note"}
    # 手机号来自教师工作台资料（users 表没有该列）
    assert data["teacher"]["phone"] != ""

    img = client.get(f"/api/public/courses/{token}/qr")
    assert img.status_code == 200 and img.content_type == "image/png"
    assert len(img.data) > 0
    client.delete(f"/api/courses/{C1}/qr")


def test_public_qr_blocked_when_course_closed(client, store):
    client.post(f"/api/courses/{C3}/qr",
                data={"file": (io.BytesIO(_png()), "qr.png")},
                content_type="multipart/form-data")
    token = _share_token(store, C3)
    r = client.get(f"/api/public/courses/{token}/qr")
    assert r.status_code == 403, "未开放课程不下发二维码"
    r = client.get(f"/api/public/courses/{token}")
    assert r.status_code == 403
    body = r.get_json()
    assert "assistants" not in (body.get("course") or {}), "关闭态不泄漏助教联系方式"
    assert "data" not in body or body.get("data") is None, "关闭态不下发正文"
    client.delete(f"/api/courses/{C3}/qr")


def test_public_qr_invalid_token(client):
    assert client.get("/api/public/courses/deadbeefdeadbeef/qr").status_code == 404


def test_public_qr_without_upload(client, store):
    token = _share_token(store, C1)
    assert client.get(f"/api/public/courses/{token}/qr").status_code == 404
