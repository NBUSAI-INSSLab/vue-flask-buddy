"""智能体大模型配置：多供应商预设、租户级持久化、连通性测试。

配置按教师隔离存放在租户库 ``settings`` 集合（id = ``agent_llm``），
字段：``provider`` / ``baseUrl`` / ``apiKey`` / ``model`` / ``temperature``。

供应商均走 OpenAI 兼容协议（langchain-openai 的 ``ChatOpenAI``），
因此 DeepSeek、通义 DashScope 兼容模式、本地 Ollama、各类中转站
只需换 ``base_url`` + ``model`` 即可复用同一套代码。
"""
from __future__ import annotations

from .store import Store

# settings 集合中智能体配置的文档 id
CONFIG_ID = "agent_llm"

# 供应商预设：默认 base_url 与常用模型（用户可改）
PROVIDERS = {
    "deepseek": {
        "label": "DeepSeek",
        "baseUrl": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "needKey": True,
        "hint": "platform.deepseek.com 申请 API Key",
    },
    "qwen": {
        "label": "通义千问",
        "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "needKey": True,
        "hint": "阿里云百炼控制台申请 API Key",
    },
    "moonshot": {
        "label": "Kimi",
        "baseUrl": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "needKey": True,
        "hint": "platform.moonshot.cn 申请 API Key",
    },
    "ollama": {
        "label": "本地 Ollama",
        "baseUrl": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5:7b",
        "needKey": False,
        "hint": "本机运行 ollama serve，无需 API Key",
    },
    "custom": {
        "label": "自定义（OpenAI 兼容）",
        "baseUrl": "",
        "model": "",
        "needKey": True,
        "hint": "填写任意 OpenAI 兼容服务的地址与模型名",
    },
}

DEFAULT_PROVIDER = "deepseek"
TEXT_MAX = 200          # 各文本字段落库截断上限
TEMP_MIN, TEMP_MAX = 0.0, 2.0

# 配置白名单（落库字段）
_FIELDS = ("provider", "baseUrl", "apiKey", "model", "temperature")


def _clip(value, limit: int = TEXT_MAX) -> str:
    return str(value or "").strip()[:limit]


def get_llm_config(store: Store) -> dict:
    """读取租户的智能体配置，缺失字段用供应商预设补齐。"""
    doc = store.get("settings", CONFIG_ID) or {}
    provider = doc.get("provider") if doc.get("provider") in PROVIDERS else DEFAULT_PROVIDER
    preset = PROVIDERS[provider]
    cfg = {
        "provider": provider,
        "baseUrl": _clip(doc.get("baseUrl")) or preset["baseUrl"],
        "apiKey": _clip(doc.get("apiKey"), 200),
        "model": _clip(doc.get("model")) or preset["model"],
        "temperature": _temperature(doc.get("temperature")),
    }
    cfg["ready"] = bool(cfg["apiKey"]) or not preset["needKey"]
    return cfg


def _temperature(value) -> float:
    try:
        t = float(value)
    except (TypeError, ValueError):
        return 0.3
    return min(TEMP_MAX, max(TEMP_MIN, t))


def save_llm_config(store: Store, patch: dict) -> dict:
    """保存配置补丁；键不在白名单的字段一律忽略。返回保存后的完整配置（key 掩码）。"""
    current = store.get("settings", CONFIG_ID) or {}
    data: dict = {}
    for f in _FIELDS:
        if f in patch:
            if f == "temperature":
                data[f] = _temperature(patch[f])
            elif f == "apiKey":
                # 掩码值（前端未改动 key 时原样传回）不覆盖真实 key
                v = str(patch[f] or "").strip()
                if v and not v.startswith("***"):
                    data[f] = v[:200]
            else:
                data[f] = _clip(patch[f], 200)
    current.update(data)
    store.add("settings", dict(current, id=CONFIG_ID))
    return public_llm_config(store)


def public_llm_config(store: Store) -> dict:
    """对外视图：不回显明文 key，只给掩码与就绪状态。"""
    cfg = get_llm_config(store)
    key = cfg.pop("apiKey", "")
    preset = PROVIDERS[cfg["provider"]]
    cfg.update({
        "hasKey": bool(key),
        "keyMasked": (key[:3] + "***" + key[-4:]) if len(key) > 8 else ("***" if key else ""),
        "ready": cfg.pop("ready"),
        "needKey": preset["needKey"],
        "hint": preset["hint"],
        "providers": [
            {"key": k, "label": p["label"], "baseUrl": p["baseUrl"],
             "model": p["model"], "needKey": p["needKey"]}
            for k, p in PROVIDERS.items()
        ],
    })
    return cfg


def real_llm_config(store: Store) -> dict:
    """内部视图：含明文 key，仅供构造 LLM 客户端使用。"""
    return get_llm_config(store)


def build_llm(cfg: dict):
    """按配置构造 ChatOpenAI 客户端（OpenAI 兼容协议）。"""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=cfg.get("model") or PROVIDERS[cfg.get("provider", DEFAULT_PROVIDER)]["model"],
        api_key=cfg.get("apiKey") or "EMPTY",     # Ollama 等本地服务允许占位
        base_url=cfg.get("baseUrl") or None,
        temperature=float(cfg.get("temperature") or 0.3),
        timeout=90,
        max_retries=1,
    )


def test_llm(cfg: dict) -> dict:
    """连通性测试：发一条最小补全请求。返回 {ok, message, model}。"""
    if not cfg.get("baseUrl"):
        return {"ok": False, "message": "请先填写接口地址（base_url）"}
    preset = PROVIDERS.get(cfg.get("provider"), {})
    if preset.get("needKey") and not cfg.get("apiKey"):
        return {"ok": False, "message": "该供应商需要 API Key"}
    try:
        llm = build_llm(cfg)
        reply = llm.invoke("请只回复两个字：正常")
        text = str(getattr(reply, "content", "") or "").strip()
        return {"ok": True, "message": f"连接成功，模型回复：{text[:40] or '（空）'}",
                "model": cfg.get("model")}
    except Exception as exc:  # noqa: BLE001 —— 网络/鉴权错误都转成可读提示
        msg = str(exc)
        for pat, human in (
            ("401", "API Key 无效或未授权"),
            ("404", "接口地址或模型名不存在"),
            ("timed out", "连接超时，请检查地址与网络"),
            ("Connection", "无法连接服务，请检查接口地址"),
        ):
            if pat in msg:
                msg = human
                break
        else:
            msg = msg[:160]
        return {"ok": False, "message": f"连接失败：{msg}", "model": cfg.get("model")}
