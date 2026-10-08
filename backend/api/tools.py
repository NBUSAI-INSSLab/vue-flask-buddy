"""工具接口：字段规格、上传、运行、产物下载。

文件流：上传 → `data/uploads/<token>/`；运行产物 → `data/tmp/<token>/`，
前端拿到的是下载 URL，避免把大文件塞进 JSON。
"""
from __future__ import annotations

import re
import shutil
import secrets
import time

from flask import Blueprint, jsonify, request, send_file

from .. import config
from ..store import open_store
from ..tool_specs import all_specs, tool_specs
from ..tools import KEY_BY_URL, TOOL_IMPLS, ToolContext, run_tool
from ..utils import safe_name

bp = Blueprint("tools", __name__)

_URL_BY_KEY = {v: k for k, v in KEY_BY_URL.items()}
_TOKEN_RE = re.compile(r"^[0-9a-f]{8,32}$")


def _ok(data):
    return jsonify({"ok": True, "data": data})


def _err(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


def _new_token() -> str:
    return f"{int(time.time()):x}{secrets.token_hex(3)}"


def purge_old_temp(max_age_seconds: int = 2 * 24 * 3600) -> int:
    """清理 2 天前的上传 / 产物目录，避免磁盘无限增长。"""
    removed = 0
    now = time.time()
    for base in (config.UPLOAD_DIR, config.TMP_DIR):
        if not base.exists():
            continue
        for child in base.iterdir():
            try:
                if child.is_dir() and now - child.stat().st_mtime > max_age_seconds:
                    shutil.rmtree(child, ignore_errors=True)
                    removed += 1
            except OSError:
                continue
    return removed


# --------------------------------------------------------------------------- #
# 字段规格
# --------------------------------------------------------------------------- #
@bp.get("/tools/specs")
def specs_all():
    return _ok(all_specs(open_store()))


@bp.get("/tools/<key>/specs")
def specs_one(key: str):
    if key not in TOOL_IMPLS:
        return _err(f"未知工具：{key}", 404)
    return _ok(tool_specs(key, open_store()))


# --------------------------------------------------------------------------- #
# 上传
# --------------------------------------------------------------------------- #
@bp.post("/tools/upload")
def upload():
    incoming = request.files.getlist("files")
    if not incoming:
        return _err("没有收到文件")
    token = _new_token()
    folder = config.UPLOAD_DIR / token
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, fs in enumerate(incoming):
        original = fs.filename or f"file-{i}"
        name = safe_name(original.rsplit(".", 1)[0], 40) + _ext(original)
        fs.save(folder / name)
        saved.append({
            "id": f"{token}/{name}",
            "name": original,
            "size": (folder / name).stat().st_size,
        })
    return _ok({"token": token, "files": saved})


def _ext(filename: str) -> str:
    idx = filename.rfind(".")
    return filename[idx:].lower() if idx >= 0 else ""


def _load_uploads(ids: list[str]) -> list[dict]:
    """把上传 id 还原成 [{name, data}]，并做路径穿越校验。"""
    out = []
    root = config.UPLOAD_DIR.resolve()
    for fid in ids or []:
        parts = str(fid).split("/", 1)
        if len(parts) != 2 or not _TOKEN_RE.match(parts[0]):
            continue
        path = (root / parts[0] / parts[1]).resolve()
        if root not in path.parents or not path.is_file():
            continue
        out.append({"name": parts[1], "data": path.read_bytes()})
    return out


# --------------------------------------------------------------------------- #
# 运行
# --------------------------------------------------------------------------- #
@bp.post("/tools/<key>/run")
def run(key: str):
    if key not in TOOL_IMPLS:
        return _err(f"未知工具：{key}", 404)

    body = request.get_json(silent=True) or {}
    params = body.get("params") or {}
    if not isinstance(params, dict):
        return _err("params 必须是 JSON 对象")

    store = open_store()
    ctx = ToolContext(store=store, params=params, files=_load_uploads(body.get("files") or []))

    # 必填校验（与前端一致，服务端再兜一层）
    for field in tool_specs(key, store):
        if field.get("req") and field["type"] != "file":
            if str(params.get(field["name"], "") or "").strip() == "":
                return _err(f"请填写：{field['label']}")
        if field.get("req") and field["type"] == "file" and not ctx.files:
            return _err(f"请选择：{field['label']}")

    result = run_tool(key, ctx)

    # 留痕：工具频次 + 使用记录（仅成功时）
    if result.ok:
        try:
            tool = next((t for t in store.list("tools") if t.get("url") == _URL_BY_KEY.get(key)), None)
            if tool:
                store.bump_tool_freq(tool["id"])
            store.record_tool_run(key, (tool or {}).get("name", key), result.summary[:80])
        except Exception:  # noqa: BLE001 — 留痕失败不影响工具结果
            pass

    payload = {
        "summary": result.summary,
        "metrics": [list(m) for m in result.metrics],
        "text": result.text,
        "table": {"header": result.table[0], "rows": result.table[1]} if result.table else None,
        "log": result.log,
        "ok": result.ok,
        "files": _persist_outputs(result.files),
    }
    return _ok(payload)


def _persist_outputs(files) -> list[dict]:
    """把内存产物写入 tmp 目录并返回可下载的元信息。"""
    if not files:
        return []
    token = _new_token()
    folder = config.TMP_DIR / token
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    used: set[str] = set()
    for f in files:
        name = safe_name(f.name.rsplit(".", 1)[0], 56) + _ext(f.name)
        base, n = name, 1
        while name in used:
            stem, ext = base.rsplit(".", 1) if "." in base else (base, "")
            name = f"{stem}({n}).{ext}" if ext else f"{stem}({n})"
            n += 1
        used.add(name)
        (folder / name).write_bytes(f.data)
        out.append({
            "name": name,
            "mime": f.mime,
            "size": len(f.data),
            "url": f"/api/tools/download/{token}/{name}",
        })
    return out


# --------------------------------------------------------------------------- #
# 下载
# --------------------------------------------------------------------------- #
@bp.get("/tools/download/<token>/<path:name>")
def download(token: str, name: str):
    if not _TOKEN_RE.match(token) or "/" in name or "\\" in name:
        return _err("非法下载路径", 400)
    root = config.TMP_DIR.resolve()
    path = (root / token / name).resolve()
    if root not in path.parents or not path.is_file():
        return _err("文件不存在或已过期", 404)
    return send_file(path, as_attachment=True, download_name=name)
