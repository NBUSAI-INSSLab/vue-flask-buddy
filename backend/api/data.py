"""数据接口：集合 CRUD、个人信息、统计、搜索、导入导出与重置。

约定：所有响应形如 ``{"ok": true, "data": ...}``，失败为 ``{"ok": false, "error": "..."}``。
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from .. import audit, config
from ..seed import full_seed
from ..store import open_store

bp = Blueprint("data", __name__)

# 全局搜索：集合 -> 参与匹配的字段
SEARCH_FIELDS = {
    "projects": ("name", "code", "desc", "type"),
    "literature": ("title", "authors", "journal", "note", "direction"),
    "courses": ("name", "code", "intro"),
    "students": ("name", "direction", "thesisTitle", "stage"),
    "events": ("title", "note", "location", "type"),
    "todos": ("title", "tag"),
    "exchanges": ("title", "organizer", "topic", "note", "location"),
    "teachings": ("name", "code", "note", "type"),
    "achievements": ("title", "venue", "authors", "note", "type", "level"),
    "developments": ("title", "target", "current", "category"),
    "educations": ("school", "major", "degree", "supervisor", "note"),
    "services": ("org", "role", "kind", "note"),
    "tools": ("name", "desc", "category"),
    "links": ("name", "url", "group", "note"),
}

# 搜索结果点击后跳转的页面
SEARCH_PAGE = {
    "projects": "projects", "literature": "literature", "courses": "courses",
    "students": "students", "events": "schedule", "todos": "dashboard",
    "exchanges": "exchanges", "teachings": "teachings", "achievements": "achievements",
    "developments": "developments", "educations": "cv", "services": "cv",
    "tools": "tools", "links": "dashboard",
}

# 搜索结果条目前缀
SEARCH_LABEL = {
    "projects": "科研项目", "literature": "文献", "courses": "课程",
    "students": "学生", "events": "日程", "todos": "待办", "exchanges": "学术交流",
    "teachings": "教学", "achievements": "成果", "developments": "个人发展", "tools": "工具",
    "educations": "教育经历", "services": "社会服务",
    "links": "常用网站",
}


def _ok(data):
    return jsonify({"ok": True, "data": data})


def _err(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


def _check_collection(name: str) -> bool:
    return name in config.COLLECTIONS


# --------------------------------------------------------------------------- #
# 全量状态（前端启动时一次拉取）
# --------------------------------------------------------------------------- #
@bp.get("/state")
def get_state():
    store = open_store()
    data = store.export()
    # 成果附带审核状态，教师端据此展示「待审核 / 已通过 / 已退回」徽标
    data["achievements"] = audit.decorate(data.get("achievements") or [])
    data["stats"] = store.stats()
    data["meta"] = {
        "schemaVersion": config.SCHEMA_VERSION,
        "collections": config.COLLECTIONS,
    }
    return _ok(data)


@bp.get("/stats")
def get_stats():
    store = open_store()
    return _ok({
        "overview": store.stats(),
        "achievements": store.achievement_stats(),
        "teaching": store.teaching_load(),
        "development": store.development_progress(),
        "toolCategories": store.tool_categories(),
    })


# --------------------------------------------------------------------------- #
# 集合 CRUD
# --------------------------------------------------------------------------- #
@bp.get("/collections/<coll>")
def list_collection(coll: str):
    if not _check_collection(coll):
        return _err(f"未知集合：{coll}", 404)
    return _ok(open_store().list(coll))


@bp.post("/collections/<coll>")
def create_item(coll: str):
    if not _check_collection(coll):
        return _err(f"未知集合：{coll}", 404)
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict) or not payload:
        return _err("请求体必须是非空 JSON 对象")
    if coll == "achievements":
        # 新登记的成果自动进入待审核队列
        author = (getattr(g, "user", None) or {}).get("name") or "本人"
        payload = audit.prepare_new(payload, author)
    item = open_store().add(coll, payload)
    return _ok(item), 201


@bp.patch("/collections/<coll>/<doc_id>")
def update_item(coll: str, doc_id: str):
    if not _check_collection(coll):
        return _err(f"未知集合：{coll}", 404)
    patch = request.get_json(silent=True) or {}
    if not isinstance(patch, dict) or not patch:
        return _err("请求体必须是非空 JSON 对象")
    store = open_store()
    if coll == "achievements":
        current = store.get(coll, doc_id)
        # 已出审核结论的成果被修改后，需要重新走一次审核
        if current and audit.needs_resubmit(current, patch):
            patch = dict(patch, **audit.resubmit_patch(current))
    updated = store.update(coll, doc_id, patch)
    if updated is None:
        return _err("记录不存在", 404)
    return _ok(updated)


@bp.delete("/collections/<coll>/<doc_id>")
def delete_item(coll: str, doc_id: str):
    if not _check_collection(coll):
        return _err(f"未知集合：{coll}", 404)
    if not open_store().remove(coll, doc_id):
        return _err("记录不存在", 404)
    if coll == "courses":
        # 课程删除后其资料目录不再被引用，一并清理，避免磁盘留下孤儿文件
        try:
            from .. import courses as courses_util
            courses_util.purge_course_files(g.user_id, doc_id)
        except Exception:  # noqa: BLE001 - 清理失败不影响删除结果
            pass
    return _ok({"id": doc_id, "deleted": True})


# --------------------------------------------------------------------------- #
# 个人信息
# --------------------------------------------------------------------------- #
@bp.get("/profile")
def get_profile():
    return _ok(open_store().get_profile())


@bp.put("/profile")
def put_profile():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _err("请求体必须是 JSON 对象")
    name = str(payload.get("name", "")).strip()
    if not name:
        return _err("姓名不能为空")
    return _ok(open_store().set_profile(payload))


# --------------------------------------------------------------------------- #
# 全局搜索
# --------------------------------------------------------------------------- #
@bp.get("/search")
def search():
    q = str(request.args.get("q", "")).strip().lower()
    if not q:
        return _ok([])
    store = open_store()
    hits = []
    for coll, fields in SEARCH_FIELDS.items():
        for item in store.list(coll):
            haystack = " ".join(str(item.get(f, "")) for f in fields)
            tags = item.get("tags")
            if isinstance(tags, list):
                haystack += " " + " ".join(str(t) for t in tags)
            if q in haystack.lower():
                hits.append({
                    "collection": coll,
                    "id": item.get("id", ""),
                    "label": SEARCH_LABEL.get(coll, coll),
                    "page": SEARCH_PAGE.get(coll, "dashboard"),
                    "title": _title_of(coll, item),
                    "sub": _sub_of(coll, item),
                })
    return _ok(hits[:60])


def _title_of(coll: str, item: dict) -> str:
    for k in ("name", "title", "chapter"):
        if item.get(k):
            return str(item[k])
    return str(item.get("id", ""))


def _sub_of(coll: str, item: dict) -> str:
    parts = []
    for k in ("code", "type", "date", "journal", "venue", "status", "stage",
              "category", "direction", "group", "degree", "school", "kind", "org", "role"):
        if item.get(k):
            parts.append(str(item[k]))
    return " · ".join(parts[:3])


# --------------------------------------------------------------------------- #
# 导入 / 导出 / 重置
# --------------------------------------------------------------------------- #
@bp.get("/export")
def export_json():
    store = open_store()
    return jsonify(store.export())


@bp.post("/import")
def import_json():
    payload = request.get_json(silent=True, force=True)
    if payload is None:
        return _err("请求体不是合法 JSON")
    data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
    if not isinstance(data, dict) or not isinstance(data.get("profile"), dict):
        return _err("不是本工作台的备份文件（缺少 profile 字段）")
    store = open_store()
    store.replace_all(store.migrate(data))
    return _ok({"imported": True, "collections": len(config.COLLECTIONS)})


@bp.post("/reset")
def reset_data():
    store = open_store()
    store.replace_all(full_seed())
    return _ok({"reset": True})
