"""账号与鉴权：用户 CRUD、密码哈希、登录态、权限装饰器。

- 密码用 ``werkzeug.security``（PBKDF2-SHA256，自带盐）哈希，绝不明文落库；
- 登录态用 Flask 签名 Cookie session（密钥持久化在 ``data/secret.key``）；
- 每位教师在 ``tenants/<uid>.db`` 拥有独立数据空间，注册时一并创建。
"""
from __future__ import annotations

import re
from datetime import datetime
from functools import wraps

from flask import g, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash

from . import config, db

USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")
MIN_PASSWORD = 6

ROLE_LABEL = {config.ROLE_ADMIN: "管理员", config.ROLE_TEACHER: "教师"}


# --------------------------------------------------------------------------- #
# 行 → 字典
# --------------------------------------------------------------------------- #
def _to_user(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "roleLabel": ROLE_LABEL.get(row["role"], row["role"]),
        "name": row["name"],
        "title": row["title"] or "",
        "dept": row["dept"] or "",
        "email": row["email"] or "",
        "office": row["office"] or "",
        "active": bool(row["active"]),
        "createdAt": row["created_at"] or "",
        "lastLogin": row["last_login"] or "",
    }


# --------------------------------------------------------------------------- #
# 查询
# --------------------------------------------------------------------------- #
def get_user(user_id: str) -> dict | None:
    row = db.get_users_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _to_user(row) if row else None


def get_user_by_username(username: str) -> dict | None:
    row = db.get_users_db().execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
    ).fetchone()
    return _to_user(row) if row else None


def list_users(role: str | None = None) -> list[dict]:
    sql = "SELECT * FROM users"
    args: tuple = ()
    if role:
        sql += " WHERE role = ?"
        args = (role,)
    sql += " ORDER BY created_at ASC, id ASC"
    rows = db.get_users_db().execute(sql, args).fetchall()
    return [_to_user(r) for r in rows]


def list_teachers() -> list[dict]:
    return list_users(config.ROLE_TEACHER)


def count_admins() -> int:
    row = db.get_users_db().execute(
        "SELECT COUNT(*) AS n FROM users WHERE role = ?", (config.ROLE_ADMIN,)
    ).fetchone()
    return int(row["n"])


# --------------------------------------------------------------------------- #
# 写入
# --------------------------------------------------------------------------- #
def create_user(*, user_id: str, username: str, password: str, role: str, name: str,
                title: str = "", dept: str = "", email: str = "", office: str = "",
                seed: dict | None = None, active: bool = True) -> dict:
    """创建账号；给出 ``seed`` 时同时初始化其租户库（空库也会建表）。"""
    now = datetime.now().isoformat(timespec="seconds")
    db.get_users_db().execute(
        "INSERT INTO users (id, username, password_hash, role, name, title, dept, email,"
        " office, active, created_at, last_login) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (user_id, username, generate_password_hash(password), role, name, title, dept,
         email, office, 1 if active else 0, now, ""),
    )
    db.get_users_db().commit()

    if seed is not None:
        from .store import Store

        Store(db.connect_tenant(user_id)).replace_all(seed)
    else:
        conn = db.connect_tenant(user_id)  # 仅建表，内容留空
        conn.close()
    return get_user(user_id)


def update_user(user_id: str, patch: dict) -> dict | None:
    """更新账号资料（不含密码，密码走 set_password）。"""
    fields = ("name", "title", "dept", "email", "office", "role")
    sets, args = [], []
    for f in fields:
        if f in patch and patch[f] is not None:
            sets.append(f"{f} = ?")
            args.append(str(patch[f]).strip())
    if "active" in patch and patch["active"] is not None:
        sets.append("active = ?")
        args.append(1 if patch["active"] else 0)
    if not sets:
        return get_user(user_id)
    args.append(user_id)
    db.get_users_db().execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", tuple(args))
    db.get_users_db().commit()
    return get_user(user_id)


def set_password(user_id: str, password: str) -> bool:
    cur = db.get_users_db().execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(password), user_id),
    )
    db.get_users_db().commit()
    return cur.rowcount > 0


def touch_login(user_id: str) -> None:
    db.get_users_db().execute(
        "UPDATE users SET last_login = ? WHERE id = ?",
        (datetime.now().isoformat(timespec="seconds"), user_id),
    )
    db.get_users_db().commit()


def delete_user(user_id: str) -> bool:
    """删除账号并抹掉其租户库文件。"""
    row = db.get_users_db().execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return False
    if row["role"] == config.ROLE_ADMIN and count_admins() <= 1:
        raise ValueError("至少保留一个管理员账号")
    db.get_users_db().execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.get_users_db().commit()
    _drop_tenant_files(user_id)
    return True


def _drop_tenant_files(user_id: str) -> None:
    # 先关闭本请求内可能存在的连接（Windows 下文件被占用会删不掉）
    conns = getattr(g, "tenant_dbs", None)
    if isinstance(conns, dict) and user_id in conns:
        try:
            conns.pop(user_id).close()
        except Exception:  # noqa: BLE001
            pass
    base = config.tenant_db_path(user_id)
    for suffix in ("", "-wal", "-shm"):
        p = base.with_name(base.name + suffix)
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# 登录态
# --------------------------------------------------------------------------- #
def verify_credentials(username: str, password: str) -> tuple[dict | None, str]:
    """返回 (user, error)。"""
    user = get_user_by_username(str(username or "").strip())
    if user is None:
        return None, "用户名或密码不正确"
    row = db.get_users_db().execute(
        "SELECT password_hash FROM users WHERE id = ?", (user["id"],)
    ).fetchone()
    if not row or not check_password_hash(row["password_hash"], str(password or "")):
        return None, "用户名或密码不正确"
    if not user["active"]:
        return None, "账号已被停用，请联系管理员"
    return user, ""


def login_session(user: dict) -> None:
    session.clear()
    session["uid"] = user["id"]
    session.permanent = True
    touch_login(user["id"])


def logout_session() -> None:
    session.clear()


def current_user() -> dict | None:
    uid = session.get("uid")
    if not uid:
        return None
    user = get_user(uid)
    if user is None or not user["active"]:
        session.clear()
        return None
    return user


# --------------------------------------------------------------------------- #
# 装饰器
# --------------------------------------------------------------------------- #
def _bind(user: dict) -> None:
    g.user = user
    g.user_id = user["id"]


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "请先登录", "code": "unauthenticated"}), 401
        _bind(user)
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "请先登录", "code": "unauthenticated"}), 401
        if user["role"] != config.ROLE_ADMIN:
            return jsonify({"ok": False, "error": "需要管理员权限"}), 403
        _bind(user)
        return fn(*args, **kwargs)

    return wrapper


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #
def validate_register(payload: dict) -> tuple[dict, str]:
    """校验注册表单，返回 (清洗后的字段, 错误信息)。"""
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    name = str(payload.get("name", "")).strip()

    if not USERNAME_RE.match(username):
        return {}, "用户名需 3-20 位，字母开头，仅含字母 / 数字 / 下划线"
    if len(password) < MIN_PASSWORD:
        return {}, f"密码至少 {MIN_PASSWORD} 位"
    if not name:
        return {}, "姓名不能为空"
    if get_user_by_username(username):
        return {}, "该用户名已被注册"
    return {
        "username": username,
        "password": password,
        "name": name,
        "title": str(payload.get("title", "")).strip(),
        "dept": str(payload.get("dept", "")).strip(),
        "email": str(payload.get("email", "")).strip(),
        "office": str(payload.get("office", "")).strip(),
    }, ""
