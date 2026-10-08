"""数据访问层：文档集合的 CRUD、迁移、导入导出、派生统计。

对外接口刻意与前端原有 `Store` 保持一致（list/get/add/update/remove），
这样 12 个工具的逻辑可以近乎逐行从 JS 移植过来。
"""
from __future__ import annotations

import json
from datetime import datetime

from . import config, db, seed
from .utils import uid

_UNSET = object()


class Store:
    """基于 SQLite documents 表的文档集合仓库。"""

    def __init__(self, conn):
        self.conn = conn

    # ------------------------------------------------------------------ #
    # 基础读写
    # ------------------------------------------------------------------ #
    def _next_seq(self) -> int:
        row = self.conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS s FROM documents").fetchone()
        return int(row["s"])

    def list(self, collection: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT data FROM documents WHERE collection = ? ORDER BY seq DESC",
            (collection,),
        ).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def get(self, collection: str, doc_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT data FROM documents WHERE collection = ? AND id = ?",
            (collection, doc_id),
        ).fetchone()
        return json.loads(row["data"]) if row else None

    def add(self, collection: str, obj: dict, prefix: str = "id", commit: bool = True) -> dict:
        obj = dict(obj)
        obj.setdefault("id", uid(prefix))
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT OR REPLACE INTO documents (collection, id, seq, data, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (collection, obj["id"], self._next_seq(), json.dumps(obj, ensure_ascii=False), now, now),
        )
        if commit:
            self.conn.commit()
        return obj

    def update(self, collection: str, doc_id: str, patch: dict) -> dict | None:
        current = self.get(collection, doc_id)
        if current is None:
            return None
        current.update(patch)
        self.conn.execute(
            "UPDATE documents SET data = ?, updated_at = ? WHERE collection = ? AND id = ?",
            (json.dumps(current, ensure_ascii=False), datetime.now().isoformat(timespec="seconds"),
             collection, doc_id),
        )
        self.conn.commit()
        return current

    def remove(self, collection: str, doc_id: str) -> bool:
        cur = self.conn.execute(
            "DELETE FROM documents WHERE collection = ? AND id = ?", (collection, doc_id)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def exists(self, collection: str, doc_id: str) -> bool:
        return self.get(collection, doc_id) is not None

    # ------------------------------------------------------------------ #
    # 个人信息（单文档）
    # ------------------------------------------------------------------ #
    def get_profile(self) -> dict:
        row = self.conn.execute(
            "SELECT data FROM documents WHERE collection = 'profile' AND id = ?",
            (config.PROFILE_ID,),
        ).fetchone()
        return json.loads(row["data"]) if row else dict(seed.PROFILE)

    def set_profile(self, data: dict) -> dict:
        current = self.get_profile()
        current.update({k: v for k, v in data.items() if v is not None})
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT OR REPLACE INTO documents (collection, id, seq, data, created_at, updated_at)"
            " VALUES ('profile', ?, ?, ?, ?, ?)",
            (config.PROFILE_ID, self._next_seq(), json.dumps(current, ensure_ascii=False), now, now),
        )
        self.conn.commit()
        return current

    # ------------------------------------------------------------------ #
    # 迁移 / 全量替换
    # ------------------------------------------------------------------ #
    def ensure_seed(self) -> None:
        """首次运行写入种子；缺集合时补齐（等价于前端 migrate）。"""
        row = self.conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()
        if int(row["n"]) == 0:
            self.replace_all(seed.full_seed())
            return
        for coll in config.COLLECTIONS:
            n = self.conn.execute(
                "SELECT COUNT(*) AS n FROM documents WHERE collection = ?", (coll,)
            ).fetchone()["n"]
            if int(n) == 0 and seed.COLLECTION_SEED.get(coll):
                self._add_many_ordered(coll, seed.COLLECTION_SEED[coll])
        if not self.conn.execute(
            "SELECT 1 FROM documents WHERE collection='profile' LIMIT 1"
        ).fetchone():
            self.set_profile(seed.PROFILE)

    def _add_many_ordered(self, coll: str, items: list) -> None:
        """按给定顺序批量写入（一次 executemany，避免逐条 commit）。

        seq 越大越靠前（``list`` 按 seq 降序返回），因此倒序写入，
        使 ``items[0]`` 最终位于列表首位 —— 与前端数组顺序、导出顺序一致。
        """
        objs = [dict(o) for o in items if isinstance(o, dict)]
        if not objs:
            return
        now = datetime.now().isoformat(timespec="seconds")
        base = self._next_seq()
        rows = []
        for i, obj in enumerate(reversed(objs)):
            obj.setdefault("id", uid("id"))
            rows.append((coll, obj["id"], base + i,
                         json.dumps(obj, ensure_ascii=False), now, now))
        self.conn.executemany(
            "INSERT OR REPLACE INTO documents (collection, id, seq, data, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            rows,
        )
        self.conn.commit()

    def replace_all(self, data: dict) -> None:
        """用给定数据整体替换（导入 / 重置）。"""
        self.conn.execute("DELETE FROM documents")
        profile = data.get("profile") or dict(seed.PROFILE)
        self.set_profile(profile)
        for coll in config.COLLECTIONS:
            items = data.get(coll)
            if not isinstance(items, list):
                # 缺失集合补种子，保证结构完整
                items = seed.COLLECTION_SEED.get(coll, [])
            self._add_many_ordered(coll, items)
        self.conn.commit()
        # 种子 / 备份数据可能没有成果审核字段，这里统一补齐
        from . import audit, courses, cv
        audit.ensure_fields(self)
        # 同理：课程开放设置与访问令牌、资料条目 id
        courses.ensure_fields(self)
        # 个人简历：固定链接令牌与区块开关（此处无 user，不做存量补种）
        cv.ensure_fields(self)

    def migrate(self, data: dict) -> dict:
        """把任意来源的数据补齐为完整结构（供导入校验后调用）。"""
        out = dict(data)
        for coll in config.COLLECTIONS:
            if not isinstance(out.get(coll), list):
                out[coll] = [dict(x) for x in seed.COLLECTION_SEED.get(coll, [])]
        if not isinstance(out.get("profile"), dict):
            out["profile"] = dict(seed.PROFILE)
        return out

    # ------------------------------------------------------------------ #
    # 导出
    # ------------------------------------------------------------------ #
    def export(self) -> dict:
        data = {"profile": self.get_profile()}
        for coll in config.COLLECTIONS:
            data[coll] = self.list(coll)
        return data

    # ------------------------------------------------------------------ #
    # 派生统计（与前端 Store.stats 等保持一致）
    # ------------------------------------------------------------------ #
    def stats(self) -> dict:
        from .utils import day_offset, today

        t = today()
        week_end = day_offset(7)
        return {
            "activeProjects": sum(1 for p in self.list("projects") if p.get("status") != "已结题"),
            "unreadLits": sum(1 for l in self.list("literature") if l.get("status") != "已读"),
            "students": len(self.list("students")),
            "weekEvents": sum(
                1 for e in self.list("events") if t <= str(e.get("date", "")) <= week_end
            ),
            "openTodos": sum(1 for x in self.list("todos") if not x.get("done")),
            "papers": len(self.list("literature")),
            "exchanges": sum(
                1 for x in self.list("exchanges") if x.get("status") in ("已确认", "进行中")
            ),
            "teachings": sum(
                1 for g in self.list("teachings") if g.get("stage") in ("进行中", "备课中")
            ),
            "achievements": len(self.list("achievements")),
            "developments": sum(1 for x in self.list("developments") if x.get("status") != "已完成"),
        }

    def achievement_stats(self) -> dict:
        from . import audit

        items = self.list("achievements")
        by_type: dict[str, int] = {}
        for a in items:
            t = a.get("type") or "其他"
            by_type[t] = by_type.get(t, 0) + 1
        published_states = {"已发表", "已录用", "已授权", "已登记", "已交付", "已获奖"}
        audit_states = [audit.normalize(a)["auditStatus"] for a in items]
        return {
            "total": len(items),
            "byType": by_type,
            "score": sum(_f(a.get("score")) for a in items),
            "published": sum(1 for a in items if a.get("status") in published_states),
            "pending": sum(1 for s in audit_states if s == audit.PENDING),
            "approved": sum(1 for s in audit_states if s == audit.APPROVED),
            "rejected": sum(1 for s in audit_states if s == audit.REJECTED),
        }

    def teaching_load(self) -> dict:
        items = self.list("teachings")
        hours = 0
        for g in items:
            h = _i(g.get("hours"), None)
            if h is not None:
                hours += h
        return {
            "courses": len(items),
            "students": sum(_i(g.get("students"), 0) for g in items),
            "hours": hours,
        }

    def development_progress(self) -> int:
        items = self.list("developments")
        if not items:
            return 0
        return round(sum(_i(d.get("progress"), 0) for d in items) / len(items))

    def tool_categories(self) -> list[list]:
        counts: dict[str, int] = {}
        for t in self.list("tools"):
            c = t.get("category") or "其他"
            counts[c] = counts.get(c, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    # ------------------------------------------------------------------ #
    # 工具留痕 / 频次
    # ------------------------------------------------------------------ #
    def record_tool_run(self, tool_key: str, title: str, memo: str = "") -> dict:
        from .utils import today

        return self.add(
            "tool_runs",
            {"tool": tool_key, "title": title, "memo": memo, "created": today()},
            "r",
        )

    def tool_runs_for(self, tool_key: str | None = None) -> list[dict]:
        runs = self.list("tool_runs")
        if tool_key:
            runs = [r for r in runs if r.get("tool") == tool_key]
        return sorted(runs, key=lambda r: str(r.get("created", "")), reverse=True)

    def bump_tool_freq(self, tool_id: str) -> None:
        tool = self.get("tools", tool_id)
        if tool:
            self.update("tools", tool_id, {"freq": _i(tool.get("freq"), 0) + 1})

    # ------------------------------------------------------------------ #
    # 日程派生
    # ------------------------------------------------------------------ #
    def upcoming_events(self, days: int = 7) -> list[dict]:
        from .utils import day_offset, today

        t, end = today(), day_offset(days)
        items = [e for e in self.list("events") if t <= str(e.get("date", "")) <= end]
        return sorted(items, key=lambda e: (str(e.get("date", "")), str(e.get("start", ""))))


# --------------------------------------------------------------------------- #
# 局部数字转换（容错：中文字符串、None、"—" 都返回默认值）
# --------------------------------------------------------------------------- #
def _f(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _i(v, default: int | None = 0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def open_store(user_id: str | None = None) -> Store:
    """打开某位教师的工作台数据仓库。

    不传 ``user_id`` 时按当前登录用户取库（无请求上下文则兜底到默认租户）。
    """
    return Store(db.get_db(user_id))
