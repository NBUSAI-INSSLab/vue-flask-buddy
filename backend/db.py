"""SQLite 连接与建表。

设计取向：教研工作台的数据是「嵌套文档」（项目带阶段/成果、课程带大纲/资料、
学生带里程碑/沟通记录），因此租户库采用「文档集合」模型：

    documents(collection, id, seq, data JSON, created_at, updated_at)

- 每个集合是一组文档，data 列保存完整 JSON，天然支持任意深度嵌套；
- seq 单调递增，ORDER BY seq DESC 即「最新在前」，与原前端 unshift 语义一致；
- 换用关系型多表反而要为每种嵌套结构建十几张表与迁移，收益有限。

两类库：
- **全局库** ``users.db``：账号、角色、密码哈希（唯一一张 users 表）；
- **租户库** ``tenants/<uid>.db``：上表的 documents，一位教师一个文件，
  教师视角的 SQL 完全不带 owner 过滤（物理隔离），跨教师统计逐个汇总即可。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import current_app, g

from . import config

# ---- 租户库：文档集合 ----
DOCUMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    collection  TEXT    NOT NULL,
    id          TEXT    NOT NULL,
    seq         INTEGER NOT NULL DEFAULT 0,
    data        TEXT    NOT NULL,
    created_at  TEXT,
    updated_at  TEXT,
    PRIMARY KEY (collection, id)
);

CREATE INDEX IF NOT EXISTS idx_documents_coll_seq
    ON documents (collection, seq DESC);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

# ---- 全局库：账号 ----
USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'teacher',
    name          TEXT NOT NULL,
    title         TEXT NOT NULL DEFAULT '',
    dept          TEXT NOT NULL DEFAULT '',
    email         TEXT NOT NULL DEFAULT '',
    office        TEXT NOT NULL DEFAULT '',
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT,
    last_login    TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_role ON users (role, created_at);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def _open_with_schema(path: str | Path, schema: str, table: str) -> sqlite3.Connection:
    """打开库；仅在新建或缺少表时执行建表脚本（避免每次连接都跑 DDL）。"""
    path = Path(path)
    fresh = not path.exists()
    conn = _connect(path)
    if fresh or not _has_table(conn, table):
        conn.executescript(schema)
        conn.commit()
    return conn


def connect_tenant(user_id: str) -> sqlite3.Connection:
    """独立打开某个租户库（建表后返回），调用方负责关闭。"""
    return _open_with_schema(config.tenant_db_path(user_id), DOCUMENT_SCHEMA, "documents")


def get_db(user_id: str | None = None) -> sqlite3.Connection:
    """取得租户库连接（惰性创建并建表，请求结束统一关闭）。

    优先级：显式传入 > 当前登录用户 > 兜底租户（脚本 / 初始化场景）。
    """
    uid = user_id or getattr(g, "user_id", None) or config.DEFAULT_TENANT_ID
    conns = getattr(g, "tenant_dbs", None)
    if conns is None:
        conns = {}
        g.tenant_dbs = conns
    if uid not in conns:
        conns[uid] = _open_with_schema(
            config.tenant_db_path(uid), DOCUMENT_SCHEMA, "documents"
        )
    return conns[uid]


def get_users_db() -> sqlite3.Connection:
    """全局库连接（账号）。"""
    if "users_db" not in g:
        g.users_db = _open_with_schema(
            current_app.config["USERS_DB_PATH"], USERS_SCHEMA, "users"
        )
    return g.users_db


def close_db(exc=None) -> None:  # noqa: ARG001
    for conn in getattr(g, "tenant_dbs", {}).values():
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    g.pop("tenant_dbs", None)
    users_db = g.pop("users_db", None)
    if users_db is not None:
        try:
            users_db.close()
        except Exception:  # noqa: BLE001
            pass


def init_db(app) -> None:
    """在应用上下文中建全局库表（租户库在首次访问时建）。"""
    with app.app_context():
        get_users_db()


def register(app) -> None:
    app.teardown_appcontext(close_db)
