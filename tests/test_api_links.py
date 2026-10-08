"""常用网站与图标抓取 —— 接口 / 纯函数用例。

覆盖：URL 规范化与 SSRF 防护、图片类型嗅探、页面图标解析与排序、
两级缓存（命中 / 失败标记 / 强制刷新）、首字母头像兜底、站点信息接口，
以及网站清单走通用集合接口的增删改与全局搜索。
"""
from __future__ import annotations

import time
from urllib.parse import quote

import pytest

from backend import links as links_util

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
ICO = b"\x00\x00\x01\x00\x01\x00" + b"\x00" * 40
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"></svg>'

PAGE_HTML = """
<html><head>
  <title>中国知网 - 学术期刊全文数据库</title>
  <link rel="mask-icon" href="/mask.svg">
  <link rel="icon" href="/static/favicon-32.png" sizes="32x32">
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple.png">
</head><body>正文</body></html>
"""


@pytest.fixture()
def icons(app):
    """每个用例前后清空图标缓存与进程内备忘，保证互不影响。"""
    links_util.clear_cache()
    yield links_util
    links_util.clear_cache()


# --------------------------------------------------------------------------- #
# URL 规范化 / SSRF 防护
# --------------------------------------------------------------------------- #
def test_normalize_url_accepts_common_forms():
    assert links_util.normalize_url("arxiv.org") == "https://arxiv.org/"
    assert links_util.normalize_url("  https://www.cnki.net/kns/  ") == "https://www.cnki.net/kns/"
    assert links_util.normalize_url("//example.com/a") == "https://example.com/a"
    assert links_util.normalize_url("http://example.com:8080/x") == "http://example.com:8080/x"
    # 账号信息与 fragment 必须被丢弃（避免把凭据写进缓存键 / 链接）
    assert links_util.normalize_url("https://u:p@example.com/#top") == "https://example.com/"


def test_normalize_url_rejects_non_http_and_local():
    for bad in ("javascript:alert(1)", "file:///etc/passwd", "localhost", "http://127.0.0.1/x",
                "http://192.168.1.10/", "http://[::1]/", "", None, "https://", "https://a b.com"):
        assert links_util.normalize_url(bad) is None, bad


def test_target_allowed_blocks_private_ip_literals():
    assert links_util._target_allowed("http://10.0.0.5/") is False
    assert links_util._target_allowed("http://169.254.169.254/latest/meta-data") is False
    assert links_util._target_allowed("http://127.0.0.1:8080/") is False
    assert links_util._target_allowed("ftp://example.com/x") is False


def test_host_and_cache_key():
    assert links_util.display_host("https://www.cnki.net/kns/") == "cnki.net"
    # 同一站点的不同页面共用一份图标缓存
    a = links_util.cache_key(links_util.normalize_url("https://www.cnki.net/a"))
    b = links_util.cache_key(links_util.normalize_url("https://www.cnki.net/b"))
    assert a == b


# --------------------------------------------------------------------------- #
# 图片嗅探 / HTML 解析（纯函数）
# --------------------------------------------------------------------------- #
def test_sniff_ext_recognises_images_only():
    assert links_util.sniff_ext(PNG) == "png"
    assert links_util.sniff_ext(ICO) == "ico"
    assert links_util.sniff_ext(SVG) == "svg"
    assert links_util.sniff_ext(b'\xff\xd8\xff\xe0' + b"\x00" * 10) == "jpg"
    assert links_util.sniff_ext(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    # 站点的 404 / 登录页 HTML 不能被当成图标
    assert links_util.sniff_ext(b"<!DOCTYPE html><html>not found</html>") is None
    assert links_util.sniff_ext(b"") is None


def test_icon_candidates_prefers_larger_and_resolves_relative():
    cands = links_util.icon_candidates(PAGE_HTML, "https://www.cnki.net/index.html")
    assert cands[0] == "https://www.cnki.net/static/apple.png"      # apple-touch 优先
    assert "https://www.cnki.net/static/favicon-32.png" in cands
    assert cands[-1] == "https://www.cnki.net/mask.svg"             # 掩码图标最后
    assert all(c.startswith("https://") for c in cands)


def test_icon_candidates_supports_data_uri():
    html = '<link rel="icon" href="data:image/png;base64,iVBORw0KGgo=">'
    cands = links_util.icon_candidates(html, "https://example.com/")
    assert cands == ['data:image/png;base64,iVBORw0KGgo=']
    assert links_util._data_uri(cands[0])
    assert links_util._data_uri(cands[0])[1] == "png"


def test_page_title_strips_site_suffix():
    assert links_util.page_title("<title>中国知网 - 学术期刊全文数据库</title>") == "中国知网"
    assert links_util.page_title("<title>arXiv.org e-Print archive</title>") == "arXiv.org e-Print archive"
    assert links_util.page_title("<html>没有标题</html>") == ""


def test_avatar_is_deterministic_and_escaped():
    from backend.utils import esc_xml

    a = links_util._avatar("中国知网", "https://www.cnki.net/")
    b = links_util._avatar("中国知网", "https://www.cnki.net/")
    assert a == b and a.startswith(b"<svg") and "中".encode() in a
    # 名称里的特殊字符必须转义，不能破坏 SVG 结构
    assert esc_xml('<a & "b">') == "&lt;a &amp; &quot;b&quot;&gt;"
    # 无名称时退回主机首字母（大写）
    assert b">E<" in links_util._avatar("", "https://example.com/")
    # 名称里的非字母数字字符会被跳过
    assert b">X<" in links_util._avatar("  ★X 站", "https://example.com/")


# --------------------------------------------------------------------------- #
# 抓取与缓存
# --------------------------------------------------------------------------- #
def test_get_icon_uses_crawler_and_caches(icons, monkeypatch):
    calls = []

    def fake_crawl(url):
        calls.append(url)
        return PNG, "png"

    monkeypatch.setattr(links_util, "_crawl", fake_crawl)
    data, mime = links_util.get_icon("https://www.cnki.net", name="中国知网")
    assert (data, mime) == (PNG, "image/png")
    # 第二次应当命中缓存，不再打外网
    links_util._MEMO.clear()
    links_util.get_icon("https://www.cnki.net", name="中国知网")
    assert len(calls) == 1
    # 磁盘上确实落了一份缓存
    assert list(links_util.ICON_DIR.glob("*.png"))


def test_get_icon_falls_back_and_marks_miss(icons, monkeypatch):
    calls = []

    def fake_crawl(url):
        calls.append(url)
        return None

    monkeypatch.setattr(links_util, "_crawl", fake_crawl)
    data, mime = links_util.get_icon("https://www.example.com", name="示例")
    assert mime == "image/svg+xml" and data.startswith(b"<svg")
    # 失败后 6 小时内不再重试（否则每次开首页都要等一遍超时）
    links_util.get_icon("https://www.example.com", name="示例")
    assert len(calls) == 1
    assert list(links_util.ICON_DIR.glob("*.miss"))


def test_force_refresh_retries_after_miss(icons, monkeypatch):
    calls = []
    state = {"ok": False}

    def fake_crawl(url):
        calls.append(url)
        return (PNG, "png") if state["ok"] else None

    monkeypatch.setattr(links_util, "_crawl", fake_crawl)
    links_util.get_icon("https://www.example.com")
    assert len(calls) == 1
    state["ok"] = True
    data, mime = links_util.get_icon("https://www.example.com", force=True)
    assert mime == "image/png"
    assert len(calls) == 2
    assert not list(links_util.ICON_DIR.glob("*.miss"))   # 成功后清掉失败标记


def test_expired_cache_is_refetched(icons, monkeypatch):
    calls = []

    def fake_crawl(url):
        calls.append(url)
        return PNG, "png"

    monkeypatch.setattr(links_util, "_crawl", fake_crawl)
    links_util.get_icon("https://www.example.com")
    path = list(links_util.ICON_DIR.glob("*.png"))[0]
    old = time.time() - links_util.ICON_TTL - 10
    import os
    os.utime(path, (old, old))
    links_util._MEMO.clear()
    links_util.get_icon("https://www.example.com")
    assert len(calls) == 2


def test_crawl_reads_declared_icon_after_missing_default(icons, monkeypatch):
    """默认 /favicon.ico 不可用时，改用页面里声明的图标。"""
    requested = []

    def fake_get(url, limit, deadline):
        requested.append(url)
        if url.endswith("/favicon.ico"):
            raise OSError("404")
        if url.endswith("/index.html"):
            return PAGE_HTML.encode("utf-8"), "utf-8"
        return PNG, ""

    monkeypatch.setattr(links_util, "_http_get", fake_get)
    monkeypatch.setattr(links_util, "_target_allowed", lambda url: True)
    data, mime = links_util.get_icon("https://www.cnki.net/index.html")
    assert mime == "image/png"
    assert any(u.endswith("/static/apple.png") for u in requested)


def test_invalid_url_never_hits_network(icons, monkeypatch):
    def boom(*a, **k):  # pragma: no cover - 不应该被调用
        raise AssertionError("非法网址不应触发抓取")

    monkeypatch.setattr(links_util, "_crawl", boom)
    data, mime = links_util.get_icon("javascript:alert(1)", name="坏链接")
    assert mime == "image/svg+xml" and data.startswith(b"<svg")


def test_clear_cache_all_and_by_url(icons, monkeypatch):
    monkeypatch.setattr(links_util, "_crawl", lambda url: (PNG, "png"))
    links_util.get_icon("https://a.example.com")
    links_util.get_icon("https://b.example.com")
    assert links_util.clear_cache("https://a.example.com") == 1
    assert links_util.clear_cache() == 1
    assert links_util.clear_cache() == 0


# --------------------------------------------------------------------------- #
# HTTP 接口：图标
# --------------------------------------------------------------------------- #
def test_favicon_requires_login(anon_client):
    assert anon_client.get("/api/links/favicon?url=https://www.cnki.net").status_code == 401


def test_favicon_returns_site_icon(client, monkeypatch):
    monkeypatch.setattr(links_util, "_crawl", lambda url: (PNG, "png"))
    r = client.get("/api/links/favicon?url=https://www.cnki.net&name=中国知网")
    assert r.status_code == 200
    assert r.mimetype == "image/png"
    assert r.data == PNG
    assert r.headers["X-Favicon-Source"] == "site"
    assert "max-age" in r.headers["Cache-Control"]


def test_favicon_falls_back_without_404(client, monkeypatch):
    monkeypatch.setattr(links_util, "_crawl", lambda url: None)
    r = client.get("/api/links/favicon?url=https://www.example.com&name=示例")
    assert r.status_code == 200
    assert r.mimetype == "image/svg+xml"
    assert r.headers["X-Favicon-Source"] == "fallback"
    # 头像不留缓存，下次还能重试拿真实图标
    assert r.headers["Cache-Control"] == "no-store"


def test_crawl_refuses_private_hosts(icons, monkeypatch):
    """即便网址通过了规范化，_crawl 也不会对内网地址发起请求。"""
    def boom(*a, **k):  # pragma: no cover - 不应该被调用
        raise AssertionError("内网地址不应发起任何请求")

    monkeypatch.setattr(links_util, "_http_get", boom)
    monkeypatch.setattr(links_util, "_is_public_host", lambda host: False)
    assert links_util._crawl("http://internal.example.com/") is None
    assert links_util._load_image("http://10.1.2.3/a.png", time.time() + 5) is None


def test_favicon_rejects_private_host(client, monkeypatch):
    """内网地址不能借这个接口被当成探测跳板：直接给头像，不发请求。"""
    def boom(*a, **k):  # pragma: no cover
        raise AssertionError("内网地址不应触发抓取")

    monkeypatch.setattr(links_util, "_http_get", boom)
    for bad in ("http://192.168.0.1/", "http://localhost:5000/api/state",
                "http://127.0.0.1:5000/", "http://[::1]/"):
        r = client.get("/api/links/favicon?url=" + quote(bad, safe=""))
        assert r.status_code == 200 and r.headers["X-Favicon-Source"] == "fallback", bad


# --------------------------------------------------------------------------- #
# HTTP 接口：站点信息
# --------------------------------------------------------------------------- #
def test_meta_returns_title(client, monkeypatch):
    monkeypatch.setattr(links_util, "_http_get",
                        lambda url, limit, deadline: (PAGE_HTML.encode("utf-8"), "utf-8"))
    monkeypatch.setattr(links_util, "_target_allowed", lambda url: True)
    res = client.get("/api/links/meta?url=https://www.cnki.net/index.html").get_json()
    assert res["ok"] is True
    assert res["data"]["title"] == "中国知网"
    assert res["data"]["host"] == "cnki.net"
    assert res["data"]["icon"].startswith("/api/links/favicon?")


def test_meta_reports_unreachable_without_failing(client, monkeypatch):
    def boom(url, limit, deadline):
        raise OSError("connection refused")

    monkeypatch.setattr(links_util, "_http_get", boom)
    monkeypatch.setattr(links_util, "_target_allowed", lambda url: True)
    res = client.get("/api/links/meta?url=https://unreachable.example.com").get_json()
    assert res["ok"] is True                     # 打不开也算正常响应，前端提示手填
    assert res["data"]["ok"] is False
    assert res["data"]["host"] == "unreachable.example.com"
    assert res["data"]["error"]


def test_meta_rejects_garbage(client):
    r = client.get("/api/links/meta?url=not a url")
    assert r.status_code == 400
    assert "合法" in r.get_json()["error"]


# --------------------------------------------------------------------------- #
# 网站清单：种子与集合 CRUD
# --------------------------------------------------------------------------- #
def test_seed_links_present_and_ordered(client):
    rows = client.get("/api/collections/links").get_json()["data"]
    assert len(rows) == 12
    assert {r["group"] for r in rows} == {"学术资源", "教学平台", "科研工具", "公共服务"}
    assert all(r["url"].startswith("https://") for r in rows)
    sorts = [r["sort"] for r in rows]
    assert sorts == sorted(sorts)


def test_state_exposes_links(client):
    data = client.get("/api/state").get_json()["data"]
    assert len(data["links"]) == 12


def test_links_crud(client):
    created = client.post("/api/collections/links", json={
        "name": "课题组 GitLab", "url": "https://git.example.edu.cn",
        "group": "科研工具", "note": "内部代码托管", "sort": 99,
    }).get_json()["data"]
    assert created["id"]

    updated = client.patch("/api/collections/links/" + created["id"],
                           json={"name": "课题组 GitLab（新）"}).get_json()["data"]
    assert updated["name"] == "课题组 GitLab（新）"

    rows = client.get("/api/collections/links").get_json()["data"]
    assert any(r["id"] == created["id"] for r in rows)

    r = client.delete("/api/collections/links/" + created["id"])
    assert r.status_code == 200
    rows = client.get("/api/collections/links").get_json()["data"]
    assert not any(r["id"] == created["id"] for r in rows)


def test_links_are_searchable(client):
    hits = [h for h in client.get("/api/search?q=知网").get_json()["data"]
            if h["collection"] == "links"]
    assert hits and hits[0]["label"] == "常用网站" and hits[0]["page"] == "dashboard"


def test_bare_domain_still_resolves(icons, client, monkeypatch):
    """教师只填了裸域名时，图标接口仍能按 https 补全后抓取，而不是 500。"""
    monkeypatch.setattr(links_util, "_crawl", lambda url: (PNG, "png"))
    created = client.post("/api/collections/links",
                          json={"name": "arXiv", "url": "arxiv.org"}).get_json()["data"]
    r = client.get("/api/links/favicon?url=" + quote(created["url"], safe=""))
    assert r.status_code == 200 and r.mimetype == "image/png"
    assert r.headers["X-Favicon-Source"] == "site"
