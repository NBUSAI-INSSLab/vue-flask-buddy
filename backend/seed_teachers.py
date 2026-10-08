"""多教师种子：管理员 + 5 位教师的账号与各自的工作台数据。

- 首位教师 **江先亮** 复用 ``seed.full_seed()``（完整演示数据）；
- 其余教师按不同规模生成精简数据 —— 项目 / 论文 / 学生 / 教学 / 成果 / 交流
  数量刻意错开，使管理端的横向统计对比有意义；
- 注册新账号时可选「演示数据初始化」（复用完整演示包）或空白工作台。
"""
from __future__ import annotations

import copy

from . import config, seed
from .utils import day_offset as D

# --------------------------------------------------------------------------- #
# 账号
# --------------------------------------------------------------------------- #
ADMIN_USER = {
    "id": "u_admin",
    "username": "admin",
    "password": "admin123",
    "role": config.ROLE_ADMIN,
    "name": "系统管理员",
    "title": "管理员",
    "dept": "计算机科学与技术学院",
    "email": "admin@university.edu.cn",
    "office": "信息楼 A-101",
}

TEACHER_USERS = [
    {
        "id": "u_jiangxl", "username": "jiangxl", "password": "123456",
        "role": config.ROLE_TEACHER, "name": "江先亮", "title": "教授",
        "dept": "计算机科学与技术学院", "email": "jiangxl@university.edu.cn",
        "office": "信息楼 A-513", "mode": "full",
    },
    {
        "id": "u_zhangwei", "username": "zhangwei", "password": "123456",
        "role": config.ROLE_TEACHER, "name": "张伟", "title": "副教授",
        "dept": "计算机科学与技术学院", "email": "zhangwei@university.edu.cn",
        "office": "信息楼 B-402", "mode": "zhangwei",
    },
    {
        "id": "u_limin", "username": "limin", "password": "123456",
        "role": config.ROLE_TEACHER, "name": "李敏", "title": "副教授",
        "dept": "人工智能学院", "email": "limin@university.edu.cn",
        "office": "智能楼 508", "mode": "limin",
    },
    {
        "id": "u_wangqiang", "username": "wangqiang", "password": "123456",
        "role": config.ROLE_TEACHER, "name": "王强", "title": "讲师",
        "dept": "计算机科学与技术学院", "email": "wangqiang@university.edu.cn",
        "office": "信息楼 B-215", "mode": "wangqiang",
    },
    {
        "id": "u_chenjing", "username": "chenjing", "password": "123456",
        "role": config.ROLE_TEACHER, "name": "陈静", "title": "教授",
        "dept": "人工智能学院", "email": "chenjing@university.edu.cn",
        "office": "智能楼 612", "mode": "chenjing",
    },
]

TEACHER_BY_ID = {t["id"]: t for t in TEACHER_USERS}


# --------------------------------------------------------------------------- #
# 小工具：快速构造日程 / 待办
# --------------------------------------------------------------------------- #
def _ev(prefix, i, title, kind, off, start, end, loc, note="", done=False):
    return {"id": f"{prefix}e{i}", "title": title, "type": kind, "date": D(off),
            "start": start, "end": end, "location": loc, "note": note, "done": done}


def _td(prefix, i, title, due_off, priority="mid", tag="", done=False):
    return {"id": f"{prefix}t{i}", "title": title, "due": D(due_off),
            "priority": priority, "done": done, "tag": tag}


def _pack(profile, **colls) -> dict:
    """按集合打包一份完整工作台数据（缺省集合为空，工具清单统一）。"""
    data = {c: [] for c in config.COLLECTIONS}
    data.update({k: v for k, v in colls.items() if k in config.COLLECTIONS})
    data["profile"] = dict(profile)
    data["tools"] = copy.deepcopy(seed.TOOLS)
    data["tools"] = [dict(t, freq=0) for t in data["tools"]]
    data["tool_runs"] = []
    # 常用网站是全校通用的入口清单，任何工作台（含空白工作台）都带上
    data["links"] = [dict(x) for x in seed.LINKS]
    return data


def empty_seed(profile: dict) -> dict:
    """空白工作台（仅保留工具清单）。"""
    return _pack(profile)


def demo_seed(profile: dict) -> dict:
    """标准演示数据（复用完整演示包，仅替换个人信息）。"""
    data = seed.full_seed()
    data["profile"] = dict(profile)
    data["tool_runs"] = []
    return data


# --------------------------------------------------------------------------- #
# 张伟：副教授 · 物联网与边缘智能（3 项目 / 4 文献 / 3 学生 / 3 教学 / 5 成果 / 3 交流）
# --------------------------------------------------------------------------- #
def _zhangwei() -> dict:
    p = {"name": "张伟", "title": "副教授", "dept": "计算机科学与技术学院",
         "email": "zhangwei@university.edu.cn", "office": "信息楼 B-402"}
    projects = [
        {"id": "zwp1", "name": "面向智慧园区的低功耗物联网感知节点协同调度研究",
         "code": "ZJNSF-LY24F020015", "type": "浙江省自然科学基金探索项目", "role": "主持",
         "funding": "18", "startDate": "2024-01-01", "deadline": D(120), "status": "在研",
         "progress": 62, "desc": "研究 LoRa / BLE 混合组网下的节点休眠—唤醒协同调度策略，降低园区感知网络能耗并提升数据时效性。",
         "phases": [
             {"name": "组网方案与仿真平台搭建", "dueDate": "2024-09-30", "done": True},
             {"name": "协同调度算法设计", "dueDate": "2025-12-31", "done": True},
             {"name": "园区实测与能效评估", "dueDate": D(120), "done": False, "active": True},
         ],
         "outcomes": [{"type": "期刊论文", "title": "LoRa/BLE 混合组网下的能耗感知调度", "status": "审稿中", "date": D(-30)}]},
        {"id": "zwp2", "name": "工业现场边缘计算网关的实时任务卸载方法",
         "code": "HZ-KJ2025-118", "type": "横向课题", "role": "主持",
         "funding": "32", "startDate": "2025-03-01", "deadline": D(300), "status": "在研",
         "progress": 41, "desc": "面向某汽车零部件产线，研究边缘网关与云端之间的任务卸载与模型增量更新机制。",
         "phases": [
             {"name": "产线需求调研与数据采集", "dueDate": "2025-08-31", "done": True},
             {"name": "卸载策略原型实现", "dueDate": D(60), "done": False, "active": True},
             {"name": "现场部署与验收", "dueDate": D(300), "done": False},
         ],
         "outcomes": []},
        {"id": "zwp3", "name": "面向校园能耗监测的物联网数据中台建设",
         "code": "XQ-2023-072", "type": "校级重点项目", "role": "主持",
         "funding": "12", "startDate": "2023-06-01", "deadline": D(-40), "status": "验收中",
         "progress": 95, "desc": "建设覆盖 6 栋教学楼的能耗监测数据中台，支撑用能分析与节能策略验证。",
         "phases": [
             {"name": "数据采集与清洗", "dueDate": "2024-06-30", "done": True},
             {"name": "中台服务与可视化", "dueDate": "2025-06-30", "done": True},
             {"name": "结题验收", "dueDate": D(-40), "done": False, "active": True},
         ],
         "outcomes": [{"type": "软件著作权", "title": "校园能耗监测数据中台软件", "status": "已登记", "date": "2025-05-18"}]},
    ]
    literature = [
        {"id": "zwl1", "title": "Energy-Efficient Scheduling for LPWAN: A Survey",
         "authors": "Raza U., Kulkarni P., Sooriyabandara M.", "journal": "IEEE Communications Surveys & Tutorials",
         "year": "2022", "doi": "10.1109/COMST.2021.3125526", "tags": ["LPWAN", "能耗优化"],
         "status": "已读", "rating": 5, "addedDate": D(-80), "direction": "物联网",
         "note": "系统梳理了 LPWAN 的能耗模型与调度策略分类，其中 duty-cycle 协同部分对 zwp1 的休眠—唤醒设计直接可用。"},
        {"id": "zwl2", "title": "Edge Computing for Industrial IoT: Task Offloading and Resource Allocation",
         "authors": "Zhou Z., Chen X., Li E.", "journal": "IEEE Internet of Things Journal",
         "year": "2023", "doi": "10.1109/JIOT.2023.3245669", "tags": ["边缘计算", "任务卸载"],
         "status": "在读", "rating": 4, "addedDate": D(-42), "direction": "边缘计算",
         "note": "提出以时延—能耗联合代价为目标的两阶段卸载框架，可作为 zwp2 的对照方法（baseline）。"},
        {"id": "zwl3", "title": "TinyML: Machine Learning with TensorFlow Lite on Arduino",
         "authors": "Warden P., Situnayake D.", "journal": "O'Reilly Media",
         "year": "2020", "doi": "", "tags": ["TinyML", "端侧推理"],
         "status": "已读", "rating": 4, "addedDate": D(-150), "direction": "边缘计算",
         "note": "端侧模型部署的工程实践手册，适合作为学生入门材料与节点侧推理的选型参考。"},
        {"id": "zwl4", "title": "Digital Twin for Smart Campus Energy Management",
         "authors": "Liu Q., Wang Y.", "journal": "Applied Energy",
         "year": "2024", "doi": "10.1016/j.apenergy.2024.122884", "tags": ["数字孪生", "校园能耗"],
         "status": "未读", "rating": 0, "addedDate": D(-9), "direction": "物联网",
         "note": "待读：数字孪生在中台项目结题材料中可作为展望方向引用。"},
    ]
    students = [
        {"id": "zws1", "name": "刘洋", "degree": "硕士", "grade": "2024 级", "direction": "物联网与边缘计算",
         "email": "liuyang24@university.edu.cn", "thesisTitle": "面向园区的低功耗感知节点协同调度方法研究",
         "stage": "中期检查", "progress": 63, "nextMeeting": D(3),
         "milestones": [
             {"name": "开题报告", "date": "2025-05-18", "done": True},
             {"name": "调度算法仿真", "date": "2025-11-30", "done": True},
             {"name": "园区实测", "date": D(75), "done": False, "active": True},
             {"name": "学位论文答辩", "date": D(320), "done": False},
         ],
         "logs": [
             {"date": D(-6), "type": "组会", "content": "汇报调度算法在 64 节点拓扑下的能耗对比结果，已优于基线 18%；建议补充节点失效场景的鲁棒性实验。"},
             {"date": D(-20), "type": "个别指导", "content": "梳理小论文结构，确定投《物联网学报》并商定投稿时间节点。"},
         ]},
        {"id": "zws2", "name": "赵蕾", "degree": "硕士", "grade": "2025 级", "direction": "边缘智能",
         "email": "zhaolei25@university.edu.cn", "thesisTitle": "边缘网关实时任务卸载策略研究",
         "stage": "文献综述", "progress": 34, "nextMeeting": D(5),
         "milestones": [
             {"name": "文献综述", "date": D(40), "done": False, "active": True},
             {"name": "开题报告", "date": D(110), "done": False},
             {"name": "学位论文答辩", "date": D(600), "done": False},
         ],
         "logs": [{"date": D(-13), "type": "个别指导", "content": "确认以「时延约束下的能耗最小化」为切入点，布置 8 篇精读文献并约定两周后汇报。"}]},
        {"id": "zws3", "name": "孙浩", "degree": "博士", "grade": "2023 级", "direction": "边缘计算",
         "email": "sunhao23@university.edu.cn", "thesisTitle": "边云协同下的模型增量更新与任务调度联合优化",
         "stage": "论文撰写", "progress": 78, "nextMeeting": D(2),
         "milestones": [
             {"name": "开题报告", "date": "2024-06-20", "done": True},
             {"name": "中期检查", "date": "2025-09-15", "done": True},
             {"name": "期刊论文投稿", "date": D(30), "done": False, "active": True},
             {"name": "学位论文答辩", "date": D(420), "done": False},
         ],
         "logs": [{"date": D(-4), "type": "组会", "content": "论文第 3 章实验已补齐消融，建议增加与联邦学习基线的对比，预计两周内完成初稿。"}]},
    ]
    teachings = [
        {"id": "zwg1", "name": "物联网技术导论", "code": "CS412", "semester": "2026 秋",
         "students": 62, "hours": "48", "type": "本科生专业课", "stage": "进行中",
         "syllabusDone": 4, "syllabusTotal": 8, "examType": "课程设计 + 平时作业",
         "evalScore": "4.58 / 5.0",
         "tasks": [{"name": "第 05 讲课件定稿", "due": D(6), "done": False},
                   {"name": "实验一指导书更新", "due": D(-3), "done": True},
                   {"name": "课程设计选题发布", "due": D(18), "done": False}],
         "note": "本学期加入 LoRa 实测环节，需提前申请实验室设备。"},
        {"id": "zwg2", "name": "边缘计算与云协同", "code": "CS518", "semester": "2026 秋",
         "students": 34, "hours": "32", "type": "研究生学位课", "stage": "进行中",
         "syllabusDone": 3, "syllabusTotal": 6, "examType": "课程论文",
         "evalScore": "4.66 / 5.0",
         "tasks": [{"name": "研讨课分组名单", "due": D(4), "done": False}],
         "note": "以顶会论文研讨为主，已安排 5 组学生轮讲。"},
        {"id": "zwg3", "name": "本科毕业设计指导", "code": "BD2026", "semester": "2026 春",
         "students": 8, "hours": "24", "type": "毕业设计指导", "stage": "选题阶段",
         "syllabusDone": 1, "syllabusTotal": 4, "examType": "过程考核 + 答辩",
         "evalScore": "—",
         "tasks": [{"name": "选题清单确认", "due": D(9), "done": False}],
         "note": "8 名学生均围绕物联网 / 边缘计算方向选题。"},
    ]
    achievements = [
        {"id": "zwa1", "title": "LoRa 与 BLE 混合组网的低能耗路由协议设计", "type": "期刊论文",
         "level": "EI 期刊", "authors": "张伟, 刘洋", "role": "第一作者", "venue": "电子学报",
         "date": D(-95), "status": "已发表", "score": 4.0, "projectId": "zwp1", "doi": "",
         "note": "提出跨协议路由度量，实测网络生存期提升 23%。"},
        {"id": "zwa2", "title": "面向工业产线的边缘网关任务卸载方法", "type": "发明专利",
         "level": "发明专利", "authors": "张伟, 赵蕾", "role": "第一发明人", "venue": "国家知识产权局",
         "date": D(-160), "status": "已授权", "score": 5.0, "projectId": "zwp2", "doi": "",
         "note": "已授权，专利号 ZL2024 1 0xxxxxx.x。"},
        {"id": "zwa3", "title": "校园能耗监测数据中台软件 V1.0", "type": "软件著作权",
         "level": "软著", "authors": "张伟, 孙浩", "role": "第一完成人", "venue": "中国版权保护中心",
         "date": "2025-05-18", "status": "已登记", "score": 2.0, "projectId": "zwp3", "doi": "",
         "note": "登记号 2025SR0xxxxxx。"},
        {"id": "zwa4", "title": "基于能耗感知的物联网节点调度方法", "type": "期刊论文",
         "level": "SCI 三区", "authors": "张伟, 刘洋, 赵蕾", "role": "通讯作者", "venue": "Sensors",
         "date": D(-25), "status": "审稿中", "score": 3.0, "projectId": "zwp1", "doi": "",
         "note": "一审意见已回，处于复审阶段。"},
        {"id": "zwa5", "title": "省高校教师教学创新大赛三等奖", "type": "科技奖励",
         "level": "省部级二等奖", "authors": "张伟", "role": "第一完成人", "venue": "浙江省教育厅",
         "date": D(-210), "status": "已获奖", "score": 4.0, "projectId": "", "doi": "",
         "note": "《物联网技术导论》课程改革成果。"},
    ]
    exchanges = [
        {"id": "zwx1", "title": "中国物联网大会（CIoT 2026）", "kind": "学术会议", "role": "分会场报告",
         "organizer": "中国电子学会 · 物联网分会", "location": "杭州国际博览中心", "level": "国内",
         "start": D(35), "end": D(37), "status": "已确认", "funding": "注册费 1200 元（zwp1 支出）",
         "topic": "报告「低功耗感知节点的协同调度实践」，时长 15 分钟。", "note": "需提前提交报告 PPT 与摘要。",
         "travel": "高铁往返", "participants": ["张伟", "刘洋"]},
        {"id": "zwx2", "title": "IEEE EDGE 2026 边缘计算国际会议", "kind": "学术会议", "role": "论文宣讲",
         "organizer": "IEEE Computer Society", "location": "线上（Zoom）", "level": "国际",
         "start": D(-60), "end": D(-58), "status": "已结束", "funding": "注册费 3200 元（zwp2 支出）",
         "topic": "宣讲论文「Task Offloading for Industrial Edge Gateways」。", "note": "",
         "travel": "线上参加", "participants": ["张伟"]},
        {"id": "zwx3", "title": "国家自然科学基金面上项目函评", "kind": "基金评审", "role": "评审专家",
         "organizer": "国家自然科学基金委员会", "location": "线上评审系统", "level": "国家级",
         "start": D(-20), "end": D(-10), "status": "已结束", "funding": "",
         "topic": "完成 7 份面上项目申请书的通讯评审。", "note": "", "travel": "", "participants": ["张伟"]},
    ]
    developments = [
        {"id": "zwd1", "title": "副教授聘期考核（2024-2027）", "category": "职称晋升", "status": "进行中",
         "start": "2024-01-01", "deadline": D(430), "progress": 52,
         "target": "聘期内主持省部级以上项目 1 项、发表高水平论文 3 篇、授权发明专利 1 项",
         "current": "主持省基金 1 项；论文 2 篇（1 篇在审）；发明专利已授权 1 项",
         "note": "建议每年度自评一次并留档佐证材料。",
         "metrics": [{"name": "主持省部级以上项目", "target": 1, "current": 1, "unit": "项"},
                     {"name": "高水平论文", "target": 3, "current": 2, "unit": "篇"},
                     {"name": "授权发明专利", "target": 1, "current": 1, "unit": "项"}]},
        {"id": "zwd2", "title": "青年教师企业实践锻炼", "category": "能力提升", "status": "已完成",
         "start": "2025-07-01", "deadline": "2025-12-31", "progress": 100,
         "target": "赴合作企业实践 6 个月，参与真实产线项目", "current": "已完成 6 个月实践并提交总结报告",
         "note": "实践成果已转化为横向课题 zwp2。",
         "metrics": [{"name": "实践月数", "target": 6, "current": 6, "unit": "月"}]},
    ]
    courses = [
        {"id": "zwc1", "name": "物联网技术导论", "code": "CS412", "semester": "2026 秋",
         "students": 62, "credits": 3.0, "hours": 48,
         "color": "linear-gradient(135deg,#1d6fd0,#3aa0e8)",
         "intro": "面向本科生的物联网入门课程，覆盖感知层、网络层、平台层与应用层，强调动手实验。",
         "syllabus": [
             {"chapter": "第 1 章 物联网概述", "hours": "4", "type": "讲授", "point": "体系架构、应用场景"},
             {"chapter": "第 2 章 感知与识别技术", "hours": "8", "type": "讲授 + 实验", "point": "传感器、RFID"},
             {"chapter": "第 3 章 低功耗广域网", "hours": "10", "type": "讲授 + 实验", "point": "LoRa、NB-IoT"},
             {"chapter": "第 4 章 物联网平台与数据", "hours": "8", "type": "讲授", "point": "云平台、时序数据"},
             {"chapter": "第 5 章 综合应用设计", "hours": "10", "type": "课程设计", "point": "智慧园区案例"},
         ],
         "resources": [{"name": "实验指导书 v2.pdf", "type": "PDF", "size": "1.8 MB"},
                       {"name": "LoRa 实验源码包.zip", "type": "ZIP", "size": "6.4 MB"}]},
    ]
    events = [
        _ev("zw", 1, "课题组例会", "组会", 2, "14:00", "16:00", "信息楼 B-402", "汇报园区实测进展"),
        _ev("zw", 2, "《物联网技术导论》第 05 讲", "上课", 1, "10:00", "11:40", "一教 305"),
        _ev("zw", 3, "与产线工程师对接网关接口", "会议", 5, "09:30", "11:00", "线上", "确认数据协议"),
        _ev("zw", 4, "研究生中期检查答辩", "答辩", 12, "13:30", "17:00", "信息楼 A-201"),
    ]
    todos = [
        _td("zw", 1, "提交省基金年度进展报告", 14, "high", "科研项目"),
        _td("zw", 2, "批改物联网课程实验报告", 4, "mid", "教学", True),
        _td("zw", 3, "回复 Sensors 期刊审稿意见", 8, "high", "成果管理"),
    ]
    return _pack(p, projects=projects, literature=literature, students=students,
                 teachings=teachings, achievements=achievements, exchanges=exchanges,
                 developments=developments, courses=courses, events=events, todos=todos)


# --------------------------------------------------------------------------- #
# 李敏：副教授 · 计算机视觉与工业检测（2 项目 / 3 文献 / 2 学生 / 2 教学 / 4 成果 / 2 交流）
# --------------------------------------------------------------------------- #
def _limin() -> dict:
    p = {"name": "李敏", "title": "副教授", "dept": "人工智能学院",
         "email": "limin@university.edu.cn", "office": "智能楼 508"}
    projects = [
        {"id": "lmp1", "name": "复杂光照条件下的工业零件表面缺陷检测方法研究",
         "code": "NSFC-62306124", "type": "国家自然科学基金青年项目", "role": "主持",
         "funding": "30", "startDate": "2024-01-01", "deadline": D(210), "status": "在研",
         "progress": 67, "desc": "针对金属零件高反光、低对比度的成像特点，研究光照归一化与多尺度缺陷分割方法，并在产线部署验证。",
         "phases": [
             {"name": "缺陷数据集构建", "dueDate": "2024-10-31", "done": True},
             {"name": "分割模型设计与训练", "dueDate": "2025-12-31", "done": True},
             {"name": "产线部署与鲁棒性验证", "dueDate": D(210), "done": False, "active": True},
         ],
         "outcomes": [{"type": "期刊论文", "title": "光照归一化驱动的金属表面缺陷分割", "status": "已录用", "date": D(-15)}]},
        {"id": "lmp2", "name": "面向智能制造的视觉检测算法平台",
         "code": "HZ-2025-266", "type": "横向课题", "role": "主持",
         "funding": "45", "startDate": "2025-09-01", "deadline": D(420), "status": "在研",
         "progress": 28, "desc": "为制造企业搭建可配置的视觉检测算法平台，支持缺陷标注、模型训练与在线推理一体化。",
         "phases": [
             {"name": "需求分析与架构设计", "dueDate": "2025-12-31", "done": True},
             {"name": "平台核心模块开发", "dueDate": D(180), "done": False, "active": True},
             {"name": "试点产线联调", "dueDate": D(420), "done": False},
         ],
         "outcomes": []},
    ]
    literature = [
        {"id": "lml1", "title": "Segmentation-Based Deep Learning for Surface Defect Detection: A Review",
         "authors": "Tang B., Chen L., Sun W.", "journal": "IEEE Transactions on Instrumentation and Measurement",
         "year": "2023", "doi": "10.1109/TIM.2023.3256541", "tags": ["缺陷检测", "语义分割"],
         "status": "已读", "rating": 5, "addedDate": D(-120), "direction": "工业视觉",
         "note": "综述了分割类缺陷检测的骨干网络与损失设计，其中对类别极不平衡的处理方式直接用于 lmp1。"},
        {"id": "lml2", "title": "Retinexformer: One-stage Retinex-based Transformer for Low-light Enhancement",
         "authors": "Cai Y., Bian H., Lin J.", "journal": "ICCV", "year": "2023", "doi": "",
         "tags": ["低光照增强", "Transformer"], "status": "已读", "rating": 4, "addedDate": D(-70),
         "direction": "计算机视觉",
         "note": "把 Retinex 分解与 Transformer 结合，可作为高反光场景下的预处理模块。"},
        {"id": "lml3", "title": "Anomaly Detection in Manufacturing via Normalizing Flows",
         "authors": "Rudolph M., Wandt B., Rosenhahn B.", "journal": "WACV", "year": "2022", "doi": "",
         "tags": ["异常检测", "无监督"], "status": "在读", "rating": 3, "addedDate": D(-18),
         "direction": "工业视觉", "note": "待评估：无监督路线能否缓解缺陷样本稀缺问题。"},
    ]
    students = [
        {"id": "lms1", "name": "周琳", "degree": "硕士", "grade": "2024 级", "direction": "工业视觉检测",
         "email": "zhoulin24@university.edu.cn", "thesisTitle": "复杂光照下的金属表面缺陷分割方法研究",
         "stage": "中期检查", "progress": 58, "nextMeeting": D(4),
         "milestones": [
             {"name": "开题报告", "date": "2025-05-22", "done": True},
             {"name": "数据集与标注规范", "date": "2025-11-10", "done": True},
             {"name": "模型对比实验", "date": D(60), "done": False, "active": True},
             {"name": "学位论文答辩", "date": D(300), "done": False},
         ],
         "logs": [{"date": D(-7), "type": "组会", "content": "分割模型在低对比度样本上召回偏低，建议引入 focal loss 并扩充困难样本。"}]},
        {"id": "lms2", "name": "吴桐", "degree": "硕士", "grade": "2025 级", "direction": "异常检测",
         "email": "wutong25@university.edu.cn", "thesisTitle": "基于无监督异常检测的零件缺陷识别",
         "stage": "文献综述", "progress": 26, "nextMeeting": D(6),
         "milestones": [
             {"name": "文献综述", "date": D(55), "done": False, "active": True},
             {"name": "开题报告", "date": D(130), "done": False},
             {"name": "学位论文答辩", "date": D(600), "done": False},
         ],
         "logs": [{"date": D(-15), "type": "个别指导", "content": "确定以 MVTec AD 数据集为基准，先复现 PatchCore 再改进。"}]},
    ]
    teachings = [
        {"id": "lmg1", "name": "数字图像处理", "code": "AI302", "semester": "2026 秋",
         "students": 58, "hours": "48", "type": "本科生专业课", "stage": "进行中",
         "syllabusDone": 5, "syllabusTotal": 8, "examType": "闭卷考试 + 编程作业",
         "evalScore": "4.71 / 5.0",
         "tasks": [{"name": "第 06 讲课件定稿", "due": D(5), "done": False},
                   {"name": "作业三批改", "due": D(11), "done": False}],
         "note": "本学期增加 PyTorch 实现环节，学生反馈较好。"},
        {"id": "lmg2", "name": "计算机视觉", "code": "AI506", "semester": "2026 秋",
         "students": 41, "hours": "32", "type": "研究生学位课", "stage": "备课中",
         "syllabusDone": 2, "syllabusTotal": 6, "examType": "课程项目 + 答辩",
         "evalScore": "4.80 / 5.0",
         "tasks": [{"name": "课程项目选题设计", "due": D(16), "done": False}],
         "note": "以「检测/分割」为主线组织课程项目。"},
    ]
    achievements = [
        {"id": "lma1", "title": "光照归一化的金属表面缺陷分割网络", "type": "期刊论文",
         "level": "SCI 二区", "authors": "李敏, 周琳", "role": "第一作者",
         "venue": "IEEE Transactions on Instrumentation and Measurement", "date": D(-15),
         "status": "已录用", "score": 6.0, "projectId": "lmp1", "doi": "",
         "note": "在自建数据集上 mIoU 达 0.842。"},
        {"id": "lma2", "title": "一种高反光零件表面缺陷的成像增强装置", "type": "发明专利",
         "level": "发明专利", "authors": "李敏, 吴桐", "role": "第一发明人", "venue": "国家知识产权局",
         "date": D(-45), "status": "申报中", "score": 0.0, "projectId": "lmp1", "doi": "",
         "note": "已提交申请，处于初审阶段。"},
        {"id": "lma3", "title": "智能视觉检测算法平台软件 V1.0", "type": "软件著作权",
         "level": "软著", "authors": "李敏, 周琳", "role": "第一完成人", "venue": "中国版权保护中心",
         "date": D(-200), "status": "已登记", "score": 2.0, "projectId": "lmp2", "doi": "",
         "note": "登记号 2026SR0xxxxxx。"},
        {"id": "lma4", "title": "基于多尺度特征融合的微小缺陷检测方法", "type": "期刊论文",
         "level": "EI 期刊", "authors": "李敏, 吴桐", "role": "通讯作者", "venue": "光学精密工程",
         "date": "2025-03-10", "status": "已发表", "score": 3.0, "projectId": "lmp1", "doi": "",
         "note": "被引 6 次。"},
    ]
    exchanges = [
        {"id": "lmx1", "title": "中国机器视觉技术与应用大会", "kind": "学术会议", "role": "特邀报告",
         "organizer": "中国图象图形学学会", "location": "苏州国际博览中心", "level": "国内",
         "start": D(50), "end": D(52), "status": "已确认", "funding": "注册费 1500 元（lmp1 支出）",
         "topic": "分享工业缺陷检测的工程落地经验，时长 25 分钟。", "note": "需准备工业案例素材。",
         "travel": "高铁往返", "participants": ["李敏"]},
        {"id": "lmx2", "title": "CVPR 2026 论文审稿", "kind": "期刊审稿", "role": "审稿人",
         "organizer": "CVPR Program Committee", "location": "线上", "level": "国际",
         "start": D(-90), "end": D(-70), "status": "已结束", "funding": "",
         "topic": "完成 4 篇投稿论文的评审。", "note": "", "travel": "", "participants": ["李敏"]},
    ]
    developments = [
        {"id": "lmd1", "title": "副教授聘期考核（2025-2028）", "category": "职称晋升", "status": "进行中",
         "start": "2025-01-01", "deadline": D(700), "progress": 38,
         "target": "主持国家级项目 1 项、发表高水平论文 3 篇、授权发明专利 2 项",
         "current": "主持国基金青年项目 1 项；论文 2 篇（1 篇已录用）；发明专利 1 项申报中",
         "note": "青年项目结题后可筹备面上项目申报。",
         "metrics": [{"name": "主持国家级项目", "target": 1, "current": 1, "unit": "项"},
                     {"name": "高水平论文", "target": 3, "current": 2, "unit": "篇"},
                     {"name": "授权发明专利", "target": 2, "current": 0, "unit": "项"}]},
        {"id": "lmd2", "title": "指导学生参加中国大学生计算机设计大赛", "category": "教学能力", "status": "进行中",
         "start": D(-60), "deadline": D(90), "progress": 45,
         "target": "指导 1 支队伍进入国赛并获奖", "current": "校赛已出线，正在完善作品",
         "note": "作品方向为零件缺陷检测系统。",
         "metrics": [{"name": "参赛队伍", "target": 1, "current": 1, "unit": "支"}]},
        {"id": "lmd3", "title": "双语教学能力提升计划", "category": "能力提升", "status": "进行中",
         "start": D(-30), "deadline": D(200), "progress": 20,
         "target": "完成《计算机视觉》双语课程建设并开设一轮", "current": "已完成英文讲义前 3 章初稿",
         "note": "", "metrics": [{"name": "讲义章节", "target": 6, "current": 3, "unit": "章"}]},
    ]
    courses = [
        {"id": "lmc1", "name": "数字图像处理", "code": "AI302", "semester": "2026 秋",
         "students": 58, "credits": 3.0, "hours": 48,
         "color": "linear-gradient(135deg,#7c3aed,#a78bfa)",
         "intro": "讲授数字图像的获取、变换、增强、分割与识别，强调算法实现与工程应用。",
         "syllabus": [
             {"chapter": "第 1 章 数字图像基础", "hours": "6", "type": "讲授", "point": "成像模型、采样量化"},
             {"chapter": "第 2 章 空域与频域增强", "hours": "10", "type": "讲授 + 实验", "point": "直方图、滤波"},
             {"chapter": "第 3 章 图像分割", "hours": "12", "type": "讲授 + 实验", "point": "阈值、边缘、区域"},
             {"chapter": "第 4 章 特征与识别", "hours": "10", "type": "讲授", "point": "SIFT、CNN 基础"},
             {"chapter": "第 5 章 综合项目", "hours": "10", "type": "项目实践", "point": "缺陷检测小系统"},
         ],
         "resources": [{"name": "课程实验讲义.pdf", "type": "PDF", "size": "2.6 MB"}]},
    ]
    events = [
        _ev("lm", 1, "课题组例会", "组会", 3, "15:00", "17:00", "智能楼 508"),
        _ev("lm", 2, "《数字图像处理》第 06 讲", "上课", 1, "08:00", "09:40", "二教 210"),
        _ev("lm", 3, "企业视觉平台需求评审", "会议", 6, "14:00", "16:00", "线上"),
    ]
    todos = [
        _td("lm", 1, "回复国基金青年项目中期检查材料", 10, "high", "科研项目"),
        _td("lm", 2, "提交 CVPR 审稿意见", 5, "high", "学术交流"),
        _td("lm", 3, "整理缺陷数据集标注规范", 12, "mid", "科研项目"),
    ]
    return _pack(p, projects=projects, literature=literature, students=students,
                 teachings=teachings, achievements=achievements, exchanges=exchanges,
                 developments=developments, courses=courses, events=events, todos=todos)


# --------------------------------------------------------------------------- #
# 王强：讲师 · 网络与云计算（1 项目 / 2 文献 / 1 学生 / 2 教学 / 2 成果 / 1 交流）
# --------------------------------------------------------------------------- #
def _wangqiang() -> dict:
    p = {"name": "王强", "title": "讲师", "dept": "计算机科学与技术学院",
         "email": "wangqiang@university.edu.cn", "office": "信息楼 B-215"}
    projects = [
        {"id": "wqp1", "name": "数据中心网络拥塞控制算法的性能建模与优化",
         "code": "XQ-2025-031", "type": "校级青年基金", "role": "主持",
         "funding": "6", "startDate": "2025-01-01", "deadline": D(260), "status": "在研",
         "progress": 46, "desc": "围绕 BBRv3 在浅缓冲交换机上的公平性问题，构建性能模型并提出自适应参数调整策略。",
         "phases": [
             {"name": "仿真环境搭建", "dueDate": "2025-06-30", "done": True},
             {"name": "算法建模与分析", "dueDate": D(90), "done": False, "active": True},
             {"name": "论文撰写与投稿", "dueDate": D(260), "done": False},
         ],
         "outcomes": []},
    ]
    literature = [
        {"id": "wql1", "title": "BBR v3: An Improved Congestion Control Algorithm",
         "authors": "Cardwell N., Cheng Y., et al.", "journal": "IETF Draft",
         "year": "2024", "doi": "", "tags": ["拥塞控制", "BBR"], "status": "在读",
         "rating": 5, "addedDate": D(-35), "direction": "计算机网络",
         "note": "重点看浅缓冲场景下的 pacing gain 调整策略，与 wqp1 的建模目标一致。"},
        {"id": "wql2", "title": "Fairness in Datacenter Congestion Control: Measurement Study",
         "authors": "Kumar G., Dukkipati N.", "journal": "ACM SIGCOMM", "year": "2023", "doi": "",
         "tags": ["公平性", "数据中心网络"], "status": "未读", "rating": 0, "addedDate": D(-12),
         "direction": "计算机网络", "note": "待读：为公平性度量指标提供参考。"},
    ]
    students = [
        {"id": "wqs1", "name": "郑凯", "degree": "硕士", "grade": "2025 级", "direction": "数据中心网络",
         "email": "zhengkai25@university.edu.cn", "thesisTitle": "数据中心网络的拥塞控制公平性研究",
         "stage": "文献综述", "progress": 30, "nextMeeting": D(7),
         "milestones": [
             {"name": "文献综述", "date": D(70), "done": False, "active": True},
             {"name": "开题报告", "date": D(150), "done": False},
             {"name": "学位论文答辩", "date": D(620), "done": False},
         ],
         "logs": [{"date": D(-9), "type": "个别指导", "content": "熟悉 ns-3 仿真环境，先用 BBRv3 复现经典公平性实验。"}]},
    ]
    teachings = [
        {"id": "wqg1", "name": "计算机网络", "code": "CS301", "semester": "2026 秋",
         "students": 74, "hours": "56", "type": "本科生专业课", "stage": "进行中",
         "syllabusDone": 4, "syllabusTotal": 8, "examType": "闭卷考试 + 实验",
         "evalScore": "4.42 / 5.0",
         "tasks": [{"name": "第 05 讲课件定稿", "due": D(3), "done": False},
                   {"name": "实验二批改", "due": D(13), "done": False}],
         "note": "沿用课程组统一大纲，重点补充拥塞控制实测案例。"},
        {"id": "wqg2", "name": "云计算技术基础", "code": "CS405", "semester": "2026 秋",
         "students": 45, "hours": "40", "type": "本科生专业课", "stage": "备课中",
         "syllabusDone": 1, "syllabusTotal": 6, "examType": "课程作业 + 上机",
         "evalScore": "—",
         "tasks": [{"name": "虚拟化实验环境搭建", "due": D(20), "done": False}],
         "note": "新开课程，需完善实验手册。"},
    ]
    achievements = [
        {"id": "wqa1", "title": "数据中心网络拥塞控制性能评测软件 V1.0", "type": "软件著作权",
         "level": "软著", "authors": "王强, 郑凯", "role": "第一完成人", "venue": "中国版权保护中心",
         "date": D(-130), "status": "已登记", "score": 2.0, "projectId": "wqp1", "doi": "",
         "note": "登记号 2026SR0xxxxxx。"},
        {"id": "wqa2", "title": "面向浅缓冲交换机的拥塞窗口自适应方法", "type": "发明专利",
         "level": "发明专利", "authors": "王强, 郑凯", "role": "第一发明人", "venue": "国家知识产权局",
         "date": D(-20), "status": "撰写中", "score": 0.0, "projectId": "wqp1", "doi": "",
         "note": "技术交底书已完成，拟本季度提交。"},
    ]
    exchanges = [
        {"id": "wqx1", "title": "中国计算机网络大会", "kind": "学术会议", "role": "参会学习",
         "organizer": "中国计算机学会 · 网络与数据通信专委", "location": "成都", "level": "国内",
         "start": D(-40), "end": D(-38), "status": "已结束", "funding": "注册费 900 元（wqp1 支出）",
         "topic": "学习数据中心网络与可编程网络最新进展。", "note": "", "travel": "高铁往返",
         "participants": ["王强"]},
    ]
    developments = [
        {"id": "wqd1", "title": "讲师职称晋升准备（目标副教授）", "category": "职称晋升", "status": "进行中",
         "start": "2025-09-01", "deadline": D(800), "progress": 22,
         "target": "主持省部级以上项目 1 项、发表核心期刊论文 2 篇、完成教学工作量考核",
         "current": "主持校级项目 1 项；软著 1 项；论文在研",
         "note": "优先补齐高水平论文短板。",
         "metrics": [{"name": "主持省部级以上项目", "target": 1, "current": 0, "unit": "项"},
                     {"name": "核心期刊论文", "target": 2, "current": 0, "unit": "篇"}]},
    ]
    courses = [
        {"id": "wqc1", "name": "计算机网络", "code": "CS301", "semester": "2026 秋",
         "students": 74, "credits": 3.5, "hours": 56,
         "color": "linear-gradient(135deg,#0f766e,#14b8a6)",
         "intro": "专业核心课，覆盖 TCP/IP 协议栈、拥塞控制与网络性能分析。",
         "syllabus": [
             {"chapter": "第 1 章 概述", "hours": "4", "type": "讲授", "point": "体系结构"},
             {"chapter": "第 2 章 应用层", "hours": "6", "type": "讲授", "point": "HTTP/DNS"},
             {"chapter": "第 3 章 运输层", "hours": "12", "type": "讲授 + 实验", "point": "TCP、拥塞控制"},
             {"chapter": "第 4 章 网络层", "hours": "12", "type": "讲授", "point": "IP、路由"},
             {"chapter": "第 5 章 链路层", "hours": "8", "type": "讲授 + 实验", "point": "以太网、交换"},
         ],
         "resources": [{"name": "实验手册.pdf", "type": "PDF", "size": "1.2 MB"}]},
    ]
    events = [
        _ev("wq", 1, "《计算机网络》第 05 讲", "上课", 2, "14:00", "15:40", "三教 108"),
        _ev("wq", 2, "课程组教学研讨会", "会议", 4, "10:00", "11:30", "信息楼 A-201"),
        _ev("wq", 3, "与郑凯讨论仿真进度", "指导", 1, "16:00", "17:00", "信息楼 B-215"),
    ]
    todos = [
        _td("wq", 1, "完成云计算课程实验环境搭建", 18, "mid", "教学"),
        _td("wq", 2, "整理专利技术交底书", 7, "high", "成果管理"),
    ]
    return _pack(p, projects=projects, literature=literature, students=students,
                 teachings=teachings, achievements=achievements, exchanges=exchanges,
                 developments=developments, courses=courses, events=events, todos=todos)


# --------------------------------------------------------------------------- #
# 陈静：教授 · 数据挖掘与教育大数据（3 项目 / 5 文献 / 4 学生 / 3 教学 / 6 成果 / 4 交流）
# --------------------------------------------------------------------------- #
def _chenjing() -> dict:
    p = {"name": "陈静", "title": "教授", "dept": "人工智能学院",
         "email": "chenjing@university.edu.cn", "office": "智能楼 612"}
    projects = [
        {"id": "cjp1", "name": "教育大数据的因果推断与学业预警模型研究",
         "code": "NSFC-62076111", "type": "国家自然科学基金面上项目", "role": "主持",
         "funding": "58", "startDate": "2023-01-01", "deadline": D(-60), "status": "验收中",
         "progress": 92, "desc": "构建面向高校学业数据的因果推断框架，识别可干预因素并输出预警策略。",
         "phases": [
             {"name": "数据治理与特征工程", "dueDate": "2023-12-31", "done": True},
             {"name": "因果模型设计与验证", "dueDate": "2025-06-30", "done": True},
             {"name": "平台化与结题", "dueDate": D(-60), "done": False, "active": True},
         ],
         "outcomes": [{"type": "期刊论文", "title": "基于因果森林的学业风险因素识别", "status": "已发表", "date": D(-150)}]},
        {"id": "cjp2", "name": "面向在线学习的多行为序列建模与推荐",
         "code": "ZJNSF-LZ23F020003", "type": "浙江省自然科学基金重点项目", "role": "主持",
         "funding": "40", "startDate": "2024-01-01", "deadline": D(330), "status": "在研",
         "progress": 55, "desc": "研究学习行为序列的表示学习与可解释推荐，提升在线学习平台的资源匹配效率。",
         "phases": [
             {"name": "行为日志建模", "dueDate": "2024-12-31", "done": True},
             {"name": "推荐模型与可解释性", "dueDate": D(150), "done": False, "active": True},
             {"name": "平台试点", "dueDate": D(330), "done": False},
         ],
         "outcomes": []},
        {"id": "cjp3", "name": "高校教学质量监测数据平台建设",
         "code": "HZ-2024-088", "type": "横向课题", "role": "主持",
         "funding": "66", "startDate": "2024-05-01", "deadline": D(180), "status": "在研",
         "progress": 63, "desc": "为学校教务处建设教学质量监测平台，覆盖课程评价、成绩分布与达成度分析。",
         "phases": [
             {"name": "指标体系设计", "dueDate": "2024-10-31", "done": True},
             {"name": "平台开发", "dueDate": D(60), "done": False, "active": True},
             {"name": "全校推广培训", "dueDate": D(180), "done": False},
         ],
         "outcomes": []},
    ]
    literature = [
        {"id": "cjl1", "title": "Causal Inference in Education: Methods and Applications",
         "authors": "Pearl J., Mackenzie D.", "journal": "Educational Researcher", "year": "2023",
         "doi": "", "tags": ["因果推断", "教育数据"], "status": "已读", "rating": 5,
         "addedDate": D(-200), "direction": "数据挖掘",
         "note": "系统讨论了教育场景下因果识别的假设与敏感性分析，是 cjp1 的方法论基础。"},
        {"id": "cjl2", "title": "Self-Attentive Sequential Recommendation",
         "authors": "Kang W., McAuley J.", "journal": "ICDM", "year": "2018", "doi": "",
         "tags": ["序列推荐", "自注意力"], "status": "已读", "rating": 5, "addedDate": D(-160),
         "direction": "推荐系统", "note": "SASRec 是 cjp2 的 baseline，需注意其长序列处理的开销。"},
        {"id": "cjl3", "title": "Learning Analytics Dashboards: A Systematic Review",
         "authors": "Matcha W., Gašević D.", "journal": "Computers & Education", "year": "2019",
         "doi": "", "tags": ["学习分析", "可视化"], "status": "已读", "rating": 4, "addedDate": D(-120),
         "direction": "教育大数据", "note": "为监测平台的指标呈现提供设计参考。"},
        {"id": "cjl4", "title": "Deep Learning for Educational Data Mining",
         "authors": "Karimi H., et al.", "journal": "IEEE TLT", "year": "2024", "doi": "",
         "tags": ["教育数据挖掘", "深度学习"], "status": "在读", "rating": 3, "addedDate": D(-25),
         "direction": "教育大数据", "note": "待整理：与经典统计方法的对比实验部分。"},
        {"id": "cjl5", "title": "Counterfactual Reasoning for Student Dropout Prediction",
         "authors": "Zhao Y., Li X.", "journal": "LAK", "year": "2024", "doi": "",
         "tags": ["反事实", "退学预测"], "status": "未读", "rating": 0, "addedDate": D(-8),
         "direction": "数据挖掘", "note": "待读：与学业预警主题高度相关。"},
    ]
    students = [
        {"id": "cjs1", "name": "何雪", "degree": "博士", "grade": "2022 级", "direction": "因果推断",
         "email": "hexue22@university.edu.cn", "thesisTitle": "教育场景下的因果效应估计与可解释建模",
         "stage": "论文撰写", "progress": 84, "nextMeeting": D(2),
         "milestones": [
             {"name": "开题报告", "date": "2023-06-15", "done": True},
             {"name": "中期检查", "date": "2024-11-20", "done": True},
             {"name": "期刊论文投稿", "date": D(25), "done": False, "active": True},
             {"name": "学位论文答辩", "date": D(300), "done": False},
         ],
         "logs": [{"date": D(-5), "type": "组会", "content": "因果森林的稳健性实验已完成，建议补充与工具变量法的对比。"}]},
        {"id": "cjs2", "name": "林涛", "degree": "博士", "grade": "2023 级", "direction": "序列推荐",
         "email": "lintao23@university.edu.cn", "thesisTitle": "面向在线学习的多行为序列推荐方法",
         "stage": "中期检查", "progress": 61, "nextMeeting": D(4),
         "milestones": [
             {"name": "开题报告", "date": "2024-06-18", "done": True},
             {"name": "中期检查", "date": D(45), "done": False, "active": True},
             {"name": "学位论文答辩", "date": D(520), "done": False},
         ],
         "logs": [{"date": D(-11), "type": "个别指导", "content": "多行为融合模块已跑通，下一步补消融实验并整理中期材料。"}]},
        {"id": "cjs3", "name": "许晴", "degree": "硕士", "grade": "2024 级", "direction": "教育数据挖掘",
         "email": "xuqing24@university.edu.cn", "thesisTitle": "基于行为序列的学业风险早期识别",
         "stage": "中期检查", "progress": 57, "nextMeeting": D(3),
         "milestones": [
             {"name": "开题报告", "date": "2025-05-25", "done": True},
             {"name": "特征体系构建", "date": "2025-12-05", "done": True},
             {"name": "模型实验", "date": D(50), "done": False, "active": True},
             {"name": "学位论文答辩", "date": D(310), "done": False},
         ],
         "logs": [{"date": D(-8), "type": "组会", "content": "早期识别模型 AUC 0.86，建议引入时序注意力提升可解释性。"}]},
        {"id": "cjs4", "name": "马晓", "degree": "硕士", "grade": "2025 级", "direction": "学习分析",
         "email": "maxiao25@university.edu.cn", "thesisTitle": "学习分析仪表盘的指标设计与效果评估",
         "stage": "文献综述", "progress": 29, "nextMeeting": D(8),
         "milestones": [
             {"name": "文献综述", "date": D(60), "done": False, "active": True},
             {"name": "开题报告", "date": D(140), "done": False},
             {"name": "学位论文答辩", "date": D(610), "done": False},
         ],
         "logs": [{"date": D(-16), "type": "个别指导", "content": "确定以「仪表盘对学习行为的影响」为研究问题，需设计对照实验。"}]},
    ]
    teachings = [
        {"id": "cjg1", "name": "数据挖掘", "code": "AI401", "semester": "2026 秋",
         "students": 66, "hours": "48", "type": "本科生专业课", "stage": "进行中",
         "syllabusDone": 5, "syllabusTotal": 8, "examType": "闭卷考试 + 课程项目",
         "evalScore": "4.75 / 5.0",
         "tasks": [{"name": "第 06 讲课件定稿", "due": D(4), "done": False},
                   {"name": "课程项目中期检查", "due": D(15), "done": False}],
         "note": "课程项目与教育数据实际场景结合，学生参与度高。"},
        {"id": "cjg2", "name": "机器学习", "code": "AI301", "semester": "2026 秋",
         "students": 92, "hours": "56", "type": "本科生基础课", "stage": "进行中",
         "syllabusDone": 4, "syllabusTotal": 10, "examType": "闭卷考试 + 实验",
         "evalScore": "4.63 / 5.0",
         "tasks": [{"name": "实验三批改", "due": D(9), "done": False}],
         "note": "大班教学，需协调 3 名助教完成实验批改。"},
        {"id": "cjg3", "name": "教育数据挖掘专题", "code": "AI607", "semester": "2026 秋",
         "students": 22, "hours": "32", "type": "研究生学位课", "stage": "进行中",
         "syllabusDone": 3, "syllabusTotal": 6, "examType": "课程论文 + 研讨",
         "evalScore": "4.85 / 5.0",
         "tasks": [{"name": "研讨主题分配", "due": D(7), "done": False}],
         "note": "以文献研讨为主，每人负责 1 个专题。"},
    ]
    achievements = [
        {"id": "cja1", "title": "基于因果森林的学业风险因素识别方法", "type": "期刊论文",
         "level": "SCI 二区", "authors": "陈静, 何雪", "role": "第一作者", "venue": "IEEE TKDE",
         "date": D(-150), "status": "已发表", "score": 8.0, "projectId": "cjp1", "doi": "",
         "note": "被引 12 次，入选期刊年度高关注论文。"},
        {"id": "cja2", "title": "教育大数据因果分析平台软件 V2.0", "type": "软件著作权",
         "level": "软著", "authors": "陈静, 林涛", "role": "第一完成人", "venue": "中国版权保护中心",
         "date": D(-100), "status": "已登记", "score": 2.0, "projectId": "cjp1", "doi": "",
         "note": "登记号 2026SR0xxxxxx。"},
        {"id": "cja3", "title": "一种基于行为序列的学业风险预警方法", "type": "发明专利",
         "level": "发明专利", "authors": "陈静, 许晴", "role": "第一发明人", "venue": "国家知识产权局",
         "date": D(-75), "status": "已授权", "score": 5.0, "projectId": "cjp2", "doi": "",
         "note": "已授权，正在推进成果转化对接。"},
        {"id": "cja4", "title": "面向在线学习的可解释推荐模型", "type": "期刊论文",
         "level": "SCI 三区", "authors": "陈静, 林涛", "role": "通讯作者", "venue": "IEEE Access",
         "date": D(-30), "status": "审稿中", "score": 3.0, "projectId": "cjp2", "doi": "",
         "note": "一审大修意见已回。"},
        {"id": "cja5", "title": "省教学成果奖二等奖", "type": "科技奖励",
         "level": "省部级二等奖", "authors": "陈静 等", "role": "第一完成人", "venue": "浙江省教育厅",
         "date": D(-240), "status": "已获奖", "score": 4.0, "projectId": "", "doi": "",
         "note": "教育大数据驱动的教学质量提升实践。"},
        {"id": "cja6", "title": "校级优秀硕士论文指导教师", "type": "学位论文",
         "level": "校级优秀硕士论文", "authors": "陈静（导师）", "role": "指导教师", "venue": "研究生院",
         "date": D(-180), "status": "已获奖", "score": 3.0, "projectId": "", "doi": "",
         "note": "指导的 2022 级硕士论文获校级优秀。"},
    ]
    exchanges = [
        {"id": "cjx1", "title": "国际学习分析与知识会议（LAK 2026）", "kind": "学术会议", "role": "分会场报告",
         "organizer": "Society for Learning Analytics Research", "location": "线上", "level": "国际",
         "start": D(45), "end": D(48), "status": "已确认", "funding": "注册费 4200 元（cjp2 支出）",
         "topic": "报告「因果推断在学习分析中的应用」。", "note": "需提交 camera-ready 版本。",
         "travel": "线上参加", "participants": ["陈静", "何雪"]},
        {"id": "cjx2", "title": "全国教育大数据学术年会", "kind": "学术会议", "role": "主题报告",
         "organizer": "中国教育技术协会", "location": "武汉", "level": "国内",
         "start": D(20), "end": D(22), "status": "已确认", "funding": "注册费 1600 元（cjp1 支出）",
         "topic": "作 30 分钟主题报告，介绍教育大数据平台建设经验。", "note": "", "travel": "高铁往返",
         "participants": ["陈静"]},
        {"id": "cjx3", "title": "国家自然科学基金项目会评", "kind": "基金评审", "role": "评审专家",
         "organizer": "国家自然科学基金委员会", "location": "北京", "level": "国家级",
         "start": D(-30), "end": D(-27), "status": "已结束", "funding": "",
         "topic": "参与信息科学部会评工作。", "note": "", "travel": "已报销", "participants": ["陈静"]},
        {"id": "cjx4", "title": "与省教育厅洽谈平台推广", "kind": "企业交流", "role": "技术负责人",
         "organizer": "浙江省教育厅教育技术中心", "location": "杭州", "level": "省级",
         "start": D(8), "end": D(8), "status": "进行中", "funding": "",
         "topic": "讨论质量监测平台在全省高校的推广方案。", "note": "需准备平台演示材料。",
         "travel": "当日往返", "participants": ["陈静"]},
    ]
    developments = [
        {"id": "cjd1", "title": "教授聘期考核（2025-2030）", "category": "职称晋升", "status": "进行中",
         "start": "2025-01-01", "deadline": D(900), "progress": 34,
         "target": "主持国家级重点项目 1 项、一区论文 3 篇、省部级奖励 1 项、指导博士 2 名",
         "current": "主持国基金面上项目 1 项（结题中）；二区论文 1 篇；省教学成果二等奖 1 项",
         "note": "建议以重点项目申报为抓手整合团队成果。",
         "metrics": [{"name": "主持国家级重点项目", "target": 1, "current": 0, "unit": "项"},
                     {"name": "高水平论文（一区）", "target": 3, "current": 1, "unit": "篇"},
                     {"name": "省部级奖励", "target": 1, "current": 1, "unit": "项"},
                     {"name": "指导博士研究生", "target": 2, "current": 2, "unit": "名"}]},
        {"id": "cjd2", "title": "省级教学团队建设", "category": "教学能力", "status": "进行中",
         "start": "2025-03-01", "deadline": D(400), "progress": 48,
         "target": "组建教育大数据课程群教学团队并完成课程资源建设",
         "current": "已完成 3 门课程的资源整合，团队 5 人",
         "note": "", "metrics": [{"name": "课程资源", "target": 5, "current": 3, "unit": "门"}]},
    ]
    courses = [
        {"id": "cjc1", "name": "数据挖掘", "code": "AI401", "semester": "2026 秋",
         "students": 66, "credits": 3.0, "hours": 48,
         "color": "linear-gradient(135deg,#b45309,#f59e0b)",
         "intro": "讲授数据预处理、关联规则、分类聚类与集成学习，结合真实教育数据集开展项目实践。",
         "syllabus": [
             {"chapter": "第 1 章 数据挖掘概述", "hours": "4", "type": "讲授", "point": "任务与流程"},
             {"chapter": "第 2 章 数据预处理", "hours": "8", "type": "讲授 + 实验", "point": "清洗、变换"},
             {"chapter": "第 3 章 关联规则与聚类", "hours": "12", "type": "讲授 + 实验", "point": "Apriori、K-means"},
             {"chapter": "第 4 章 分类与集成学习", "hours": "14", "type": "讲授 + 实验", "point": "决策树、随机森林"},
             {"chapter": "第 5 章 课程项目", "hours": "10", "type": "项目实践", "point": "教育数据挖掘"},
         ],
         "resources": [{"name": "课程项目数据集.zip", "type": "ZIP", "size": "12.3 MB"},
                       {"name": "教学大纲.pdf", "type": "PDF", "size": "0.6 MB"}]},
    ]
    events = [
        _ev("cj", 1, "课题组例会（含文献分享）", "组会", 1, "14:00", "17:00", "智能楼 612"),
        _ev("cj", 2, "《数据挖掘》第 06 讲", "上课", 2, "08:00", "09:40", "二教 305"),
        _ev("cj", 3, "教学质量监测平台阶段评审", "会议", 4, "15:00", "16:30", "行政楼 402"),
        _ev("cj", 4, "与省教育厅平台推广洽谈", "会议", 8, "10:00", "12:00", "省教育厅"),
        _ev("cj", 5, "博士生何雪论文讨论", "指导", 2, "19:00", "20:00", "智能楼 612"),
    ]
    todos = [
        _td("cj", 1, "完成国基金面上项目结题材料", 6, "high", "科研项目"),
        _td("cj", 2, "提交 LAK 2026 camera-ready 论文", 12, "high", "学术交流"),
        _td("cj", 3, "审阅林涛中期检查材料", 5, "mid", "学生指导"),
        _td("cj", 4, "安排教学团队课程资源评审", 20, "low", "教学", True),
    ]
    return _pack(p, projects=projects, literature=literature, students=students,
                 teachings=teachings, achievements=achievements, exchanges=exchanges,
                 developments=developments, courses=courses, events=events, todos=todos)


# --------------------------------------------------------------------------- #
# 对外入口
# --------------------------------------------------------------------------- #
_SEED_BUILDERS = {
    "zhangwei": _zhangwei,
    "limin": _limin,
    "wangqiang": _wangqiang,
    "chenjing": _chenjing,
}


def initial_data(teacher: dict) -> dict:
    """按种子模式构造某位教师的完整工作台数据。"""
    mode = teacher.get("mode", "full")
    if mode == "full":
        return seed.full_seed()
    if mode == "empty":
        return empty_seed({k: teacher.get(k, "") for k in ("name", "title", "dept", "email", "office")})
    builder = _SEED_BUILDERS.get(mode)
    return builder() if builder else seed.full_seed()


def all_users() -> list[dict]:
    """管理员 + 全部教师的账号定义。"""
    return [ADMIN_USER, *TEACHER_USERS]
