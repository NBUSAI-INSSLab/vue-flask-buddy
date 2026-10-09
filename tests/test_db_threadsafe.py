"""数据库连接的跨线程可用性 —— 回归用例。

**背景**：智能体内核（LangChain / LangGraph）由工具节点在线程池里执行工具，
而连接是在 Flask 请求线程中创建并放进 ``g`` 的。``sqlite3`` 默认禁止跨线程
使用连接，会抛 ``SQLite objects created in a thread can only be used in that
same thread`` —— 表现为「智能体一用就报错」。

``backend.db._connect`` 因此以 ``check_same_thread=False`` 打开连接，并用
``ThreadSafeConn`` 内部的可重入锁把语句串行化。这里锁住该行为。
"""
from __future__ import annotations

import concurrent.futures
import sqlite3
import threading

from backend import agent_core, db
from backend.store import Store


def test_connection_allows_cross_thread_use(app, store):
    """在工作线程中使用请求线程创建的连接：读 / 写 / 提交都应正常。"""
    def work(_i: int) -> int:
        rows = store.list("events")                       # 读
        store.add("todos", {"title": "跨线程待办", "done": False})   # 写 + 提交
        return len(rows)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(work, range(4)))

    assert all(n >= 0 for n in results)
    titles = [t.get("title") for t in store.list("todos")]
    assert titles.count("跨线程待办") == 4


def test_concurrent_writes_are_serialized(app, store):
    """多线程并发写不报错、不丢数据（锁串行化，而非抛 database is locked）。"""
    per_thread, threads = 25, 8

    def work(tid: int) -> bool:
        for i in range(per_thread):
            store.add("todos", {"title": f"t{tid}-{i}", "done": False})
        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as pool:
        assert all(pool.map(work, range(threads)))

    titles = [t.get("title") for t in store.list("todos") if str(t.get("title", "")).startswith("t")]
    assert len(set(titles)) == per_thread * threads


def test_row_factory_proxy(app, store):
    """属性代理：``row_factory`` 落到当前线程的连接上，返回 sqlite3.Row。"""
    assert isinstance(store.conn, db.ThreadSafeConn)
    assert store.conn.row_factory is sqlite3.Row
    row = store.conn.execute("SELECT 1 AS n").fetchone()
    assert row["n"] == 1                     # 只有 Row 才支持按键取值


def test_each_thread_gets_its_own_connection(app, store):
    """不同线程拿到的必须是不同连接对象（否则游标会互相作废）。"""
    main_conn = store.conn._conn()
    seen: list = []
    lock = threading.Lock()

    def grab():
        c = store.conn._conn()
        with lock:
            seen.append(c)

    threads = [threading.Thread(target=grab) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(seen) == 3
    assert len({id(c) for c in seen}) == 3, "工作线程应各自持有独立连接"
    assert all(c is not main_conn for c in seen)


def test_close_then_reuse_reopens(app, store):
    """整体 close 后再次使用应自动重开，而不是抛「closed database」。"""
    store.add("todos", {"title": "关闭前", "done": False})
    store.conn.close()
    store.add("todos", {"title": "关闭后", "done": False})
    titles = [t.get("title") for t in store.list("todos")]
    assert "关闭前" in titles and "关闭后" in titles


def test_agent_tools_invoked_concurrently(app, store):
    """还原真实场景：LangGraph 在线程池里并发调用工具，读写都要正常。

    这是「智能体使用不了」的直接回归 —— 修复前工具一执行就抛
    ``SQLite objects created in a thread ...``。
    """
    by_name = {t.name: t for t in agent_core.make_tools(store)}

    def call(i: int) -> str:
        out = by_name["query_events"].invoke({"keyword": ""})
        by_name["add_todo"].invoke({"title": f"并发{i}"})
        return out

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        outs = list(pool.map(call, range(6)))

    assert all(isinstance(o, str) for o in outs)
    titles = [t.get("title") for t in store.list("todos") if str(t.get("title", "")).startswith("并发")]
    assert len(set(titles)) == 6
