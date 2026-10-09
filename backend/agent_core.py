"""智能体内核：LangGraph ReAct 智能体 + 教师工作台工具集。

- ``make_tools`` 把租户库封装成一批工具（查询 + 增补日程/待办），
  智能体按需调用；``search_kb`` 提供知识库 RAG 检索。
- ``run_agent`` 组装（系统提示 + 历史 + 本轮提问）交给
  ``langchain.agents.create_agent``（底层 LangGraph 预置 ReAct 图），
  返回最终回答与「工具调用轨迹」供前端展示思考过程。
"""
from __future__ import annotations

from datetime import date

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from . import kb as kb_util
from . import llm as llm_util
from .store import Store
from .utils import uid

HISTORY_ROUNDS = 8          # 带入对话历史的最大轮数（人机各算一条）
STEP_TEXT_MAX = 220         # 工具结果摘要截断
KB_CONTEXT_MAX = 900        # 知识库检索单块注入上限

SYSTEM_PROMPT = """你是「NBUSAI 教师工作台」的智能助手，服务对象是高校计算机专业教师。

## 你的能力
1. 直接查询/登记工作台数据：日程、待办、科研项目、课程（含大纲与教学日历）、学生、文献、个人资料。
2. 检索教师的个人知识库（search_kb），基于库内内容回答专业问题。

## 工作台数据约定
- 日程 events：date(YYYY-MM-DD)、start/end(HH:MM)、type(组会/上课/答辩/申报/会议…)、location、note。
- 待办 todos：title、due(YYYY-MM-DD)、priority(high/mid/low)、tag。
- 项目 projects：name、code、status、deadline；课程 courses：name、code、syllabus(大纲)、calendar(教学日历行)。
- 学生 students：name、degree(硕士/博士)、direction、thesisTitle、stage。
- 文献 literature：title、authors、journal、direction。

## 回答规范
- 始终用简体中文，简洁专业；列表数据用短句罗列，不要编造数据。
- 涉及事实性/制度性/专业知识的问题，先调用 search_kb；命中内容在回答中以「（依据：文档名）」标注出处；未命中则如实说明知识库中没有相关内容，再基于通用知识回答并声明未经知识库核对。
- 教师让你「记一下 / 帮我安排 / 加个待办」时调用对应写入工具，并把登记结果复述一遍。
- 今天的日期是 {today}，星期{weekday}；相对时间一律换算成具体日期再入库。"""


def _clip(value, limit: int) -> str:
    return str(value if value is not None else "").strip()[:limit]


def make_tools(store: Store):
    """把当前租户的 Store 封装成智能体工具集（闭包隔离，天然多租户安全）。"""

    @tool
    def query_events(keyword: str = "", limit: int = 8) -> str:
        """查询日程。keyword 按标题/地点/类型/备注模糊过滤；不传 keyword 返回最近的日程。"""
        items = store.list("events")
        kw = _clip(keyword, 40)
        if kw:
            items = [e for e in items if kw in "".join(
                str(e.get(f, "")) for f in ("title", "location", "type", "note"))]
        items = sorted(items, key=lambda e: str(e.get("date", "")), reverse=True)[: max(1, min(int(limit or 8), 30))]
        if not items:
            return "没有匹配的日程。"
        return "\n".join(
            f"- {e.get('date')} {e.get('start','')}-{e.get('end','')}「{e.get('title')}」"
            f"[{e.get('type','')}] @{e.get('location','')}" + ("（已完结）" if e.get("done") else "")
            for e in items
        )

    @tool
    def add_event(date: str, title: str, type: str = "会议", start: str = "09:00",
                  end: str = "", location: str = "", note: str = "") -> str:
        """登记一条日程。date 必须是 YYYY-MM-DD；type 可选 组会/上课/答辩/申报/会议；start/end 为 HH:MM。"""
        import re as _re

        if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", _clip(date, 10)):
            return "失败：date 需为 YYYY-MM-DD 格式，请先向教师确认具体日期。"
        ev = store.add("events", {
            "title": _clip(title, 60) or "未命名日程", "type": _clip(type, 12) or "会议",
            "date": _clip(date, 10), "start": _clip(start, 5) or "09:00",
            "end": _clip(end, 5), "location": _clip(location, 60),
            "note": _clip(note, 200), "done": False,
        }, prefix="ae")
        return f"已登记日程：{ev['date']} {ev['start']}「{ev['title']}」"

    @tool
    def list_todos(include_done: bool = False) -> str:
        """查询待办清单（默认只看待办中，include_done=true 时含已完成）。"""
        items = [t for t in store.list("todos") if include_done or not t.get("done")]
        prio = {"high": 0, "mid": 1, "low": 2}
        items.sort(key=lambda t: (str(t.get("due", "")), prio.get(t.get("priority"), 3)))
        if not items:
            return "当前没有待办。"
        return "\n".join(
            f"- [{t.get('priority','mid')}] {t.get('due','无期限')} {t.get('title')}"
            f"（{t.get('tag','')}）" + ("（已完成）" if t.get("done") else "")
            for t in items
        )

    @tool
    def add_todo(title: str, due: str = "", priority: str = "mid", tag: str = "") -> str:
        """新增待办。priority 可选 high/mid/low；due 为 YYYY-MM-DD，可留空。"""
        due = _clip(due, 10)
        if due and not __import__("re").fullmatch(r"\d{4}-\d{2}-\d{2}", due):
            return "失败：due 需为 YYYY-MM-DD 格式。"
        t = store.add("todos", {
            "title": _clip(title, 80) or "未命名待办", "due": due,
            "priority": priority if priority in ("high", "mid", "low") else "mid",
            "tag": _clip(tag, 16) or "智能助手", "done": False,
        }, prefix="at")
        return f"已新增待办：「{t['title']}」" + (f"，期限 {t['due']}" if t["due"] else "")

    @tool
    def list_projects() -> str:
        """查询全部科研项目（名称、编号、状态、截止）。"""
        ps = store.list("projects")
        if not ps:
            return "暂无项目。"
        return "\n".join(
            f"- {p.get('name')}（{p.get('code','')}）[{p.get('status','')}]"
            f" 截止 {p.get('deadline','')}" for p in ps
        )

    @tool
    def list_courses() -> str:
        """查询本学期全部课程（名称、编码、班级）。"""
        cs = store.list("courses")
        if not cs:
            return "暂无课程。"
        return "\n".join(
            f"- {c.get('name')}（{c.get('code','')}）{c.get('semester','')}"
            for c in cs
        )

    @tool
    def get_course(name: str) -> str:
        """查询单门课程详情：简介、大纲与教学日历。name 为课程名称关键词。"""
        kw = _clip(name, 40)
        cs = [c for c in store.list("courses") if kw in str(c.get("name", ""))]
        if not cs:
            return f"没有找到名称包含「{kw}」的课程。"
        c = cs[0]
        lines = [f"课程：{c.get('name')}（{c.get('code','')}）",
                 f"简介：{c.get('intro','')}"]
        if c.get("syllabus"):
            lines.append("大纲：" + "；".join(
                f"{s.get('week','')}-{s.get('topic', s.get('title',''))}"
                for s in c["syllabus"][:20]))
        if c.get("calendar"):
            lines.append("日历前 6 行：" + "；".join(
                f"第{r.get('week')}周{r.get('date','')} {r.get('topic','')}"
                for r in c["calendar"][:6]))
        return "\n".join(lines)

    @tool
    def list_students() -> str:
        """查询指导学生（姓名、学位、方向、论文进度）。"""
        ss = store.list("students")
        if not ss:
            return "暂无学生。"
        return "\n".join(
            f"- {s.get('name')}[{s.get('degree','')}] {s.get('direction','')}"
            f" 论文：{s.get('thesisTitle','')}（{s.get('stage','')}）" for s in ss
        )

    @tool
    def search_literature(keyword: str, limit: int = 8) -> str:
        """检索个人文献仓库。keyword 匹配标题/作者/期刊/方向。"""
        kw = _clip(keyword, 40)
        lits = [l for l in store.list("literature") if kw in "".join(
            str(l.get(f, "")) for f in ("title", "authors", "journal", "direction", "note")
        )][: max(1, min(int(limit or 8), 20))]
        if not lits:
            return f"文献仓库中没有匹配「{kw}」的条目。"
        return "\n".join(
            f"- {l.get('title')}（{l.get('authors','')[:40]}）{l.get('journal','')}"
            f" [{l.get('direction','')}]" for l in lits
        )

    @tool
    def get_profile() -> str:
        """查询教师个人资料（姓名、职称、院系、联系方式、研究方向）。"""
        p = store.get_profile()
        return "\n".join(f"{k}: {v}" for k, v in p.items() if v and k not in ("id",))

    @tool
    def search_kb(query: str, top_k: int = 5) -> str:
        """检索教师个人知识库（上传的课程资料、规章制度、专业文档等）。query 为检索问题。"""
        hits = kb_util.search(store, _clip(query, 200), top_k=min(int(top_k or 5), 8))
        if not hits:
            return "知识库中没有检索到相关内容。"
        return "\n\n".join(
            f"【{h['docName']} · 片段{h['idx'] + 1}】{h['text'][:KB_CONTEXT_MAX]}"
            for h in hits
        )

    return [query_events, add_event, list_todos, add_todo, list_projects,
            list_courses, get_course, list_students, search_literature,
            get_profile, search_kb]


def _system_prompt() -> str:
    d = date.today()
    return SYSTEM_PROMPT.format(today=d.isoformat(), weekday="一二三四五六日"[d.weekday()])


def _steps_of(messages) -> list[dict]:
    """从消息流提取工具调用轨迹：谁被调用、入参、结果摘要。"""
    steps: list[dict] = []
    for m in messages:
        calls = getattr(m, "tool_calls", None)
        if calls:
            for c in calls:
                steps.append({"tool": c.get("name") or c["args"].get("__name__", ""),
                              "args": {k: v for k, v in (c.get("args") or {}).items()
                                       if k != "__arg1"},
                              "summary": ""})
        elif type(m).__name__ == "ToolMessage" and steps and not steps[-1]["summary"]:
            steps[-1]["summary"] = _clip(getattr(m, "content", ""), STEP_TEXT_MAX)
    return steps


def run_agent(store: Store, history: list[dict], message: str) -> dict:
    """执行一轮对话。history 为 [{role, content}]，role ∈ user/assistant。"""
    cfg = llm_util.real_llm_config(store)
    if not cfg.get("ready"):
        raise PermissionError("尚未配置大模型（API Key），请先在「智能助手 → 设置」中完成配置。")

    from langchain.agents import create_agent

    agent = create_agent(
        model=llm_util.build_llm(cfg),
        tools=make_tools(store),
        system_prompt=_system_prompt(),
    )
    msgs = []
    for h in history[-HISTORY_ROUNDS * 2:]:
        if h.get("role") == "user":
            msgs.append(HumanMessage(content=_clip(h.get("content"), 4000)))
        elif h.get("role") == "assistant":
            msgs.append(AIMessage(content=_clip(h.get("content"), 6000)))
    msgs.append(HumanMessage(content=_clip(message, 4000)))

    result = agent.invoke({"messages": msgs})
    out = result.get("messages", [])
    content = ""
    for m in reversed(out):
        if isinstance(m, AIMessage) and (getattr(m, "content", "") or "").strip():
            content = m.content if isinstance(m.content, str) else str(m.content)
            break
    return {"content": content.strip() or "（模型没有返回内容）", "steps": _steps_of(out)}


def new_session_id() -> str:
    return uid("as")
