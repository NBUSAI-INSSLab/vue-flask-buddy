"""Flask 应用工厂。

启动流程：建目录 → 建全局库（账号） → 引导账号与各租户库 → 注册 API → 托管前端。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from . import config, db


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        static_folder=str(config.FRONTEND_DIR),
        static_url_path="",  # 前端资源挂在根路径（/css/... /js/...）
    )
    app.config.update(
        USERS_DB_PATH=str(config.USERS_DB_PATH),
        MAX_CONTENT_LENGTH=64 * 1024 * 1024,  # 上传上限 64 MB
        SECRET_KEY=config.load_secret_key(),
        PERMANENT_SESSION_LIFETIME=config.SESSION_MAX_AGE,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.json.ensure_ascii = False  # 中文按原文输出，便于阅读与调试
    if config_overrides:
        app.config.update(config_overrides)

    config.ensure_dirs()
    db.register(app)
    db.init_db(app)
    _bootstrap_accounts(app)

    from .api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    # 清理过期上传/产物目录
    try:
        from .api.tools import purge_old_temp
        purge_old_temp()
    except Exception:  # noqa: BLE001
        pass

    # ---- 前端入口 ----
    @app.route("/")
    def index():
        return send_from_directory(config.FRONTEND_DIR, "index.html")

    @app.route("/c/<token>")
    def public_course(token):  # noqa: ARG001 — 令牌由前端脚本从 URL 解析
        """学生公开课程页：免登录，页面自取 /api/public/courses/<token>。"""
        return send_from_directory(config.FRONTEND_DIR, "course.html")

    @app.route("/favicon.ico")
    def favicon():
        return ("", 204)

    # ---- 统一 JSON 错误响应 ----
    @app.errorhandler(404)
    def not_found(err):  # noqa: ARG001
        return jsonify({"ok": False, "error": "接口或资源不存在"}), 404

    @app.errorhandler(405)
    def not_allowed(err):  # noqa: ARG001
        return jsonify({"ok": False, "error": "请求方法不允许"}), 405

    @app.errorhandler(413)
    def too_large(err):  # noqa: ARG001
        return jsonify({"ok": False, "error": "上传文件超过 64 MB 限制"}), 413

    @app.errorhandler(500)
    def server_error(err):  # noqa: ARG001
        return jsonify({"ok": False, "error": "服务器内部错误"}), 500

    return app


# --------------------------------------------------------------------------- #
# 账号与租户库引导
# --------------------------------------------------------------------------- #
def _bootstrap_accounts(app) -> None:
    """首次运行创建管理员与教师账号；为每位教师准备好独立数据空间。"""
    with app.app_context():
        migrate_legacy_db()

        from . import auth
        if auth.list_users():
            _ensure_tenant_spaces()
            _ensure_audit_fields()
            _ensure_course_fields()
            _ensure_link_seed()
            return

        from . import seed_teachers

        for u in seed_teachers.all_users():
            seed = (seed_teachers.initial_data(u)
                    if u["role"] == config.ROLE_TEACHER else None)
            auth.create_user(
                user_id=u["id"], username=u["username"], password=u["password"],
                role=u["role"], name=u["name"], title=u["title"], dept=u["dept"],
                email=u["email"], office=u["office"], seed=seed,
            )


def _ensure_audit_fields() -> None:
    """为存量成果补齐审核字段（v2 之前登记的成果没有审核状态）。"""
    from . import audit

    try:
        fixed = audit.ensure_all()
    except Exception:  # noqa: BLE001 - 回填失败不应阻断启动
        return
    if fixed:
        import logging
        logging.getLogger("fwb").info("已为 %d 条存量成果补齐审核字段", fixed)


def _ensure_course_fields() -> None:
    """为存量课程补齐开放设置与访问令牌（功能上线前登记的课程没有这些字段）。"""
    from . import courses

    try:
        fixed = courses.ensure_all()
    except Exception:  # noqa: BLE001
        return
    if fixed:
        import logging
        logging.getLogger("fwb").info("已为 %d 门存量课程补齐开放设置", fixed)


def _ensure_link_seed() -> int:
    """为存量工作台补上「常用网站」出厂清单（每个租户库只补一次）。"""
    from . import links

    try:
        added = links.ensure_all()
    except Exception:  # noqa: BLE001 - 补种失败不应阻断启动
        return 0
    if added:
        import logging
        logging.getLogger("fwb").info("已为存量工作台补入 %d 个常用网站", added)
    return added


def _ensure_tenant_spaces() -> None:
    """补齐缺失的租户库（例如手工删除过数据文件）。"""
    from . import auth, seed_teachers
    from .store import Store

    for user in auth.list_teachers():
        if config.tenant_db_path(user["id"]).exists():
            continue
        tpl = seed_teachers.TEACHER_BY_ID.get(user["id"])
        if tpl:
            data = seed_teachers.initial_data(tpl)
        else:
            data = seed_teachers.empty_seed({
                "name": user["name"], "title": user["title"], "dept": user["dept"],
                "email": user["email"], "office": user["office"],
            })
        Store(db.connect_tenant(user["id"])).replace_all(data)


def migrate_legacy_db() -> None:
    """把 v1 的单教师库 ``data/workbench.db`` 迁移为首位教师的租户库。"""
    legacy: Path = config.LEGACY_DB_PATH
    if not legacy.exists():
        return
    target = config.tenant_db_path(config.DEFAULT_TENANT_ID)
    try:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy), str(target))
        else:
            legacy.unlink()
    except OSError:
        return
    for suffix in ("-wal", "-shm"):
        leftover = legacy.with_name(legacy.name + suffix)
        try:
            leftover.unlink(missing_ok=True)
        except OSError:
            pass
