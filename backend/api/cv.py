"""个人简历接口（教师端，需登录）。

- 发布概况：固定链接令牌 + 公开开关 + 各区块条目数（简历页的「发布卡」）
- 头像：上传 / 读取 / 删除，落盘 ``data/avatars/<uid>/``
- 预览：返回聚合后的简历数据（教师自己看，与公开页同一份数据）

公开侧（免登录）在 ``api/public.py``：``/api/public/cv/<token>``。
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request, send_file

from .. import cv as cv_util
from ..store import open_store

bp = Blueprint("cv", __name__)


def _ok(data):
    return jsonify({"ok": True, "data": data})


def _err(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


def _profile_url(token: str) -> str:
    """简历的完整固定链接（便于「复制链接」直接发给别人）。"""
    return f"{request.host_url.rstrip('/')}/cv/{token}"


def _overview(store) -> dict:
    """发布概况：链接、开关、区块开关、各区块条目数。"""
    profile = store.get_profile()
    token = cv_util.ensure_token(store, profile)
    data = cv_util.build_cv(store)
    return {
        "token": token,
        "path": f"/cv/{token}",
        "url": _profile_url(token),
        "published": bool(profile.get("cvPublished", True)),
        "sections": data["sections"],
        "sectionLabels": cv_util.SECTION_LABELS,
        "avatar": cv_util.resolve_avatar(profile, "/api/cv"),
        "updatedAt": data["updatedAt"],
        "counts": {
            "educations": len(data["educations"]),
            "services": len(data["services"]),
            "projects": len(data["projects"]),
            "papers": len(data["papers"]),
            "patents": len(data["patents"]),
            "honors": len(data["honors"]),
            "students": len(data["students"]),
            "teachings": len(data["teachings"]),
            "directions": len(data["directions"]),
        },
        "stats": data["stats"],
        "name": data["name"],
    }


# --------------------------------------------------------------------------- #
# 概况与设置
# --------------------------------------------------------------------------- #
@bp.get("/cv")
def overview():
    return _ok(_overview(open_store()))


@bp.post("/cv/visibility")
def set_visibility():
    store = open_store()
    body = request.get_json(silent=True) or {}
    if "published" not in body:
        return _err("缺少 published 字段")
    store.set_profile({"cvPublished": bool(body.get("published"))})
    return _ok(_overview(store))


@bp.post("/cv/sections")
def set_sections():
    """区块开关：只接受已知区块，未提及的保持原值。"""
    store = open_store()
    body = request.get_json(silent=True) or {}
    patch = {k: bool(v) for k, v in body.items() if k in cv_util.DEFAULT_SECTIONS}
    if not patch:
        return _err("没有可识别的区块名")
    current = cv_util.sections_of(store.get_profile())
    current.update(patch)
    store.set_profile({"cvSections": current})
    return _ok(_overview(store))


@bp.post("/cv/token")
def rotate():
    """更换固定链接：旧链接立即失效。"""
    store = open_store()
    token = cv_util.rotate_token(store)
    return _ok({"token": token, "path": f"/cv/{token}", "url": _profile_url(token)})


# --------------------------------------------------------------------------- #
# 头像
# --------------------------------------------------------------------------- #
@bp.post("/cv/avatar")
def upload_avatar():
    fs = request.files.get("file") or request.files.get("avatar")
    if fs is None:
        return _err("没有收到文件")
    try:
        saved = cv_util.save_avatar(g.user_id, fs)
    except ValueError as e:
        return _err(str(e))
    store = open_store()
    store.set_profile({"avatar": saved["stored"]})
    profile = store.get_profile()
    return _ok({
        "avatar": cv_util.resolve_avatar(profile, "/api/cv"),
        "bytes": saved["bytes"],
        "ext": saved["ext"],
    })


@bp.delete("/cv/avatar")
def delete_avatar():
    store = open_store()
    store.set_profile({"avatar": ""})
    cv_util.drop_avatar(g.user_id)
    return _ok({"avatar": {"url": "", "external": False, "set": False}})


@bp.get("/cv/avatar")
def get_avatar():
    """教师端读取自己的头像（工作台内预览用）。"""
    profile = open_store().get_profile()
    path = cv_util.avatar_path(g.user_id, profile.get("avatar"))
    if path is None:
        return _err("尚未设置头像", 404)
    return send_file(path, max_age=60)


# --------------------------------------------------------------------------- #
# 预览
# --------------------------------------------------------------------------- #
@bp.get("/cv/preview")
def preview():
    """聚合后的简历数据（与公开页同源，教师端无需令牌即可预览）。"""
    store = open_store()
    profile = store.get_profile()
    data = cv_util.build_cv(store, g.user)
    data["avatar"] = cv_util.resolve_avatar(profile, "/api/cv")
    data["published"] = bool(profile.get("cvPublished", True))
    data["url"] = _profile_url(cv_util.ensure_token(store, profile))
    return _ok(data)
