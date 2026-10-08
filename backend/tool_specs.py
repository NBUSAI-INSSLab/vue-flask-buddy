"""12 项工具的表单字段规格（供前端动态渲染运行器）。

字段结构：
    {name, label, type, value?, opts?, ph?, hint?, req?, rows?}
type ∈ select | date | number | text | textarea | mono | check | file

规格是"数据"而非"界面代码"，因此新增工具或调整参数无需改动前端组件。
"""
from __future__ import annotations

from .tools import BUDGET_RULES, DEVICE_CONDITIONS, PPT_PRESETS
from .utils import day_offset, today


def _f(name, label, type_="text", **kw) -> dict:
    d = {"name": name, "label": label, "type": type_}
    d.update({k: v for k, v in kw.items() if v is not None})
    return d


def tool_specs(key: str, store) -> list[dict]:
    """返回指定工具的字段列表；key 未知时返回空列表。"""

    if key == "teaching_calendar":
        courses = store.list("courses")
        opts = [f"{c.get('code', '')} {c.get('name', '')}".strip() for c in courses] or ["（暂无课程）"]
        return [
            _f("course_label", "选择课程", "select", opts=opts, value=opts[0]),
            _f("start_date", "开课首日", "date", value=day_offset(30), req=True),
            _f("sessions_per_week", "每周上课次数", "select", opts=["1", "2", "3", "4", "5"], value="2"),
            _f("weekdays", "上课星期（1=周一 … 7=周日）", ph="留空按每周次数自动分配，如 1,3"),
            _f("holidays", "节假日 / 调休日期", ph="多个用逗号分隔，如 2026-10-01,2026-10-02"),
            _f("skip_holidays", "节假日自动顺延", "check", value=True),
            _f("hours_per_session", "每次课时长（学时）", "number", value="2"),
        ]

    if key == "grade_calc":
        return [
            _f("raw", "成绩数据（每行：姓名 平时 期中 期末）", "mono", rows=8, req=True,
               ph="李明 85 78 92\n王雪 90 88 95\n张伟 72 65 70",
               hint="支持空格 / 逗号 / 制表符分隔，可直接从 Excel 粘贴"),
            _f("w_usual", "平时权重（%）", "number", value="30"),
            _f("w_mid", "期中权重（%）", "number", value="20"),
            _f("w_final", "期末权重（%）", "number", value="50"),
            _f("fail_line", "及格线", "number", value="60"),
            _f("curve", "整体调分（分）", "number", value="0"),
        ]

    if key == "cite_convert":
        return [
            _f("raw", "文献数据（粘贴 BibTeX / RIS / 参考文献列表）", "mono", rows=9, req=True,
               ph="@article{li2024radar,\n  author = {Li, Xin and He, Yuan},\n"
                  "  title  = {Radar-based Human Activity Recognition},\n"
                  "  journal= {IEEE Sensors Journal},\n  year   = {2024}\n}"),
            _f("src_format", "源格式", "select", opts=["自动识别", "BibTeX", "RIS", "GB/T 7714"], value="自动识别"),
            _f("dst_format", "目标格式", "select", opts=["GB/T 7714", "APA", "BibTeX", "RIS"], value="GB/T 7714"),
            _f("sort_by", "排序方式", "select", opts=["保持原顺序", "按年份", "按作者", "按标题"], value="保持原顺序"),
        ]

    if key == "budget_calc":
        fields = [
            _f("total", "项目总经费（万元）", "number", value="62", req=True),
            _f("allocated", "已支出 / 已分配（万元）", "number", value="0"),
        ]
        for name, rule in BUDGET_RULES.items():
            fields.append(_f(f"_{name}", f"{name}（建议上限 {rule['max']:.0%}）", "number",
                             value="0", hint=rule["note"]))
        return fields

    if key == "submission_track":
        return [
            _f("only_paper", "统计范围", "select", opts=["仅期刊论文", "全部成果类型"], value="仅期刊论文"),
            _f("warn_days", "在审超期阈值（天）", "number", value="90"),
        ]

    if key == "student_board":
        return [
            _f("scope", "统计范围", "select",
               opts=["全部学生", "硕士生", "博士生", "进度滞后"], value="全部学生"),
        ]

    if key == "duty_log":
        return [
            _f("kind", "事项类型", "select", opts=["调课", "补课", "代课", "监考", "值班"], value="调课"),
            _f("course", "课程 / 事项名称", req=True, ph="如 计算机网络（第 03 讲）"),
            _f("orig_date", "原定日期", ph="yyyy-MM-dd，如 2026-10-08"),
            _f("orig_time", "原定时间", ph="如 10:00"),
            _f("new_date", "新日期", ph="yyyy-MM-dd，如 2026-10-15"),
            _f("new_time", "新时间", ph="如 14:00"),
            _f("room", "上课地点", ph="如 一教 302"),
            _f("reason", "变更原因", ph="如 参加学术会议"),
            _f("audience", "通知对象", ph="如 全班学生 + 教务办"),
            _f("notify", "执行动作", "select",
               opts=["写入日程并生成通知", "仅生成通知文本"], value="写入日程并生成通知"),
        ]

    if key == "meeting_note":
        return [
            _f("title", "会议主题", req=True, ph="如 课题组第 12 次例会"),
            _f("when", "会议时间", value=today(), ph="yyyy-MM-dd 或 2026-10-04 14:00"),
            _f("place", "会议地点", ph="如 信息楼 A-513 / 线上"),
            _f("host", "主持人", value=(store.get_profile() or {}).get("name", "")),
            _f("attendees", "参会人", ph="多人用逗号分隔，如 李明,王雪,张伟"),
            _f("agenda", "会议议题", "textarea", rows=3, ph="逐条列出讨论议题…"),
            _f("conclusion", "讨论结论", "textarea", rows=3, ph="形成的决定与共识…"),
            _f("actions", "待办事项（每行：事项 | 负责人 | 截止日期）", "mono", rows=5,
               ph="补充消融实验对比 | 李明 | 2026-10-20\n重绘投稿图表 | 王雪 | 2026-10-25"),
            _f("push_todo", "同时写入待办清单", "check", value=True),
        ]

    if key == "pdf_toolkit":
        return [
            _f("mode", "操作模式", "select",
               opts=["合并多个 PDF", "拆分 PDF", "仅统计信息"], value="合并多个 PDF"),
            _f("_files", "选择 PDF 文件（可多选）", "file", req=True, accept=".pdf",
               hint="文件上传到服务端后在服务器本地处理"),
            _f("out_name", "输出文件名", ph="留空自动命名，如 结题材料汇编"),
            _f("ranges", "拆分页码范围（可选）", ph="留空按每份 N 页拆分；也可写 1-5,7,9-12"),
            _f("chunk", "每份页数", "number", value="1"),
        ]

    if key == "achievement_export":
        years, types = [], []
        for a in store.list("achievements"):
            y = str(a.get("date") or "")[:4]
            if y and y not in years:
                years.append(y)
            if a.get("type") and a["type"] not in types:
                types.append(a["type"])
        years.sort(reverse=True)
        return [
            _f("year", "年度", "select", opts=["全部年度"] + years, value="全部年度"),
            _f("type", "成果类型", "select", opts=["全部类型"] + types, value="全部类型"),
            _f("format", "导出格式", "select",
               opts=["CSV（Excel 可直接打开）", "Markdown（报告用）", "JSON（结构化）"],
               value="CSV（Excel 可直接打开）"),
            _f("with_score", "分值列", "select", opts=["含业绩分", "不含业绩分"], value="含业绩分"),
        ]

    if key == "ppt_theme":
        return [
            _f("preset", "样式方案", "select", opts=list(PPT_PRESETS), value="薄荷绿学术（默认）",
               hint="上传 .pptx 且服务端装有 python-pptx 时可直接批量改写"),
            _f("font", "统一中文字体（留空用方案默认）", ph="如 微软雅黑"),
            _f("size", "默认字号（0=不修改）", "number", value="0"),
            _f("_files", "上传课件（可选，.pptx 可多选）", "file", accept=".pptx",
               hint="不上传则仅生成样式规范与检查清单"),
        ]

    if key == "device_lend":
        return [
            _f("action", "登记类型", "select", opts=["借出登记", "归还登记", "超期催还"], value="借出登记"),
            _f("device", "设备名称 / 编号", req=True, ph="如 毫米波雷达开发板 TI-AWR1843"),
            _f("person", "借用人", req=True, ph="如 张伟"),
            _f("contact", "联系方式", ph="手机号或邮箱"),
            _f("borrow_date", "借出日期", "date", value=today()),
            _f("due_date", "应归还日期", "date", value=day_offset(14)),
            _f("back_date", "实际归还日期", "date", ph="归还登记时填写，留空=今天"),
            _f("condition_out", "借出时状态", "select", opts=DEVICE_CONDITIONS, value="完好"),
            _f("condition_back", "归还时状态", "select", opts=[""] + DEVICE_CONDITIONS, value=""),
            _f("overdue_days", "已逾期天数（催还时填写）", "number", value="0"),
            _f("purpose", "使用用途", ph="如 跌倒检测数据采集实验"),
        ]

    return []


def all_specs(store) -> dict:
    """一次性返回 12 个工具的字段规格。"""
    from .tools import TOOL_IMPLS

    return {key: tool_specs(key, store) for key in TOOL_IMPLS}
