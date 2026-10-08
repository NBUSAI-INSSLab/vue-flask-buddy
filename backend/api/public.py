"""学生侧公开接口（**免登录**）。

学生只拿到一个课程链接 ``/c/<token>``，页面据此拉取本蓝图的接口。
可见性由 ``backend/courses.visibility`` 统一判定：未开放时返回 403 +
可直接展示的提示文案，正文数据（大纲、资料）一律不下发。

安全边界：
- 令牌非法 → 404（不区分「不存在」与「格式错误」，避免探测）
- 未开放 → 403，且只返回课程名与课程代码（够学生确认没走错门），
  不下发简介、大纲、资料
- 资料下载二次校验可见性，避免「关课前拿到直链」绕过
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file

from .. import courses as courses_util

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
