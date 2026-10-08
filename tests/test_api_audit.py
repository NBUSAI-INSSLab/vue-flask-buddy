"""成果审核接口测试：队列汇总 / 筛选 / 通过 / 退回 / 批量 / 权限 / 教师侧流转。

所有写操作只落在「江先亮」这一位教师身上 —— ``tests/conftest.py`` 的
``reset_data`` 夹具会在每个用例前把他的租户库还原为 ``full_seed()``，
因此用例之间互不影响，也不会污染其他教师的数据。
"""
from __future__ import annotations

import pytest

from backend import audit, config

ADMIN_CREDS = {"username": "admin", "password": "admin123"}
TEACHER_ID = config.DEFAULT_TENANT_ID          # 江先亮
OTHER_TEACHER_ID = "u_zhangwei"                # 张伟

PENDING = config.AUDIT_PENDING
APPROVED = config.AUDIT_APPROVED
REJECTED = config.AUDIT_REJECTED


def _data(resp):
    body = resp.get_json()
    assert body["ok"] is True, body
    return body["data"]


def _error(resp):
    body = resp.get_json()
    assert body["ok"] is False, body
    return body["error"]


def _mine(admin_client, status=""):
    """江先亮的成果行（可直接安全修改）。"""
    query = f"?teacher={TEACHER_ID}"
    if status:
        query += f"&status={status}"
    return _data(admin_client.get("/api/admin/achievements" + query))["rows"]


def _one_pending(admin_client):
    rows = _mine(admin_client, PENDING)
    assert rows, "江先亮应有待审成果"
    return rows[0]


def _one_approved(admin_client):
    rows = _mine(admin_client, APPROVED)
    assert rows, "江先亮应有已通过成果"
    return rows[0]


# --------------------------------------------------------------------------- #
# 队列汇总
# --------------------------------------------------------------------------- #
def test_achievements_queue_shape(admin_client):
    data = _data(admin_client.get("/api/admin/achievements"))
    assert data["rows"], "审核队列不应为空"
    assert data["filter"] == {"status": "", "teacher": "", "q": ""}

    row = data["rows"][0]
    for key in ("id", "teacherId", "teacherName", "title", "type", "level",
                "status", "date", "score", "auditStatus", "auditNote",
                "auditBy", "auditAt", "auditLog"):
        assert key in row, f"审核行缺少字段 {key}"
    assert row["auditStatus"] in config.AUDIT_STATUSES
    assert isinstance(row["auditLog"], list) and row["auditLog"], "每条成果都应有审核轨迹"


def test_queue_stats_are_self_consistent(admin_client):
    stats = _data(admin_client.get("/api/admin/achievements"))["stats"]
    assert stats["total"] == stats["pending"] + stats["approved"] + stats["rejected"]
    assert stats["total"] == 25
    assert stats["teachers"] == 5
    assert stats["pendingTeachers"] <= stats["teachers"]
    assert sum(stats["pendingByType"].values()) == stats["pending"]
    assert stats["rejectedTeachers"] == (1 if stats["rejected"] else 0)


def test_queue_sorted_pending_first(admin_client):
    rows = _data(admin_client.get("/api/admin/achievements"))["rows"]
    rank = {PENDING: 0, REJECTED: 1, APPROVED: 2}
    seq = [rank[r["auditStatus"]] for r in rows]
    assert seq == sorted(seq), "待审核应排在队列最前"


def test_filter_by_status(admin_client):
    for state in (PENDING, APPROVED, REJECTED):
        rows = _data(admin_client.get(f"/api/admin/achievements?status={state}"))["rows"]
        assert all(r["auditStatus"] == state for r in rows)
        assert len(rows) == _data(admin_client.get("/api/admin/achievements"))["stats"][
            {"待审核": "pending", "已通过": "approved", "已退回": "rejected"}[state]]


def test_filter_rejects_bad_status(admin_client):
    resp = admin_client.get("/api/admin/achievements?status=随便")
    assert resp.status_code == 400
    assert "审核状态" in _error(resp)


def test_filter_by_teacher(admin_client):
    rows = _mine(admin_client)
    assert rows and {r["teacherId"] for r in rows} == {TEACHER_ID}
    assert all(r["teacherName"] == "江先亮" for r in rows)


def test_filter_by_keyword(admin_client):
    rows = _data(admin_client.get("/api/admin/achievements?q=专利"))["rows"]
    assert rows
    for r in rows:
        hay = " ".join(str(r.get(k, "")) for k in
                       ("title", "type", "level", "venue", "authors", "status",
                        "teacherName", "teacherDept", "projectName"))
        assert "专利" in hay
    assert len(rows) < 25


def test_teacher_options_carry_pending_count(admin_client):
    data = _data(admin_client.get("/api/admin/achievements"))
    options, stats = data["teachers"], data["stats"]
    assert len(options) == 5
    assert [o["pending"] for o in options] == sorted(
        [o["pending"] for o in options], reverse=True), "下拉按待审计数倒序"
    assert sum(o["total"] for o in options) == stats["total"]
    assert sum(o["pending"] for o in options) == stats["pending"], "下拉待审计数之和应等于队列待审总数"


# --------------------------------------------------------------------------- #
# 单条审核
# --------------------------------------------------------------------------- #
def test_approve_single(admin_client):
    before = _data(admin_client.get("/api/admin/achievements"))["stats"]
    row = _one_pending(admin_client)
    data = _data(admin_client.post("/api/admin/achievements/review", json={
        "teacherId": TEACHER_ID, "id": row["id"], "action": "approve",
    }))
    assert data["achievement"]["auditStatus"] == APPROVED
    assert data["achievement"]["auditBy"] == "系统管理员"
    assert data["achievement"]["auditAt"]
    log = data["achievement"]["auditLog"]
    assert log[-1]["action"] == "通过"
    assert log[-1]["by"] == "系统管理员"
    assert len(log) == len(row["auditLog"]) + 1
    assert data["stats"]["pending"] == before["pending"] - 1
    assert data["stats"]["approved"] == before["approved"] + 1


def test_reject_requires_note(admin_client):
    row = _one_pending(admin_client)
    resp = admin_client.post("/api/admin/achievements/review", json={
        "teacherId": TEACHER_ID, "id": row["id"], "action": "reject",
    })
    assert resp.status_code == 400
    assert "退回时必须填写审核意见" in _error(resp)


def test_reject_with_note(admin_client):
    row = _one_pending(admin_client)
    note = "录用函未附，请补充后再提交。"
    data = _data(admin_client.post("/api/admin/achievements/review", json={
        "teacherId": TEACHER_ID, "id": row["id"], "action": "reject", "note": note,
    }))
    assert data["achievement"]["auditStatus"] == REJECTED
    assert data["achievement"]["auditNote"] == note
    assert data["achievement"]["auditLog"][-1]["note"] == note
    assert data["stats"]["rejected"] == 1


def test_reject_note_length_limited(admin_client):
    row = _one_pending(admin_client)
    resp = admin_client.post("/api/admin/achievements/review", json={
        "teacherId": TEACHER_ID, "id": row["id"], "action": "reject", "note": "补" * 201,
    })
    assert resp.status_code == 400
    assert "审核意见" in _error(resp)


def test_reset_returns_to_pending(admin_client):
    row = _one_approved(admin_client)
    data = _data(admin_client.post("/api/admin/achievements/review", json={
        "teacherId": TEACHER_ID, "id": row["id"], "action": "reset",
    }))
    assert data["achievement"]["auditStatus"] == PENDING
    assert data["achievement"]["auditNote"] == ""
    assert data["achievement"]["auditLog"][-1]["action"] == "撤回"


def test_review_unknown_action(admin_client):
    row = _one_pending(admin_client)
    resp = admin_client.post("/api/admin/achievements/review", json={
        "teacherId": TEACHER_ID, "id": row["id"], "action": "delete",
    })
    assert resp.status_code == 400
    assert "approve / reject / reset" in _error(resp)


def test_review_missing_id(admin_client):
    resp = admin_client.post("/api/admin/achievements/review", json={
        "teacherId": TEACHER_ID, "action": "approve",
    })
    assert resp.status_code == 400
    assert "缺少" in _error(resp)


def test_review_unknown_achievement(admin_client):
    resp = admin_client.post("/api/admin/achievements/review", json={
        "teacherId": TEACHER_ID, "id": "a_not_exist", "action": "approve",
    })
    assert resp.status_code == 404
    assert "成果不存在" in _error(resp)


def test_review_unknown_teacher(admin_client):
    resp = admin_client.post("/api/admin/achievements/review", json={
        "teacherId": "u_nobody", "id": "a1", "action": "approve",
    })
    assert resp.status_code == 404


def test_review_rejects_non_object_body(admin_client):
    resp = admin_client.post("/api/admin/achievements/review", json=[1, 2])
    assert resp.status_code == 400
    assert "JSON 对象" in _error(resp)


# --------------------------------------------------------------------------- #
# 批量审核
# --------------------------------------------------------------------------- #
def test_batch_approve(admin_client):
    before = _data(admin_client.get("/api/admin/achievements"))["stats"]
    rows = _mine(admin_client, PENDING)
    assert len(rows) >= 3
    picked = rows[:2]
    data = _data(admin_client.post("/api/admin/achievements/batch-review", json={
        "action": "approve",
        "items": [{"teacherId": TEACHER_ID, "id": r["id"]} for r in picked],
    }))
    assert data["reviewed"] == 2
    assert data["missing"] == [] and data["invalid"] == 0
    assert data["stats"]["pending"] == before["pending"] - 2
    assert data["stats"]["approved"] == before["approved"] + 2

    left = {r["id"]: r["auditStatus"] for r in _mine(admin_client)}
    for r in picked:
        assert left[r["id"]] == APPROVED


def test_batch_reject_requires_note(admin_client):
    rows = _mine(admin_client, PENDING)[:2]
    resp = admin_client.post("/api/admin/achievements/batch-review", json={
        "action": "reject",
        "items": [{"teacherId": TEACHER_ID, "id": r["id"]} for r in rows],
    })
    assert resp.status_code == 400


def test_batch_empty_items(admin_client):
    resp = admin_client.post("/api/admin/achievements/batch-review", json={
        "action": "approve", "items": [],
    })
    assert resp.status_code == 400
    assert "至少一条" in _error(resp)


def test_batch_tolerates_bad_items(admin_client):
    good = _mine(admin_client, PENDING)[0]
    data = _data(admin_client.post("/api/admin/achievements/batch-review", json={
        "action": "approve",
        "items": [
            {"teacherId": TEACHER_ID, "id": good["id"]},
            {"teacherId": TEACHER_ID, "id": "a_missing"},
            {"teacherId": "u_nobody", "id": "a1"},
            "not-an-object",
        ],
    }))
    assert data["reviewed"] == 1
    assert data["missing"] == ["a_missing"]
    assert data["invalid"] == 2


def test_batch_limit(admin_client):
    resp = admin_client.post("/api/admin/achievements/batch-review", json={
        "action": "approve",
        "items": [{"teacherId": TEACHER_ID, "id": f"a{i}"} for i in range(201)],
    })
    assert resp.status_code == 400
    assert "200" in _error(resp)


# --------------------------------------------------------------------------- #
# 权限
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("method,path", [
    ("get", "/api/admin/achievements"),
    ("post", "/api/admin/achievements/review"),
    ("post", "/api/admin/achievements/batch-review"),
])
def test_audit_endpoints_forbidden_for_teacher(client, method, path):
    assert getattr(client, method)(path).status_code == 403


@pytest.mark.parametrize("method,path", [
    ("get", "/api/admin/achievements"),
    ("post", "/api/admin/achievements/review"),
])
def test_audit_endpoints_require_login(anon_client, method, path):
    assert getattr(anon_client, method)(path).status_code == 401


# --------------------------------------------------------------------------- #
# 总览 / 教师详情携带审核信息
# --------------------------------------------------------------------------- #
def test_overview_carries_audit_stats(admin_client):
    data = _data(admin_client.get("/api/admin/overview"))
    assert "audit" in data
    assert data["audit"] == _data(admin_client.get("/api/admin/achievements"))["allStats"]


def test_teacher_detail_carries_audit_block(admin_client):
    detail = _data(admin_client.get(f"/api/admin/teachers/{TEACHER_ID}"))["detail"]
    block = detail["audit"]
    assert block["total"] == 8
    assert block["pending"] + block["approved"] + block["rejected"] == 8
    assert 0 <= block["approveRate"] <= 100
    assert len(block["history"]) <= 6
    if block["history"]:
        assert {"title", "at", "by", "action"} <= set(block["history"][0])


# --------------------------------------------------------------------------- #
# 教师侧流转
# --------------------------------------------------------------------------- #
def test_new_achievement_enters_pending(client):
    created = _data(client.post("/api/collections/achievements", json={
        "title": "测试用新成果", "type": "期刊论文", "level": "SCI 二区",
        "status": "撰写中", "score": 3,
    }))
    assert created["auditStatus"] == PENDING
    assert created["auditNote"] == ""
    assert created["auditLog"][0]["action"] == "登记"
    assert created["auditLog"][0]["status"] == PENDING


def test_editing_approved_achievement_triggers_resubmit(client):
    state = _data(client.get("/api/state"))
    approved = [a for a in state["achievements"] if a["auditStatus"] == APPROVED]
    assert approved, "种子数据应有已通过成果"
    target = approved[0]

    updated = _data(client.patch(f"/api/collections/achievements/{target['id']}",
                                json={"title": target["title"] + "（修订版）"}))
    assert updated["auditStatus"] == PENDING
    assert updated["auditNote"] == ""
    assert updated["auditLog"][-1]["action"] == "重新提交"


def test_editing_non_core_field_keeps_status(client):
    state = _data(client.get("/api/state"))
    approved = [a for a in state["achievements"] if a["auditStatus"] == APPROVED][0]
    updated = _data(client.patch(f"/api/collections/achievements/{approved['id']}",
                                 json={"favorite": True}))
    assert updated["auditStatus"] == APPROVED, "非核心字段变更不应触发重新审核"


def test_state_exposes_audit_fields_for_teacher(client):
    items = _data(client.get("/api/state"))["achievements"]
    assert items
    for a in items:
        assert a["auditStatus"] in config.AUDIT_STATUSES
        assert isinstance(a["auditLog"], list) and a["auditLog"]


def test_audit_module_backfills_legacy_docs(store):
    """删掉审核字段后，回填逻辑应恢复它们（模拟 v2 前的存量数据）。"""
    target = store.list("achievements")[0]
    store.update("achievements", target["id"], {
        "auditStatus": "", "auditNote": "", "auditBy": "",
        "auditAt": "", "auditLog": [],
    })
    assert audit.ensure_fields(store) >= 1
    fixed = store.get("achievements", target["id"])
    assert audit.is_normalized(fixed)
    assert fixed["auditLog"][0]["action"] == "登记"


def test_pending_count_matches_queue(admin_client, store):
    rows = _mine(admin_client, PENDING)
    assert audit.pending_count(TEACHER_ID) == len(rows)
