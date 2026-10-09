"""智能助手 —— 接口与模块用例。

覆盖：知识库解析分块与 BM25 检索、文档上传（multipart）/ 清单 / 删除、
LLM 配置读写（key 掩码回显）与连通测试的缺键分支、未配置大模型时
对话被拦截、mock 模型后的会话创建与消息落库、会话删除。
"""
from __future__ import annotations

import io

import pytest

from backend import agent_core, kb as kb_util, llm as llm_util

KB_TEXT = (
    "研究生学位论文写作规范：\n\n"
    "硕士论文正文字数不少于三万字，参考文献不少于四十篇。论文查重率不得超过百分之八。\n\n"
    "开题报告应当在第三学期结束前完成，中期检查安排在第五学期。"
)


# --------------------------------------------------------------------------- #
# 知识库模块（纯函数）
# --------------------------------------------------------------------------- #
def test_extract_text_rejects_unknown_ext():
    with pytest.raises(ValueError, match="不支持"):
        kb_util.extract_text("病毒.exe", b"MZ...")
    with pytest.raises(ValueError, match="不支持"):
        kb_util.extract_text("noext", b"abc")


def test_chunk_text_merges_and_caps():
    long_para = "这是超长段落。" * 200        # 1200 字，超过 CHUNK_SIZE，应硬切
    chunks = kb_util.chunk_text("短段落一。\n\n短段落二。\n\n" + long_para)
    assert len(chunks) >= 2
    assert all(len(c) <= kb_util.CHUNK_SIZE + kb_util.CHUNK_OVERLAP + 10 for c in chunks)
    assert kb_util.chunk_text("   \n\n  ") == []


def test_bm25_search_ranks_relevant_chunk_first(tmp_path):
    from backend.store import open_store
    from backend import create_app
    app = create_app()
    with app.app_context():
        store = open_store()
        d1 = kb_util.add_document(store, "写作规范.md", KB_TEXT.encode("utf-8"))
        d2 = kb_util.add_document(store, "网络课大纲.txt", "计算机网络课程共计 48 学时，期末闭卷考试。".encode("utf-8"))
        try:
            hits = kb_util.search(store, "查重率不能超过多少", top_k=3)
            assert hits, "应命中至少一条"
            assert hits[0]["docName"] == "写作规范.md"
            assert hits[0]["score"] >= hits[-1]["score"]
            miss = kb_util.search(store, "量子纠缠")
            assert miss == [] or all(h["docName"] != "写作规范.md" or "查重" in h["text"] for h in miss)
        finally:
            kb_util.delete_document(store, d1["id"])
            kb_util.delete_document(store, d2["id"])


def test_add_document_rejects_oversize(monkeypatch):
    from backend.store import open_store
    from backend import create_app
    app = create_app()
    with app.app_context():
        store = open_store()
        monkeypatch.setattr(kb_util, "MAX_FILE_BYTES", 10)
        with pytest.raises(ValueError, match="10MB"):
            kb_util.add_document(store, "大文件.txt", b"x" * 64)


# --------------------------------------------------------------------------- #
# LLM 配置
# --------------------------------------------------------------------------- #
def test_settings_default_and_masking(client):
    r = client.get("/api/agent/settings").get_json()
    assert r["ok"] and r["data"]["provider"] == "deepseek"
    assert r["data"]["ready"] is False          # 未填 key
    assert r["data"]["hasKey"] is False
    assert len(r["data"]["providers"]) >= 4

    r = client.put("/api/agent/settings", json={"apiKey": "sk-test-1234567890", "model": "deepseek-chat"}).get_json()
    assert r["ok"] and r["data"]["hasKey"] is True
    assert "sk-test-1234567890" not in r["data"]["keyMasked"]    # 不回显明文
    assert "***" in r["data"]["keyMasked"]

    # 掩码原样传回不覆盖真实 key
    r = client.put("/api/agent/settings", json={"apiKey": "***" + "x", "model": "deepseek-reasoner"}).get_json()
    assert r["ok"] and r["data"]["model"] == "deepseek-reasoner"
    assert r["data"]["hasKey"] is True          # key 未被掩码串覆盖


def test_settings_test_requires_key(client):
    r = client.post("/api/agent/settings/test",
                    json={"provider": "deepseek", "baseUrl": "https://api.deepseek.com/v1",
                          "model": "deepseek-chat"}).get_json()
    assert r["ok"] and r["data"]["ok"] is False and "Key" in r["data"]["message"]


# --------------------------------------------------------------------------- #
# 会话与对话
# --------------------------------------------------------------------------- #
def test_chat_blocked_without_llm(client):
    r = client.post("/api/agent/chat", json={"message": "今天有什么安排？"}).get_json()
    assert r["ok"] is False and r.get("code") == "llm_not_configured"


def test_chat_full_flow_with_mock(client, monkeypatch):
    calls = {}
    # 先配置好 LLM（mock 不真正联网，仅通过就绪校验）
    r = client.put("/api/agent/settings", json={"apiKey": "sk-mock-1234567890"}).get_json()
    assert r["ok"] and r["data"]["ready"] is True

    def fake_run_agent(store, history, message):
        calls["history_len"] = len(history)
        calls["message"] = message
        return {"content": "你今天有课题组例会（14:00，信息楼 A-513）。",
                "steps": [{"tool": "query_events", "args": {"keyword": ""}, "summary": "- 2026-10-08 14:00 课题组例会"}]}

    monkeypatch.setattr(agent_core, "run_agent", fake_run_agent)

    r = client.post("/api/agent/chat", json={"message": "我最近有什么日程？"})
    assert r.status_code == 200
    data = r.get_json()["data"]
    sid = data["sessionId"]
    assert data["message"]["role"] == "assistant"
    assert "课题组例会" in data["message"]["content"]
    assert data["message"]["steps"][0]["tool"] == "query_events"
    assert calls["message"] == "我最近有什么日程？"

    # 第二轮：历史应包含前两问两答
    r2 = client.post("/api/agent/chat", json={"sessionId": sid, "message": "地点在哪？"}).get_json()
    assert calls["history_len"] == 2
    assert r2["data"]["sessionId"] == sid

    # 会话列表 / 消息回读
    sessions = client.get("/api/agent/sessions").get_json()["data"]
    assert any(s["id"] == sid for s in sessions)
    msgs = client.get(f"/api/agent/sessions/{sid}/messages").get_json()["data"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]

    # 删除会话连同消息
    assert client.delete(f"/api/agent/sessions/{sid}").status_code == 200
    assert client.get(f"/api/agent/sessions/{sid}/messages").status_code == 404


def test_chat_validates_input(client, monkeypatch):
    monkeypatch.setattr(agent_core, "run_agent", lambda *a: {"content": "ok", "steps": []})
    assert client.post("/api/agent/chat", json={"message": "  "}).status_code == 400
    assert client.post("/api/agent/chat", json={"message": "x" * 5000}).status_code == 400


def test_chat_failure_leaves_no_trace(client, monkeypatch):
    """模型调用失败时不得留下「没有回答的孤立提问」，新建的空会话也要一并清理。"""
    client.put("/api/agent/settings", json={"apiKey": "sk-mock-1234567890"})
    before = len(client.get("/api/agent/sessions").get_json()["data"])

    def boom(*_a):
        raise RuntimeError(
            "SQLite objects created in a thread can only be used in that same thread")

    monkeypatch.setattr(agent_core, "run_agent", boom)
    r = client.post("/api/agent/chat", json={"message": "今天有什么安排？"})
    assert r.status_code == 502
    assert r.get_json()["code"] == "llm_error"
    assert len(client.get("/api/agent/sessions").get_json()["data"]) == before


def test_chat_failure_keeps_existing_session_clean(client, monkeypatch):
    """失败发生在已有会话里：只撤回本轮提问，会话与历史保留。"""
    client.put("/api/agent/settings", json={"apiKey": "sk-mock-1234567890"})
    monkeypatch.setattr(agent_core, "run_agent", lambda *a: {"content": "好", "steps": []})
    sid = client.post("/api/agent/chat", json={"message": "第一问"}).get_json()["data"]["sessionId"]

    def boom(*_a):
        raise PermissionError("尚未配置大模型（API Key），请先在「智能助手 → 设置」中完成配置。")

    monkeypatch.setattr(agent_core, "run_agent", boom)
    r = client.post("/api/agent/chat", json={"sessionId": sid, "message": "第二问"})
    assert r.status_code == 400
    assert r.get_json()["code"] == "llm_not_configured"
    msgs = client.get(f"/api/agent/sessions/{sid}/messages").get_json()["data"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]


# --------------------------------------------------------------------------- #
# 知识库接口
# --------------------------------------------------------------------------- #
def test_kb_upload_list_search_delete(client):
    data = {"files": (io.BytesIO(KB_TEXT.encode("utf-8")), "论文写作规范.md")}
    r = client.post("/api/agent/kb", data=data, content_type="multipart/form-data").get_json()
    assert r["ok"] and len(r["data"]["saved"]) == 1
    doc = r["data"]["saved"][0]
    assert doc["chunks"] >= 1 and doc["name"] == "论文写作规范.md"

    # 不支持的类型进入 failed
    r2 = client.post("/api/agent/kb",
                     data={"files": (io.BytesIO(b"evil"), "木马.exe")},
                     content_type="multipart/form-data").get_json()
    assert r2["data"]["failed"] and "不支持" in r2["data"]["failed"][0]["error"]

    # 清单带分块计数
    lst = client.get("/api/agent/kb").get_json()["data"]
    mine = [d for d in lst if d["id"] == doc["id"]]
    assert mine and mine[0]["chunks"] == doc["chunks"]

    # 检索接口
    r3 = client.get("/api/agent/kb/search?q=" + "查重率要求").get_json()
    assert r3["ok"] and r3["data"]["hits"]
    assert r3["data"]["hits"][0]["docName"] == "论文写作规范.md"
    assert "依据" not in r3["data"]["hits"][0]["text"]

    # 删除后检索不再命中
    assert client.delete(f"/api/agent/kb/{doc['id']}").status_code == 200
    r4 = client.get("/api/agent/kb/search?q=" + "查重率要求").get_json()
    assert r4["data"]["hits"] == []
    assert client.delete(f"/api/agent/kb/{doc['id']}").status_code == 404


def test_kb_requires_login(app):
    c = app.test_client()
    assert c.get("/api/agent/kb").status_code == 401
    assert c.get("/api/agent/sessions").status_code == 401
