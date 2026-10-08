"""集中配置：路径、数据目录、默认参数。

所有路径均可通过环境变量覆盖，方便容器化部署或把数据放到独立盘。

多租户布局（v2）::

    data/
      users.db            # 全局库：账号、角色、密码哈希
      secret.key          # 会话签名密钥（首次运行生成）
      tenants/<uid>.db    # 每位教师一个独立库：documents 文档集合
      uploads/  tmp/      # 上传缓存与工具产物

采用「一教师一库」而非在 documents 里加 owner 列：教师视角的查询语句
完全不变（物理隔离），跨教师统计只需逐个打开小库汇总，数据量下成本可忽略。
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

# vue-flask-buddy/
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据目录（SQLite 库、上传缓存、导出产物都放这里）
DATA_DIR = Path(os.environ.get("FWB_DATA_DIR", BASE_DIR / "data"))

# 全局库：账号
USERS_DB_PATH = Path(os.environ.get("FWB_USERS_DB_PATH", DATA_DIR / "users.db"))
# 租户库目录：每位教师一个文件
TENANT_DIR = DATA_DIR / "tenants"
# 旧版单库位置（v1 只有一位教师），首启迁移为首位教师的租户库
LEGACY_DB_PATH = DATA_DIR / "workbench.db"
# 会话签名密钥
SECRET_KEY_FILE = DATA_DIR / "secret.key"

UPLOAD_DIR = DATA_DIR / "uploads"
TMP_DIR = DATA_DIR / "tmp"

# 前端静态资源目录
FRONTEND_DIR = BASE_DIR / "frontend"

# 数据结构版本：种子结构变化时递增，用于 migrate
SCHEMA_VERSION = 2

# 全部数据集合（与前端导航、全局搜索一致）
COLLECTIONS = [
    "projects",     # 科研项目
    "literature",   # 文献仓库
    "courses",      # 课程资源
    "students",     # 学生指导
    "events",       # 日程管理
    "todos",        # 待办
    "exchanges",    # 学术交流
    "teachings",    # 教学管理
    "achievements", # 成果管理
    "developments", # 个人发展
    "educations",   # 教育经历（个人简历）
    "services",     # 社会服务（个人简历：兼职 / 审稿 / 评审 / 学会任职）
    "tools",        # 常用工具
    "tool_runs",    # 工具执行留痕（设备台账等）
    "links",        # 常用网站（首页底部快捷入口，图标自动抓取）
]

PROFILE_ID = "self"

# ---- 角色 ----
ROLE_ADMIN = "admin"
ROLE_TEACHER = "teacher"

# ---- 成果审核状态 ----
AUDIT_PENDING = "待审核"
AUDIT_APPROVED = "已通过"
AUDIT_REJECTED = "已退回"
AUDIT_STATUSES = (AUDIT_PENDING, AUDIT_APPROVED, AUDIT_REJECTED)

# 成果状态中视为「已落地」的取值：审核回填时默认标记为已通过
PUBLISHED_STATUSES = ("已发表", "已录用", "已授权", "已登记", "已交付", "已获奖")

# 无请求上下文（脚本 / 测试 / 初始化）时的兜底租户
DEFAULT_TENANT_ID = "u_jiangxl"

# 登录态有效期：14 天
SESSION_MAX_AGE = 14 * 24 * 3600


def tenant_db_path(user_id: str) -> Path:
    """某位教师的租户库路径。"""
    return TENANT_DIR / f"{user_id}.db"


def ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOAD_DIR, TMP_DIR, TENANT_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_secret_key() -> str:
    """读取（或首次生成）会话签名密钥。

    持久化到文件，避免每次重启都让已登录用户的 Cookie 失效。
    """
    env = os.environ.get("FWB_SECRET_KEY")
    if env:
        return env
    ensure_dirs()
    if SECRET_KEY_FILE.exists():
        key = SECRET_KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key
    key = secrets.token_hex(32)
    SECRET_KEY_FILE.write_text(key, encoding="utf-8")
    try:  # 尽力收紧权限（Windows 上可能不支持，忽略即可）
        os.chmod(SECRET_KEY_FILE, 0o600)
    except OSError:
        pass
    return key
