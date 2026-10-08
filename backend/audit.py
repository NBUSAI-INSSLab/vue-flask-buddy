"""成果审核：跨教师汇总成果、记录审核意见与审核轨迹。

审核状态直接写在成果文档上（教师租户库的 ``achievements`` 集合），
因此「教师提交 → 管理员审核」共用同一份数据，不需要额外的中间表：

    auditStatus   待审核 / 已通过 / 已退回
    auditNote     最近一次审核意见
    auditBy       审核人姓名
    auditAt       审核时间
    auditLog      审核轨迹 [{at, by, action, status, note}]

存量数据（v2 之前登记的成果）没有这些字段，启动时由
``ensure_fields`` 统一回填：已落地状态（已发表 / 已授权…）视为已通过，
其余（撰写中 / 审稿中 / 申报中…）进入待审核队列。
"""
from __future__ import annotations

from . import auth, config
from .store import Store, open_store
from .utils import now_str

PENDING = config.AUDIT_PENDING
APPROVED = config.AUDIT_APPROVED
REJECTED = config.AUDIT_REJECTED
STATUSES = config.AUDIT_STATUSES

# 审核动作 -> 目标状态
ACTIONS = {
    "approve": APPROVED,
    "reject": REJECTED,
    "reset": PENDING,
}
# 目标状态 -> 轨迹里显示的动作名
ACTION_LABEL = {APPROVED: "通过", REJECTED: "退回", PENDING: "撤回"}

# 审核轨迹最多保留的条数
MAX_LOG = 20

_TOTAL_FIELDS = ("research", "achievements", "literature", "exchanges",
                 "teaching", "students")


# --------------------------------------------------------------------------- #
# 字段规范化
# --------------------------------------------------------------------------- #
def default_status(achievement: dict) -> str:
    """存量成果的默认审核状态：已落地的视为已通过，其余待审核。"""
    state = str(achievement.get("status") or "")
    return APPROVED if state in config.PUBLISHED_STATUSES else PENDING


def normalize(achievement: dict) -> dict:
    """返回补全审核字段的副本（不落库）。"""
    out = dict(achievement)
    state = str(out.get("auditStatus") or "")
    if state not in STATUSES:
        out["auditStatus"] = default_status(out)
    out["auditNote"] = str(out.get("auditNote") or "")
    out["auditBy"] = str(out.get("auditBy") or "")
    out["auditAt"] = str(out.get("auditAt") or "")
    if not isinstance(out.get("auditLog"), list):
        out["auditLog"] = []
    if not out["auditLog"]:
        # 存量成果：补一条「登记」轨迹，让审核时间线完整
        out["auditLog"] = [submitted_entry(out, out["auditStatus"])]
    return out


def submitted_entry(achievement: dict, status: str = PENDING) -> dict:
    """教师登记成果时的初始轨迹。"""
    day = str(achievement.get("date") or "").strip()
    return {"at": day or "—", "by": "本人", "action": "登记",
            "status": status, "note": "教师提交成果登记，等待学院审核"}


def is_normalized(achievement: dict) -> bool:
    """审核字段是否齐备（状态合法 + 至少有一条审核轨迹）。"""
    return (str(achievement.get("auditStatus") or "") in STATUSES
            and bool(achievement.get("auditLog")))


def ensure_fields(store: Store) -> int:
    """补齐某个租户库中缺失审核字段的成果，返回修补条数。"""
    changed = 0
    for raw in store.list("achievements"):
        if is_normalized(raw):
            continue
        doc_id = raw.get("id")
        if not doc_id:
            continue
        fixed = normalize(raw)
        store.update("achievements", doc_id, {
            "auditStatus": fixed["auditStatus"],
            "auditNote": fixed["auditNote"],
            "auditBy": fixed["auditBy"],
            "auditAt": fixed["auditAt"],
            "auditLog": fixed["auditLog"],
        })
        changed += 1
    return changed


def ensure_all(users: list[dict] | None = None) -> int:
    """为全部教师回填审核字段（启动时调用）。"""
    total = 0
    for user in (users if users is not None else auth.list_teachers()):
        total += ensure_fields(open_store(user["id"]))
    return total


# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #
def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _row(teacher: dict, achievement: dict, projects: dict) -> dict:
    a = normalize(achievement)
    return {
        "id": a.get("id", ""),
        "teacherId": teacher["id"],
        "teacherName": teacher.get("name", ""),
        "teacherTitle": teacher.get("title", ""),
        "teacherDept": teacher.get("dept", ""),
        "title": a.get("title", ""),
        "type": a.get("type", ""),
        "level": a.get("level", ""),
        "status": a.get("status", ""),
        "date": a.get("date", ""),
        "venue": a.get("venue", ""),
        "authors": a.get("authors", ""),
        "role": a.get("role", ""),
        "doi": a.get("doi", ""),
        "note": a.get("note", ""),
        "projectId": a.get("projectId", ""),
        "projectName": projects.get(a.get("projectId"), ""),
        "score": round(_num(a.get("score")), 1),
        "auditStatus": a["auditStatus"],
        "auditNote": a["auditNote"],
        "auditBy": a["auditBy"],
        "auditAt": a["auditAt"],
        "auditLog": a["auditLog"],
    }


def collect(*, status: str = "", teacher_id: str = "", q: str = "",
            users: list[dict] | None = None) -> list[dict]:
    """汇总全部教师的成果；可按审核状态 / 教师 / 关键词过滤。

    结果按「待审核优先、日期倒序」排序，审核队列天然排在最前。
    """
    keyword = str(q or "").strip().lower()
    only = str(teacher_id or "").strip()
    want = str(status or "").strip()

    rows: list[dict] = []
    for teacher in (users if users is not None else auth.list_teachers()):
        if only and teacher["id"] != only:
            continue
        store = open_store(teacher["id"])
        projects = {p.get("id"): p.get("name", "") for p in store.list("projects")}
        for ach in store.list("achievements"):
            row = _row(teacher, ach, projects)
            if want and row["auditStatus"] != want:
                continue
            if keyword:
                haystack = " ".join(str(row.get(k, "")) for k in (
                    "title", "type", "level", "venue", "authors", "status",
                    "teacherName", "teacherDept", "projectName", "doi", "note"))
                if keyword not in haystack.lower():
                    continue
            rows.append(row)
    return rows


def sort_rows(rows: list[dict]) -> list[dict]:
    order = {PENDING: 0, REJECTED: 1, APPROVED: 2}
    return sorted(rows, key=lambda r: (
        order.get(r["auditStatus"], 9),
        str(r.get("date") or "0000-00-00"),
    ), reverse=False)


def stats(rows: list[dict]) -> dict:
    """审核面板顶部指标 + 待审结构。"""
    def count(state: str) -> int:
        return sum(1 for r in rows if r["auditStatus"] == state)

    def score(state: str) -> float:
        return round(sum(r["score"] for r in rows if r["auditStatus"] == state), 1)

    pending = [r for r in rows if r["auditStatus"] == PENDING]
    rejected = [r for r in rows if r["auditStatus"] == REJECTED]
    by_type: dict[str, int] = {}
    for r in pending:
        by_type[r["type"] or "其他"] = by_type.get(r["type"] or "其他", 0) + 1

    return {
        "total": len(rows),
        "pending": count(PENDING),
        "approved": count(APPROVED),
        "rejected": count(REJECTED),
        "pendingScore": score(PENDING),
        "approvedScore": score(APPROVED),
        "rejectedScore": score(REJECTED),
        "teachers": len({r["teacherId"] for r in rows}),
        "pendingTeachers": len({r["teacherId"] for r in pending}),
        "pendingByType": dict(sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0]))),
        "pendingScoreMax": round(max([r["score"] for r in pending], default=0.0), 1),
        "rejectedTeachers": len({r["teacherId"] for r in rejected}),
    }


def store_stats(store: Store) -> dict:
    """单位教师的成果审核概览（教师统计详情页用）。"""
    items = [normalize(a) for a in store.list("achievements")]

    def pick(state: str) -> list[dict]:
        return [a for a in items if a["auditStatus"] == state]

    total = len(items)
    approved = pick(APPROVED)
    history = []
    for a in items:
        for entry in reversed(a["auditLog"] or []):
            history.append({
                "title": a.get("title", ""),
                "type": a.get("type", ""),
                "status": a["auditStatus"],
                **{k: entry.get(k, "") for k in ("at", "by", "action", "note")},
            })
            break
    history.sort(key=lambda x: str(x.get("at") or ""), reverse=True)

    return {
        "total": total,
        "pending": len(pick(PENDING)),
        "approved": len(approved),
        "rejected": len(pick(REJECTED)),
        "pendingScore": round(sum(_num(a.get("score")) for a in pick(PENDING)), 1),
        "approvedScore": round(sum(_num(a.get("score")) for a in approved), 1),
        "rejectedScore": round(sum(_num(a.get("score")) for a in pick(REJECTED)), 1),
        "approveRate": round(len(approved) / total * 100) if total else 0,
        "history": history[:6],
    }


def teacher_options(rows: list[dict]) -> list[dict]:
    """筛选下拉：参与审核的教师及其待审计数。"""
    bucket: dict[str, dict] = {}
    for r in rows:
        item = bucket.setdefault(r["teacherId"], {
            "id": r["teacherId"], "name": r["teacherName"],
            "title": r["teacherTitle"], "dept": r["teacherDept"],
            "total": 0, "pending": 0, "rejected": 0,
        })
        item["total"] += 1
        if r["auditStatus"] == PENDING:
            item["pending"] += 1
        elif r["auditStatus"] == REJECTED:
            item["rejected"] += 1
    return sorted(bucket.values(), key=lambda x: (-x["pending"], -x["total"], x["name"]))


# --------------------------------------------------------------------------- #
# 审核落库
# --------------------------------------------------------------------------- #
def apply_review(store: Store, doc_id: str, action: str, note: str = "",
                 by: str = "系统管理员") -> dict | None:
    """对单条成果执行审核；返回更新后的成果，成果不存在时返回 None。"""
    target = ACTIONS.get(str(action))
    if target is None:
        raise ValueError("审核动作只能是 approve / reject / reset")

    current = store.get("achievements", doc_id)
    if current is None:
        return None

    now = now_str()
    log = list(current.get("auditLog") or [])
    log.append({"at": now, "by": by, "action": ACTION_LABEL[target],
                "status": target, "note": str(note or "")})
    return store.update("achievements", doc_id, {
        "auditStatus": target,
        "auditNote": str(note or ""),
        "auditBy": by,
        "auditAt": now,
        "auditLog": log[-MAX_LOG:],
    })


def review_one(teacher_id: str, doc_id: str, action: str, note: str = "",
               by: str = "系统管理员") -> dict | None:
    """按教师打开租户库后审核单条成果。"""
    return apply_review(open_store(teacher_id), doc_id, action, note, by)


def pending_count(user_id: str) -> int:
    """某位教师的待审成果数（教师列表 / 总览用）。"""
    return sum(1 for a in open_store(user_id).list("achievements")
               if normalize(a)["auditStatus"] == PENDING)


# --------------------------------------------------------------------------- #
# 教师视角：给自己的成果附上审核字段
# --------------------------------------------------------------------------- #
def decorate(items: list[dict]) -> list[dict]:
    return [normalize(a) for a in items]


# 修改这些字段意味着成果内容发生变化，已审核的成果需重新走审核
CORE_FIELDS = ("title", "type", "level", "authors", "role", "venue",
               "date", "status", "score", "projectId", "doi", "note")


def prepare_new(achievement: dict, by: str = "") -> dict:
    """教师新登记成果：初始为待审核，并写入一条「登记」轨迹。"""
    out = dict(achievement)
    entry = submitted_entry(out, PENDING)
    entry["by"] = by or entry["by"]
    out.update({
        "auditStatus": PENDING,
        "auditNote": "",
        "auditBy": "",
        "auditAt": "",
        "auditLog": [entry],
    })
    return out


def needs_resubmit(current: dict, patch: dict) -> bool:
    """内容变化且已出审核结论 → 需要重新提交审核。"""
    if not any(k in patch for k in CORE_FIELDS):
        return False
    return normalize(current)["auditStatus"] != PENDING


def resubmit_patch(current: dict) -> dict:
    """重新提交时写回审核字段（保留历史轨迹）。"""
    now = now_str()
    log = list(current.get("auditLog") or [])
    log.append({"at": now, "by": "本人", "action": "重新提交",
                "status": PENDING, "note": "内容有更新，等待复核"})
    return {
        "auditStatus": PENDING,
        "auditNote": "",
        "auditBy": "",
        "auditAt": "",
        "auditLog": log[-MAX_LOG:],
    }


__all__ = [
    "PENDING", "APPROVED", "REJECTED", "STATUSES", "ACTIONS", "ACTION_LABEL",
    "default_status", "normalize", "is_normalized", "ensure_fields", "ensure_all",
    "collect", "sort_rows", "stats", "store_stats", "teacher_options",
    "apply_review", "review_one", "pending_count", "decorate",
    "prepare_new", "needs_resubmit", "resubmit_patch",
]
