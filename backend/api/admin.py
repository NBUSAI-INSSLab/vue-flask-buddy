"""管理端接口：教师列表 / 统计 / 账号管理 / 成果审核。

全部接口要求 ``role == admin``（见 ``auth.admin_required``）。
统计数据按需逐个打开教师的租户库汇总 —— 库很小，成本可忽略。
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from .. import analytics, audit, auth, config
from ..seed_teachers import demo_seed, empty_seed
from ..store import open_store
from ..utils import uid

bp = Blueprint("admin", __name__)

EDITABLE = ("name", "title", "dept", "email", "office", "role")

# 单次批量审核的上限，避免误触发超大请求
BATCH_LIMIT = 200
MAX_NOTE = 200


def _ok(data, code: int = 200):
    return jsonify({"ok": True, "data": data}), code


def _err(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


def _teacher_rows(users: list[dict]) -> list[dict]:
    rows = []
    for u in users:
        summary = analytics.teacher_summary(open_store(u["id"]))
        rows.append({**u, "summary": summary})
    return rows


def _review_payload() -> tuple[dict, str | None]:
    """读取并校验审核请求体。"""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return {}, "请求体必须是 JSON 对象"
    action = str(payload.get("action") or "")
    if action not in audit.ACTIONS:
        return {}, "审核动作只能是 approve / reject / reset"
    note = str(payload.get("note") or "").strip()
    if len(note) > MAX_NOTE:
        return {}, f"审核意见不能超过 {MAX_NOTE} 字"
    if action == "reject" and not note:
        return {}, "退回时必须填写审核意见"
    return {"action": action, "note": note}, None


# --------------------------------------------------------------------------- #
# 总览：全校汇总 + 每位教师一行
# --------------------------------------------------------------------------- #
@bp.get("/admin/overview")
@auth.admin_required
def overview():
    rows = _teacher_rows(auth.list_teachers())
    achievements = audit.collect()
    return _ok({
        "totals": analytics.totalize([r["summary"] for r in rows]),
        "teachers": rows,
        # 审核总数随总览一起下发，导航徽标无需再单独请求
        "audit": audit.stats(achievements),
    })


# --------------------------------------------------------------------------- #
# 教师列表
# --------------------------------------------------------------------------- #
@bp.get("/admin/teachers")
@auth.admin_required
def list_teachers():
    return _ok(_teacher_rows(auth.list_teachers()))


# --------------------------------------------------------------------------- #
# 教师详情：四类统计
# --------------------------------------------------------------------------- #
@bp.get("/admin/teachers/<teacher_id>")
@auth.admin_required
def teacher_detail(teacher_id: str):
    user = auth.get_user(teacher_id)
    if user is None or user["role"] != config.ROLE_TEACHER:
        return _err("教师不存在", 404)
    store = open_store(teacher_id)
    return _ok({
        "user": user,
        "profile": store.get_profile(),
        "summary": analytics.teacher_summary(store),
        "detail": analytics.teacher_detail(store),
    })


# --------------------------------------------------------------------------- #
# 新建 / 修改 / 删除
# --------------------------------------------------------------------------- #
@bp.post("/admin/teachers")
@auth.admin_required
def create_teacher():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _err("请求体必须是 JSON 对象")
    role = str(payload.get("role") or config.ROLE_TEACHER)
    if role not in (config.ROLE_ADMIN, config.ROLE_TEACHER):
        return _err("角色只能是 admin 或 teacher")
    if role == config.ROLE_ADMIN and not str(payload.get("password", "")):
        return _err("新建管理员必须设置密码")

    fields, error = auth.validate_register(payload)
    if error:
        return _err(error, 409 if "已被注册" in error else 400)

    profile = {k: fields[k] for k in ("name", "title", "dept", "email", "office")}
    with_demo = bool(payload.get("withDemo", False))
    initial = None
    if role == config.ROLE_TEACHER:
        initial = demo_seed(profile) if with_demo else empty_seed(profile)

    user = auth.create_user(
        user_id=uid("u"),
        username=fields["username"],
        password=fields["password"],
        role=role,
        name=fields["name"],
        title=fields["title"],
        dept=fields["dept"],
        email=fields["email"],
        office=fields["office"],
        seed=initial,
    )
    return _ok({"user": user}, 201)


@bp.patch("/admin/teachers/<teacher_id>")
@auth.admin_required
def update_teacher(teacher_id: str):
    user = auth.get_user(teacher_id)
    if user is None:
        return _err("账号不存在", 404)
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _err("请求体必须是 JSON 对象")

    if "role" in payload and payload["role"] not in (config.ROLE_ADMIN, config.ROLE_TEACHER):
        return _err("角色只能是 admin 或 teacher")
    if (user["role"] == config.ROLE_ADMIN and payload.get("role") == config.ROLE_TEACHER
            and auth.count_admins() <= 1):
        return _err("至少保留一个管理员账号")
    if "name" in payload and not str(payload.get("name", "")).strip():
        return _err("姓名不能为空")
    if "active" in payload and not payload["active"] and teacher_id == g.user["id"]:
        return _err("不能停用当前登录账号")

    patch = {k: payload[k] for k in payload if k in (*EDITABLE, "active")}
    return _ok({"user": auth.update_user(teacher_id, patch)})


@bp.post("/admin/teachers/<teacher_id>/password")
@auth.admin_required
def reset_password(teacher_id: str):
    if auth.get_user(teacher_id) is None:
        return _err("账号不存在", 404)
    payload = request.get_json(silent=True) or {}
    password = str(payload.get("password", ""))
    if len(password) < auth.MIN_PASSWORD:
        return _err(f"密码至少 {auth.MIN_PASSWORD} 位")
    auth.set_password(teacher_id, password)
    return _ok({"reset": True})


@bp.delete("/admin/teachers/<teacher_id>")
@auth.admin_required
def delete_teacher(teacher_id: str):
    if teacher_id == g.user["id"]:
        return _err("不能删除当前登录账号")
    try:
        removed = auth.delete_user(teacher_id)
    except ValueError as exc:
        return _err(str(exc))
    if not removed:
        return _err("账号不存在", 404)
    return _ok({"id": teacher_id, "deleted": True})


# --------------------------------------------------------------------------- #
# 成果审核
# --------------------------------------------------------------------------- #
@bp.get("/admin/achievements")
@auth.admin_required
def list_achievements():
    """全部教师的成果清单（默认返回全部状态，前端按标签页过滤）。"""
    status = str(request.args.get("status", "")).strip()
    if status and status not in audit.STATUSES:
        return _err("审核状态不正确")
    teacher_id = str(request.args.get("teacher", "")).strip()
    q = str(request.args.get("q", "")).strip()

    every = audit.collect()
    rows = audit.collect(status=status, teacher_id=teacher_id, q=q, users=auth.list_teachers())
    return _ok({
        "rows": audit.sort_rows(rows),
        "stats": audit.stats(rows),
        "allStats": audit.stats(every),
        "teachers": audit.teacher_options(every),
        "filter": {"status": status, "teacher": teacher_id, "q": q},
    })


@bp.post("/admin/achievements/review")
@auth.admin_required
def review_achievement():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _err("请求体必须是 JSON 对象")
    teacher_id = str(payload.get("teacherId") or "").strip()
    doc_id = str(payload.get("id") or "").strip()
    if not teacher_id or not doc_id:
        return _err("缺少 teacherId 或成果 id")
    teacher = auth.get_user(teacher_id)
    if teacher is None or teacher["role"] != config.ROLE_TEACHER:
        return _err("教师不存在", 404)

    fields, error = _review_payload()
    if error:
        return _err(error)

    updated = audit.review_one(teacher_id, doc_id, fields["action"],
                               fields["note"], g.user["name"])
    if updated is None:
        return _err("成果不存在", 404)
    return _ok({
        "achievement": audit.normalize(updated),
        "teacherId": teacher_id,
        "action": fields["action"],
        "stats": audit.stats(audit.collect()),
    })


@bp.post("/admin/achievements/batch-review")
@auth.admin_required
def batch_review():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _err("请求体必须是 JSON 对象")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return _err("请选择至少一条成果")
    if len(items) > BATCH_LIMIT:
        return _err(f"单次最多审核 {BATCH_LIMIT} 条")

    fields, error = _review_payload()
    if error:
        return _err(error)

    done, missing, invalid = [], [], 0
    for item in items:
        if not isinstance(item, dict):
            invalid += 1
            continue
        teacher_id = str(item.get("teacherId") or "").strip()
        doc_id = str(item.get("id") or "").strip()
        teacher = auth.get_user(teacher_id)
        if not teacher_id or not doc_id or teacher is None:
            invalid += 1
            continue
        updated = audit.review_one(teacher_id, doc_id, fields["action"],
                                   fields["note"], g.user["name"])
        if updated is None:
            missing.append(doc_id)
        else:
            done.append({"teacherId": teacher_id, "id": doc_id})

    return _ok({
        "reviewed": len(done),
        "items": done,
        "missing": missing,
        "invalid": invalid,
        "action": fields["action"],
        "stats": audit.stats(audit.collect()),
    })
