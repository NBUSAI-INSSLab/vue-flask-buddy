"""学生侧与访客侧公开接口（**免登录**）。

学生只拿到一个课程链接 ``/c/<token>``，页面据此拉取本蓝图的接口。
可见性由 ``backend/courses.visibility`` 统一判定：未开放时返回 403 +
可直接展示的提示文案，正文数据（大纲、资料）一律不下发。

访客只拿到一个简历链接 ``/cv/<token>``，同理走 ``/api/public/cv/<token>``；
教师关闭公开开关后返回 403 且不下发任何简历数据。

安全边界：
- 令牌非法 → 404（不区分「不存在」与「格式错误」，避免探测）
- 未开放 → 403，且只返回课程名与课程代码（够学生确认没走错门），
  不下发简介、大纲、资料
- 资料下载二次校验可见性，避免「关课前拿到直链」绕过
- 简历只下发白名单字段；学生邮箱、成果审核状态、内部备注一律不出库
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file

from .. import courses as courses_util
from .. import cv as cv_util

bp = Blueprint("public", __name__)


def _err(message: str, code: int = 400, extra: dict | None = None):
    payload = {"ok": False, "error": message}
    if extra:
        payload.update(extra)
    return jsonify(payload), code


@bp.get("/public/courses/<token>")
def course_by_token(token: str):
    course, teacher = courses_util.find_anywhere(token)
    if course is None:
        return _err("课程链接无效或已失效", 404)

    vis = courses_util.visibility(course)
    if not vis["visible"]:
        return _err(vis["detail"], 403, extra={
            "visibility": vis,
            "course": {
                "name": course.get("name") or "",
                "code": course.get("code") or "",
                "color": course.get("color") or "",
                "teacherName": (teacher or {}).get("name") or "",
            },
        })

    payload = courses_util.public_payload(course, teacher or {}, vis)
    payload["token"] = token
    return jsonify({"ok": True, "data": payload})


@bp.get("/public/courses/<token>/materials/<material_id>/download")
def download(token: str, material_id: str):
    course, teacher = courses_util.find_anywhere(token)
    if course is None:
        return _err("课程链接无效或已失效", 404)

    vis = courses_util.visibility(course)
    if not vis["visible"]:
        return _err(vis["detail"], 403, extra={"visibility": vis})

    material = next(
        (m for m in (course.get("materials") or [])
         if isinstance(m, dict) and m.get("id") == material_id),
        None,
    )
    if material is None:
        return _err("资料不存在", 404)

    # 归属校验依赖课程所属教师 id：跨库查找时一并带出，避免越权读到他人文件
    path = courses_util.material_path((teacher or {}).get("id", ""), course["id"], material)
    if path is None:
        return _err("该资料暂不可下载", 404)

    name = (material.get("name") or path.name).replace("/", "_").replace("\\", "_")
    return send_file(path, as_attachment=True, download_name=name)


@bp.get("/public/courses/<token>/qr")
def course_qr(token: str):
    """课程群二维码：归属由令牌决定，未开放时同样不下发。"""
    course, _teacher = courses_util.find_anywhere(token)
    if course is None:
        return _err("课程链接无效或已失效", 404)
    vis = courses_util.visibility(course)
    if not vis["visible"]:
        return _err(vis["detail"], 403)

    path = courses_util.qr_path(((_teacher or {}).get("id")) or "", course["id"], course)
    if path is None:
        return _err("教师尚未上传群二维码", 404)
    return send_file(path, max_age=600)


# --------------------------------------------------------------------------- #
# 个人简历公开页
# --------------------------------------------------------------------------- #
def _cv_of(token: str):
    """按令牌定位简历；返回 ``(profile, user, store, err)``。"""
    from ..store import Store
    from .. import db

    profile, user = cv_util.find_anywhere(token)
    if profile is None:
        return None, None, None, _err("简历链接无效或已失效", 404)
    try:
        store = Store(db.connect_tenant(user["id"]))
    except Exception:  # noqa: BLE001
        return None, None, None, _err("简历暂时无法访问", 500)
    return profile, user, store, None


@bp.get("/public/cv/<token>")
def cv_by_token(token: str):
    profile, user, store, err = _cv_of(token)
    if err:
        return err

    if not profile.get("cvPublished", True):
        return _err("该简历暂未公开", 403, extra={"state": "private"})

    data = cv_util.build_cv(store, user)
    data["avatar"] = cv_util.resolve_avatar(profile, f"/api/public/cv/{token}")
    data["token"] = token
    return jsonify({"ok": True, "data": data})


@bp.get("/public/cv/<token>/avatar")
def cv_avatar(token: str):
    """简历头像。归属由令牌决定，不接受客户端传入的路径。"""
    profile, user, _store, err = _cv_of(token)
    if err:
        return err
    if not profile.get("cvPublished", True):
        return _err("该简历暂未公开", 403)

    path = cv_util.avatar_path(user["id"], profile.get("avatar"))
    if path is None:
        return _err("尚未设置头像", 404)
    return send_file(path, max_age=600)
