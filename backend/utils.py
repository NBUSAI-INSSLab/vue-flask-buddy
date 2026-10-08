"""通用工具：日期处理、ID 生成、文件命名、CSV 构造。"""
from __future__ import annotations

import base64
import csv
import io
import itertools
import re
import secrets
import time
from datetime import date, datetime, timedelta

WEEKDAYS_CN = ["一", "二", "三", "四", "五", "六", "日"]

# 进程内 ID 自增序号（见 uid()）
_UID_SEQ = itertools.count(1)


# --------------------------------------------------------------------------- #
# 日期
# --------------------------------------------------------------------------- #
def today() -> str:
    return date.today().isoformat()


def fmt(d: date | datetime | None) -> str:
    if d is None:
        return ""
    if isinstance(d, datetime):
        d = d.date()
    return d.isoformat()


def parse_ymd(value) -> date | None:
    """宽松解析 yyyy-MM-dd（允许带时间后缀）。失败返回 None。"""
    if not value:
        return None
    text = str(value).strip()
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def day_offset(n: int) -> str:
    return fmt(date.today() + timedelta(days=n))


def add_days(d: date | datetime, n: int) -> date:
    if isinstance(d, datetime):
        d = d.date()
    return d + timedelta(days=n)


def days_until(date_str) -> int | None:
    d = parse_ymd(date_str)
    if not d:
        return None
    return (d - date.today()).days


def weekday_cn(d: date) -> str:
    return WEEKDAYS_CN[d.weekday()]


def cn_date(date_str) -> str:
    d = parse_ymd(date_str)
    if not d:
        return ""
    return f"{d.month}月{d.day}日 周{weekday_cn(d)}"


def cn_date_short(date_str) -> str:
    d = parse_ymd(date_str)
    if not d:
        return ""
    return f"{d.month}/{d.day}"


def due_text(date_str) -> str:
    n = days_until(date_str)
    if n is None:
        return "无截止日期"
    if n < 0:
        return f"已逾期 {abs(n)} 天"
    if n == 0:
        return "今天截止"
    if n == 1:
        return "明天截止"
    return f"剩 {n} 天"


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# --------------------------------------------------------------------------- #
# ID / 命名
# --------------------------------------------------------------------------- #
def uid(prefix: str = "id") -> str:
    """生成带前缀的短 ID：毫秒时间戳 + 进程内自增序号 + 随机后缀。

    时间戳只到毫秒，同一毫秒内连续生成大量 ID 时，仅靠 4 位十六进制
    随机后缀会撞上生日问题（实测连续 200 个约有 1/4 概率重复）。
    因此再叠加一个单调自增序号 —— 同进程内 (时间戳, 序号) 必然唯一，
    随机后缀只用于区分不同进程。
    """
    seq = next(_UID_SEQ)
    return f"{prefix}_{int(time.time() * 1000):x}{seq:08x}{secrets.token_hex(2)}"


def esc_xml(text) -> str:
    """转义 XML/SVG 文本节点里的特殊字符。"""
    return (str("" if text is None else text)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


def safe_name(text: str, limit: int = 48) -> str:
    """把任意文本清洗为安全的文件名。

    路径分隔符、通配符与空白折叠为 ``-``；连续点号折叠为单个点，
    并去掉首尾的点与连字符，因此结果中不可能出现 ``/``、``\\`` 或 ``..``
    （防路径穿越），同时保留扩展名分隔点。
    """
    cleaned = re.sub(r'[\\/:*?"<>|\s]+', "-", str(text or ""))
    cleaned = re.sub(r"\.{2,}", ".", cleaned).strip("-.")
    return cleaned[:limit] or "output"


# --------------------------------------------------------------------------- #
# 文件产物
# --------------------------------------------------------------------------- #
def to_base64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def csv_bytes(header: list, rows: list[list], extra_rows: list | None = None) -> bytes:
    """构造 CSV 字节串：带 UTF-8 BOM，Excel 双击不乱码；CRLF 换行。"""
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow([_cell(x) for x in header])
    for r in rows:
        writer.writerow([_cell(x) for x in r])
    for r in (extra_rows or []):
        writer.writerow([_cell(x) for x in r])
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def _cell(v) -> str:
    return "" if v is None else str(v)


def text_bytes(text: str) -> bytes:
    return str(text).encode("utf-8")


def barrier(value: float, total: float = 1.0, width: int = 40) -> str:
    """终端风格条形图，用于纯文本报告。"""
    if total <= 0:
        return ""
    n = max(0, min(width, round(value / total * width)))
    return "█" * n
