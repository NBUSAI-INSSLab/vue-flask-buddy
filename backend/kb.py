"""教师个人知识库：文档解析、中文分块与本地 BM25 检索。

设计取舍：
- 教师个人知识库规模小（几十篇内），检索采用**本地 BM25**（jieba 分词），
  零外部依赖、零额外费用，不依赖供应商是否提供 embedding 接口；
  后续如需向量召回，可在 ``search`` 内并列一路向量检索再融合。
- 文档与分块分别存租户库 ``kb_docs`` / ``kb_chunks`` 集合，随租户物理隔离。
- 支持 ``.txt`` ``.md`` ``.pdf`` ``.docx``，解析库已在项目依赖内。
"""
from __future__ import annotations

import math
import re
from datetime import datetime

from .store import Store

MAX_FILE_BYTES = 10 * 1024 * 1024        # 单文件 10MB
ALLOWED_EXTS = (".txt", ".md", ".pdf", ".docx")
CHUNK_SIZE = 480                          # 分块目标字符数（中文 1 字 ≈ 1 token 上下浮动）
CHUNK_OVERLAP = 80
MAX_DOCS = 200                            # 每租户文档数上限
BM25_K1, BM25_B = 1.5, 0.75

_DOC_NAME_MAX = 120


# --------------------------------------------------------------------------- #
# 解析
# --------------------------------------------------------------------------- #
def extract_text(filename: str, data: bytes) -> str:
    """按扩展名解析出纯文本；不支持的类型抛 ValueError。"""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"暂不支持 {ext or '无扩展名'} 文件，仅支持 " + " / ".join(ALLOWED_EXTS))
    if ext in (".txt", ".md"):
        for enc in ("utf-8", "gb18030"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")
    if ext == ".pdf":
        import io

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        parts = [(page.extract_text() or "") for page in reader.pages]
        return "\n".join(parts)
    if ext == ".docx":
        import io

        import docx
        document = docx.Document(io.BytesIO(data))
        parts = [p.text for p in document.paragraphs if p.text.strip()]
        return "\n".join(parts)
    raise ValueError("不支持的文件类型")


def _clean(text: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", text or "").strip()


def chunk_text(text: str) -> list[str]:
    """中文友好的滑动窗口分块：先按段落聚拢，超长段落硬切，相邻块重叠。"""
    text = _clean(text)
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n{2,}|(?<=。)\n", text) if p.strip()]
    # 段落聚拢
    blocks: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(p) > CHUNK_SIZE:
            if buf:
                blocks.append(buf)
                buf = ""
            for i in range(0, len(p), CHUNK_SIZE - CHUNK_OVERLAP):
                blocks.append(p[i:i + CHUNK_SIZE])
            continue
        if len(buf) + len(p) + 1 > CHUNK_SIZE and buf:
            blocks.append(buf)
            buf = p
        else:
            buf = f"{buf}\n{p}" if buf else p
    if buf:
        blocks.append(buf)
    # 相邻块保留少量重叠，弱化边界截断
    out: list[str] = []
    for i, b in enumerate(blocks):
        if i > 0 and CHUNK_OVERLAP and len(blocks[i - 1]) > CHUNK_OVERLAP:
            out.append(blocks[i - 1][-CHUNK_OVERLAP:] + b)
        else:
            out.append(b)
    return [b.strip() for b in out if b.strip()]


# --------------------------------------------------------------------------- #
# 分词与 BM25
# --------------------------------------------------------------------------- #
def _tokenize(text: str) -> list[str]:
    import jieba

    words = jieba.lcut_for_search(text)
    return [w for w in words if w.strip() and not re.fullmatch(r"[\s\W]", w)]


def _bm25_scores(query_tokens: list[str], corpus_tokens: list[list[str]]) -> list[float]:
    """经典 BM25：返回每个文档的得分（与 query_tokens 顺序无关）。"""
    n = len(corpus_tokens)
    if n == 0 or not query_tokens:
        return [0.0] * n
    avgdl = sum(len(t) for t in corpus_tokens) / n or 1.0
    df: dict[str, int] = {}
    for toks in corpus_tokens:
        for w in set(toks):
            df[w] = df.get(w, 0) + 1
    scores = [0.0] * n
    for i, toks in enumerate(corpus_tokens):
        tf: dict[str, int] = {}
        for w in toks:
            tf[w] = tf.get(w, 0) + 1
        dl = len(toks)
        for w in query_tokens:
            if w not in tf:
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            scores[i] += idf * tf[w] * (BM25_K1 + 1) / (
                tf[w] + BM25_K1 * (1 - BM25_B + BM25_B * dl / avgdl)
            )
    return scores


# --------------------------------------------------------------------------- #
# 文档管理
# --------------------------------------------------------------------------- #
def list_docs(store: Store) -> list[dict]:
    """文档清单（不含正文）。"""
    docs = store.list("kb_docs")
    chunk_count: dict[str, int] = {}
    for c in store.list("kb_chunks"):
        chunk_count[c["docId"]] = chunk_count.get(c["docId"], 0) + 1
    for d in docs:
        d["chunks"] = chunk_count.get(d["id"], 0)
    return docs


def add_document(store: Store, filename: str, data: bytes) -> dict:
    """解析 → 分块 → 落库。返回文档记录；解析失败抛 ValueError。"""
    filename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1][: _DOC_NAME_MAX]
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("文件超过 10MB 上限")
    if len(list_docs(store)) >= MAX_DOCS:
        raise ValueError(f"知识库文档已达 {MAX_DOCS} 篇上限")
    text = extract_text(filename, data)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("未能从文件中提取到文本内容")
    doc = store.add("kb_docs", {
        "name": filename,
        "size": len(data),
        "chars": len(_clean(text)),
        "chunks": len(chunks),
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }, prefix="kb")
    for idx, ck in enumerate(chunks):
        store.add("kb_chunks", {"docId": doc["id"], "docName": filename,
                                "idx": idx, "text": ck[:2000]}, prefix="kc",
                  commit=(idx % 50 == 49))
    store.conn.commit()
    return doc


def delete_document(store: Store, doc_id: str) -> bool:
    """删除文档及其全部分块。"""
    doc = store.get("kb_docs", doc_id)
    if not doc:
        return False
    for c in store.list("kb_chunks"):
        if c.get("docId") == doc_id:
            store.remove("kb_chunks", c["id"])
    store.conn.commit()
    return store.remove("kb_docs", doc_id)


def doc_exists_name(store: Store, name: str) -> bool:
    return any(d.get("name") == name for d in store.list("kb_docs"))


# --------------------------------------------------------------------------- #
# 检索
# --------------------------------------------------------------------------- #
def search(store: Store, query: str, top_k: int = 5) -> list[dict]:
    """BM25 检索，返回 [{docId, docName, idx, text, score}]，得分归一到 0~1。"""
    query = _clean(query)
    if not query:
        return []
    chunks = store.list("kb_chunks")
    if not chunks:
        return []
    q_tokens = _tokenize(query)
    corpus_tokens = [_tokenize(c["text"]) for c in chunks]
    scores = _bm25_scores(q_tokens, corpus_tokens)
    ranked = sorted(zip(chunks, scores), key=lambda x: -x[1])[: max(1, int(top_k))]
    best = ranked[0][1] or 1.0
    return [
        {"docId": c["docId"], "docName": c.get("docName") or "",
         "idx": c.get("idx", 0), "text": c["text"],
         "score": round(s / best, 3)}
        for c, s in ranked if s > 0
    ]
