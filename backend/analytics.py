"""教师统计：管理端所需的四类统计（科研 / 学术交流 / 教学 / 学生指导）。

在教师工作台内部（store.stats）之外，管理端需要更适合横向对比的口径：
按项目状态、成果类型与级别、交流类型、教学任务与学生结构分别汇总，
并给出「简要计数」用于教师列表。
"""
from __future__ import annotations

import re
from collections import Counter

from . import audit
from .utils import today

_PUBLISHED_STATES = {"已发表", "已录用", "已授权", "已登记", "已交付", "已获奖"}
_ACTIVE_EXCH = {"已确认", "进行中"}


# --------------------------------------------------------------------------- #
# 数值容错
# --------------------------------------------------------------------------- #
def _i(v, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _f(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _score_of(text) -> float | None:
    """从 "4.72 / 5.0" 这类文本里取出首个数值。"""
    m = re.search(r"\d+(?:\.\d+)?", str(text or ""))
    return float(m.group()) if m else None


def _counter(items: list[dict], key: str, fallback: str = "其他") -> dict:
    c = Counter(str(it.get(key) or fallback) for it in items)
    return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))


def _by_year(items: list[dict], date_key: str = "date") -> dict:
    """按年份计数（近 4 年，含今年）。"""
    year = today()[:4]
    years = [str(int(year) - i) for i in range(3, -1, -1)]
    counts = {y: 0 for y in years}
    for it in items:
        y = str(it.get(date_key) or "")[:4]
        if y in counts:
            counts[y] += 1
    return counts


# --------------------------------------------------------------------------- #
# 简要计数（教师列表 / 横向对比表）
# --------------------------------------------------------------------------- #
def teacher_counts(store) -> dict:
    projects = store.list("projects")
    literature = store.list("literature")
    achievements = store.list("achievements")
    students = store.list("students")
    teachings = store.list("teachings")
    exchanges = store.list("exchanges")
    todos = store.list("todos")
    return {
        "projects": len(projects),
        "activeProjects": sum(1 for p in projects if str(p.get("status") or "") != "已结题"),
        "papers": len(literature),
        "achievements": len(achievements),
        "score": round(sum(_f(a.get("score")) for a in achievements), 1),
        "published": sum(1 for a in achievements if a.get("status") in _PUBLISHED_STATES),
        "pending": sum(1 for a in achievements
                       if audit.normalize(a)["auditStatus"] == audit.PENDING),
        "approvedScore": round(sum(_f(a.get("score")) for a in achievements
                                  if audit.normalize(a)["auditStatus"] == audit.APPROVED), 1),
        "students": len(students),
        "teachings": len(teachings),
        "hours": sum(_i(g.get("hours")) for g in teachings),
        "exchanges": len(exchanges),
        "openTodos": sum(1 for t in todos if not t.get("done")),
    }


# --------------------------------------------------------------------------- #
# 一、科研成果统计
# --------------------------------------------------------------------------- #
def research_stats(store) -> dict:
    projects = store.list("projects")
    achievements = store.list("achievements")
    literature = store.list("literature")

    by_type = Counter(str(a.get("type") or "其他") for a in achievements)
    by_level = Counter(str(a.get("level") or "未标注") for a in achievements)
    by_status = Counter(str(a.get("status") or "未知") for a in achievements)
    proj_status = Counter(str(p.get("status") or "未知") for p in projects)

    return {
        "projects": {
            "total": len(projects),
            "leading": sum(1 for p in projects if str(p.get("role") or "") == "主持"),
            "active": proj_status.get("在研", 0),
            "review": proj_status.get("验收中", 0),
            "finished": proj_status.get("已结题", 0),
            "funding": round(sum(_f(p.get("funding")) for p in projects), 1),
            "byStatus": dict(proj_status),
            "byType": _counter(projects, "type"),
            "list": [
                {"id": p.get("id", ""), "name": p.get("name", ""), "type": p.get("type", ""),
                 "role": p.get("role", ""), "status": p.get("status", ""),
                 "funding": p.get("funding", "")}
                for p in projects
            ],
        },
        "achievements": {
            "total": len(achievements),
            "published": sum(1 for a in achievements if a.get("status") in _PUBLISHED_STATES),
            "score": round(sum(_f(a.get("score")) for a in achievements), 1),
            "byType": dict(by_type),
            "byLevel": dict(by_level),
            "byStatus": dict(by_status),
            "byYear": _by_year(achievements),
        },
        "literature": {
            "total": len(literature),
            "read": sum(1 for l in literature if str(l.get("status") or "") == "已读"),
            "reading": sum(1 for l in literature if str(l.get("status") or "") == "在读"),
            "unread": sum(1 for l in literature if str(l.get("status") or "") == "未读"),
            "byDirection": _counter(literature, "direction"),
        },
    }


# --------------------------------------------------------------------------- #
# 二、学术交流统计
# --------------------------------------------------------------------------- #
def exchange_stats(store) -> dict:
    items = store.list("exchanges")
    year = today()[:4]
    organizers = {str(x.get("organizer") or "").strip() for x in items if x.get("organizer")}
    recent = sorted(items, key=lambda x: str(x.get("start") or ""), reverse=True)[:4]
    return {
        "total": len(items),
        "upcoming": sum(1 for x in items if x.get("status") in _ACTIVE_EXCH),
        "finished": sum(1 for x in items if str(x.get("status") or "") == "已结束"),
        "international": sum(1 for x in items if str(x.get("level") or "") == "国际"),
        "thisYear": sum(1 for x in items if str(x.get("start") or "").startswith(year)),
        "organizers": len(organizers),
        "byKind": _counter(items, "kind"),
        "byLevel": _counter(items, "level", "未标注"),
        "byRole": _counter(items, "role", "参会"),
        "byStatus": _counter(items, "status", "未标注"),
        "recent": [
            {"title": x.get("title", ""), "kind": x.get("kind", ""), "level": x.get("level", ""),
             "start": x.get("start", ""), "status": x.get("status", ""), "role": x.get("role", "")}
            for x in recent
        ],
    }


# --------------------------------------------------------------------------- #
# 三、教学情况统计
# --------------------------------------------------------------------------- #
def teaching_stats(store) -> dict:
    items = store.list("teachings")
    courses = store.list("courses")

    done = total = 0
    for g in items:
        outline = g.get("tasks")
        if isinstance(outline, list):
            for t in outline:
                total += 1
                if t.get("done"):
                    done += 1

    scores = [_score_of(g.get("evalScore")) for g in items]
    scores = [s for s in scores if s is not None]

    progress = []
    for g in items:
        d, t = _i(g.get("syllabusDone")), _i(g.get("syllabusTotal"))
        if t > 0:
            progress.append(min(100.0, d / t * 100))

    return {
        "tasks": len(items),
        "ongoing": sum(1 for g in items if str(g.get("stage") or "") == "进行中"),
        "preparing": sum(1 for g in items if str(g.get("stage") or "") == "备课中"),
        "courses": len(courses),
        "students": sum(_i(g.get("students")) for g in items),
        "hours": sum(_i(g.get("hours")) for g in items),
        "credits": round(sum(_f(c.get("credits")) for c in courses), 1),
        "byType": _counter(items, "type"),
        "byStage": _counter(items, "stage"),
        "outlineProgress": round(sum(progress) / len(progress)) if progress else 0,
        "taskDoneRate": round(done / total * 100) if total else 0,
        "evalAvg": round(sum(scores) / len(scores), 2) if scores else None,
        "list": [
            {"id": g.get("id", ""), "name": g.get("name", ""), "code": g.get("code", ""),
             "type": g.get("type", ""), "stage": g.get("stage", ""), "hours": g.get("hours", ""),
             "students": g.get("students", ""), "syllabusDone": _i(g.get("syllabusDone")),
             "syllabusTotal": _i(g.get("syllabusTotal")), "evalScore": g.get("evalScore", "")}
            for g in items
        ],
    }


# --------------------------------------------------------------------------- #
# 四、学生指导统计
# --------------------------------------------------------------------------- #
def student_stats(store) -> dict:
    from .utils import day_offset

    items = store.list("students")
    t = today()
    week_end = day_offset(7)

    ms_total = ms_done = 0
    logs = 0
    for s in items:
        for m in (s.get("milestones") or []):
            ms_total += 1
            if m.get("done"):
                ms_done += 1
        logs += len(s.get("logs") or [])

    progress = [_i(s.get("progress")) for s in items]
    need = []
    for s in items:
        nxt = str(s.get("nextMeeting") or "")
        if nxt and t <= nxt <= week_end:
            need.append({"name": s.get("name", ""), "nextMeeting": nxt,
                         "stage": s.get("stage", ""), "progress": _i(s.get("progress"))})

    return {
        "total": len(items),
        "master": sum(1 for s in items if str(s.get("degree") or "") == "硕士"),
        "phd": sum(1 for s in items if str(s.get("degree") or "") == "博士"),
        "avgProgress": round(sum(progress) / len(progress)) if progress else 0,
        "needMeeting": len(need),
        "needMeetingList": need[:6],
        "milestones": {"total": ms_total, "done": ms_done,
                       "rate": round(ms_done / ms_total * 100) if ms_total else 0},
        "logCount": logs,
        "byStage": _counter(items, "stage"),
        "byDirection": _counter(items, "direction"),
        "list": [
            {"name": s.get("name", ""), "degree": s.get("degree", ""), "grade": s.get("grade", ""),
             "stage": s.get("stage", ""), "progress": _i(s.get("progress")),
             "thesisTitle": s.get("thesisTitle", ""), "nextMeeting": s.get("nextMeeting", "")}
            for s in items
        ],
    }


# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #
def teacher_summary(store) -> dict:
    """教师列表用：计数 + 四类统计的关键指标。"""
    counts = teacher_counts(store)
    ach = store.achievement_stats()
    teach = store.teaching_load()
    return {
        "counts": counts,
        "score": ach["score"],
        "published": ach["published"],
        "teachingHours": teach["hours"],
        "teachingStudents": teach["students"],
    }


def teacher_detail(store) -> dict:
    """教师详情用：四类统计的完整口径。"""
    return {
        "research": research_stats(store),
        "exchanges": exchange_stats(store),
        "teaching": teaching_stats(store),
        "students": student_stats(store),
        "audit": audit.store_stats(store),
    }


def totalize(summaries: list[dict]) -> dict:
    """把多位教师的简要计数汇总成管理端总览。"""
    keys = ["projects", "activeProjects", "papers", "achievements", "score",
            "published", "pending", "students", "teachings", "hours", "exchanges",
            "openTodos"]
    totals = {k: 0 for k in keys}
    for s in summaries:
        c = s.get("counts", {})
        for k in keys:
            totals[k] += c.get(k, 0)
    totals["teachers"] = len(summaries)
    totals["score"] = round(totals["score"], 1)
    return totals
