"""API 蓝图汇总与统一鉴权。

除白名单（注册 / 登录 / 登出 / 当前用户 / 学生侧公开课程 / 访客侧公开简历）外，
所有接口都要求已登录；登录后 ``g.user`` / ``g.user_id`` 即当前账号，
各接口据此选租户库。
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from .. import auth as auth_util
from .admin import bp as admin_bp
from .agent import bp as agent_bp
from .auth import bp as auth_bp
from .courses import bp as courses_bp
from .cv import bp as cv_bp
from .data import bp as data_bp
from .links import bp as links_bp
from .public import bp as public_bp
from .tools import bp as tools_bp

bp = Blueprint("api", __name__)
bp.register_blueprint(auth_bp)
bp.register_blueprint(agent_bp)
bp.register_blueprint(data_bp)
bp.register_blueprint(tools_bp)
bp.register_blueprint(admin_bp)
bp.register_blueprint(courses_bp)
bp.register_blueprint(cv_bp)
bp.register_blueprint(links_bp)
bp.register_blueprint(public_bp)

# 无需登录即可访问（注意是完整路径，蓝图挂在 /api 前缀下）
OPEN_PATHS = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/logout",
    "/api/auth/me",
}

# 学生侧公开课程 / 访客侧公开简历：整段放行（持有令牌即访问，天然无账号）
OPEN_PREFIXES = ("/api/public/",)


def is_open(path: str) -> bool:
    return path in OPEN_PATHS or path.startswith(OPEN_PREFIXES)


@bp.before_request
def _authenticate():
    if is_open(request.path):
        return None
    user = auth_util.current_user()
    if user is None:
        return jsonify({"ok": False, "error": "请先登录", "code": "unauthenticated"}), 401
    g.user = user
    g.user_id = user["id"]
    return None
