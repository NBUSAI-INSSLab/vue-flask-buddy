"""个人简历：固定链接、头像落盘与简历数据聚合。

设计要点
--------
1. **固定链接**：令牌写在 ``profile.cvToken``（16 位十六进制），与教师账号 id
   解耦，生成后**不再变化** —— 简历链接一旦发给别人就不会失效；只有教师主动
   「更换链接」才会重新生成。访问路径 ``/cv/<token>``。
2. **数据全部来自工作台自身**：简历页不存副本，每次访问都由 ``build_cv()``
   现场聚合。教师改了项目 / 论文 / 学生 / 教学，简历页刷新即变，不存在
   「同步」这一步。
3. **公开边界**：``build_cv()`` 只输出白名单字段。学生联系方式、成果审核状态
   与业绩分、成果的内部备注、日程待办、工具与常用网站一律不出库；教师个人
   电话 / 地址属简历本身要展示的内容，由教师自行决定是否填写。
4. **头像落盘**：``data/avatars/<uid>/<file>``，读取时双重校验「路径必须属于
   该教师」且「解析后仍在头像根目录内」，防越权读取与 ``..`` 穿越。

简历区块开关（``profile.cvSections``）让教师可以按需隐藏某些区块，
例如尚未整理好的「社会服务」。缺失的键按默认值（显示）补齐。
"""
from __future__ import annotations

import re
import secrets
import shutil
from datetime import datetime
from pathlib import Path

from . import config

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
AVATAR_DIR = config.DATA_DIR / "avatars"

CV_TOKEN_RE = re.compile(r"^[0-9a-f]{16}$")
# 头像允许的落盘格式（按内容嗅探结果判断，不信任客户端扩展名）
AVATAR_EXTS = ("png", "jpg", "gif", "webp", "bmp")
AVATAR_MIME = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp",
}
MAX_AVATAR_BYTES = 4 * 1024 * 1024  # 4 MB

# 存量租户库的一次性补种标记（与 links 同款做法，避免教师清空后被种子复活）
SEED_FLAG = "seeded:cv"

# 成果类型 → 简历区块
PAPER_TYPES = ("期刊论文", "会议论文")
PATENT_TYPES = ("发明专利", "软件著作权", "实用新型")
# 「科技奖励」计入荣誉；「技术报告」属于本人产出，一并归入该区块。
# 「学位论文」不计入 —— 种子里的学位论文是学生的成果（教师为指导教师），
# 它已经通过「学生指导」区块的论文题目体现，列进本人荣誉会失真。
HONOR_TYPES = ("科技奖励", "技术报告")

# 简历区块开关的默认值（False 表示该区块不展示）
DEFAULT_SECTIONS = {
    "stats": True,       # 顶部数字条
    "bio": True,         # 个人简介
    "directions": True,  # 研究方向
    "educations": True,  # 教育经历
    "projects": True,    # 项目经历
    "papers": True,      # 论文发表
    "patents": True,     # 专利软著
    "services": True,    # 社会服务
    "students": True,    # 学生指导
    "teachings": True,   # 教学经历
    "honors": True,      # 荣誉奖励
}

SECTION_LABELS = {
    "stats": "数据概览", "bio": "个人简介", "directions": "研究方向",
    "educations": "教育经历", "projects": "项目经历", "papers": "论文发表",
    "patents": "专利软著", "services": "社会服务", "students": "学生指导",
    "teachings": "教学经历", "honors": "荣誉与奖励",
}

# 公开页展示的个人信息字段白名单
PROFILE_FIELDS = (
    "name", "ename", "title", "dept", "email", "phone", "office", "address",
    "homepage", "orcid", "scholar", "bio", "tagline",
)

# 简历专属的展示字段：存量 profile 里没有这些键，首次补种时按出厂设计补齐。
# 只补「键不存在」的 —— 教师主动清空（键在、值为空）的内容不会被复活。
PROFILE_DISPLAY_FIELDS = (
    "ename", "tagline", "bio", "phone", "homepage", "orcid", "scholar",
    "address", "directions", "avatar",
)


# --------------------------------------------------------------------------- #
# 令牌
# --------------------------------------------------------------------------- #
def new_token() -> str:
    return secrets.token_hex(8)


def ensure_token(store, profile: dict | None = None) -> str:
    """取简历固定链接令牌；缺失时生成并落库（幂等）。"""
    profile = profile if profile is not None else store.get_profile()
    token = str(profile.get("cvToken") or "").strip()
    if CV_TOKEN_RE.match(token):
        return token
    token = new_token()
    store.set_profile({"cvToken": token})
    profile["cvToken"] = token
    return token


def rotate_token(store) -> str:
    """更换链接（旧链接立即失效，用于误发或需要收紧范围的场景）。"""
    token = new_token()
    store.set_profile({"cvToken": token})
    return token


def find_anywhere(token: str):
    """跨全部教师租户库按令牌查找，返回 ``(profile, user)``。

    简历链接里没有教师 id，访问时必须自己找到「这是谁的简历」——
    逐个打开小库比对令牌即可，数据量下成本可忽略。
    """
    from . import auth, db
    from .store import Store

    if not CV_TOKEN_RE.match(str(token or "")):
        return None, None
    for user in auth.list_teachers():
        if not config.tenant_db_path(user["id"]).exists():
            continue
        try:
            store = Store(db.connect_tenant(user["id"]))
        except Exception:  # noqa: BLE001
            continue
        profile = store.get_profile()
        if (profile.get("cvToken") or "") == token:
            return profile, user
    return None, None


def sections_of(profile: dict) -> dict:
    """合并区块开关：未知键丢弃，缺失键取默认值。"""
    raw = profile.get("cvSections")
    out = dict(DEFAULT_SECTIONS)
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k in DEFAULT_SECTIONS:
                out[k] = bool(v)
    return out


# --------------------------------------------------------------------------- #
# 字段补齐 / 存量补种
# --------------------------------------------------------------------------- #
def _seed_lists_for(user: dict | None) -> dict:
    """取该教师「出厂设计」的简历数据（仅用于存量库一次性补种）。"""
    if not user:
        return {}
    from . import seed_teachers

    tpl = seed_teachers.TEACHER_BY_ID.get(user.get("id"))
    if not tpl:
        return {}
    try:
        data = seed_teachers.initial_data(tpl)
    except Exception:  # noqa: BLE001
        return {}
    return {
        "profile": dict(data.get("profile") or {}),
        "educations": [dict(x) for x in (data.get("educations") or [])],
        "services": [dict(x) for x in (data.get("services") or [])],
    }


def ensure_fields(store, user: dict | None = None) -> int:
    """补齐简历相关字段；返回修复条数（0 表示无需改动）。

    - ``cvToken`` 缺失 / 格式非法 → 生成
    - ``cvPublished`` 不是布尔 → 默认公开
    - ``cvSections`` 缺失或含未知键 → 归一
    - 首次为存量租户库补入简历展示字段（简介 / 研究方向 / 联系方式等）
      与教育经历、社会服务；``meta`` 标记位保证只补一次，
      且只补「键不存在」的内容，教师主动清空的数据不会被种子复活
    """
    fixed = 0
    profile = store.get_profile()
    patch: dict = {}

    token = str(profile.get("cvToken") or "").strip()
    if not CV_TOKEN_RE.match(token):
        patch["cvToken"] = new_token()
    if not isinstance(profile.get("cvPublished"), bool):
        patch["cvPublished"] = True
    if sections_of(profile) != profile.get("cvSections"):
        patch["cvSections"] = sections_of(profile)
    if patch:
        store.set_profile(patch)
        fixed += 1

    if _seed_flag(store):
        return fixed
    _set_seed_flag(store)

    lists = _seed_lists_for(user)
    seed_profile = lists.get("profile") or {}
    missing = {
        k: v for k, v in seed_profile.items()
        if k in PROFILE_DISPLAY_FIELDS and k not in profile
    }
    if missing:
        store.set_profile(missing)
        fixed += 1

    for coll in ("educations", "services"):
        items = lists.get(coll) or []
        if items and not store.list(coll):
            store._add_many_ordered(coll, items)  # noqa: SLF001 - 与 links 同一套批量写入
            fixed += 1
    return fixed


def _seed_flag(store) -> bool:
    row = store.conn.execute("SELECT value FROM meta WHERE key = ?", (SEED_FLAG,)).fetchone()
    return row is not None


def _set_seed_flag(store) -> None:
    store.conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (SEED_FLAG, "1")
    )
    store.conn.commit()


def ensure_all(user_ids=None) -> int:
    """为全部教师租户库补齐简历字段（启动时调用）。"""
    from . import auth, db
    from .store import Store

    if user_ids is None:
        try:
            user_ids = [u["id"] for u in auth.list_teachers()]
        except Exception:  # noqa: BLE001 - 账号库尚未就绪时直接跳过
            return 0
    teachers = {}
    try:
        teachers = {u["id"]: u for u in auth.list_teachers()}
    except Exception:  # noqa: BLE001
        pass

    total = 0
    for uid in user_ids:
        if not config.tenant_db_path(uid).exists():
            continue
        try:
            total += ensure_fields(Store(db.connect_tenant(uid)), teachers.get(uid))
        except Exception:  # noqa: BLE001
            continue
    return total


# --------------------------------------------------------------------------- #
# 头像
# --------------------------------------------------------------------------- #
def avatar_dir(user_id: str) -> Path:
    return AVATAR_DIR / user_id


def avatar_path(user_id: str, rel) -> Path | None:
    """把 ``profile.avatar`` 里的相对路径还原为磁盘路径。

    两道校验缺一不可：
    1. 相对路径必须以 ``<uid>/`` 开头 —— 个人信息可被 PUT /api/profile 整体
       覆盖，不校验归属就能把头像指向别人的文件；
    2. 解析后的真实路径必须仍在头像根目录内 —— 防 ``..`` 穿越。
    """
    rel = str(rel or "").strip()
    if not rel or rel.startswith("http://") or rel.startswith("https://"):
        return None
    if not rel.startswith(f"{user_id}/"):
        return None
    root = AVATAR_DIR.resolve()
    path = (root / rel).resolve()
    if root not in path.parents or not path.is_file():
        return None
    return path


def is_external(value) -> bool:
    return str(value or "").strip().lower().startswith(("http://", "https://"))


def save_avatar(user_id: str, fs) -> dict:
    """保存上传的头像，返回 ``{stored, ext, bytes}``。

    类型按文件内容嗅探（复用 links.sniff_ext），不信任客户端给的扩展名。
    """
    from .links import sniff_ext

    data = fs.read(MAX_AVATAR_BYTES + 1)
    if not data:
        raise ValueError("没有收到文件内容")
    if len(data) > MAX_AVATAR_BYTES:
        raise ValueError(f"头像不能超过 {MAX_AVATAR_BYTES // 1024 // 1024} MB")
    ext = sniff_ext(data)
    if ext is None:
        raise ValueError("不是可识别的图片格式")
    if ext not in AVATAR_EXTS:
        raise ValueError("头像仅支持 PNG / JPG / GIF / WebP / BMP 格式")

    folder = avatar_dir(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(6)}.{ext}"
    target = folder / name
    target.write_bytes(data)

    # 换新头像时清掉旧的，避免磁盘上堆积孤儿文件
    _prune_avatars(folder, keep=name)
    return {"stored": f"{user_id}/{name}", "ext": ext, "bytes": len(data)}


def _prune_avatars(folder: Path, keep: str) -> None:
    try:
        for p in folder.iterdir():
            if p.is_file() and p.name != keep:
                p.unlink(missing_ok=True)
    except OSError:
        pass


def drop_avatar(user_id: str) -> None:
    shutil.rmtree(avatar_dir(user_id), ignore_errors=True)


# --------------------------------------------------------------------------- #
# 排序辅助
# --------------------------------------------------------------------------- #
def _txt(v) -> str:
    return str(v or "")


def _sorted_educations(items: list[dict]) -> list[dict]:
    """教育经历：按毕业时间倒序（无毕业时间排最后）。"""
    return sorted(items, key=lambda e: (_txt(e.get("to")), _txt(e.get("from"))), reverse=True)


def _sorted_services(items: list[dict]) -> list[dict]:
    """社会服务：按起始时间倒序（在任的排最前）。"""
    return sorted(items, key=lambda s: (_txt(s.get("from")), _txt(s.get("org"))), reverse=True)


def _sorted_projects(items: list[dict]) -> list[dict]:
    """项目经历：在研优先，组内按开始时间倒序。"""
    live = [p for p in items if _txt(p.get("status")) != "已结题"]
    done = [p for p in items if _txt(p.get("status")) == "已结题"]
    key = lambda p: _txt(p.get("startDate"))  # noqa: E731
    return sorted(live, key=key, reverse=True) + sorted(done, key=key, reverse=True)


def _sorted_by_date(items: list[dict]) -> list[dict]:
    """成果：按日期倒序（无日期的排最后）。"""
    return sorted(items, key=lambda a: _txt(a.get("date")), reverse=True)


def _sorted_students(items: list[dict]) -> list[dict]:
    """学生指导：先按年级、再按阶段倒序。"""
    return sorted(items, key=lambda s: (_txt(s.get("grade")), _txt(s.get("name"))), reverse=True)


def _sorted_teachings(items: list[dict]) -> list[dict]:
    """教学经历：按开课学期倒序。"""
    return sorted(items, key=lambda t: _txt(t.get("semester")), reverse=True)


# --------------------------------------------------------------------------- #
# 白名单投影
# --------------------------------------------------------------------------- #
def _pick(src: dict, keys) -> dict:
    return {k: src.get(k) for k in keys if src.get(k) not in (None, "")}


def public_profile(profile: dict) -> dict:
    out = _pick(profile, PROFILE_FIELDS)
    dirs = profile.get("directions")
    out["directions"] = [str(x) for x in dirs if str(x).strip()] if isinstance(dirs, list) else []
    out["avatar"] = str(profile.get("avatar") or "")
    return out


def _proj_row(p: dict) -> dict:
    return _pick(p, ("id", "name", "code", "type", "role", "funding",
                     "startDate", "deadline", "status", "desc"))


def _ach_row(a: dict) -> dict:
    """成果条目：剔除业绩分、关联项目、内部备注与审核痕迹。"""
    return _pick(a, ("id", "title", "type", "level", "authors", "role",
                     "venue", "date", "status", "doi"))


def _student_row(s: dict) -> dict:
    """学生条目：只保留学术信息，学生的邮箱属于隐私，不下发。"""
    return _pick(s, ("id", "name", "degree", "grade", "direction",
                     "thesisTitle", "stage"))


def _teaching_row(t: dict) -> dict:
    return _pick(t, ("id", "name", "code", "semester", "type", "students", "hours", "stage"))


def _service_row(s: dict) -> dict:
    return _pick(s, ("id", "kind", "org", "role", "from", "to", "note"))


def _edu_row(e: dict) -> dict:
    return _pick(e, ("id", "from", "to", "school", "major", "degree", "supervisor", "note"))


# --------------------------------------------------------------------------- #
# 统计
# --------------------------------------------------------------------------- #
def _i(v, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _year(v) -> int:
    m = re.match(r"^(\d{4})", _txt(v))
    return int(m.group(1)) if m else 0


def build_stats(projects, papers, patents, honors, students, teachings, services) -> dict:
    levels: dict[str, int] = {}
    for a in papers:
        lv = _txt(a.get("level")) or "其他"
        levels[lv] = levels.get(lv, 0) + 1

    return {
        "projects": len(projects),
        "projectsLeading": sum(1 for p in projects if _txt(p.get("role")) == "主持"),
        "funding": round(sum(_funding(p.get("funding")) for p in projects), 1),
        "papers": len(papers),
        "paperLevels": levels,
        "patents": len(patents),
        "honors": len(honors),
        "services": len(services),
        "students": len(students),
        "studentsMaster": sum(1 for s in students if "硕" in _txt(s.get("degree"))),
        "studentsPhd": sum(1 for s in students if "博" in _txt(s.get("degree"))),
        "teachings": len(teachings),
        "hours": sum(_i(t.get("hours")) for t in teachings),
        "since": min([y for y in (_year(p.get("startDate")) for p in projects) if y] or [0]) or 0,
    }


def _funding(v) -> float:
    """经费：容错解析（'62'、'62.5'、'62万'、'—' 都能处理）。"""
    m = re.search(r"\d+(?:\.\d+)?", _txt(v))
    return float(m.group(0)) if m else 0.0


# --------------------------------------------------------------------------- #
# 聚合
# --------------------------------------------------------------------------- #
def build_cv(store, user: dict | None = None) -> dict:
    """把工作台数据聚合成一份简历。数据全部现场计算，不落库副本。"""
    profile = store.get_profile()
    achievements = store.list("achievements")
    papers = _sorted_by_date([a for a in achievements if _txt(a.get("type")) in PAPER_TYPES])
    patents = _sorted_by_date([a for a in achievements if _txt(a.get("type")) in PATENT_TYPES])
    honors = _sorted_by_date([a for a in achievements if _txt(a.get("type")) in HONOR_TYPES])

    projects = _sorted_projects(store.list("projects"))
    educations = _sorted_educations(store.list("educations"))
    services = _sorted_services(store.list("services"))
    students = _sorted_students(store.list("students"))
    teachings = _sorted_teachings(store.list("teachings"))

    stats = build_stats(projects, papers, patents, honors, students, teachings, services)

    # 研究方向：优先取教师手填的；没填则从项目类型 / 文献方向里归纳，保证不为空
    directions = public_profile(profile)["directions"]
    if not directions:
        seen: list[str] = []
        for src in ([_txt(l.get("direction")) for l in store.list("literature")]
                    + [_txt(p.get("type")) for p in projects]):
            for part in re.split(r"[/、,，;；]+", src):
                part = part.strip()
                if part and part not in seen and len(part) <= 12:
                    seen.append(part)
        directions = seen[:6]

    return {
        "name": _txt(profile.get("name")) or (user or {}).get("name", ""),
        "profile": public_profile(profile),
        "directions": directions,
        "educations": [_edu_row(e) for e in educations],
        "services": [_service_row(s) for s in services],
        "projects": [_proj_row(p) for p in projects],
        "papers": [_ach_row(a) for a in papers],
        "patents": [_ach_row(a) for a in patents],
        "honors": [_ach_row(a) for a in honors],
        "students": [_student_row(s) for s in students],
        "teachings": [_teaching_row(t) for t in teachings],
        "stats": stats,
        "sections": sections_of(profile),
        "updatedAt": _latest_change(store),
    }


def _latest_change(store) -> str:
    """最近一次数据变动时间（工作台所有文档的最大 updated_at）。"""
    try:
        row = store.conn.execute(
            "SELECT MAX(updated_at) AS t FROM documents"
        ).fetchone()
        return str(row["t"] or "") if row else ""
    except Exception:  # noqa: BLE001
        return ""


def resolve_avatar(profile: dict, base: str) -> dict:
    """把 ``profile.avatar`` 解析成前端可直接用的地址。

    返回 ``{url, external, set}``：外链原样返回；上传文件拼成公开/教师端接口；
    未设置时 ``set`` 为 False，页面回落为首字母头像。
    """
    raw = str(profile.get("avatar") or "").strip()
    if not raw:
        return {"url": "", "external": False, "set": False}
    if is_external(raw):
        return {"url": raw, "external": True, "set": True}
    return {"url": f"{base}/avatar?t={_avatar_stamp(raw)}", "external": False, "set": True}


def _avatar_stamp(rel: str) -> str:
    """头像版本号（用文件名当戳），换头像后浏览器立刻刷新缓存。"""
    return re.sub(r"[^0-9a-zA-Z]", "", Path(str(rel)).stem)[-12:] or "1"


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")
