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
import threading
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


class ThreadSafeConn:
    """跨线程安全的 sqlite3 连接外观（**按线程惰性分配独立连接**）。

    **为什么需要**：智能体内核（LangChain / LangGraph）由工具节点在
    ``ThreadPoolExecutor`` 中并发执行工具，而 ``Store`` 是在 Flask 请求线程里
    创建并挂在 ``g`` 上的。一个 ``sqlite3`` 连接既不允许跨线程使用
    （``created in a thread can only be used in that same thread``），
    也不能靠加锁硬扛：即便放开线程检查，**另一个线程的 ``commit()`` 会作废
    本线程尚未取数的游标**，查询会静默返回 ``None``（曾表现为智能体报错）。

    因此这里按线程惰性创建**独立连接**，文件级并发交给 WAL + 10s busy timeout：
    - 每个线程只用自己的连接，不存在游标互相作废；
    - 多线程写入在同一文件上排队等待（``busy_timeout``），不会 ``database is locked``。

    对上层保持「一个连接对象」的外观：``execute`` / ``commit`` / ``close`` 语义
    与真实连接一致，``store.conn`` 的所有既有用法无需改动；
    ``row_factory`` 等属性读写透明代理到当前线程的连接。
    """

    __slots__ = ("_path", "_local", "_registry", "_lock", "_generation")

    def __init__(self, path: str | Path) -> None:
        object.__setattr__(self, "_path", str(path))
        object.__setattr__(self, "_local", threading.local())
        object.__setattr__(self, "_registry", [])
        object.__setattr__(self, "_lock", threading.Lock())
        object.__setattr__(self, "_generation", 0)

    # ------------------------------------------------------------------ #
    # 连接分配
    # ------------------------------------------------------------------ #
    def _conn(self) -> sqlite3.Connection:
        """取当前线程的连接，没有（或已被 ``close`` 关闭）则新建。"""
        gen = getattr(object.__getattribute__(self, "_local"), "gen", -1)
        conn = getattr(object.__getattribute__(self, "_local"), "conn", None)
        if conn is not None and gen == object.__getattribute__(self, "_generation"):
            return conn
        # check_same_thread=False：连接可能由请求线程统一 close（工作线程创建的），
        # 因此必须放开线程检查；连接本身只被创建它的线程使用，故不会并发冲突。
        conn = sqlite3.connect(object.__getattribute__(self, "_path"),
                               timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        try:
            # 已是 WAL 时为无副作用读取；并发首次连接时若正被占用则等待
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError:
            pass
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        local = object.__getattribute__(self, "_local")
        local.conn = conn
        local.gen = object.__getattribute__(self, "_generation")
        with object.__getattribute__(self, "_lock"):
            object.__getattribute__(self, "_registry").append(conn)
        return conn

    # -- 属性代理：row_factory / isolation_level 等落到当前线程的连接 -- #
    def __getattr__(self, name):
        return getattr(self._conn(), name)

    def __setattr__(self, name, value):
        if name in ThreadSafeConn.__slots__:
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn(), name, value)

    # -- 语句接口（与 sqlite3.Connection 同名同义） -- #
    def execute(self, *args, **kwargs):
        return self._conn().execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._conn().executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        return self._conn().executescript(*args, **kwargs)

    def commit(self):
        return self._conn().commit()

    def rollback(self):
        return self._conn().rollback()

    def cursor(self):
        return self._conn().cursor()

    def close(self) -> None:
        """关闭本对象已分配的全部连接（各线程下次使用时自动重开）。"""
        with object.__getattribute__(self, "_lock"):
            conns = object.__getattribute__(self, "_registry")
            object.__setattr__(self, "_registry", [])
            object.__setattr__(self, "_generation",
                               object.__getattribute__(self, "_generation") + 1)
        for conn in conns:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 —— 已关闭 / 正在使用，忽略
                pass


def _connect(path: str | Path) -> ThreadSafeConn:
    return ThreadSafeConn(path)


def _has_table(conn: ThreadSafeConn, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def _open_with_schema(path: str | Path, schema: str, table: str) -> ThreadSafeConn:
    """打开库；仅在新建或缺少表时执行建表脚本（避免每次连接都跑 DDL）。"""
    path = Path(path)
    fresh = not path.exists()
    conn = _connect(path)
    if fresh or not _has_table(conn, table):
        conn.executescript(schema)
        conn.commit()
    return conn


def connect_tenant(user_id: str) -> ThreadSafeConn:
    """独立打开某个租户库（建表后返回），调用方负责关闭。"""
    return _open_with_schema(config.tenant_db_path(user_id), DOCUMENT_SCHEMA, "documents")


def get_db(user_id: str | None = None) -> ThreadSafeConn:
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


def get_users_db() -> ThreadSafeConn:
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
