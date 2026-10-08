"""课程开放与学生可见性。

设计要点
--------
1. **可见性内嵌于课程文档**：``published`` / ``openFrom`` / ``openUntil`` / ``shareToken``
   直接写在 ``courses`` 集合的文档上，不建中间表 —— 课程与学生页共用同一份数据。
2. **学生访问凭 ``shareToken``**：随机 16 位十六进制串，与课程 id 解耦，
   避免学生侧链接被枚举；令牌一旦生成不再变化（换链接会打断已发出去的通知）。
3. **时间窗口按「自然日」判定**：``openFrom`` 当天 00:00 起可见，
   ``openUntil`` 当天 23:59:59 止可见。二者均可留空，表示不设边界。
4. **资料文件落盘**：``data/course_files/<uid>/<cid>/<mid><ext>``，
   课程文档里只存相对路径与体积，避免把二进制塞进 SQLite。

不可见的四种状态（``visible=False``）::

    closed     教师手动关闭
    scheduled  尚未到 openFrom
    expired    已过 openUntil
"""
from __future__ import annotations

import re
import secrets
import shutil
from datetime import date, datetime
from pathlib import Path

from . import config
from .utils import safe_name

# 课程资料目录（与 uploads/ tmp/ 平级，长期保留，不参与定时清理）
COURSE_FILES_DIR = config.DATA_DIR / "course_files"

STATE_OPEN = "open"
STATE_CLOSED = "closed"
STATE_SCHEDULED = "scheduled"
STATE_EXPIRED = "expired"

STATE_LABEL = {
    STATE_OPEN: "已开放",
    STATE_CLOSED: "已关闭",
    STATE_SCHEDULED: "定时开放",
    STATE_EXPIRED: "已结束",
}

SHARE_TOKEN_RE = re.compile(r"^[0-9a-f]{16}$")
MATERIAL_ID_RE = re.compile(r"^[0-9a-zA-Z_-]{1,40}$")


# --------------------------------------------------------------------------- #
# 令牌与体积
# --------------------------------------------------------------------------- #
def new_share_token() -> str:
    return secrets.token_hex(8)


def human_size(num) -> str:
    """字节 → 便于阅读的字符串（教师手填的 '8.4 MB' 之类原样保留）。"""
    try:
        n = float(num)
    except (TypeError, ValueError):
        return ""
    if n < 0:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


# --------------------------------------------------------------------------- #
# 可见性
# --------------------------------------------------------------------------- #
def parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _as_day(value) -> date | None:
    """``now`` 参数既接受 datetime 也接受 date。"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def visibility(course: dict, now=None) -> dict:
    """判定课程对学生的可见性。

    返回 ``{visible, state, label, detail, openFrom, openUntil}``；
    ``detail`` 是给学生的提示文案（中文，可直接展示）。
    """
    today = _as_day(now) or date.today()
    frm = parse_date(course.get("openFrom"))
    until = parse_date(course.get("openUntil"))

    payload = {
        "visible": False,
        "state": STATE_CLOSED,
        "label": STATE_LABEL[STATE_CLOSED],
        "detail": "本课程暂未开放，请联系任课教师。",
        "openFrom": frm.isoformat() if frm else "",
        "openUntil": until.isoformat() if until else "",
    }

    if not course.get("published"):
        return payload

    if frm and today < frm:
        payload.update(
            state=STATE_SCHEDULED,
            label=STATE_LABEL[STATE_SCHEDULED],
            detail=f"本课程将于 {frm.isoformat()} 起开放，届时可查看教学大纲与下载课程资料。",
        )
        return payload

    if until and today > until:
        payload.update(
            state=STATE_EXPIRED,
            label=STATE_LABEL[STATE_EXPIRED],
            detail=f"本课程已于 {until.isoformat()} 结束开放，如有需要请联系任课教师。",
        )
        return payload

    payload.update(visible=True, state=STATE_OPEN, label=STATE_LABEL[STATE_OPEN], detail="")
    return payload


# --------------------------------------------------------------------------- #
# 字段回填
# --------------------------------------------------------------------------- #
def ensure_share_token(store, course: dict) -> str:
    """取课程访问令牌；缺失时生成并落库（幂等）。"""
    token = (course.get("shareToken") or "").strip()
    if SHARE_TOKEN_RE.match(token):
        return token
    while True:
        token = new_share_token()
        if not find_by_token(store, token):
            break
    store.update("courses", course["id"], {"shareToken": token})
    course["shareToken"] = token
    return token


def normalize(course: dict) -> dict:
    """补齐缺失字段（就地修改并返回 patch，空 patch 表示无需落库）。"""
    patch: dict = {}
    if "published" not in course:
        # 功能上线前的存量课程：教师并未主动关闭，视为已开放，保持原有可访问性
        patch["published"] = True
    if not course.get("shareToken"):
        patch["shareToken"] = new_share_token()

    materials = [m for m in (course.get("materials") or []) if isinstance(m, dict)]
    if not materials:
        # 早期种子数据把课程资料写在 ``resources`` 里（且 type 存的是文件格式），
        # 而前端详情页只读 ``materials`` —— 导致这些课程一直显示「暂无课程资料」。
        materials = [_from_resource(m) for m in (course.get("resources") or []) if isinstance(m, dict)]

    fixed = []
    changed = bool(materials) and not (course.get("materials") or [])
    for i, m in enumerate(materials):
        item = dict(m)
        if not MATERIAL_ID_RE.match(str(item.get("id") or "")):
            item["id"] = f"m{i + 1}{secrets.token_hex(3)}"
            changed = True
        fixed.append(item)
    if changed:
        patch["materials"] = fixed
    return patch


# 资料类型推断：种子数据的 ``resources`` 只给了文件格式，这里按文件名还原教学用途
_TYPE_HINTS = (
    ("大纲", "教学大纲"),
    ("实验", "实验"),
    ("讲义", "实验"),
    ("手册", "实验"),
    ("课件", "课件"),
    ("讲", "课件"),
    ("案例", "案例"),
    ("习题", "习题"),
    ("数据", "其他"),
    ("源码", "其他"),
)


def _from_resource(res: dict) -> dict:
    name = str(res.get("name") or "").strip()
    mtype = "课件"
    for kw, value in _TYPE_HINTS:
        if kw in name:
            mtype = value
            break
    return {
        "type": mtype,
        "name": name,
        "size": str(res.get("size") or ""),
        "date": str(res.get("date") or ""),
    }


def ensure_fields(store) -> int:
    """为某个租户库补齐课程开放相关字段，返回修复的课程数。"""
    fixed = 0
    for course in store.list("courses"):
        patch = normalize(course)
        if patch:
            store.update("courses", course["id"], patch)
            fixed += 1
    return fixed


def ensure_all(user_ids=None) -> int:
    """为全部教师租户库补齐字段（启动时调用）。"""
    from . import auth, db
    from .store import Store

    if user_ids is None:
        try:
            user_ids = [u["id"] for u in auth.list_teachers()]
        except Exception:  # noqa: BLE001 - 账号库尚未就绪时直接跳过
            return 0
    total = 0
    for uid in user_ids:
        if not config.tenant_db_path(uid).exists():
            continue
        try:
            total += ensure_fields(Store(db.connect_tenant(uid)))
        except Exception:  # noqa: BLE001
            continue
    return total


# --------------------------------------------------------------------------- #
# 学生侧查找
# --------------------------------------------------------------------------- #
def find_by_token(store, token: str) -> dict | None:
    """按访问令牌找课程；令牌非法直接返回 None（不做全表扫描）。"""
    if not SHARE_TOKEN_RE.match(str(token or "")):
        return None
    for course in store.list("courses"):
        if (course.get("shareToken") or "") == token:
            return course
    return None


def find_anywhere(token: str):
    """跨全部教师租户库按令牌查找，返回 ``(course, user)``。

    学生只拿到一个链接，必须自己找到「是哪位教师的哪门课」——
    逐个打开小库比对令牌即可，数据量下成本可忽略。
    """
    from . import auth, db
    from .store import Store

    if not SHARE_TOKEN_RE.match(str(token or "")):
        return None, None
    for user in auth.list_teachers():
        if not config.tenant_db_path(user["id"]).exists():
            continue
        try:
            store = Store(db.connect_tenant(user["id"]))
        except Exception:  # noqa: BLE001
            continue
        course = find_by_token(store, token)
        if course:
            return course, user
    return None, None


# --------------------------------------------------------------------------- #
# 资料文件
# --------------------------------------------------------------------------- #
def material_dir(user_id: str, course_id: str) -> Path:
    return COURSE_FILES_DIR / user_id / course_id


def material_path(user_id: str, course_id: str, material: dict) -> Path | None:
    """由课程文档里的 ``stored`` 还原磁盘路径。

    两道校验缺一不可：
    1. ``stored`` 必须以 ``<uid>/<cid>/`` 开头 —— 课程文档可被教师接口整体
       PATCH，若不校验归属，教师可把 ``stored`` 指向别的教师目录从而越权下载；
    2. 解析后的真实路径必须仍在 ``course_files`` 根目录内 —— 防 ``..`` 穿越。
    """
    rel = str(material.get("stored") or "").strip()
    if not rel:
        return None
    if not rel.startswith(f"{user_id}/{course_id}/"):
        return None
    root = COURSE_FILES_DIR.resolve()
    path = (root / rel).resolve()
    if root not in path.parents or not path.is_file():
        return None
    return path


def build_stored(user_id: str, course_id: str, material_id: str, filename: str) -> str:
    """生成相对存储路径 ``<uid>/<cid>/<mid><ext>``。"""
    ext = ""
    idx = str(filename).rfind(".")
    if idx > 0:
        ext = str(filename)[idx:].lower()
        if len(ext) > 12 or not re.match(r"^\.[0-9a-zA-Z]+$", ext):
            ext = ""
    return f"{user_id}/{course_id}/{material_id}{ext}"


def save_upload(user_id: str, course_id: str, material_id: str, fs) -> dict:
    """保存一个上传文件，返回 ``{stored, filename, bytes, ext}``。"""
    original = (fs.filename or "file").strip() or "file"
    stored = build_stored(user_id, course_id, material_id, original)
    target = COURSE_FILES_DIR / stored
    target.parent.mkdir(parents=True, exist_ok=True)
    fs.save(target)
    size = target.stat().st_size
    return {
        "stored": stored,
        "filename": safe_name(original.rsplit(".", 1)[0], 60) + Path(original).suffix.lower(),
        "original": original,
        "bytes": size,
        "size": human_size(size),
    }


def drop_file(user_id: str, course_id: str, material: dict) -> bool:
    """删除资料对应的磁盘文件（不存在也算成功）。"""
    path = material_path(user_id, course_id, material)
    if path is None:
        return False
    try:
        path.unlink()
        return True
    except OSError:
        return False


def purge_course_files(user_id: str, course_id: str) -> None:
    """删除课程时清理其资料目录。"""
    folder = material_dir(user_id, course_id).resolve()
    root = COURSE_FILES_DIR.resolve()
    if root not in folder.parents and folder != root:
        return
    shutil.rmtree(folder, ignore_errors=True)


# --------------------------------------------------------------------------- #
# 学生可见的数据
# --------------------------------------------------------------------------- #
def public_material(m: dict) -> dict:
    """学生侧资料条目：只暴露可下载的文件。"""
    return {
        "id": m.get("id", ""),
        "type": m.get("type") or "资料",
        "name": m.get("name") or "未命名文件",
        "size": m.get("size") or "",
        "date": m.get("date") or "",
        "bytes": int(m.get("bytes") or 0),
    }


def public_payload(course: dict, teacher: dict, vis: dict) -> dict:
    """学生可见的课程数据（剥离教师私有字段）。"""
    materials = [public_material(m) for m in (course.get("materials") or [])
                 if isinstance(m, dict) and m.get("stored")]
    return {
        "name": course.get("name") or "",
        "code": course.get("code") or "",
        "semester": course.get("semester") or "",
        "color": course.get("color") or "linear-gradient(135deg,#0c6b3d,#189d5b)",
        "intro": course.get("intro") or "",
        "credits": course.get("credits", 0),
        "hours": course.get("hours", 0),
        "syllabus": [
            {
                "chapter": s.get("chapter") or "",
                "hours": s.get("hours") or "",
                "type": s.get("type") or "",
                "point": s.get("point") or "",
            }
            for s in (course.get("syllabus") or []) if isinstance(s, dict)
        ],
        "materials": materials,
        "materialCount": len(materials),
        "teacher": {
            "name": (teacher or {}).get("name") or "",
            "title": (teacher or {}).get("title") or "",
            "dept": (teacher or {}).get("dept") or "",
            "email": (teacher or {}).get("email") or "",
            "office": (teacher or {}).get("office") or "",
        },
        "visibility": vis,
    }
