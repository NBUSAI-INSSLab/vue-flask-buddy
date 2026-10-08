"""pytest 共享夹具：隔离数据目录 → 应用 → 各类登录态的测试客户端。

关键点：``FWB_DATA_DIR`` 必须在导入 ``backend`` 之前设置，
因为 ``backend.config`` 在模块导入时就把数据目录解析成常量。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---- 隔离数据目录（测试不污染 data/）----
_TMP_DIR = Path(tempfile.mkdtemp(prefix="fwb-test-"))
os.environ["FWB_DATA_DIR"] = str(_TMP_DIR)

from backend import auth, config, db, seed_teachers  # noqa: E402
from backend import create_app  # noqa: E402
from backend.seed import full_seed  # noqa: E402
from backend.store import open_store  # noqa: E402

TEACHER_ID = config.DEFAULT_TENANT_ID          # 江先亮
TEACHER_CREDS = {"username": "jiangxl", "password": "123456"}
ADMIN_CREDS = {"username": "admin", "password": "admin123"}
SEED_USER_IDS = {u["id"] for u in seed_teachers.all_users()}


@pytest.fixture(scope="session", autouse=True)
def _cleanup_tmp():
    yield
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def app():
    application = create_app({"TESTING": True})
    return application


@pytest.fixture(autouse=True)
def reset_data(app):
    """每个用例开始前把演示教师的数据恢复到初始状态。"""
    with app.app_context():
        open_store(TEACHER_ID).replace_all(full_seed())
    yield


def _rebuild_users(app) -> None:
    """把账号表恢复为初始种子，并清掉用例期间新建账号的租户库。"""
    with app.app_context():
        udb = db.get_users_db()
        extra = [r["id"] for r in udb.execute("SELECT id FROM users").fetchall()
                 if r["id"] not in SEED_USER_IDS]
        udb.execute("DELETE FROM users")
        udb.commit()
        for user_id in extra:
            base = config.tenant_db_path(user_id)
            for suffix in ("", "-wal", "-shm"):
                path = base.with_name(base.name + suffix)
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
        for u in seed_teachers.all_users():
            # 只在租户库缺失时才重新灌种子（重建账号不重置既有数据，保持用例间一致）
            need_seed = (u["role"] == config.ROLE_TEACHER
                         and not config.tenant_db_path(u["id"]).exists())
            auth.create_user(
                user_id=u["id"], username=u["username"], password=u["password"],
                role=u["role"], name=u["name"], title=u["title"], dept=u["dept"],
                email=u["email"], office=u["office"],
                seed=seed_teachers.initial_data(u) if need_seed else None,
            )


@pytest.fixture()
def clean_users(app):
    """账号表回到初始状态（供会改动账号的管理端用例）。"""
    _rebuild_users(app)
    yield
    _rebuild_users(app)


def _login(client, creds) -> None:
    resp = client.post("/api/auth/login", json=creds)
    assert resp.status_code == 200, resp.get_json()


def _preset_session(client, user_id: str) -> None:
    """直接写入登录态，跳过 PBKDF2 校验（密码流程由专门的用例覆盖）。"""
    with client.session_transaction() as sess:
        sess["uid"] = user_id
        sess.permanent = True


@pytest.fixture()
def anon_client(app):
    """未登录客户端。"""
    return app.test_client()


@pytest.fixture()
def client(app):
    """已登录的教师客户端（江先亮）。"""
    c = app.test_client()
    _preset_session(c, TEACHER_ID)
    return c


@pytest.fixture()
def admin_client(app):
    """已登录的管理员客户端。"""
    c = app.test_client()
    _preset_session(c, "u_admin")
    return c


@pytest.fixture()
def store(app):
    with app.app_context():
        yield open_store(TEACHER_ID)
