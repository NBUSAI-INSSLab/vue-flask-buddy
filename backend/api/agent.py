"""智能助手接口：大模型设置、会话对话、知识库管理。

- ``GET/PUT  /api/agent/settings``        大模型配置（key 只回掩码）
- ``POST    /api/agent/settings/test``    连通性测试
- ``GET/POST /api/agent/sessions``        会话列表 / 新建
- ``GET/DEL  /api/agent/sessions/<id>``   会话消息 / 删除会话
- ``POST    /api/agent/chat``             发送消息（自动建会话，落库）
- ``GET     /api/agent/kb``               知识库文档清单
- ``POST    /api/agent/kb``               上传文档（multipart，多文件）
- ``DELETE  /api/agent/kb/<docId>``       删除文档（连同分块）
- ``GET     /api/agent/kb/search?q=``     检索测试（返回命中片段与出处）
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from .. import agent_core, kb as kb_util, llm as llm_util
from ..store import open_store

bp = Blueprint("agent", __name__)

CHAT_MSG_MAX = 4000          # 单条提问长度上限
HISTORY_LIMIT = 40           # 带入模型的历史条数上限
TITLE_MAX = 40


def _ok(data):
    return jsonify({"ok": True, "data": data})


def _err(message: str, code: int = 400, err_code: str | None = None):
    body = {"ok": False, "error": message}
    if err_code:
        body["code"] = err_code
    return jsonify(body), code


# --------------------------------------------------------------------------- #
# 大模型设置
# --------------------------------------------------------------------------- #
@bp.get("/agent/settings")
def get_settings():
    return _ok(llm_util.public_llm_config(open_store()))


@bp.put("/agent/settings")
def put_settings():
    return _ok(llm_util.save_llm_config(open_store(), request.get_json(silent=True) or {}))


@bp.post("/agent/settings/test")
def test_settings():
    payload = request.get_json(silent=True) or {}
    if payload.get("apiKey", "").startswith("***"):
        # 掩码 key 原样传回时，替换为库里真实 key 再测
        cfg = llm_util.real_llm_config(open_store())
        for k in ("provider", "baseUrl", "model", "temperature"):
            if k in payload:
                cfg[k] = payload[k]
        result = llm_util.test_llm(cfg)
    else:
        merged = llm_util.real_llm_config(open_store())
        merged.update({k: payload[k] for k in ("provider", "baseUrl", "apiKey", "model", "temperature")
                       if k in payload})
        result = llm_util.test_llm(merged)
    return _ok(result)


# --------------------------------------------------------------------------- #
# 会话与对话
# --------------------------------------------------------------------------- #
def _session(store, session_id: str) -> dict | None:
    return store.get("agent_sessions", session_id)


def _messages(store, session_id: str) -> list[dict]:
    msgs = [m for m in store.list("agent_messages") if m.get("sessionId") == session_id]
    msgs.sort(key=lambda m: m.get("seq", 0))
    return msgs


@bp.get("/agent/sessions")
def list_sessions():
    store = open_store()
    items = store.list("agent_sessions")
    for s in items:
        s["messages"] = len(_messages(store, s["id"]))
    items.sort(key=lambda s: s.get("updatedAt", ""), reverse=True)
    return _ok(items)


@bp.post("/agent/sessions")
def create_session():
    store = open_store()
    title = (request.get_json(silent=True) or {}).get("title") or "新的对话"
    s = store.add("agent_sessions", {"title": title[:TITLE_MAX], "createdAt": _now(),
                                     "updatedAt": _now()}, prefix="as")
    return _ok(s)


@bp.delete("/agent/sessions/<sid>")
def drop_session(sid: str):
    store = open_store()
    if not _session(store, sid):
        return _err("会话不存在", 404)
    for m in _messages(store, sid):
        store.remove("agent_messages", m["id"])
    return _ok({"deleted": store.remove("agent_sessions", sid)})


@bp.get("/agent/sessions/<sid>/messages")
def session_messages(sid: str):
    store = open_store()
    if not _session(store, sid):
        return _err("会话不存在", 404)
    return _ok(_messages(store, sid))


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


@bp.post("/agent/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message") or "").strip()
    if not message:
        return _err("请输入内容")
    if len(message) > CHAT_MSG_MAX:
        return _err(f"单条消息不能超过 {CHAT_MSG_MAX} 字")

    store = open_store()
    if not llm_util.get_llm_config(store).get("ready"):
        return _err("尚未配置大模型：请打开「设置」填写 API Key 后再对话。",
                    400, "llm_not_configured")

    sid = payload.get("sessionId")
    session = _session(store, sid) if sid else None
    created_here = session is None
    if session is None:
        session = store.add("agent_sessions",
                            {"title": message[:TITLE_MAX], "createdAt": _now(),
                             "updatedAt": _now()}, prefix="as")
        sid = session["id"]

    history = [{"role": m["role"], "content": m["content"]}
               for m in _messages(store, sid)][-HISTORY_LIMIT:]
    umsg = store.add("agent_messages", {"sessionId": sid, "role": "user",
                                        "content": message[:CHAT_MSG_MAX], "seq": _next_seq(store)},
                     prefix="am")
    try:
        result = agent_core.run_agent(store, history, message)
    except Exception as exc:  # noqa: BLE001 —— 网络/模型错误转可读提示
        # 失败就把这轮提问撤回：否则会话里会留下没有回答的孤立提问，
        # 前端「输入还原」后重发还会在历史里产生重复。会话是本次新建且已空则一并删除。
        store.remove("agent_messages", umsg["id"])
        if created_here and not _messages(store, sid):
            store.remove("agent_sessions", sid)
        if isinstance(exc, PermissionError):
            return _err(str(exc), 400, "llm_not_configured")
        return _err(f"模型调用失败：{str(exc)[:200]}", 502, "llm_error")

    reply = store.add("agent_messages", {
        "sessionId": sid, "role": "assistant", "content": result["content"][:8000],
        "steps": result["steps"][:20], "seq": _next_seq(store),
    }, prefix="am")
    store.update("agent_sessions", sid, {"updatedAt": _now()})
    return _ok({"sessionId": sid, "message": reply})


def _next_seq(store) -> int:
    """会话内消息序号：按全局最大 seq 递增（保证排序稳定）。"""
    msgs = store.list("agent_messages")
    return max((int(m.get("seq", 0)) for m in msgs), default=0) + 1


# --------------------------------------------------------------------------- #
# 知识库
# --------------------------------------------------------------------------- #
@bp.get("/agent/kb")
def kb_list():
    return _ok(kb_util.list_docs(open_store()))


@bp.post("/agent/kb")
def kb_upload():
    files = request.files.getlist("files") or ([request.files["file"]]
                                               if "file" in request.files else [])
    if not files:
        return _err("请选择要上传的文件")
    store = open_store()
    saved, failed = [], []
    for f in files:
        name = f.filename or "未命名"
        try:
            doc = kb_util.add_document(store, name, f.read())
            saved.append(doc)
        except ValueError as exc:
            failed.append({"name": name, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            failed.append({"name": name, "error": f"解析失败：{str(exc)[:120]}"})
    return _ok({"saved": saved, "failed": failed})


@bp.delete("/agent/kb/<doc_id>")
def kb_delete(doc_id: str):
    if not kb_util.delete_document(open_store(), doc_id):
        return _err("文档不存在", 404)
    return _ok({"deleted": True})


@bp.get("/agent/kb/search")
def kb_search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return _err("请输入检索问题")
    top_k = min(int(request.args.get("top", 5) or 5), 10)
    return _ok({"query": q, "hits": kb_util.search(open_store(), q, top_k=top_k)})
