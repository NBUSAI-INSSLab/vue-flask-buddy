"""12 项教研工具的真实实现（纯逻辑，无 Web 框架依赖，可独立单测）。

设计约定
--------
每个工具 = 一个纯函数 ``fn(ctx: ToolContext) -> ToolResult``：

* ``ToolContext`` 打包了 store、参数字典与上传文件，工具不直接触碰 HTTP；
* ``ToolResult`` 统一描述产出（摘要 / 指标 / 正文 / 表格 / 内存文件）；
* 文件产出以 ``OutFile(name, data, mime)`` 形式返回，由 API 层落盘并提供下载链接。

这样工具逻辑可以脱离 Flask 单测（见 tests/test_tools.py），新增工具也无需改动接口层。
"""
from __future__ import annotations

import csv as _csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .utils import (
    cn_date,
    days_until,
    day_offset,
    fmt,
    parse_ymd,
    safe_name,
    today,
    weekday_cn,
)

_XLSX_LINE_TERMINATOR = "\r\n"


# =====================================================================
# 结果 / 上下文
# =====================================================================
@dataclass
class OutFile:
    """内存中的产出文件（由 API 层落盘并返回下载地址）。"""

    name: str
    data: bytes
    mime: str = "text/plain"


@dataclass
class ToolResult:
    summary: str = ""
    metrics: list[tuple[str, str, str]] = field(default_factory=list)
    text: str = ""
    table: tuple[list[str], list[list]] | None = None
    files: list[OutFile] = field(default_factory=list)
    log: str = ""
    ok: bool = True


@dataclass
class ToolContext:
    store: object
    params: dict
    files: list[dict] = field(default_factory=list)  # [{name, data: bytes}]

    def p(self, key, default=None):
        v = self.params.get(key, default)
        return default if v is None or v == "" else v

    def pi(self, key, default: int = 0) -> int:
        try:
            return int(float(str(self.params.get(key, default)).strip()))
        except (TypeError, ValueError):
            return default

    def pf(self, key, default: float = 0.0) -> float:
        try:
            return float(str(self.params.get(key, default)).strip())
        except (TypeError, ValueError):
            return default

    def pb(self, key, default: bool = False) -> bool:
        """读布尔参数：兼容真 bool 与表单字符串（"是"/"true"/"1"/"写入…"）。"""
        v = self.params.get(key, default)
        if isinstance(v, bool):
            return v
        if v is None:
            return default
        s = str(v).strip().lower()
        if s in ("", "0", "false", "no", "否", "不", "关闭"):
            return False
        if s in ("1", "true", "yes", "是", "开启", "开"):
            return True
        return s.startswith("是") or "写入" in s or "扫描" in s


# =====================================================================
# 通用文件构造
# =====================================================================
def _csv_file(name: str, header: list, rows: list[list], extra: list[list] | None = None) -> OutFile:
    buf = io.StringIO(newline="")
    w = _csv.writer(buf, lineterminator=_XLSX_LINE_TERMINATOR)
    w.writerow(header)
    w.writerows(rows)
    for r in (extra or []):
        w.writerow(r)
    return OutFile(name, b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8"), "text/csv")


def _text_file(name: str, content: str, mime: str = "text/plain") -> OutFile:
    return OutFile(name, content.encode("utf-8"), mime)


# =====================================================================
# 1. 教学日历编排
# =====================================================================
def run_teaching_calendar(ctx: ToolContext) -> ToolResult:
    """按教学周把课程大纲铺到自然周，跳过节假日与调休日。"""
    course = ctx.store.get("courses", ctx.p("course_id"))
    if not course:
        # 兼容表单传来的 "CS301 计算机网络" 标签
        lab = str(ctx.p("course_label", "") or "").strip()
        if lab:
            for c in ctx.store.list("courses"):
                if lab.startswith(str(c.get("code", ""))) or lab == str(c.get("name", "")) \
                        or lab.endswith(str(c.get("name", ""))):
                    course = c
                    break
    if not course:
        return ToolResult(summary="未找到所选课程，请先在「课程资源」中创建。")

    syl = course.get("syllabus") or []
    if not syl:
        return ToolResult(summary=f"课程「{course.get('name')}」尚未录入教学大纲，无法编排。")

    start = parse_ymd(ctx.p("start_date"))
    if not start:
        return ToolResult(summary="开始日期无效。")

    skip_holidays = ctx.pb("skip_holidays", True)
    holidays: set[str] = set()
    for chunk in re.split(r"[,，;；\s]+", str(ctx.p("holidays", "") or "")):
        if not chunk:
            continue
        d = parse_ymd(chunk)
        if d:
            holidays.add(d.isoformat())
            if skip_holidays:
                holidays.add((d + timedelta(days=1)).isoformat())
                holidays.add((d - timedelta(days=1)).isoformat())

    sessions = max(1, min(5, ctx.pi("sessions_per_week", 2)))
    # 上课星期：1=周一 … 7=周日（Python weekday: 周一=0）
    dow_raw = str(ctx.p("weekdays", "") or "")
    if dow_raw:
        try:
            dows = sorted({int(x) - 1 for x in re.split(r"[,，\s]+", dow_raw) if x.strip()})
            dows = [d for d in dows if 0 <= d <= 6] or [0, 2][:sessions]
        except ValueError:
            dows = [0, 2][:sessions]
    else:
        dows = [0, 2, 4, 1, 3][:sessions]

    def hours_of(ch) -> int:
        try:
            return max(1, int(float(str(ch.get("hours") or 1))))
        except (TypeError, ValueError):
            return 1

    hours_per_session = max(1, ctx.pi("hours_per_session", 2))

    lines: list[str] = []
    rows: list[list] = []
    cursor = start
    week_no = 1
    skipped: list[str] = []
    ch_idx = 0
    remaining = hours_of(syl[0])
    session_no = 0
    guard = 0

    while ch_idx < len(syl) and guard < 400:
        guard += 1
        day_hits = [cursor + timedelta(days=(d - cursor.weekday()) % 7) for d in dows]
        day_hits = sorted({d for d in day_hits if d >= cursor})
        if not day_hits:
            cursor += timedelta(days=7)
            continue
        for d in day_hits:
            if ch_idx >= len(syl):
                break
            if skip_holidays and d.isoformat() in holidays:
                skipped.append(f"{d.isoformat()}（周{weekday_cn(d)}）顺延")
                continue
            ch = syl[ch_idx]
            session_no += 1
            take = min(hours_per_session, max(1, remaining))
            rows.append([
                f"第 {week_no} 周", f"{d.month}/{d.day} 周{weekday_cn(d)}",
                f"第 {session_no} 次", ch.get("chapter", ""), f"{take} 学时",
                ch.get("point", ""),
            ])
            lines.append(
                f"第 {week_no:>2} 周  周{weekday_cn(d)}  {d.isoformat()}   "
                f"[{ch.get('type', '讲授')}] {ch.get('chapter', '')}  ({take} 学时)"
                + (f"   要点：{ch.get('point')}" if ch.get("point") else "")
            )
            remaining -= take
            if remaining <= 0:
                ch_idx += 1
                if ch_idx < len(syl):
                    remaining = hours_of(syl[ch_idx])
        cursor += timedelta(days=7)
        week_no += 1

    if not rows:
        return ToolResult(summary="未能生成任何课次，请检查开始日期与上课星期设置。")

    total_hours = sum(int(r[4].split()[0]) for r in rows)
    text = "\n".join(lines)
    if skipped:
        text += "\n\n已顺延日期：\n  " + "\n  ".join(skipped)

    return ToolResult(
        summary=f"《{course.get('name')}》共编排 {len(rows)} 次课、{total_hours} 学时，"
                f"覆盖 {week_no - 1} 个教学周。",
        metrics=[("课次", str(len(rows)), "次"), ("总学时", str(total_hours), "学时"),
                 ("教学周", str(week_no - 1), "周"), ("顺延", str(len(skipped)), "天")],
        table=(["教学周", "日期", "课次", "章节", "学时", "教学要点"], rows),
        text=text,
        files=[_csv_file(f"教学日历-{safe_name(course.get('name', ''))}-{today()}.csv",
                         ["教学周", "日期", "课次", "章节", "学时", "教学要点"], rows)],
        log=f"编排《{course.get('name')}》教学日历，{len(rows)} 次课",
    )


# =====================================================================
# 2. 成绩批量计算
# =====================================================================
def run_grade_calc(ctx: ToolContext) -> ToolResult:
    """按权重合成总评，支持缺考/缓考标记与等级换算。"""
    raw = str(ctx.p("raw", "") or "")
    if not raw.strip():
        return ToolResult(summary="请粘贴成绩数据（每行一个学生）。")

    w_usual, w_mid, w_final = ctx.pf("w_usual", 30.0), ctx.pf("w_mid", 20.0), ctx.pf("w_final", 50.0)
    w_total = w_usual + w_mid + w_final
    if w_total <= 0:
        return ToolResult(summary="权重之和必须大于 0。")
    w_usual, w_mid, w_final = w_usual / w_total, w_mid / w_total, w_final / w_total

    fail_line, curve = ctx.pf("fail_line", 60.0), ctx.pf("curve", 0.0)

    rows: list[list] = []
    skipped: list[str] = []
    total: list[float] = []
    passed = failed = 0

    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        parts = [x for x in re.split(r"[,\t;，\s]+", ln) if x != ""]
        if len(parts) < 4:
            skipped.append(ln)
            continue
        name = parts[0]
        try:
            usual, mid, final = float(parts[1]), float(parts[2]), float(parts[3])
        except ValueError:
            skipped.append(ln)
            continue
        note = ""
        if any(x in ("缺考", "缓考", "免修") for x in parts):
            note = "特殊处理"
            final = 0.0
        score = max(0.0, min(100.0, usual * w_usual + mid * w_mid + final * w_final + curve))
        grade = ("优" if score >= 90 else "良" if score >= 80
                 else "中" if score >= 70 else "及格" if score >= fail_line else "不及格")
        if grade == "不及格":
            failed += 1
        else:
            passed += 1
        total.append(score)
        rows.append([name, f"{usual:g}", f"{mid:g}", f"{final:g}", f"{score:.1f}", grade, note])

    if not rows:
        return ToolResult(summary="没有解析到有效数据行。请按「姓名 平时 期中 期末」每行一条填写。")

    avg = sum(total) / len(total)
    best, worst = max(total), min(total)
    rate = passed / len(rows) * 100

    bands = ["90-100", "80-89", "70-79", "60-69", "<60"]
    dist = {k: 0 for k in bands}
    for s in total:
        if s >= 90:
            dist["90-100"] += 1
        elif s >= 80:
            dist["80-89"] += 1
        elif s >= 70:
            dist["70-79"] += 1
        elif s >= 60:
            dist["60-69"] += 1
        else:
            dist["<60"] += 1

    lines = [
        f"权重（归一化后）：平时 {w_usual:.0%} / 期中 {w_mid:.0%} / 期末 {w_final:.0%}"
        f"    及格线 {fail_line:g}    调分 +{curve:g}",
        "",
        "分数段分布：",
    ]
    for k in bands:
        bar = "█" * int(round(dist[k] / max(1, len(rows)) * 40))
        lines.append(f"  {k:>7} | {bar:<40} {dist[k]:>3} 人")
    if skipped:
        lines += ["", f"未能解析的行（{len(skipped)} 行）：", "  " + "; ".join(skipped[:8])]
    lines += ["", "不及格名单：",
              "  " + ("、".join(r[0] for r in rows if r[5] == "不及格") or "无")]

    return ToolResult(
        summary=f"完成 {len(rows)} 名学生总评计算，平均分 {avg:.2f}，及格率 {rate:.1f}%。",
        metrics=[("学生数", str(len(rows)), "人"), ("平均分", f"{avg:.2f}", ""),
                 ("及格率", f"{rate:.1f}", "%"), ("不及格", str(failed), "人")],
        table=(["姓名", "平时", "期中", "期末", "总评", "等级", "备注"], rows),
        text="\n".join(lines),
        files=[_csv_file(f"成绩汇总-{today()}.csv",
                         ["姓名", "平时", "期中", "期末", "总评", "等级", "备注"], rows,
                         [[], ["平均分", f"{avg:.2f}", "最高", f"{best:.1f}",
                               "最低", f"{worst:.1f}", f"及格率 {rate:.1f}%"]])],
        log=f"批量计算成绩 {len(rows)} 人，平均 {avg:.1f}",
    )


# =====================================================================
# 3. 参考文献格式转换
# =====================================================================
class _BibEntry:
    __slots__ = ("kind", "key", "f")

    def __init__(self, kind="", key="", fields=None):
        self.kind = kind
        self.key = key
        self.f = fields or {}


def _parse_bibtex(text: str) -> list[_BibEntry]:
    out: list[_BibEntry] = []
    for m in re.finditer(r"@(\w+)\s*[{(]\s*([^,]+),", text):
        kind, key = m.group(1).lower(), m.group(2).strip()
        tail = text[m.end():]
        nxt = re.search(r"\n\s*@", tail)
        body = tail[:nxt.start()] if nxt else tail
        fields: dict[str, str] = {}
        for fm in re.finditer(r"(\w+)\s*=\s*[\{\"](.+?)[\}\"]\s*,?\s*(?=\n|$|\w+\s*=)",
                              body, re.S):
            fields[fm.group(1).lower()] = re.sub(r"\s+", " ", fm.group(2)).strip()
        if kind in ("string", "preamble", "comment"):
            continue
        out.append(_BibEntry(kind, key, fields))
    return out


def _parse_ris(text: str) -> list[_BibEntry]:
    out: list[_BibEntry] = []
    cur: dict[str, str] = {}
    kind_map = {"JOUR": "article", "CONF": "inproceedings", "BOOK": "book",
                "THES": "phdthesis", "RPRT": "techreport", "NEWS": "article"}
    for ln in text.splitlines():
        ln = ln.rstrip()
        m = re.match(r"^([A-Z][A-Z0-9])\s{1,2}-\s?(.*)$", ln)
        if not m:
            if ln.strip() in ("ER  -", "ER -") and cur:
                out.append(_BibEntry(kind_map.get(cur.get("TY", ""), "article"), "", cur))
                cur = {}
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "TY":
            cur = {}
        if tag in ("AU", "A1"):
            cur["author"] = (cur.get("author", "") + " and " + val).strip(" and ")
        elif tag in ("TI", "T1"):
            cur["title"] = val
        elif tag in ("JO", "JF", "T2", "JA"):
            cur.setdefault("journal", val)
        elif tag in ("PY", "Y1", "DA"):
            cur["year"] = val[:4]
        elif tag in ("DO", "DI"):
            cur["doi"] = val
        elif tag == "VL":
            cur["volume"] = val
        elif tag == "IS":
            cur["number"] = val
        elif tag == "SP":
            cur["start_page"] = val
        elif tag == "EP":
            cur["end_page"] = val
        elif tag == "PB":
            cur["publisher"] = val
        elif tag == "KW":
            cur["keywords"] = (cur.get("keywords", "") + ", " + val).strip(", ")
    if cur:
        out.append(_BibEntry(kind_map.get(cur.get("TY", ""), "article"), "", cur))
    return out


def _authors_gbt(author_field: str, limit: int = 3) -> str:
    if not author_field:
        return ""
    names = []
    for p in re.split(r"\s+and\s+|;|；", author_field):
        p = p.strip()
        if not p:
            continue
        if "," in p:  # BibTeX 的 "Last, First"
            last, _, first = p.partition(",")
            p = f"{last.strip()} {first.strip()}".strip()
        names.append(p)
    if len(names) > limit:
        return ", ".join(names[:limit]) + ", et al"
    return ", ".join(names)


def _to_gbt(e: _BibEntry) -> str:
    f = e.f
    authors = _authors_gbt(f.get("author", ""))
    title, year = f.get("title", ""), f.get("year", "")
    if e.kind == "article":
        jn = f.get("journal") or f.get("journaltitle") or "—"
        pages = ""
        if f.get("start_page"):
            pages = f"({f.get('number', '')}): {f['start_page']}" + (f"-{f['end_page']}" if f.get("end_page") else "")
        elif f.get("pages"):
            pages = f": {f['pages']}"
        bits = f"{authors}. {title}[J]. {jn}, {year}"
        if f.get("volume"):
            bits += f", {f['volume']}"
        return bits + pages + "."
    if e.kind in ("inproceedings", "conference"):
        bk = f.get("booktitle") or f.get("eventtitle") or "—"
        return f"{authors}. {title}[C]//{bk}. {f.get('address', '')}, {year}" + (f": {f['pages']}" if f.get("pages") else "") + "."
    if e.kind in ("phdthesis", "mastersthesis"):
        return f"{authors}. {title}[D]. {f.get('school', '—')}, {year}."
    if e.kind in ("techreport", "report"):
        return f"{authors}. {title}[R]. {f.get('institution', '—')}, {year}."
    if e.kind in ("book", "inbook"):
        return f"{authors}. {title}[M]. {f.get('address', '')}: {f.get('publisher', '—')}, {year}."
    if e.kind in ("misc", "online"):
        return f"{authors}. {title}[EB/OL]. {f.get('url', '')}, {year}."
    return f"{authors}. {title}[Z]. {year}."


def _to_apa(e: _BibEntry) -> str:
    f = e.f
    authors = _authors_gbt(f.get("author", ""), limit=20)
    year, title = f.get("year", "n.d."), f.get("title", "")
    if e.kind == "article":
        return (f"{authors} ({year}). {title}. *{f.get('journal', '—')}*, "
                f"{f.get('volume', '')}({f.get('number', '')}), {f.get('pages', '')}.")
    if e.kind in ("inproceedings", "conference"):
        return f"{authors} ({year}). {title}. In *{f.get('booktitle', '—')}* (pp. {f.get('pages', '')})."
    if e.kind == "book":
        return f"{authors} ({year}). *{title}*. {f.get('publisher', '')}."
    return f"{authors} ({year}). {title}."


def _to_ris(e: _BibEntry) -> str:
    f = e.f
    ty = {"article": "JOUR", "inproceedings": "CONF", "conference": "CONF", "book": "BOOK",
          "phdthesis": "THES", "mastersthesis": "THES", "techreport": "RPRT"}.get(e.kind, "GEN")
    lines = [f"TY  - {ty}"]
    for name in re.split(r"\s+and\s+|;|；", f.get("author", "")):
        name = name.strip()
        if name:
            if "," in name:
                last, _, first = name.partition(",")
                name = f"{last.strip()}, {first.strip()}"
            lines.append(f"AU  - {name}")
    if f.get("title"):
        lines.append(f"TI  - {f['title']}")
    for key, tag in (("journal", "JO"), ("booktitle", "T2"), ("year", "PY"), ("volume", "VL"),
                     ("number", "IS"), ("start_page", "SP"), ("end_page", "EP"),
                     ("publisher", "PB"), ("doi", "DO"), ("url", "UR"), ("abstract", "AB")):
        if f.get(key):
            lines.append(f"{tag}  - {f[key]}")
    lines.append("ER  - ")
    return "\n".join(lines)


def _to_bibtex(e: _BibEntry) -> str:
    f = e.f
    key = e.key or (safe_name((f.get("author", "anon").split()[0] if f.get("author") else "anon"))
                    + str(f.get("year", "")))
    key = re.sub(r"[^A-Za-z0-9_:.\-]", "", key) or "ref"
    body = [f"  {k:<9} = {{{f[field]}}}," for k, field in
            (("author", "author"), ("title", "title"), ("journal", "journal"),
             ("booktitle", "booktitle"), ("year", "year"), ("volume", "volume"),
             ("number", "number"), ("pages", "pages"), ("publisher", "publisher"),
             ("doi", "doi")) if f.get(field)]
    if body:
        body[-1] = body[-1].rstrip(",")
    return f"@{e.kind or 'article'}{{{key},\n" + "\n".join(body) + "\n}"


def run_cite_convert(ctx: ToolContext) -> ToolResult:
    """BibTeX / RIS / GB-T 7714 / APA 之间的格式转换。"""
    raw = str(ctx.p("raw", "") or "")
    if not raw.strip():
        return ToolResult(summary="请粘贴待转换的文献数据。")

    src = ctx.p("src_format", "自动识别")
    dst = ctx.p("dst_format", "GB/T 7714")
    sort_by = ctx.p("sort_by", "保持原顺序")

    if src == "自动识别":
        if re.search(r"^@\w+\s*[{(]", raw, re.M):
            src = "BibTeX"
        elif re.search(r"^TY\s{1,2}-", raw, re.M):
            src = "RIS"
        else:
            src = "BibTeX"

    entries = _parse_bibtex(raw) if src == "BibTeX" else (_parse_ris(raw) if src == "RIS" else [])

    if not entries and src != "GB/T 7714":
        return ToolResult(summary=f"未能从输入中解析出 {src} 条目，请检查格式。")

    if not entries:  # 纯文本列表：仅做规范化编号
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        return ToolResult(
            summary=f"已规范化 {len(lines)} 条参考文献（文本格式直转）。",
            metrics=[("条目数", str(len(lines)), "条")],
            text="\n".join(f"[{i + 1}] {ln}" for i, ln in enumerate(lines)),
            files=[_text_file(f"参考文献-GBT7714-{today()}.txt",
                              "\n".join(f"[{i + 1}] {ln}" for i, ln in enumerate(lines)) + "\n")],
            log=f"规范化参考文献 {len(lines)} 条",
        )

    if sort_by == "按年份":
        entries.sort(key=lambda e: e.f.get("year", "0") or "0")
    elif sort_by == "按作者":
        entries.sort(key=lambda e: (e.f.get("author", "") or "zzz").lower())
    elif sort_by == "按标题":
        entries.sort(key=lambda e: (e.f.get("title", "") or "zzz").lower())

    fn = {"GB/T 7714": _to_gbt, "APA": _to_apa, "RIS": _to_ris, "BibTeX": _to_bibtex}.get(dst, _to_gbt)
    out_items = [fn(e) for e in entries]

    if dst == "GB/T 7714":
        body = "\n".join(f"[{i + 1}] {x}" for i, x in enumerate(out_items))
        ext = "txt"
    else:
        body = "\n\n".join(out_items)
        ext = "bib" if dst == "BibTeX" else ("ris" if dst == "RIS" else "txt")

    return ToolResult(
        summary=f"已将 {len(entries)} 条文献从 {src} 转换为 {dst} 格式。",
        metrics=[("条目数", str(len(entries)), "条"), ("源格式", src, ""), ("目标格式", dst, "")],
        text=body,
        files=[_text_file(f"参考文献-{dst.replace('/', '')}-{today()}.{ext}", body + "\n")],
        log=f"转换参考文献 {len(entries)} 条：{src} → {dst}",
    )


# =====================================================================
# 4. 经费预算测算
# =====================================================================
BUDGET_RULES = {
    "设备费": {"max": 0.30, "note": "一般不超过直接费用的 30%（数学、管理类等更低）"},
    "材料费": {"max": 1.00, "note": "据实测算，无硬性上限"},
    "测试化验加工费": {"max": 0.30, "note": "外协比例过高需说明必要性"},
    "差旅费": {"max": 0.20, "note": "含会议费时可到 20% 左右"},
    "会议费": {"max": 0.10, "note": "与差旅费合计一般不超 20%"},
    "出版/文献/信息传播费": {"max": 0.10, "note": "论文版面费、文献购置等"},
    "劳务费": {"max": 0.30, "note": "研究生/博士后劳务，无比例限制但需实名发放"},
    "专家咨询费": {"max": 0.10, "note": "按人次与标准测算"},
    "其他支出": {"max": 0.10, "note": "需逐项说明用途"},
}


def run_budget_calc(ctx: ToolContext) -> ToolResult:
    """按科目测算项目预算并校验比例限制。"""
    total = ctx.pf("total", 0.0)
    if total <= 0:
        return ToolResult(summary="请填写项目总经费（万元）。")

    items: list[tuple[str, float]] = []
    for key in BUDGET_RULES:
        v = ctx.pf(f"_{key}", 0.0) or ctx.pf(key, 0.0)
        if v > 0:
            items.append((key, v))
    if not items:
        return ToolResult(summary="至少填写一个科目的预算金额。")

    used = sum(v for _, v in items)
    allocated = ctx.pf("allocated", 0.0)
    rows: list[list] = []
    warns: list[str] = []
    for name, amt in sorted(items, key=lambda kv: -kv[1]):
        ratio = amt / total
        rule = BUDGET_RULES.get(name, {"max": 1.0, "note": ""})
        status = "合规"
        if ratio > rule["max"] + 1e-9:
            status = f"超限（上限 {rule['max']:.0%}）"
            warns.append(f"{name} 超限：占比 {ratio:.1%}，超过建议上限 {rule['max']:.0%} —— {rule['note']}")
        rows.append([name, f"{amt:.2f}", f"{ratio:.1%}", f"{rule['max']:.0%}", status, rule["note"]])

    remain = total - used
    lines = [
        f"项目总经费：{total:.2f} 万元",
        f"已分配合计：{used:.2f} 万元（占 {used / total:.1%}）",
        f"剩余额度　：{remain:.2f} 万元（占 {remain / total:.1%}）",
    ]
    if allocated:
        lines.append(f"已支出/已分配：{allocated:.2f} 万元（执行率 {allocated / total:.1%}）")
    lines.append("")
    if warns:
        lines.append("⚠ 比例校验提示：")
        lines += [f"  · {w}" for w in warns]
    else:
        lines.append("✓ 所有科目比例均在建议范围内。")
    if remain < -1e-6:
        lines.append(f"\n⚠ 预算超出总额 {abs(remain):.2f} 万元，请调整科目金额。")
    lines += ["", "科目占比："]
    for name, amt in sorted(items, key=lambda kv: -kv[1]):
        bar = "█" * max(1, int(round(amt / total * 36)))
        lines.append(f"  {name:<14} | {bar:<36} {amt / total:>6.1%}")

    return ToolResult(
        summary=f"预算测算完成：已分配 {used:.2f} / {total:.2f} 万元，"
                + ("全部科目合规。" if not warns else f"{len(warns)} 个科目超限。"),
        metrics=[("总经费", f"{total:.1f}", "万元"), ("已分配", f"{used:.1f}", "万元"),
                 ("剩余", f"{remain:.1f}", "万元"), ("超限科目", str(len(warns)), "个")],
        table=(["科目", "金额(万元)", "占比", "建议上限", "校验", "说明"], rows),
        text="\n".join(lines),
        files=[_csv_file(f"经费预算-{today()}.csv",
                         ["科目", "金额(万元)", "占比", "建议上限", "校验", "说明"], rows,
                         [[], ["合计", f"{used:.2f}", f"{used / total:.1%}", "", "", ""]])],
        log=f"测算项目预算 {total:.1f} 万元，{len(items)} 个科目",
    )


# =====================================================================
# 5. 论文投稿进度追踪
# =====================================================================
SUBMISSION_STAGES = ["撰写中", "已投稿", "外审中", "大修", "小修", "已录用", "已发表", "被拒"]


def run_submission_track(ctx: ToolContext) -> ToolResult:
    """从成果台账提取投稿状态，计算在审时长并给出逾期提醒。"""
    items = ctx.store.list("achievements")
    if ctx.p("only_paper", "仅期刊论文") == "仅期刊论文":
        items = [a for a in items if a.get("type") in ("期刊论文", "会议论文")]
    if not items:
        return ToolResult(summary="成果台账中没有符合条件的论文记录。")

    warn_days = ctx.pi("warn_days", 90)
    rows: list[list] = []
    alerts: list[str] = []
    pend: list[tuple[str, str, str]] = []
    done = 0
    stage_count: dict[str, int] = {}

    for a in items:
        st = a.get("status", "撰写中")
        stage_count[st] = stage_count.get(st, 0) + 1
        d = parse_ymd(a.get("date"))
        elapsed = (date.today() - d).days if d else None
        verdict = "—"
        if st in ("已发表", "已录用", "已授权", "已登记", "已交付", "已获奖"):
            done += 1
            verdict = "已完成"
        elif st in ("审稿中", "外审中", "实质审查", "投稿中", "大修", "小修"):
            if elapsed is not None and elapsed > warn_days:
                verdict = f"⚠ 已滞留 {elapsed} 天"
                alerts.append(f"《{(a.get('title') or '')[:34]}》在审 {elapsed} 天，建议催稿或改投")
            else:
                verdict = "在审（正常）"
            pend.append((a.get("date") or "", (a.get("title") or "")[:46],
                         f"{elapsed} 天" if elapsed is not None else "—"))
        elif st in ("被拒", "退稿"):
            verdict = "已被拒，需改投"
        rows.append([(a.get("title") or "")[:46], a.get("venue", "—"), st,
                     a.get("date") or "—", f"{elapsed} 天" if elapsed is not None else "—", verdict])

    lines = [f"共 {len(items)} 篇论文，已完成 {done} 篇，在审/在投 {len(items) - done} 篇。", "", "阶段分布："]
    for st in SUBMISSION_STAGES:
        if stage_count.get(st):
            lines.append(f"  {st:<8} {stage_count[st]:>3} 篇  " + "●" * stage_count[st])
    lines.append("")
    if alerts:
        lines += [f"逾期提醒（在审超过 {warn_days} 天）："] + [f"  · {x}" for x in alerts]
    else:
        lines.append(f"✓ 没有在审超过 {warn_days} 天的稿件。")
    lines += ["", "在审时长排行："]
    if pend:
        lines += [f"  {dt:<12} {el:<8} {title}" for dt, title, el in sorted(pend, key=lambda x: x[0])]
    else:
        lines.append("  （当前无在审稿件）")

    return ToolResult(
        summary=f"共追踪 {len(items)} 篇论文，其中 {len(items) - done} 篇在投/在审，"
                f"{len(alerts)} 篇超期需处理。",
        metrics=[("论文总数", str(len(items)), "篇"), ("已完成", str(done), "篇"),
                 ("在审中", str(len(items) - done), "篇"), ("超期提醒", str(len(alerts)), "条")],
        table=(["标题", "投稿期刊", "当前状态", "状态日期", "历时", "判断"], rows),
        text="\n".join(lines),
        log=f"追踪论文投稿进度 {len(items)} 篇，{len(alerts)} 条超期提醒",
    )


# =====================================================================
# 6. 研究生培养进度看板
# =====================================================================
def run_student_board(ctx: ToolContext) -> ToolResult:
    """汇总各学生的里程碑达成率、进度与最近沟通。"""
    students = ctx.store.list("students")
    if not students:
        return ToolResult(summary="尚未录入学生信息。")

    scope = ctx.p("scope", "全部学生")
    if scope in ("硕士生", "博士生"):
        students = [s for s in students if s.get("degree") == scope[:-1]]
    elif scope == "进度滞后":
        students = [s for s in students if int(s.get("progress") or 0) < 50]
    if not students:
        return ToolResult(summary=f"「{scope}」范围内没有学生。")

    rows: list[list] = []
    alerts: list[str] = []
    prog_sum = 0
    for s in sorted(students, key=lambda x: -int(x.get("progress") or 0)):
        ms = s.get("milestones") or []
        n_done = sum(1 for m in ms if m.get("done"))
        rate = f"{n_done}/{len(ms)}" if ms else "—"
        prog = int(s.get("progress") or 0)
        prog_sum += prog
        logs = s.get("logs") or []
        last = logs[0].get("date") if logs else None
        gap = None
        if last:
            ld = parse_ymd(last)
            gap = (date.today() - ld).days if ld else None
        if gap is not None and gap > 30:
            alerts.append(f"{s.get('name')} 已 {gap} 天无沟通记录（{s.get('stage')}）")
        if prog < 30 and s.get("stage") in ("中期检查", "论文撰写", "答辩准备"):
            alerts.append(f"{s.get('name')} 进度 {prog}% 但阶段为「{s.get('stage')}」，进度滞后")
        rows.append([
            s.get("name", ""), s.get("degree", ""), s.get("grade", ""), s.get("stage", ""),
            f"{prog}%", rate, (s.get("thesisTitle") or "")[:34],
            f"{gap} 天前" if gap is not None else "无记录", s.get("direction", ""),
        ])

    avg = prog_sum / len(students)
    near = [s for s in students
            if (days_until(s.get("nextMeeting")) is not None
                and 0 <= (days_until(s.get("nextMeeting")) or 999) <= 7)]

    lines = [f"共 {len(students)} 名学生，平均论文进度 {avg:.1f}%。", "", "按进度排序："]
    for r in rows:
        bar = "█" * int(round(int(r[4].rstrip("%")) / 100 * 24))
        lines.append(f"  {r[0]:<5} {r[1]:<3} {r[4]:>4} |{bar:<24}| {r[3]:<8} 里程碑 {r[5]}")
    lines.append("")
    lines.append("本周需沟通：" + ("、".join(f"{s.get('name', '')}（{cn_date(s.get('nextMeeting'))}）"
                                        for s in near) or "无安排"))
    if alerts:
        lines += ["", "需关注："] + [f"  · {a}" for a in alerts]
    else:
        lines.append("\n✓ 各学生培养状态正常。")

    return ToolResult(
        summary=f"{len(students)} 名学生平均进度 {avg:.1f}%，"
                f"{len(near)} 人本周需沟通，{len(alerts)} 条关注项。",
        metrics=[("学生数", str(len(students)), "人"), ("平均进度", f"{avg:.1f}", "%"),
                 ("本周沟通", str(len(near)), "人"), ("关注项", str(len(alerts)), "条")],
        table=(["姓名", "层次", "年级", "论文阶段", "进度", "里程碑", "论文题目", "最近沟通", "方向"], rows),
        text="\n".join(lines),
        log=f"生成培养看板：{len(students)} 名学生",
    )


# =====================================================================
# 7. 值班与调课登记
# =====================================================================
def run_duty_log(ctx: ToolContext) -> ToolResult:
    """登记一次调课/监考/值班，写入日程并生成变更通知文本。"""
    kind = ctx.p("kind", "调课")
    title = ctx.p("course", "")
    if not title:
        return ToolResult(summary="请填写课程或事项名称。")

    orig, new = parse_ymd(ctx.p("orig_date")), parse_ymd(ctx.p("new_date"))
    if kind in ("调课", "补课") and (not orig or not new):
        return ToolResult(summary="调课/补课需要同时填写原定日期与新日期。")

    t_from, t_to = ctx.p("orig_time", ""), ctx.p("new_time", "")
    room, reason = ctx.p("room", ""), ctx.p("reason", "")
    notify = ctx.p("notify", "写入日程并生成通知")
    audience = ctx.p("audience", "全班学生 + 教务办")

    detail = {
        "调课": f"由 {orig} {t_from} 调整至 {new} {t_to}",
        "补课": f"新增补课 {new} {t_to}",
        "监考": f"监考安排 {new} {t_to}",
        "值班": f"值班安排 {new}",
        "代课": f"代课 {new} {t_to}",
    }.get(kind, kind)
    ev_type = {"调课": "上课", "补课": "上课", "代课": "上课", "监考": "其他", "值班": "其他"}.get(kind, "其他")

    written = False
    if str(notify).startswith("写入日程"):
        ctx.store.add("events", {
            "title": f"[{kind}] {title}", "type": ev_type,
            "date": (new or orig).isoformat(), "start": t_to or t_from or "08:00",
            "end": "", "location": room,
            "note": f"{detail}；原因：{reason or '未说明'}", "done": False,
        }, "e")
        written = True

    lines = [
        "【课程变更通知】", "",
        f"事项类型：{kind}", f"课程/事项：{title}", f"变更内容：{detail}",
        f"地点　　：{room or '（待定）'}", f"原因　　：{reason or '（未说明）'}",
        f"通知对象：{audience}", "",
        "请相关同学注意时间调整，如有冲突请于课前联系授课教师。",
        "—— 教师工作台自动生成",
    ]
    if written:
        lines.insert(2, "（已同步写入日程管理）")

    return ToolResult(
        summary=f"已登记{kind}：{title}（{detail}）" + ("，并写入日程。" if written else "。"),
        metrics=[("类型", kind, ""), ("课程", title[:12], ""), ("同步日程", "是" if written else "否", "")],
        text="\n".join(lines),
        files=[_text_file(f"课程变更通知-{today()}.txt", "\n".join(lines) + "\n")],
        log=f"登记{kind}：{title}",
    )


# =====================================================================
# 8. 学术会议纪要
# =====================================================================
def run_meeting_note(ctx: ToolContext) -> ToolResult:
    """生成结构化会议纪要，并把待办事项写入待办清单。"""
    title = ctx.p("title", "")
    if not title:
        return ToolResult(summary="请填写会议主题。")

    when = ctx.p("when", today())
    place = ctx.p("place", "线上")
    host = ctx.p("host", "")
    attendees = [x.strip() for x in re.split(r"[,，、;；\s]+", str(ctx.p("attendees", "") or "")) if x.strip()]
    agenda, conclusion = ctx.p("agenda", ""), ctx.p("conclusion", "")
    push = ctx.pb("push_todo", True)

    actions: list[tuple[str, str, str]] = []
    for ln in str(ctx.p("actions", "") or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        parts = [x.strip() for x in re.split(r"[|｜,，;；\t]+", ln) if x.strip()]
        d = parse_ymd(parts[2]) if len(parts) > 2 else None
        actions.append((parts[0], parts[1] if len(parts) > 1 else "待定",
                        d.isoformat() if d else ((parts[2] if len(parts) > 2 else "") or "未定")))

    md = [f"# 会议纪要：{title}", "",
          f"- **时间**：{when}", f"- **地点**：{place}",
          f"- **主持人**：{host or '—'}",
          f"- **参会人**：{'、'.join(attendees) if attendees else '—'}", "",
          "## 一、议题", "", agenda.strip() or "（未填写）", "",
          "## 二、讨论结论", "", conclusion.strip() or "（未填写）", "",
          "## 三、待办事项", ""]
    if actions:
        md += ["| 序号 | 事项 | 负责人 | 截止 |", "| --- | --- | --- | --- |"]
        md += [f"| {i} | {t} | {o} | {d} |" for i, (t, o, d) in enumerate(actions, 1)]
    else:
        md.append("（无）")
    md += ["", "---", f"*纪要生成时间：{datetime.now():%Y-%m-%d %H:%M}*"]
    text = "\n".join(md)

    added = 0
    if push and actions:
        for t, o, d in actions:
            ctx.store.add("todos", {
                "title": f"[{title[:12]}] {t}（{o}）",
                "due": d if parse_ymd(d) else day_offset(7),
                "priority": "mid", "done": False, "tag": "学术交流",
            }, "t")
            added += 1

    return ToolResult(
        summary=f"已生成《{title}》会议纪要，含 {len(actions)} 项待办"
                + (f"，其中 {added} 项已写入待办清单。" if added else "。"),
        metrics=[("参会人", str(len(attendees)), "人"), ("待办事项", str(len(actions)), "项"),
                 ("写入待办", str(added), "项")],
        text=text,
        files=[_text_file(f"会议纪要-{safe_name(title)}-{today()}.md", text + "\n", "text/markdown")],
        log=f"生成会议纪要《{title}》，{len(actions)} 项待办",
    )


# =====================================================================
# 9. PDF 批量合并与拆分
# =====================================================================
def _pdf_page_count(data: bytes) -> int:
    try:
        from pypdf import PdfReader  # type: ignore
        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:
        pass
    n = len(re.findall(rb"/Type\s*/Page[^s]", data))
    if n:
        return n
    m = re.findall(rb"/Count\s+(\d+)", data)
    return max((int(x) for x in m), default=0)


def run_pdf_toolkit(ctx: ToolContext) -> ToolResult:
    """PDF 合并 / 拆分 / 页面统计（服务端处理，文件不落前端）。"""
    mode = ctx.p("mode", "合并多个 PDF")
    files = ctx.files or []
    if not files:
        return ToolResult(summary="请先上传至少一个 PDF 文件。")

    infos = [[f["name"], str(_pdf_page_count(f["data"])), f"{len(f['data']) / 1024:.1f} KB"]
             for f in files]

    if mode == "仅统计信息":
        total = sum(int(r[1]) for r in infos)
        return ToolResult(
            summary=f"扫描 {len(files)} 个 PDF 文件，合计 {total} 页。",
            metrics=[("文件数", str(len(files)), "个"), ("总页数", str(total), "页")],
            table=(["文件名", "页数", "大小"], infos),
            text="\n".join(f"{r[0]:<40} {r[1]:>6} 页  {r[2]:>10}" for r in infos),
            log=f"统计 PDF 信息 {len(files)} 个文件",
        )

    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore
    except ImportError:
        return ToolResult(
            summary="服务端未安装 pypdf，无法执行合并/拆分。请运行：pip install pypdf",
            metrics=[("文件数", str(len(files)), "个")],
            table=(["文件名", "页数", "大小"], infos),
            text="提示：仅「统计信息」模式无需依赖。\n\n" +
                 "\n".join(f"  · {r[0]} — {r[1]} 页 / {r[2]}" for r in infos),
            log="PDF 工具：缺少 pypdf 依赖",
        )

    if mode == "合并多个 PDF":
        writer = PdfWriter()
        total = 0
        for f in files:
            try:
                reader = PdfReader(io.BytesIO(f["data"]))
            except Exception as exc:
                return ToolResult(summary=f"无法读取 {f['name']}：{exc}")
            for pg in reader.pages:
                writer.add_page(pg)
            total += len(reader.pages)
        buf = io.BytesIO()
        writer.write(buf)
        out_name = str(ctx.p("out_name", "") or f"合并结果-{today()}.pdf")
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"
        return ToolResult(
            summary=f"已合并 {len(files)} 个 PDF、共 {total} 页 → {safe_name(out_name)}",
            metrics=[("合并文件", str(len(files)), "个"), ("总页数", str(total), "页")],
            table=(["文件名", "页数", "大小"], infos),
            text="合并顺序：\n" + "\n".join(f"  {i + 1}. {r[0]}（{r[1]} 页）"
                                          for i, r in enumerate(infos)),
            files=[OutFile(safe_name(out_name), buf.getvalue(), "application/pdf")],
            log=f"合并 PDF {len(files)} 个文件 → {total} 页",
        )

    # 拆分（只处理第一个文件）
    src = files[0]
    reader = PdfReader(io.BytesIO(src["data"]))
    n = len(reader.pages)
    ranges = str(ctx.p("ranges", "") or "")
    groups: list[tuple[str, list[int]]] = []
    if ranges.strip():
        for chunk in re.split(r"[,，;；\n]+", ranges):
            chunk = chunk.strip()
            if not chunk:
                continue
            m = re.match(r"^(\d+)\s*[-~—]\s*(\d+)$", chunk)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                idxs = [i for i in range(a - 1, b) if 0 <= i < n]
                label = f"{a}-{b}"
            else:
                try:
                    idxs = [int(chunk) - 1] if 0 <= int(chunk) - 1 < n else []
                except ValueError:
                    idxs = []
                label = chunk
            if idxs:
                groups.append((label, idxs))
    else:
        step = max(1, ctx.pi("chunk", 1))
        groups = [(f"{i + 1}-{min(i + step, n)}", list(range(i, min(i + step, n))))
                  for i in range(0, n, step)]

    if not groups:
        return ToolResult(summary="没有解析出有效的页码范围。")

    stem = str(ctx.p("out_name", "") or "").strip() or f"{safe_name(src['name'].rsplit('.', 1)[0])}-拆分"
    made: list[OutFile] = []
    for label, idxs in groups:
        w = PdfWriter()
        for i in idxs:
            w.add_page(reader.pages[i])
        buf = io.BytesIO()
        w.write(buf)
        made.append(OutFile(f"{safe_name(stem)}-{label}.pdf", buf.getvalue(), "application/pdf"))

    return ToolResult(
        summary=f"已将 {src['name']}（{n} 页）拆分为 {len(made)} 个文件。",
        metrics=[("源文件页数", str(n), "页"), ("输出文件", str(len(made)), "个")],
        text="\n".join(f"  {f.name}" for f in made),
        files=made,
        log=f"拆分 PDF：{n} 页 → {len(made)} 个文件",
    )


# =====================================================================
# 10. 科研成果统计导出
# =====================================================================
def run_achievement_export(ctx: ToolContext) -> ToolResult:
    """按年度/类型导出成果清单，支持 CSV / JSON / Markdown。"""
    items = ctx.store.list("achievements")
    if not items:
        return ToolResult(summary="成果台账为空。")

    year = str(ctx.p("year", "全部年度"))
    typ = ctx.p("type", "全部类型")
    fmt_sel = ctx.p("format", "CSV（Excel 可直接打开）")
    with_score = ctx.p("with_score", "含业绩分") == "含业绩分"

    def keep(a: dict) -> bool:
        if year != "全部年度" and not (a.get("date") or "").startswith(year):
            return False
        return typ == "全部类型" or a.get("type") == typ

    sel = [a for a in items if keep(a)]
    if not sel:
        return ToolResult(summary=f"没有符合条件（{year} / {typ}）的成果。")
    sel.sort(key=lambda a: (a.get("date") or "0000", a.get("type") or ""))

    proj_name = {p["id"]: p.get("name", "") for p in ctx.store.list("projects")}
    header = ["序号", "成果名称", "类型", "级别", "作者", "本人角色", "发表/授权单位", "日期", "状态", "关联项目"]
    if with_score:
        header.append("业绩分")
    rows = []
    for i, a in enumerate(sel, 1):
        r = [str(i), a.get("title", ""), a.get("type", ""), a.get("level", ""), a.get("authors", ""),
             a.get("role", ""), a.get("venue", ""), a.get("date", "") or "—", a.get("status", ""),
             proj_name.get(a.get("projectId", ""), "—") or "—"]
        if with_score:
            r.append(f"{float(a.get('score') or 0):g}")
        rows.append(r)

    total_score = sum(float(a.get("score") or 0) for a in sel)
    by_type: dict[str, int] = {}
    for a in sel:
        by_type[a.get("type", "其他")] = by_type.get(a.get("type", "其他"), 0) + 1

    if fmt_sel.startswith("CSV"):
        tail = [[], ["合计", f"{len(sel)} 项"] + [""] * (len(header) - 2)]
        if with_score:
            tail[1][-1] = f"{total_score:g}"
        out = _csv_file(f"科研成果清单-{year}-{today()}.csv", header, rows, tail)
        ext_note = "CSV（utf-8-sig，Excel 双击可直接打开）"
    elif fmt_sel.startswith("JSON"):
        payload = json.dumps({"year": year, "type": typ, "count": len(sel),
                              "total_score": total_score, "items": sel}, ensure_ascii=False, indent=2)
        out = _text_file(f"科研成果清单-{year}-{today()}.json", payload, "application/json")
        ext_note = "JSON（结构化，便于二次处理）"
    else:
        md = [f"# 科研成果清单（{year} / {typ}）", "",
              f"共 **{len(sel)}** 项" + (f"，业绩分合计 **{total_score:g}**" if with_score else ""), "",
              "| " + " | ".join(header) + " |",
              "| " + " | ".join(["---"] * len(header)) + " |"]
        md += ["| " + " | ".join(str(x).replace("|", "\\|") for x in r) + " |" for r in rows]
        out = _text_file(f"科研成果清单-{year}-{today()}.md", "\n".join(md) + "\n", "text/markdown")
        ext_note = "Markdown（可直接粘贴进报告）"

    lines = [f"导出范围：{year} / {typ}　　格式：{ext_note}", "",
             f"成果总数：{len(sel)} 项" + (f"　　业绩分合计：{total_score:g}" if with_score else ""),
             "", "按类型分布："]
    lines += [f"  {k:<10} {v:>3} 项  " + "●" * v
              for k, v in sorted(by_type.items(), key=lambda kv: -kv[1])]
    lines += ["", "清单预览（前 10 条）："]
    lines += [f"  {r[0]:>3}. {r[1][:40]:<40} {r[2]:<8} {r[7]} {r[8]}" for r in rows[:10]]
    if len(rows) > 10:
        lines.append(f"  … 其余 {len(rows) - 10} 条见导出文件")

    return ToolResult(
        summary=f"已导出 {len(sel)} 项成果（{year} / {typ}）为 {fmt_sel.split('（')[0]}。",
        metrics=[("成果项数", str(len(sel)), "项"), ("类型数", str(len(by_type)), "类"),
                 ("业绩分", f"{total_score:g}", "")],
        table=(header, rows),
        text="\n".join(lines),
        files=[out],
        log=f"导出科研成果 {len(sel)} 项（{year}/{typ}）",
    )


# =====================================================================
# 11. 课件 PPT 风格统一
# =====================================================================
PPT_PRESETS = {
    "薄荷绿学术（默认）": {"accent": "#189d5b", "text": "#1d2b24", "bg": "#ffffff",
                         "cn_font": "微软雅黑", "en_font": "Calibri", "size": 20},
    "海蓝学术": {"accent": "#0f6ea8", "text": "#1c2b3a", "bg": "#ffffff",
                "cn_font": "微软雅黑", "en_font": "Calibri", "size": 20},
    "青绿清新": {"accent": "#0d9488", "text": "#123b37", "bg": "#f6fbfa",
                "cn_font": "微软雅黑", "en_font": "Segoe UI", "size": 19},
}


def run_ppt_theme(ctx: ToolContext) -> ToolResult:
    """统一课件字体/配色：上传 .pptx 且装有 python-pptx 时实际改写，否则输出规范清单。"""
    preset = ctx.p("preset", "薄荷绿学术（默认）")
    conf = dict(PPT_PRESETS.get(preset, PPT_PRESETS["薄荷绿学术（默认）"]))
    if ctx.p("font", ""):
        conf["cn_font"] = str(ctx.p("font"))
    if ctx.pi("size", 0):
        conf["size"] = ctx.pi("size", 0)

    pptx_files = [f for f in ctx.files if str(f["name"]).lower().endswith(".pptx")]
    try:
        from pptx import Presentation  # type: ignore
        from pptx.util import Pt  # type: ignore
        has_pptx = True
    except ImportError:
        has_pptx = False

    fonts_seen: dict[str, int] = {}
    colors_seen: dict[str, int] = {}
    slides_total = 0
    for f in pptx_files:
        try:
            prs = Presentation(io.BytesIO(f["data"]))
        except Exception:
            continue
        slides_total += len(prs.slides)
        for sl in prs.slides:
            for shp in sl.shapes:
                if not getattr(shp, "has_text_frame", False) or not shp.text_frame:
                    continue
                for para in shp.text_frame.paragraphs:
                    for run in para.runs:
                        if run.font.name:
                            fonts_seen[run.font.name] = fonts_seen.get(run.font.name, 0) + 1
                        try:
                            if run.font.color and run.font.color.rgb:
                                c = f"#{run.font.color.rgb}"
                                colors_seen[c] = colors_seen.get(c, 0) + 1
                        except Exception:
                            pass

    out_files: list[OutFile] = []
    if pptx_files and has_pptx:
        for f in pptx_files:
            try:
                prs = Presentation(io.BytesIO(f["data"]))
            except Exception:
                continue
            for sl in prs.slides:
                for shp in sl.shapes:
                    if not getattr(shp, "has_text_frame", False) or not shp.text_frame:
                        continue
                    for para in shp.text_frame.paragraphs:
                        for run in para.runs:
                            has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in run.text)
                            run.font.name = conf["cn_font"] if has_cjk else conf["en_font"]
                            if run.font.size is None:
                                run.font.size = Pt(conf["size"])
            buf = io.BytesIO()
            prs.save(buf)
            stem = str(f["name"]).rsplit(".", 1)[0]
            out_files.append(OutFile(f"{stem}-统一样式.pptx", buf.getvalue(),
                                     "application/vnd.openxmlformats-officedocument.presentationml.presentation"))

    lines = [
        f"目标样式方案：{preset}",
        f"  中文字体：{conf['cn_font']}", f"  西文字体：{conf['en_font']}",
        f"  强调色　：{conf['accent']}", f"  正文色　：{conf['text']}",
        f"  背景色　：{conf['bg']}", f"  默认字号：{conf['size']} pt", "",
    ]
    if not pptx_files:
        lines.append("未上传 .pptx 文件，仅输出规范化方案与检查清单。")
    else:
        lines.append(f"解析 {len(pptx_files)} 个课件，共 {slides_total} 张幻灯片。")
        if fonts_seen:
            lines += ["", "现有字体分布（需统一）："]
            lines += [f"  {k:<24} {v:>5} 处" + ("" if k in (conf["cn_font"], conf["en_font"]) else "  ← 需替换")
                      for k, v in sorted(fonts_seen.items(), key=lambda kv: -kv[1])[:12]]
        if colors_seen:
            lines += ["", "现有字体颜色分布："]
            lines += [f"  {k:<12} {v:>5} 处" + ("" if k.lower() == conf["text"].lower() else "  ← 建议统一")
                      for k, v in sorted(colors_seen.items(), key=lambda kv: -kv[1])[:10]]
        lines += ["", "## 应用检查清单",
                  f"1. [ ] 标题页主标题 {conf['size'] + 10}pt 加粗，副标题 {conf['size'] - 2}pt",
                  f"2. [ ] 正文页标题 {conf['size'] + 4}pt，正文 {conf['size']}pt，行距 1.2~1.4",
                  f"3. [ ] 中文统一「{conf['cn_font']}」，西文统一「{conf['en_font']}」",
                  f"4. [ ] 强调色仅使用 {conf['accent']}", f"5. [ ] 正文色统一为 {conf['text']}",
                  f"6. [ ] 母版背景统一为 {conf['bg']}"]
        if out_files:
            lines += ["", f"已生成 {len(out_files)} 个统一样式后的课件可下载："]
            lines += [f"  · {f.name}" for f in out_files]
        elif not has_pptx:
            lines.append("  提示：服务端安装 python-pptx 后可自动批量改写（pip install python-pptx）。")

    spec_text = "\n".join(lines)
    return ToolResult(
        summary=(f"已按「{preset}」统一 {len(out_files)} 个课件。" if out_files else
                 f"已生成「{preset}」样式规范与检查清单"
                 + (f"，检测到 {len(fonts_seen)} 种不一致字体。" if fonts_seen else "。")),
        metrics=[("解析课件", str(len(pptx_files)), "个"), ("幻灯片", str(slides_total), "张"),
                 ("字体种类", str(len(fonts_seen)), "种"), ("已处理", str(len(out_files)), "个")],
        text=spec_text,
        files=[_text_file(f"课件样式规范-{today()}.md", spec_text + "\n", "text/markdown")] + out_files,
        log=f"课件样式统一：{preset}，解析 {len(pptx_files)} 个课件",
    )


# =====================================================================
# 12. 实验室设备借用登记
# =====================================================================
DEVICE_CONDITIONS = ["完好", "轻微磨损", "需维修", "待报废"]


def run_device_lend(ctx: ToolContext) -> ToolResult:
    """登记设备借出/归还/催还，跨次累计形成台账。"""
    action = ctx.p("action", "借出登记")
    device = ctx.p("device", "")
    if not device:
        return ToolResult(summary="请填写设备名称或编号。")
    person = ctx.p("person", "")
    if not person:
        return ToolResult(summary="请填写借用人。")

    borrow = parse_ymd(ctx.p("borrow_date")) or date.today()
    due, back = parse_ymd(ctx.p("due_date")), parse_ymd(ctx.p("back_date"))
    cond_out, cond_back = ctx.p("condition_out", "完好"), ctx.p("condition_back", "")
    purpose, contact = ctx.p("purpose", ""), ctx.p("contact", "")

    if action == "归还登记":
        back = back or date.today()
        overdue = (back - due).days if due and back > due else 0
        status = "已归还"
        note = f"借用 {(back - borrow).days} 天" + (f"，逾期 {overdue} 天" if overdue > 0 else "，按期归还")
        if cond_back and cond_back != cond_out:
            note += f"；归还状态 {cond_out} → {cond_back}"
    elif action == "超期催还":
        overdue = ctx.pi("overdue_days", 0)
        status = "催还中"
        note = f"已逾期 {overdue} 天，需联系 {person} 归还"
    else:
        overdue = (date.today() - due).days if due and date.today() > due else 0
        status = "借出中"
        note = f"应归还 {due.isoformat()}" if due else "未约定归还日期"

    lines = ["【实验室设备借用登记单】", "",
             f"设备名称：{device}",
             f"借 用 人：{person}" + (f"（联系方式：{contact}）" if contact else ""),
             f"登记类型：{action}", f"借出日期：{borrow.isoformat()}",
             f"预计归还：{due.isoformat() if due else '未约定'}"]
    if back and action == "归还登记":
        lines.append(f"实际归还：{back.isoformat()}")
    lines += [f"设备状态：{cond_out}" + (f" → {cond_back}" if cond_back and action == "归还登记" else ""),
              f"使用用途：{purpose or '（未说明）'}",
              f"当前状态：{status} —— {note}"]
    if overdue > 0 and action != "归还登记":
        lines += ["", f"⚠ 该设备已逾期 {overdue} 天，请及时催还并检查设备状态。"]

    # 台账（跨次累计，存于 tool_runs）
    records = [r for r in ctx.store.list("tool_runs") if r.get("tool") == "device_lend"]
    rows = [[(r.get("data") or {}).get(k, "") for k in
             ("device", "person", "borrow_date", "due_date")] +
            [(r.get("data") or {}).get("back_date") or "未归还"] +
            [(r.get("data") or {}).get(k, "") for k in ("status", "note")]
            for r in records]

    if action == "借出登记":
        ctx.store.add("tool_runs", {
            "tool": "device_lend", "title": f"借出 {device}", "memo": "", "created": today(),
            "data": {"device": device, "person": person, "borrow_date": borrow.isoformat(),
                     "due_date": due.isoformat() if due else "", "back_date": "", "status": status,
                     "note": note, "contact": contact, "condition_out": cond_out, "purpose": purpose},
        }, "r")
        rows.append([device, person, borrow.isoformat(), due.isoformat() if due else "",
                     "未归还", status, note])
    elif action == "归还登记":
        target = next((r for r in records
                       if (r.get("data") or {}).get("device") == device
                       and (r.get("data") or {}).get("person") == person
                       and not (r.get("data") or {}).get("back_date")), None)
        if target:
            merged = {**(target.get("data") or {}), "back_date": back.isoformat(),
                      "status": status, "note": note, "condition_back": cond_back}
            ctx.store.update("tool_runs", target["id"],
                             {"data": merged, "title": f"归还 {device}"})
            rows = [[r[0], r[1], r[2], r[3],
                     back.isoformat() if r[0] == device and r[1] == person and r[4] == "未归还" else r[4],
                     status if r[0] == device and r[1] == person and r[4] == "未归还" else r[5],
                     note if r[0] == device and r[1] == person and r[4] == "未归还" else r[6]]
                    for r in rows]
            lines.insert(2, "（已匹配并更新此前的借出记录）")

    active = sum(1 for r in rows if r[5] in ("借出中", "催还中"))
    return ToolResult(
        summary=action + f"完成：{device} → {person}"
                + (f"，应于 {due.isoformat()} 归还。" if due else "。"),
        metrics=[("操作", action, ""), ("设备", device[:12], ""), ("台账在借", str(active), "台")],
        table=(["设备名称", "借用人", "借出日期", "应归还", "实际归还", "状态", "备注"], rows),
        text="\n".join(lines),
        files=[_csv_file(f"设备借用台账-{today()}.csv",
                         ["设备名称", "借用人", "借出日期", "应归还", "实际归还", "状态", "备注"], rows)],
        log=f"{action}：{device} / {person}",
    )


# =====================================================================
# 注册表
# =====================================================================
TOOL_IMPLS = {
    "teaching_calendar": run_teaching_calendar,
    "grade_calc": run_grade_calc,
    "cite_convert": run_cite_convert,
    "budget_calc": run_budget_calc,
    "submission_track": run_submission_track,
    "student_board": run_student_board,
    "duty_log": run_duty_log,
    "meeting_note": run_meeting_note,
    "pdf_toolkit": run_pdf_toolkit,
    "achievement_export": run_achievement_export,
    "ppt_theme": run_ppt_theme,
    "device_lend": run_device_lend,
}

KEY_BY_URL = {
    "internal://teaching-calendar": "teaching_calendar",
    "internal://grade-calc": "grade_calc",
    "internal://cite-convert": "cite_convert",
    "internal://budget-calc": "budget_calc",
    "internal://submission-track": "submission_track",
    "internal://student-board": "student_board",
    "internal://duty-log": "duty_log",
    "internal://meeting-note": "meeting_note",
    "internal://pdf-toolkit": "pdf_toolkit",
    "internal://achievement-export": "achievement_export",
    "internal://ppt-theme": "ppt_theme",
    "internal://device-lend": "device_lend",
}


def run_tool(tool_key: str, ctx: ToolContext) -> ToolResult:
    """按工具 id 执行；异常兜底为失败结果，不影响其他接口。"""
    fn = TOOL_IMPLS.get(tool_key)
    if fn is None:
        return ToolResult(summary=f"未注册的工具：{tool_key}", ok=False)
    try:
        return fn(ctx)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(summary=f"执行出错：{type(exc).__name__}: {exc}", ok=False)
