"""常用网站图标接口（教师端，需登录）。

- ``GET /api/links/favicon?url=&name=&t=``  站点图标（抓不到时给首字母头像，永不 404）
- ``GET /api/links/meta?url=``              站点标题与主机名，供「添加网站」自动填充

网站清单本身走通用集合接口 ``/api/collections/links``，无需专门路由。
"""
from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from .. import links as links_util

bp = Blueprint("links", __name__)

# 图标内容变化不频繁，允许浏览器缓存一天；带 t 参数时视为强制刷新
CACHE_SECONDS = 24 * 3600


def _ok(data):
    return jsonify({"ok": True, "data": data})


def _err(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


@bp.get("/links/favicon")
def favicon():
    url = request.args.get("url", "")
    name = (request.args.get("name") or "").strip()[:24]
    force = bool(request.args.get("t") or request.args.get("refresh"))
    data, mime = links_util.get_icon(url, name=name, force=force)
    resp = Response(data, mimetype=mime)
    # 头像兜底（svg）不留缓存，好让下次能重试；真实站点图标缓存一天
    if mime == "image/svg+xml":
        resp.headers["Cache-Control"] = "no-store"
    else:
        resp.headers["Cache-Control"] = f"private, max-age={CACHE_SECONDS}"
    resp.headers["X-Favicon-Source"] = "fallback" if mime == "image/svg+xml" else "site"
    return resp


@bp.get("/links/meta")
def meta():
    """尽力而为地读取站点信息：打不开也返回 200，交给前端提示并让教师手填。"""
    info = links_util.inspect_site(request.args.get("url", ""))
    if not info.get("ok") and not info.get("host"):
        return _err(info.get("error") or "请输入合法的网址")
    return _ok(info)
