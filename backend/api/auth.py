"""认证接口：注册 / 登录 / 登出 / 当前用户。

注册的账号固定为「教师」角色；管理员账号由种子数据创建，或由已有管理员在
管理端新建（见 api/admin.py）。
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from .. import auth, config
from ..seed_teachers import demo_seed, empty_seed
from ..utils import uid

bp = Blueprint("auth", __name__)


def _ok(data, code: int = 200):
    return jsonify({"ok": True, "data": data}), code


def _err(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


def _payload(user: dict | None) -> dict:
    return {"user": user} if user else {"user": None}


# --------------------------------------------------------------------------- #
# 注册
# --------------------------------------------------------------------------- #
@bp.post("/auth/register")
def register():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _err("请求体必须是 JSON 对象")

    fields, error = auth.validate_register(payload)
    if error:
        return _err(error, 409 if "已被注册" in error else 400)

    profile = {k: fields[k] for k in ("name", "title", "dept", "email", "office")}
    with_demo = bool(payload.get("withDemo", True))
    initial = demo_seed(profile) if with_demo else empty_seed(profile)

    user = auth.create_user(
        user_id=uid("u"),
        username=fields["username"],
        password=fields["password"],
        role=config.ROLE_TEACHER,
        name=fields["name"],
        title=fields["title"],
        dept=fields["dept"],
        email=fields["email"],
        office=fields["office"],
        seed=initial,
    )
    auth.login_session(user)
    return _ok(_payload(user), 201)


# --------------------------------------------------------------------------- #
# 登录 / 登出
# --------------------------------------------------------------------------- #
@bp.post("/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    user, error = auth.verify_credentials(payload.get("username", ""), payload.get("password", ""))
    if error:
        return _err(error, 401)
    auth.login_session(user)
    return _ok(_payload(user))


@bp.post("/auth/logout")
def logout():
    auth.logout_session()
    return _ok({"loggedOut": True})


# --------------------------------------------------------------------------- #
# 当前用户
# --------------------------------------------------------------------------- #
@bp.get("/auth/me")
def me():
    user = auth.current_user()
    if user is None:
        return jsonify({"ok": False, "error": "未登录", "code": "unauthenticated"}), 401
    return _ok(_payload(user))
