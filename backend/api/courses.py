"""课程开放与资料管理接口（教师端，需登录）。

- 开放设置：``published`` 开关 + ``openFrom`` / ``openUntil`` 时间窗口
- 学生链接：课程 ``shareToken`` 驱动的 ``/c/<token>`` 公开页
- 资料文件：上传 / 下载 / 删除，磁盘落于 ``data/course_files/<uid>/<cid>/``
- 教学日历与联系方式：``calendar`` / ``assistants`` / ``qqGroup`` / 群二维码上传
"""
from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, g, jsonify, request, send_file

from .. import courses as courses_util
from ..store import open_store
from ..utils import uid

bp = Blueprint("courses", __name__)

MAX_FILES_PER_UPLOAD = 10
MATERIAL_TYPES = ("教学大纲", "课件", "案例", "实验", "习题", "参考书", "其他")


def _ok(data):
    return jsonify({"ok": True, "data": data})


def _err(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


def _course_or_404(store, course_id: str):
    course = store.get("courses", course_id)
    if course is None:
        return None, _err("课程不存在或已删除", 404)
    return course, None


def _share_payload(store, course: dict) -> dict:
    """课程分享概况：令牌 + 可见性 + 可下载资料数。"""
    token = courses_util.ensure_share_token(store, course)
    vis = courses_util.visibility(course)
    materials = [m for m in (course.get("materials") or []) if isinstance(m, dict)]
    return {
        "course": course,
        "token": token,
        "path": f"/c/{token}",
        "visibility": vis,
        "published": bool(course.get("published")),
        "openFrom": course.get("openFrom") or "",
        "openUntil": course.get("openUntil") or "",
        "materialCount": len(materials),
        "fileCount": len([m for m in materials if m.get("stored")]),
    }


# --------------------------------------------------------------------------- #
# 开放设置
# --------------------------------------------------------------------------- #
@bp.get("/courses/<course_id>/share")
def share(course_id: str):
    store = open_store()
    course, err = _course_or_404(store, course_id)
    if err:
        return err
    return _ok(_share_payload(store, course))


@bp.post("/courses/<course_id>/visibility")
def set_visibility(course_id: str):
    store = open_store()
    course, err = _course_or_404(store, course_id)
    if err:
        return err

    body = request.get_json(silent=True) or {}
    patch: dict = {}

    if "published" in body:
        patch["published"] = bool(body.get("published"))

    for key in ("openFrom", "openUntil"):
        if key not in body:
            continue
        raw = str(body.get(key) or "").strip()
        if not raw:
            patch[key] = ""
            continue
        parsed = courses_util.parse_date(raw)
        if parsed is None:
            return _err(f"{key} 日期格式应为 YYYY-MM-DD")
        patch[key] = parsed.isoformat()

    frm = patch.get("openFrom", course.get("openFrom") or "")
    until = patch.get("openUntil", course.get("openUntil") or "")
    if frm and until and frm > until:
        return _err("开放起始日期不能晚于结束日期")

    if patch:
        course = store.update("courses", course_id, patch) or course
    return _ok(_share_payload(store, course))


# --------------------------------------------------------------------------- #
# 课程资料
# --------------------------------------------------------------------------- #
@bp.post("/courses/<course_id>/materials")
def upload_materials(course_id: str):
    store = open_store()
    course, err = _course_or_404(store, course_id)
    if err:
        return err

    incoming = request.files.getlist("files")
    if not incoming:
        return _err("没有收到文件")
    if len(incoming) > MAX_FILES_PER_UPLOAD:
        return _err(f"单次最多上传 {MAX_FILES_PER_UPLOAD} 个文件")

    mtype = (request.form.get("type") or "").strip() or "课件"
    if mtype not in MATERIAL_TYPES:
        mtype = "其他"
    mdate = (request.form.get("date") or "").strip()
    if mdate and courses_util.parse_date(mdate) is None:  # noqa: SLF001
        return _err("日期格式应为 YYYY-MM-DD")

    user_id = g.user_id
    materials = [m for m in (course.get("materials") or []) if isinstance(m, dict)]
    added = []
    for fs in incoming:
        if not (fs.filename or "").strip():
            continue
        mid = uid("m")
        saved = courses_util.save_upload(user_id, course_id, mid, fs)
        item = {
            "id": mid,
            "type": mtype,
            "name": saved["original"],
            "size": saved["size"],
            "date": mdate or date.today().isoformat(),
            "bytes": saved["bytes"],
            "stored": saved["stored"],
            "uploadedAt": datetime.now().isoformat(timespec="seconds"),
            "uploadedBy": g.user.get("name") or "",
        }
        materials.append(item)
        added.append(item)

    if not added:
        return _err("没有收到有效文件")

    updated = store.update("courses", course_id, {"materials": materials}) or course
    return _ok({"added": len(added), "materials": updated.get("materials") or []})


@bp.get("/courses/<course_id>/materials/<material_id>/download")
def download_material(course_id: str, material_id: str):
    store = open_store()
    course, err = _course_or_404(store, course_id)
    if err:
        return err
    material = next(
        (m for m in (course.get("materials") or [])
         if isinstance(m, dict) and m.get("id") == material_id),
        None,
    )
    if material is None:
        return _err("资料不存在", 404)
    path = courses_util.material_path(g.user_id, course_id, material)
    if path is None:
        return _err("该资料尚未上传文件", 404)
    return send_file(path, as_attachment=True, download_name=_download_name(material, path))


@bp.delete("/courses/<course_id>/materials/<material_id>")
def delete_material(course_id: str, material_id: str):
    store = open_store()
    course, err = _course_or_404(store, course_id)
    if err:
        return err
    materials = [m for m in (course.get("materials") or []) if isinstance(m, dict)]
    target = next((m for m in materials if m.get("id") == material_id), None)
    if target is None:
        return _err("资料不存在", 404)

    courses_util.drop_file(g.user_id, course_id, target)
    left = [m for m in materials if m.get("id") != material_id]
    updated = store.update("courses", course_id, {"materials": left}) or course
    return _ok({"materials": updated.get("materials") or []})


def _download_name(material: dict, path) -> str:
    """以资料原始文件名为准，缺失时回落到磁盘文件名。"""
    name = (material.get("name") or "").strip() or path.name
    return name.replace("/", "_").replace("\\", "_")


# --------------------------------------------------------------------------- #
# 教学日历与联系方式
# --------------------------------------------------------------------------- #
def _contact_payload(course: dict) -> dict:
    """课程联系方式概况：QQ 群、二维码、教学日历与助教名单。"""
    calendar = courses_util.clean_calendar(course.get("calendar"))
    return {
        "courseId": course.get("id") or "",
        "qqGroup": str(course.get("qqGroup") or ""),
        "hasQr": courses_util.has_qr(course),
        "qrUrl": f"/api/courses/{course.get('id')}/qr",
        "assistants": courses_util.clean_assistants(course.get("assistants")),
        "calendar": calendar,
        "calendarHours": sum(
            int(float(r["hours"] or 0)) if str(r.get("hours") or "").replace(".", "", 1).isdigit() else 0
            for r in calendar
        ),
    }


@bp.get("/courses/<course_id>/contact")
def get_contact(course_id: str):
    store = open_store()
    course, err = _course_or_404(store, course_id)
    if err:
        return err
    return _ok(_contact_payload(course))


@bp.post("/courses/<course_id>/contact")
def set_contact(course_id: str):
    """保存 QQ 群号、助教名单与教学日历；内容在服务端清洗，公开页所见即所存。"""
    store = open_store()
    course, err = _course_or_404(store, course_id)
    if err:
        return err

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _err("请求体必须是 JSON 对象")
    patch = courses_util.sanitize_contact(body)
    if not patch:
        return _err("没有需要保存的内容")

    updated = store.update("courses", course_id, patch) or course
    return _ok(_contact_payload(updated))


@bp.get("/courses/<course_id>/qr")
def qr_image(course_id: str):
    """教师端读取群二维码（同源携带会话，客户端可用时间戳防缓存）。"""
    store = open_store()
    course, err = _course_or_404(store, course_id)
    if err:
        return err
    path = courses_util.qr_path(g.user_id, course_id, course)
    if path is None:
        return _err("尚未上传群二维码", 404)
    return send_file(path, max_age=0)


@bp.post("/courses/<course_id>/qr")
def upload_qr(course_id: str):
    """上传 / 更换群二维码（按内容嗅探类型，不信任客户端扩展名）。"""
    store = open_store()
    course, err = _course_or_404(store, course_id)
    if err:
        return err

    fs = request.files.get("file")
    if fs is None or not (fs.filename or "").strip():
        return _err("没有收到文件")
    try:
        saved = courses_util.save_qr(g.user_id, course_id, fs)
    except ValueError as e:
        return _err(str(e))

    updated = store.update("courses", course_id, {"qqQr": saved["qqQr"]}) or course
    return _ok(_contact_payload(updated))


@bp.delete("/courses/<course_id>/qr")
def remove_qr(course_id: str):
    """移除群二维码：磁盘文件与文档字段同步清理。"""
    store = open_store()
    course, err = _course_or_404(store, course_id)
    if err:
        return err
    courses_util.drop_qr(g.user_id, course_id, course)
    updated = store.update("courses", course_id, {"qqQr": ""}) or course
    return _ok(_contact_payload(updated))
