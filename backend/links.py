"""常用网站图标（favicon）抓取与缓存。

设计要点
--------
1. **服务端抓取**：浏览器受同源策略限制无法读取别家站点的图标，因此由后端抓取、
   缓存后同源下发（``/api/links/favicon?url=…``），前端只需一个 ``<img>``。
2. **两级缓存**：``data/favicons/<key>.<ext>`` 存真实图标（30 天有效）；
   ``<key>.miss`` 记录抓取失败（6 小时内不重试），避免每次开首页都去外网超时。
3. **永不 404**：抓不到图标时返回现场生成的首字母 SVG 头像，
   这样 ``<img>`` 永远有内容、控制台不会出现资源加载失败。
4. **SSRF 防护**：仅允许 http/https，且主机必须解析到公网地址
   （拒绝环回 / 私网 / 链路本地 / 保留网段），避免被当成内网探测器。
5. **格式校验**：按magic bytes嗅探真实类型，只接受图片，
   防止把站点的 HTML 错误页当成图标缓存下来。
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

from . import config
from .utils import esc_xml

# 图标缓存目录（与 uploads/ tmp/ course_files/ 平级，长期保留）
ICON_DIR = config.DATA_DIR / "favicons"

ICON_TTL = 30 * 24 * 3600   # 真实图标缓存有效期：30 天
MISS_TTL = 6 * 3600         # 抓取失败后的重试间隔：6 小时
MAX_BYTES = 512 * 1024      # 单个图标最大体积
HTML_BYTES = 400 * 1024     # 抓取页面只读前 400 KB（<link rel=icon> 必在其中）
TIMEOUT = 3.0               # 单次请求超时
DEADLINE = 3.0              # 一次抓取的总时间上限
MAX_CONCURRENT = 6          # 同时抓取的站点数上限（浏览器同源并发也就 6 个）

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 FWB-Favicon/1.0")

MAX_URL_LEN = 500
# 允许的主机名：域名 / IPv4；其余（含 localhost、带下划线等）一律拒绝
HOST_RE = re.compile(r"^(?=.{1,253}$)([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")

# 首字母头像配色（与主题无关的固定色板，保证任何配色下都清晰）
AVATAR_COLORS = (
    ("#189d5b", "#0c6b3d"), ("#1f6feb", "#103a7d"), ("#7c5cf0", "#4c33b8"),
    ("#0d9488", "#0b6b63"), ("#ea6a12", "#b0450a"), ("#d4385b", "#96213c"),
    ("#4f6bed", "#333fa8"), ("#0f766e", "#0b4f4a"),
)

# magic bytes → (扩展名, MIME)
_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
    (b"GIF87a", "gif", "image/gif"),
    (b"GIF89a", "gif", "image/gif"),
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"\x00\x00\x01\x00", "ico", "image/x-icon"),
    (b"\x00\x00\x02\x00", "cur", "image/x-icon"),
    (b"BM", "bmp", "image/bmp"),
)

EXT_MIME = {
    "png": "image/png", "gif": "image/gif", "jpg": "image/jpeg",
    "ico": "image/x-icon", "cur": "image/x-icon", "bmp": "image/bmp",
    "webp": "image/webp", "svg": "image/svg+xml",
}

# 进程内备忘：避免同一 URL 反复读盘 / 重复进抓取逻辑
_MEMO: dict[str, tuple[bytes, str, float]] = {}
_MEMO_LOCK = threading.Lock()
_MEMO_TTL = 600.0
_MEMO_MAX = 256

# 正在抓取中的 key：后来者直接拿头像兜底，不阻塞、不重复打外网
_INFLIGHT: set[str] = set()

# 抓取并发闸门：首页一次会请求十几张图标，超出的请求先给头像，
# 避免把 WSGI 线程池占满而拖慢其他接口（这些请求 6 小时后再试）。
_GATE = threading.Semaphore(MAX_CONCURRENT)


# --------------------------------------------------------------------------- #
# URL 规范化与安全校验
# --------------------------------------------------------------------------- #
def normalize_url(raw) -> str | None:
    """把用户输入整理成可用的 http(s) 网址；不合法返回 None。

    接受 ``arxiv.org``、``https://arxiv.org/abs/1``、``//x.com`` 等写法。
    """
    text = str(raw or "").strip()
    if not text or len(text) > MAX_URL_LEN:
        return None
    if text.startswith("//"):
        text = "https:" + text
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        text = "https://" + text.lstrip("/")
    try:
        parts = urllib.parse.urlsplit(text)
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https"):
        return None
    host = (parts.hostname or "").strip().lower().rstrip(".")
    if not host:
        return None
    if not HOST_RE.match(host):  # 中文域名转 punycode 后再校验
        try:
            host = host.encode("idna").decode("ascii")
        except (UnicodeError, ValueError):
            return None
        if not HOST_RE.match(host):
            return None
    try:  # 保留显式端口（部分校内部署在非标端口上），丢弃账号信息与 fragment
        port = parts.port
    except ValueError:
        return None
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    path = parts.path or "/"  # 保留路径：有的站点图标只在子路径下有效
    return urllib.parse.urlunsplit((parts.scheme.lower(), netloc, path, parts.query, ""))


def origin_of(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def host_of(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def display_host(url: str) -> str:
    """去掉 www. 前缀的展示用主机名。"""
    host = host_of(url)
    return host[4:] if host.startswith("www.") else host


def _is_public_host(host: str) -> bool:
    """主机必须能解析到公网地址（任意一个解析结果落在内网就拒绝）。"""
    if not HOST_RE.match(host):
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    if not infos:
        return False
    for info in infos:
        addr = info[4][0].split("%")[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if not _ip_public(ip):
            return False
    return True


def _ip_public(ip) -> bool:
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        or ip.is_reserved or ip.is_unspecified
    )


def _target_allowed(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        return False
    host = (parts.hostname or "").lower()
    if not host:
        return False
    try:  # 直接写 IP 的情况：只允许公网 IP
        return _ip_public(ipaddress.ip_address(host))
    except ValueError:
        return _is_public_host(host)


# --------------------------------------------------------------------------- #
# 缓存键与文件
# --------------------------------------------------------------------------- #
def cache_key(url: str) -> str:
    """同一站点（scheme://host）共用一份图标缓存。"""
    seed = origin_of(url)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20]


def _cached_path(key: str) -> Path | None:
    for ext in EXT_MIME:
        path = ICON_DIR / f"{key}.{ext}"
        if path.is_file():
            return path
    return None


def _cache_fresh(path: Path, ttl: float) -> bool:
    try:
        return (time.time() - path.stat().st_mtime) < ttl
    except OSError:
        return False


def _miss_marker(key: str) -> Path:
    return ICON_DIR / f"{key}.miss"


def _mark_miss(key: str) -> None:
    try:
        ICON_DIR.mkdir(parents=True, exist_ok=True)
        _miss_marker(key).write_bytes(b"")
    except OSError:
        pass


def _store(key: str, data: bytes, ext: str) -> None:
    try:
        ICON_DIR.mkdir(parents=True, exist_ok=True)
        for old in ICON_DIR.glob(f"{key}.*"):
            if old.suffix.lstrip(".") != ext or old.name.endswith(".miss"):
                old.unlink(missing_ok=True)
        (ICON_DIR / f"{key}.{ext}").write_bytes(data)
        _miss_marker(key).unlink(missing_ok=True)
    except OSError:
        pass


def clear_cache(url: str | None = None) -> int:
    """清空（或按站点清除）图标缓存，返回删除的文件数。"""
    if not ICON_DIR.exists():
        return 0
    n = 0
    if url:
        norm = normalize_url(url)
        if not norm:
            return 0
        key = cache_key(norm)
        patterns = [f"{key}.*"]
    else:
        patterns = ["*"]
    for pattern in patterns:
        for path in ICON_DIR.glob(pattern):
            try:
                path.unlink()
                n += 1
            except OSError:
                continue
    with _MEMO_LOCK:
        _MEMO.clear()
    return n


# --------------------------------------------------------------------------- #
# 网络抓取
# --------------------------------------------------------------------------- #
def _read_body(resp, limit: int) -> bytes:
    """按 Content-Encoding 解压响应体，最多返回 ``limit`` 字节。

    很多站点（如 python.org）即便没显式声明也回 gzip，直接用 ``read()``
    拿到的是压缩字节，会把 HTML 解析和图片嗅探全部弄坏，因此必须解压。
    """
    enc = (resp.headers.get("Content-Encoding") or "").lower()
    if "gzip" in enc:
        dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
    elif "deflate" in enc:
        dec = zlib.decompressobj()
    else:
        return resp.read(limit)

    out = bytearray()
    while len(out) < limit:
        chunk = resp.read(16384)
        if not chunk:
            break
        try:
            out += dec.decompress(bytes(chunk), limit - len(out))
        except zlib.error:   # 截断 / 畸形流：返回已解出的部分
            break
    return bytes(out)


def _http_get(url: str, limit: int, deadline: float) -> tuple[bytes, str]:
    """GET 一个 URL，返回 ``(bytes, charset)``；失败抛异常由调用方兜住。"""
    left = deadline - time.time()
    if left <= 0.2:
        raise TimeoutError("抓取超时")
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "image/*,text/html;q=0.9,*/*;q=0.5",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        "Accept-Encoding": "gzip, deflate",
    })
    timeout = max(0.5, min(TIMEOUT, left))
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - 已做主机白名单校验
        raw = _read_body(resp, limit)
        charset = ""
        try:
            charset = resp.headers.get_content_charset() or ""
        except Exception:  # noqa: BLE001 - 个别站点返回畸形头
            charset = ""
        ctype = (resp.headers.get_content_type() or "").lower()
        if ctype.startswith("text/") and not charset:
            charset = _charset_from_meta(raw) or ""
    return raw, charset


def _charset_from_meta(raw: bytes) -> str:
    head = raw[:2048].decode("ascii", "ignore")
    m = re.search(r'charset\s*=\s*["\']?([\w-]+)', head, re.I)
    return m.group(1) if m else ""


def _decode(raw: bytes, charset: str = "") -> str:
    """按 HTTP 头 → meta → 常见中文编码的顺序解码页面。"""
    candidates = [charset, "utf-8", "gb18030", "latin-1"]
    seen = set()
    for enc in candidates:
        enc = (enc or "").strip().lower()
        if not enc or enc in seen:
            continue
        seen.add(enc)
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "ignore")


def sniff_ext(data: bytes) -> str | None:
    """按内容嗅探图片类型；不是图片返回 None。"""
    if not data or len(data) < 4:
        return None
    for magic, ext, _mime in _MAGIC:
        if data.startswith(magic):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if _looks_like_svg(data):
        return "svg"
    return None


def _looks_like_svg(data: bytes) -> bool:
    head = data[:1024]
    try:
        text = head.decode("utf-8")
    except UnicodeDecodeError:
        text = head.decode("latin-1", "ignore")
    text = re.sub(r"^\s*(\xef\xbb\xbf)?", "", text, flags=re.UNICODE)
    text = re.sub(r"<\?xml[^>]*\?>", "", text, flags=re.I)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return text.lstrip().lower().startswith("<svg")


def _data_uri(href: str) -> tuple[bytes, str] | None:
    """支持站点把图标内联成 data:URI 的写法。"""
    if not href.lower().startswith("data:"):
        return None
    try:
        head, _, payload = href[5:].partition(",")
    except ValueError:
        return None
    if not payload:
        return None
    import base64

    if ";base64" in head.lower():
        try:
            data = base64.b64decode(payload + "=" * (-len(payload) % 4), validate=False)
        except Exception:  # noqa: BLE001
            return None
    else:
        data = urllib.parse.unquote_to_bytes(payload)
    ext = sniff_ext(data)
    return (data, ext) if ext else None


# `<link ...>` 及其属性
_LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.I)
_ATTR_RE = re.compile(r"""([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*("([^"]*)"|'([^']*)'|([^\s"'>]+))""")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def icon_candidates(html: str, base_url: str) -> list[str]:
    """从页面里挑出候选图标地址，按「更像正经图标」排序。"""
    scored: list[tuple[tuple[int, int], str]] = []
    for tag in _LINK_TAG_RE.findall(html):
        attrs = {}
        for m in _ATTR_RE.finditer(tag):
            value = m.group(3)
            if value is None:
                value = m.group(4)
            if value is None:
                value = m.group(5)
            attrs[m.group(1).lower()] = (value or "").strip()
        rel = attrs.get("rel", "").lower()
        href = attrs.get("href", "")
        if not href or "icon" not in rel:
            continue
        if "mask-icon" in rel:
            priority = 3          # 掩码图标通常是单色，最后再考虑
        elif "apple-touch" in rel:
            priority = 0          # 苹果触屏图标一般最大最清晰
        elif "shortcut" in rel:
            priority = 1
        else:
            priority = 2
        size = 0
        for token in attrs.get("sizes", "").lower().split():
            m = re.match(r"(\d+)x\d+", token)
            if m:
                size = max(size, int(m.group(1)))
        scored.append(((priority, -size), href))
    scored.sort(key=lambda x: x[0])
    out: list[str] = []
    for _score, href in scored:
        if href.lower().startswith("data:"):
            out.append(href)
            continue
        absolute = urllib.parse.urljoin(base_url, href)
        if absolute not in out:
            out.append(absolute)
    return out


# 标题里常见的「站点名」分隔符：竖线 / 中点 / 破折号 / 下划线，以及两侧带空格的连字符
_TITLE_SEP_RE = re.compile(r"\s*[|｜·—–_]\s*|\s+[-]\s+")


def page_title(html: str) -> str:
    """取 <title> 里最有信息量的那一段（「中国知网 - 学术期刊全文数据库」→「中国知网」）。"""
    m = _TITLE_RE.search(html)
    if not m:
        return ""
    raw = re.sub(r"\s+", " ", m.group(1)).strip()
    if not raw:
        return ""
    for part in _TITLE_SEP_RE.split(raw):
        part = part.strip()
        if 2 <= len(part) <= 30:
            return part
    return raw[:40]


# --------------------------------------------------------------------------- #
# 抓取主流程
# --------------------------------------------------------------------------- #
def _load_image(url: str, deadline: float) -> tuple[bytes, str] | None:
    """下载单个候选地址并校验它确实是图片。"""
    if url.lower().startswith("data:"):
        return _data_uri(url)
    if not _target_allowed(url):
        return None
    try:
        data, _charset = _http_get(url, MAX_BYTES, deadline)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    ext = sniff_ext(data)
    return (data, ext) if ext else None


def _crawl(url: str) -> tuple[bytes, str] | None:
    """依次尝试 /favicon.ico 与页面声明的图标，返回 ``(bytes, ext)``。"""
    if not _target_allowed(url):   # 入口先卡一次，页面本身也不许是内网地址
        return None
    deadline = time.time() + DEADLINE
    origin = origin_of(url)

    # 1) 约定俗成的 /favicon.ico —— 一次请求搞定绝大多数站点
    hit = _load_image(origin + "/favicon.ico", deadline)
    if hit:
        return hit

    # 2) 页面里 <link rel="icon"> 声明的图标（含子路径与 data:URI）
    try:
        raw, charset = _http_get(url, HTML_BYTES, deadline)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    for cand in icon_candidates(_decode(raw, charset), url):
        hit = _load_image(cand, deadline)
        if hit:
            return hit
    return None


def get_icon(raw_url, name: str = "", force: bool = False) -> tuple[bytes, str]:
    """取站点图标，返回 ``(bytes, mime)``。任何失败都以首字母头像兜底。"""
    url = normalize_url(raw_url)
    if not url:
        return _avatar(name, ""), "image/svg+xml"
    key = cache_key(url)

    if not force:
        with _MEMO_LOCK:
            memo = _MEMO.get(key)
        if memo and (time.time() - memo[2]) < _MEMO_TTL:
            return memo[0], memo[1]

        path = _cached_path(key)
        if path is not None and _cache_fresh(path, ICON_TTL):
            return _read_icon(path, key)
        if _cache_fresh(_miss_marker(key), MISS_TTL):
            return _avatar(name, url), "image/svg+xml"

    with _MEMO_LOCK:
        if key in _INFLIGHT:
            # 同站点的抓取已经在跑，先给头像，别让页面干等
            return _avatar(name, url), "image/svg+xml"
        _INFLIGHT.add(key)

    if not _GATE.acquire(blocking=False):
        # 并发已满：先给头像，且**不写**失败标记，下次开页仍会正常抓取
        with _MEMO_LOCK:
            _INFLIGHT.discard(key)
        return _avatar(name, url), "image/svg+xml"

    try:
        hit = _crawl(url)
    finally:
        _GATE.release()
        with _MEMO_LOCK:
            _INFLIGHT.discard(key)

    if hit:
        data, ext = hit
        _store(key, data, ext)
        mime = EXT_MIME.get(ext, "image/png")
        with _MEMO_LOCK:
            _remember(key, data, mime)
        return data, mime

    _mark_miss(key)
    return _avatar(name, url), "image/svg+xml"


def _read_icon(path: Path, key: str) -> tuple[bytes, str]:
    ext = path.suffix.lstrip(".").lower()
    mime = EXT_MIME.get(ext, "image/png")
    try:
        data = path.read_bytes()
    except OSError:
        return _avatar("", ""), "image/svg+xml"
    with _MEMO_LOCK:
        _remember(key, data, mime)
    return data, mime


def _remember(key: str, data: bytes, mime: str) -> None:
    if len(_MEMO) >= _MEMO_MAX:
        oldest = min(_MEMO, key=lambda k: _MEMO[k][2])
        _MEMO.pop(oldest, None)
    _MEMO[key] = (data, mime, time.time())


def inspect_site(raw_url) -> dict:
    """读取站点信息（标题 / 主机名），供「添加网站」表单自动填充。

    始终尽力返回 ``host`` —— 页面打不开时前端仍可拿主机名当默认名称。
    """
    url = normalize_url(raw_url)
    if not url:
        return {"ok": False, "url": "", "host": "", "title": "",
                "error": "请输入合法的网址，例如 https://www.cnki.net"}
    host = display_host(url)
    base = {"ok": False, "url": url, "host": host, "title": "", "reachable": False,
            "icon": favicon_path(url, name=host)}
    if not _target_allowed(url):
        return dict(base, error="该地址无法访问（仅支持公网 http/https 站点）")
    deadline = time.time() + DEADLINE
    try:
        raw, charset = _http_get(url, HTML_BYTES, deadline)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return dict(base, error="网站暂时打不开，可手动填写名称")
    title = page_title(_decode(raw, charset))
    return dict(base, ok=True, reachable=True, title=title, error="")


def favicon_path(url: str, name: str = "", force: bool = False) -> str:
    """前端 ``<img src>`` 用的图标地址。"""
    norm = normalize_url(url)
    if not norm:
        return ""
    query = {"url": norm}
    if name:
        query["name"] = name
    if force:
        query["t"] = str(int(time.time()))
    return "/api/links/favicon?" + urllib.parse.urlencode(query)


# --------------------------------------------------------------------------- #
# 存量工作台补种
# --------------------------------------------------------------------------- #
SEED_FLAG = "seeded:links"


def ensure_link_seed(store) -> int:
    """为「常用网站」功能上线前就存在的工作台补一份出厂清单。

    用 ``meta`` 表里的标记位保证只做一次：否则教师手动清空网站列表后，
    下次重启又会被种子复活。返回补入的条数。
    """
    from . import seed as seed_mod

    row = store.conn.execute(
        "SELECT value FROM meta WHERE key = ?", (SEED_FLAG,)
    ).fetchone()
    if row is not None:
        return 0
    added = 0
    if not store.list("links"):
        items = [dict(x) for x in seed_mod.LINKS]
        store._add_many_ordered("links", items)  # noqa: SLF001 - 与 Store 同层的内部协作
        added = len(items)
    store.conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (SEED_FLAG, "1"),
    )
    store.conn.commit()
    return added


def ensure_all(user_ids=None) -> int:
    """为全部教师租户库补种（启动时调用）。"""
    from . import auth, config, db
    from .store import Store

    if user_ids is None:
        try:
            user_ids = [u["id"] for u in auth.list_teachers()]
        except Exception:  # noqa: BLE001 - 账号库尚未就绪时跳过
            return 0
    total = 0
    for uid in user_ids:
        if not config.tenant_db_path(uid).exists():
            continue
        try:
            total += ensure_link_seed(Store(db.connect_tenant(uid)))
        except Exception:  # noqa: BLE001
            continue
    return total


# --------------------------------------------------------------------------- #
# 首字母头像
# --------------------------------------------------------------------------- #
def _monogram(name: str, host: str) -> str:
    text = (name or "").strip()
    if text:
        for ch in text:
            if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
                return ch
    host = host or ""
    return (host[:1] or "?").upper()


def _avatar(name: str, url: str) -> bytes:
    """生成确定性的首字母 SVG 头像（同名同色）。"""
    host = display_host(url) if url else ""
    letter = _monogram(name, host)
    digest = hashlib.sha1((host or letter).encode("utf-8")).digest()
    c1, c2 = AVATAR_COLORS[digest[0] % len(AVATAR_COLORS)]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>'
        "</linearGradient></defs>"
        '<rect width="64" height="64" rx="17" fill="url(#g)"/>'
        '<text x="32" y="33" text-anchor="middle" dominant-baseline="central" '
        'font-family="PingFang SC,Microsoft YaHei,Helvetica,Arial,sans-serif" '
        f'font-size="30" font-weight="700" fill="#ffffff">{esc_xml(letter)}</text>'
        "</svg>"
    )
    return svg.encode("utf-8")
