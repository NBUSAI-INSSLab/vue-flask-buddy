/* =====================================================================
   forms.js —— 业务表单规格、工具运行器、设置面板、全局搜索
   ===================================================================== */
(function (global) {
  "use strict";

  var vue = global.Vue;
  var defineComponent = vue.defineComponent;
  var FWB = global.FWB;
  var U = FWB.util;

  var PROJECT_TYPES = ["国家自然科学基金面上项目", "国家自然科学基金青年项目", "国家重点研发计划",
    "省重点研发计划", "企业横向合作", "国家电网科技项目", "校级项目", "其他"];
  var ACH_TYPES = ["期刊论文", "会议论文", "发明专利", "软件著作权", "技术报告", "科技奖励", "学位论文"];
  /* 课程封面配色：首项跟随主题主色，其余为固定辅助色 */
  var COURSE_COLORS = [
    "linear-gradient(135deg,var(--primary-700),var(--primary))",
    "linear-gradient(135deg,var(--violet-ink),var(--violet))",
    "linear-gradient(135deg,var(--teal-ink),var(--teal))",
    "linear-gradient(135deg,#0f4c81,#2e7bb8)",
    "linear-gradient(135deg,var(--amber-ink),var(--amber))"
  ];

  function open(spec, initial) {
    FWB.store.act.openModal({
      component: "fwb-form", wide: true,
      title: spec.title || "",
      props: { spec: spec, initial: initial || {} }
    });
  }

  function splitList(v) {
    return String(v || "").split(/[,，、;；\s]+/).filter(Boolean);
  }
  function joinList(v) {
    return Array.isArray(v) ? v.join(",") : (v || "");
  }
  function toolKeyOf(tool) {
    if (!tool) return "";
    var m = /internal:\/\/(.+)$/.exec(tool.url || "");
    return m ? m[1].replace(/-/g, "_") : "";
  }

  /* =====================================================================
     业务表单规格
     ===================================================================== */
  var specs = {
    project: function (item) {
      return {
        title: item ? "编辑科研项目" : "新建科研项目",
        submitLabel: "保存项目",
        fields: [
          { name: "name", label: "项目名称", req: true, ph: "如 面向智慧养老的毫米波雷达跌倒检测算法研究" },
          { name: "code", label: "项目编号", ph: "如 NSFC-62176829" },
          { name: "type", label: "项目类型", type: "select", opts: PROJECT_TYPES, value: PROJECT_TYPES[0] },
          { name: "role", label: "本人角色", type: "select", opts: ["主持", "子课题负责人", "参与"], value: "主持" },
          { name: "funding", label: "经费（万元）", ph: "如 62；无数值可填 —" },
          { name: "startDate", label: "开始日期", type: "date", value: U.today() },
          { name: "deadline", label: "截止日期", type: "date", value: U.dayOffset(365) },
          { name: "status", label: "项目状态", type: "select", opts: ["在研", "验收中", "已结题", "待启动", "已暂停"], value: "在研" },
          { name: "desc", label: "项目简介", type: "textarea", rows: 3, ph: "研究目标、技术路线与预期成果…" }
        ],
        dynamic: [
          {
            key: "phases", label: "阶段任务（完成情况自动折算进度）", addLabel: "添加阶段",
            cols: [
              { name: "name", ph: "阶段名称", width: 4 },
              { name: "dueDate", type: "date", width: 1 },
              { name: "done", type: "check", ph: "完成", width: "0 0 auto" }
            ]
          },
          {
            key: "outcomes", label: "成果产出", addLabel: "添加成果",
            cols: [
              { name: "type", type: "select", opts: ACH_TYPES, width: 1 },
              { name: "title", ph: "成果名称", width: 4 },
              { name: "status", ph: "状态（已录用 / 审稿中…）", width: 1 },
              { name: "date", type: "date", width: 1 }
            ]
          }
        ],
        fromModel: function (m, dyn) {
          var phases = (dyn.phases || []).filter(function (p) { return p.name; });
          var done = phases.filter(function (p) { return !!p.done; }).length;
          var progress = item ? (item.progress || 0) : 0;
          if (phases.length) progress = Math.round((done / phases.length) * 100);
          return Object.assign({}, m, {
            phases: phases,
            outcomes: (dyn.outcomes || []).filter(function (o) { return o.title; }),
            progress: progress
          });
        }
      };
    },

    literature: function (item) {
      return {
        title: item ? "编辑文献" : "新增文献",
        submitLabel: "保存文献",
        fields: [
          { name: "title", label: "标题", req: true, ph: "论文 / 著作标题" },
          { name: "authors", label: "作者", ph: "如 Baltrušaitis T., Ahuja C." },
          { name: "journal", label: "期刊 / 会议", ph: "如 IEEE TPAMI" },
          { name: "year", label: "年份", ph: "如 2024" },
          { name: "doi", label: "DOI / 链接", ph: "如 10.1109/TPAMI.2018.2798607" },
          { name: "direction", label: "研究方向", ph: "如 多模态学习" },
          { name: "status", label: "阅读状态", type: "select", opts: ["未读", "在读", "已读"], value: "未读" },
          { name: "rating", label: "评分（0-5）", type: "number", value: "3" },
          { name: "addedDate", label: "收录日期", type: "date", value: U.today() },
          { name: "tags", label: "标签（逗号分隔）", ph: "如 多模态融合,方法综述" },
          { name: "note", label: "阅读笔记", type: "textarea", rows: 5, ph: "核心贡献、可借鉴之处、与在研项目的关系…" }
        ],
        fromModel: function (m) {
          return Object.assign({}, m, {
            tags: splitList(m.tags),
            rating: Math.max(0, Math.min(5, U.num(m.rating, 0)))
          });
        }
      };
    },

    exchange: function (item) {
      return {
        title: item ? "编辑学术交流" : "新增学术交流",
        submitLabel: "保存记录",
        fields: [
          { name: "title", label: "活动名称", req: true, ph: "如 智能感知与多模态学习前沿论坛" },
          { name: "kind", label: "类型", type: "select", opts: ["学术会议", "期刊审稿", "基金评审", "企业交流", "学术报告", "访问交流"], value: "学术会议" },
          { name: "role", label: "本人角色", ph: "如 分会场报告 / 审稿人 / 参会" },
          { name: "organizer", label: "主办方", ph: "如 中国自动化学会" },
          { name: "location", label: "地点", ph: "如 上海国际会议中心 / 线上" },
          { name: "level", label: "级别", type: "select", opts: ["国际", "国家级", "国内", "省部级", "企业"], value: "国内" },
          { name: "start", label: "开始日期", type: "date", value: U.today() },
          { name: "end", label: "结束日期", type: "date", value: U.dayOffset(2) },
          { name: "status", label: "状态", type: "select", opts: ["待确认", "已确认", "进行中", "已完成", "已取消"], value: "待确认" },
          { name: "funding", label: "经费 / 费用", ph: "如 会议注册费 1800 元（项目 p1 支出）" },
          { name: "travel", label: "行程安排", ph: "如 10/15 高铁 虹桥，10/17 返程" },
          { name: "participants", label: "参与人（逗号分隔）", ph: "如 江先亮,王雪" },
          { name: "topic", label: "交流内容", type: "textarea", rows: 3, ph: "报告主题 / 稿件内容 / 评审要点…" },
          { name: "note", label: "备注", type: "textarea", rows: 3, ph: "需提前准备的材料、注意事项…" }
        ],
        fromModel: function (m) {
          return Object.assign({}, m, { participants: splitList(m.participants) });
        }
      };
    },

    teaching: function (item) {
      return {
        title: item ? "编辑教学任务" : "新增教学任务",
        submitLabel: "保存",
        fields: [
          { name: "name", label: "课程名称", req: true, ph: "如 计算机网络" },
          { name: "code", label: "课程代码", ph: "如 CS301" },
          { name: "semester", label: "开课学期", ph: "如 2026 春" },
          { name: "type", label: "课程类型", type: "select", opts: ["本科生专业课", "本科生基础课", "研究生学位课", "毕业设计指导", "公共选修课"], value: "本科生专业课" },
          { name: "students", label: "学生人数", type: "number", value: "60" },
          { name: "hours", label: "总学时", ph: "如 56；无数值可填 —" },
          { name: "stage", label: "教学阶段", type: "select", opts: ["备课中", "进行中", "结课归档", "已完成", "选题阶段"], value: "备课中" },
          { name: "syllabusDone", label: "已完成章数", type: "number", value: "0" },
          { name: "syllabusTotal", label: "总章数", type: "number", value: "8" },
          { name: "examType", label: "考核方式", ph: "如 闭卷考试 + 课程设计" },
          { name: "evalScore", label: "评教得分", ph: "如 4.72 / 5.0" },
          { name: "note", label: "教学备注", type: "textarea", rows: 3, ph: "教学安排、注意事项…" }
        ],
        dynamic: [
          {
            key: "tasks", label: "教学任务清单", addLabel: "添加任务",
            cols: [
              { name: "name", ph: "任务内容", width: 4 },
              { name: "due", type: "date", width: 1 },
              { name: "done", type: "check", ph: "完成", width: "0 0 auto" }
            ]
          }
        ],
        fromModel: function (m, dyn) {
          return Object.assign({}, m, {
            tasks: (dyn.tasks || []).filter(function (t) { return t.name; })
          });
        }
      };
    },

    achievement: function (item) {
      var projects = FWB.store.act.list("projects").map(function (p) {
        return { id: p.id, name: p.name };
      });
      return {
        title: item ? "编辑成果" : "登记成果",
        submitLabel: "保存成果",
        fields: [
          { name: "title", label: "成果名称", req: true, ph: "论文 / 专利 / 软著 / 奖励名称" },
          { name: "type", label: "成果类型", type: "select", opts: ACH_TYPES, value: "期刊论文" },
          { name: "level", label: "级别", ph: "如 SCI 二区 / 发明专利 / 省部级二等奖" },
          { name: "authors", label: "作者", ph: "如 江先亮, 张伟, 李明" },
          { name: "role", label: "本人角色", ph: "如 第一作者 / 通讯作者 / 第一发明人" },
          { name: "venue", label: "发表 / 授权单位", ph: "如 IEEE Sensors Journal" },
          { name: "date", label: "日期", type: "date", value: U.today() },
          { name: "status", label: "状态", type: "select", opts: ["撰写中", "审稿中", "已录用", "已发表", "已授权", "已登记", "已交付", "已获奖", "申报中"], value: "撰写中" },
          { name: "score", label: "业绩分", type: "number", value: "0" },
          { name: "projectId", label: "关联项目", type: "select", opts: [""].concat(projects.map(function (p) { return p.id; })), value: item ? (item.projectId || "") : "" },
          { name: "doi", label: "DOI / 登记号", ph: "如 10.1109/JSEN.2025.3412210" },
          { name: "note", label: "备注", type: "textarea", rows: 3, ph: "创新点、指标、应用情况…" }
        ],
        fromModel: function (m) { return Object.assign({}, m, { score: U.num(m.score, 0) }); }
      };
    },

    development: function (item) {
      return {
        title: item ? "编辑发展计划" : "新增发展计划",
        submitLabel: "保存",
        fields: [
          { name: "title", label: "计划名称", req: true, ph: "如 教授职称聘期考核（2026-2029）" },
          { name: "category", label: "类别", type: "select", opts: ["职称晋升", "人才项目", "培训进修", "产学研", "考核述职", "其他"], value: "职称晋升" },
          { name: "status", label: "状态", type: "select", opts: ["规划中", "准备中", "进行中", "已完成", "已暂停"], value: "规划中" },
          { name: "start", label: "开始日期", type: "date", value: U.today() },
          { name: "deadline", label: "目标日期", type: "date", value: U.dayOffset(365) },
          { name: "target", label: "目标", type: "textarea", rows: 3, ph: "本阶段要达到的量化目标…" },
          { name: "current", label: "当前进展", type: "textarea", rows: 3, ph: "已完成的部分…" },
          { name: "note", label: "备注", type: "textarea", rows: 2, ph: "建议、提醒…" }
        ],
        dynamic: [
          {
            key: "metrics", label: "量化指标（有指标时按完成率自动折算进度）", addLabel: "添加指标",
            cols: [
              { name: "name", ph: "指标名称", width: 3 },
              { name: "current", type: "number", ph: "当前", width: 1 },
              { name: "target", type: "number", ph: "目标", width: 1 },
              { name: "unit", ph: "单位", width: 1 }
            ]
          }
        ],
        fromModel: function (m, dyn) {
          var metrics = (dyn.metrics || []).filter(function (x) { return x.name; }).map(function (x) {
            return { name: x.name, target: U.num(x.target, 0), current: U.num(x.current, 0), unit: x.unit || "" };
          });
          var progress = item ? (item.progress || 0) : 0;
          var withTarget = metrics.filter(function (x) { return x.target > 0; });
          if (withTarget.length) {
            var sum = withTarget.reduce(function (s, x) { return s + Math.min(1, x.current / x.target); }, 0);
            progress = Math.round((sum / withTarget.length) * 100);
          }
          return Object.assign({}, m, { metrics: metrics, progress: progress });
        }
      };
    },

    course: function (item) {
      return {
        title: item ? "编辑课程" : "新增课程",
        submitLabel: "保存课程",
        fields: [
          { name: "name", label: "课程名称", req: true, ph: "如 计算机网络" },
          { name: "code", label: "课程代码", ph: "如 CS301" },
          { name: "semester", label: "开课学期", ph: "如 2026 春" },
          { name: "students", label: "学生人数", type: "number", value: "60" },
          { name: "credits", label: "学分", type: "number", value: "3" },
          { name: "hours", label: "学时", type: "number", value: "48" },
          { name: "color", label: "卡片配色", type: "select", opts: COURSE_COLORS, value: COURSE_COLORS[0] },
          { name: "intro", label: "课程简介", type: "textarea", rows: 3, ph: "面向对象、主要内容与教学目标…" }
        ],
        dynamic: [
          {
            key: "syllabus", label: "教学大纲", addLabel: "添加章节",
            cols: [
              { name: "chapter", ph: "章节名称", width: 4 },
              { name: "hours", ph: "学时", width: 1 },
              { name: "type", type: "select", opts: ["讲授", "讲授 + 实验", "实验", "实践", "研讨"], width: 1 },
              { name: "point", ph: "教学要点", width: 3 }
            ]
          },
          {
            key: "materials", label: "课程资料", addLabel: "添加资料",
            cols: [
              { name: "type", type: "select", opts: ["教学大纲", "课件", "案例", "实验", "习题", "参考书"], width: 1 },
              { name: "name", ph: "文件名", width: 4 },
              { name: "size", ph: "大小", width: 1 },
              { name: "date", type: "date", width: 1 }
            ]
          }
        ],
        fromModel: function (m, dyn) {
          return Object.assign({}, m, {
            students: U.num(m.students, 0), credits: U.num(m.credits, 0), hours: U.num(m.hours, 0),
            syllabus: (dyn.syllabus || []).filter(function (x) { return x.chapter; }),
            materials: (dyn.materials || []).filter(function (x) { return x.name; })
          });
        }
      };
    },

    student: function (item) {
      return {
        title: item ? "编辑学生信息" : "新增指导学生",
        submitLabel: "保存",
        fields: [
          { name: "name", label: "姓名", req: true, ph: "如 李明" },
          { name: "degree", label: "培养层次", type: "select", opts: ["硕士", "博士"], value: "硕士" },
          { name: "grade", label: "年级", ph: "如 2024 级" },
          { name: "direction", label: "研究方向", ph: "如 多模态情感计算" },
          { name: "email", label: "邮箱", type: "email", ph: "如 liming24@university.edu.cn" },
          { name: "stage", label: "论文阶段", type: "select", opts: ["文献调研", "开题准备", "中期检查", "论文撰写", "答辩准备", "已毕业"], value: "文献调研" },
          { name: "progress", label: "论文进度（%）", type: "number", value: "0" },
          { name: "nextMeeting", label: "下次沟通", type: "date", value: U.dayOffset(7) },
          { name: "thesisTitle", label: "学位论文题目", ph: "学位论文题目" }
        ],
        dynamic: [
          {
            key: "milestones", label: "论文里程碑（完成情况自动折算进度）", addLabel: "添加里程碑",
            cols: [
              { name: "name", ph: "里程碑名称", width: 4 },
              { name: "date", type: "date", width: 1 },
              { name: "done", type: "check", ph: "完成", width: "0 0 auto" }
            ]
          }
        ],
        fromModel: function (m, dyn) {
          var milestones = (dyn.milestones || []).filter(function (x) { return x.name; });
          return Object.assign({}, m, {
            milestones: milestones,
            progress: Math.max(0, Math.min(100, U.num(m.progress, 0)))
          });
        }
      };
    },

    event: function (item) {
      return {
        title: item ? "编辑日程" : "新增日程",
        submitLabel: "保存日程",
        fields: [
          { name: "title", label: "事项标题", req: true, ph: "如 课题组例会" },
          { name: "type", label: "类型", type: "select", opts: ["上课", "组会", "会议", "答辩", "申报", "其他"], value: "会议" },
          { name: "date", label: "日期", type: "date", value: U.today() },
          { name: "start", label: "开始时间", ph: "如 14:00" },
          { name: "end", label: "结束时间", ph: "如 16:00" },
          { name: "location", label: "地点", ph: "如 信息楼 A-513" },
          { name: "done", label: "已完成", type: "check", ph: "标记为已完成" },
          { name: "note", label: "备注", type: "textarea", rows: 3, ph: "需要准备的材料、注意事项…" }
        ],
        fromModel: function (m) { return Object.assign({}, m, { done: !!m.done }); }
      };
    },

    todo: function (item) {
      return {
        title: item ? "编辑待办" : "新增待办",
        submitLabel: "保存",
        fields: [
          { name: "title", label: "待办内容", req: true, ph: "如 审阅张伟学位论文终稿并反馈修改意见" },
          { name: "due", label: "截止日期", type: "date", value: U.today() },
          { name: "priority", label: "优先级", type: "select", opts: ["高", "中", "低"], value: "中" },
          { name: "tag", label: "分类标签", ph: "如 科研项目 / 学生指导 / 课程资源" },
          { name: "done", label: "已完成", type: "check", ph: "标记为已完成" }
        ],
        fromModel: function (m) {
          var map = { "高": "high", "中": "mid", "低": "low" };
          return Object.assign({}, m, { priority: map[m.priority] || "mid", done: !!m.done });
        }
      };
    }
  };

  /* =====================================================================
     打开业务表单
     ===================================================================== */
  /* =====================================================================
     管理端：教师账号表单（新建 / 编辑）
     ===================================================================== */
  var ROLE_TO_LABEL = { teacher: "教师", admin: "管理员" };
  var LABEL_TO_ROLE = { "教师": "teacher", "管理员": "admin" };

  specs.teacher = function (user) {
    var isEdit = !!user;
    if (isEdit) {
      return {
        title: "编辑教师资料",
        submitLabel: "保存修改",
        fields: [
          { name: "name", label: "姓名", req: true },
          { name: "role", label: "角色", type: "select", opts: ["教师", "管理员"], value: "教师" },
          { name: "title", label: "职称", ph: "讲师 / 副教授 / 教授" },
          { name: "dept", label: "所属学院" },
          { name: "email", label: "邮箱", type: "email", ph: "选填" },
          { name: "office", label: "办公室", ph: "选填" },
          { name: "active", label: "账号状态", type: "check", ph: "启用该账号（取消勾选即停用）", value: true }
        ],
        fromModel: function (m) {
          return Object.assign({}, m, {
            role: LABEL_TO_ROLE[m.role] || "teacher",
            active: !!m.active
          });
        }
      };
    }
    return {
      title: "新建账号",
      submitLabel: "创建账号",
      fields: [
        { name: "username", label: "用户名", req: true, ph: "3-20 位，字母开头，可含数字与下划线" },
        { name: "name", label: "姓名", req: true, ph: "真实姓名" },
        { name: "password", label: "初始密码", req: true, type: "password", ph: "至少 6 位" },
        { name: "role", label: "角色", type: "select", opts: ["教师", "管理员"], value: "教师" },
        { name: "title", label: "职称", ph: "讲师 / 副教授 / 教授" },
        { name: "dept", label: "所属学院" },
        { name: "email", label: "邮箱", type: "email", ph: "选填" },
        { name: "office", label: "办公室", ph: "选填" },
        { name: "withDemo", label: "初始化数据", type: "check", ph: "为该教师填入演示数据（便于快速体验）", value: false }
      ],
      fromModel: function (m) {
        return Object.assign({}, m, {
          role: LABEL_TO_ROLE[m.role] || "teacher",
          withDemo: !!m.withDemo
        });
      }
    };
  };

  var COLL = {
    project: "projects", literature: "literature", exchange: "exchanges",
    teaching: "teachings", achievement: "achievements", development: "developments",
    course: "courses", student: "students", event: "events", todo: "todos"
  };

  var forms = {
    specs: specs,
    openForm: function (kind, item) {
      var coll = COLL[kind];
      var act = FWB.store.act;
      var spec = specs[kind](item || null);
      spec.onSubmit = async function (payload) {
        if (item) {
          await act.update(coll, item.id, payload);
          act.toast("已保存修改", "success");
        } else {
          await act.create(coll, payload);
          act.toast("已创建", "success");
        }
      };
      open(spec, item ? buildInitial(kind, item) : {});
    },
    remove: async function (kind, item) {
      var coll = COLL[kind];
      var act = FWB.store.act;
      await act.confirmDelete("确定删除「" + (item.name || item.title || item.id) + "」？此操作不可撤销。",
        async function () { await act.remove(coll, item.id); });
      if (FWB.store.state.page.indexOf("-detail") > 0) act.go(FWB.util.NAV_PARENT[FWB.store.state.page] || "dashboard");
    },
    openEventForm: function (item) { forms.openForm("event", item); },
    openToolRunner: openToolRunner,
    openSettings: openSettings,
    openSearch: openSearch,

    /* ---------------- 管理端 ---------------- */
    openTeacherForm: function (user) {
      var act = FWB.store.act;
      var isEdit = !!user;
      var spec = specs.teacher(user || null);
      spec.onSubmit = async function (payload) {
        if (isEdit) {
          var patch = {};
          ["name", "title", "dept", "email", "office", "role", "active"].forEach(function (k) {
            if (payload[k] !== undefined) patch[k] = payload[k];
          });
          await act.adminUpdateTeacher(user.id, patch);
          act.toast("已保存 " + user.name + " 的资料", "success");
        } else {
          await act.adminCreateTeacher(payload);
          act.toast("已创建账号 " + payload.username, "success");
        }
      };
      var initial = isEdit
        ? {
            name: user.name, title: user.title, dept: user.dept, email: user.email,
            office: user.office, active: user.active, role: ROLE_TO_LABEL[user.role] || "教师"
          }
        : { role: "教师", title: "讲师", dept: "计算机科学与技术学院", withDemo: false };
      open(spec, initial);
    },

    openResetPwd: function (user) {
      var act = FWB.store.act;
      var spec = {
        title: "重置密码 · " + (user.name || ""),
        submitLabel: "重置密码",
        fields: [
          { name: "password", label: "新密码", req: true, type: "password", ph: "至少 6 位" },
          { name: "password2", label: "确认新密码", req: true, type: "password", ph: "再次输入新密码" }
        ],
        onSubmit: async function (payload) {
          if (payload.password !== payload.password2) throw new Error("两次输入的密码不一致");
          await act.adminResetPassword(user.id, payload.password);
          act.toast("已重置 " + user.name + " 的密码", "success");
        }
      };
      open(spec, {});
    }
  };

  function buildInitial(kind, item) {
    var out = Object.assign({}, item);
    if (kind === "literature") out.tags = joinList(item.tags);
    if (kind === "exchange") out.participants = joinList(item.participants);
    if (kind === "todo") {
      out.priority = { high: "高", mid: "中", low: "低" }[item.priority] || "中";
    }
    return out;
  }

  /* =====================================================================
     工具运行器
     ===================================================================== */
  var FwbToolRunner = defineComponent({
    name: "FwbToolRunner",
    components: { FwbField: FWB.components.FwbField, FwbIcon: FWB.components.FwbIcon },
    props: { toolKey: { type: String, required: true }, toolName: { type: String, default: "" } },
    setup: function () {
      var store = FWB.store;
      return { S: store.state, act: store.act };
    },
    data: function () {
      var list = this.S.specs[this.toolKey] || [];
      var params = {};
      list.forEach(function (f) {
        if (f.type === "check") params[f.name] = f.value === true;
        else params[f.name] = f.value !== undefined ? f.value : "";
      });
      return { fields: list, params: params, files: {}, result: null, error: "", busy: false };
    },
    computed: {
      fileFields: function () {
        return this.fields.filter(function (f) { return f.type === "file"; });
      },
      normalFields: function () {
        return this.fields.filter(function (f) { return f.type !== "file"; });
      },
      fileNames: function () {
        var out = {};
        var self = this;
        this.fileFields.forEach(function (f) {
          var fl = self.files[f.name];
          out[f.name] = fl ? Array.prototype.map.call(fl, function (x) { return x.name; }) : [];
        });
        return out;
      }
    },
    methods: {
      setVal: function (f, v) {
        this.params[f.name] = v;
        if (f.type === "file") this.files[f.name] = v;
      },
      pick: function (name, ev) { this.files[name] = ev.target.files; },
      async execute() {
        var act = this.act;
        // 必填校验
        for (var i = 0; i < this.fields.length; i++) {
          var f = this.fields[i];
          if (!f.req) continue;
          if (f.type === "file") {
            var fl = this.files[f.name];
            if (!fl || !fl.length) { this.error = "请选择：" + f.label; return; }
          } else if (String(this.params[f.name] || "").trim() === "") {
            this.error = "请填写：" + f.label;
            return;
          }
        }
        this.error = "";
        this.busy = true;
        this.result = null;
        try {
          var ids = [];
          for (var j = 0; j < this.fileFields.length; j++) {
            var ff = this.fileFields[j];
            var list = this.files[ff.name];
            if (list && list.length) {
              var up = await FWB.api.upload(list);
              ids = ids.concat(up.files.map(function (x) { return x.id; }));
            }
          }
          var res = await act.runTool(this.toolKey, this.params, ids);
          this.result = res;
          this.act.toast(res.summary.slice(0, 32), res.ok === false ? "error" : "success");
        } catch (e) {
          this.error = e.message || String(e);
        } finally {
          this.busy = false;
        }
      },
      download: function (file) {
        var a = document.createElement("a");
        a.href = file.url;
        a.download = file.name;
        document.body.appendChild(a);
        a.click();
        a.remove();
      },
      humanSize: function (n) {
        if (n < 1024) return n + " B";
        if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
        return (n / 1024 / 1024).toFixed(2) + " MB";
      }
    },
    template:
      "<div>" +
      '  <div v-if="error" class="form-error">{{ error }}</div>' +
      '  <div class="form-row two">' +
      '    <fwb-field v-for="f in normalFields" :key="f.name" :spec="f" ' +
      '      :modelValue="params[f.name]" @update:modelValue="v => setVal(f, v)"/>' +
      "  </div>" +

      '  <div v-for="f in fileFields" :key="f.name" class="form-row">' +
      '    <label style="display:block;font-size:12.5px;font-weight:600;color:var(--text-2);margin-bottom:6px">' +
      '      {{ f.label }}<span v-if="f.req" class="req" style="color:var(--red)">*</span></label>' +
      '    <div class="upload-zone" @click="$refs[\'up_\' + f.name].click()">' +
      '      <fwb-icon name="upload"/>' +
      '      <p>点击选择文件{{ f.accept === ".pdf" ? "（可多选 PDF）" : "（可多选 .pptx）" }}</p>' +
      "    </div>" +
      '    <input :ref="\'up_\' + f.name" type="file" :accept="f.accept" multiple style="display:none" @change="pick(f.name, $event)">' +
      '    <div v-if="fileNames[f.name].length" class="file-chips">' +
      '      <span v-for="(n, i) in fileNames[f.name]" :key="i" class="file-chip"><fwb-icon name="file"/>{{ n }}</span>' +
      "    </div>" +
      '    <div v-if="f.hint" class="hint">{{ f.hint }}</div>' +
      "  </div>" +

      '  <div class="modal-foot" style="padding:16px 0 0;border-top:1px solid var(--line);margin-top:18px">' +
      '    <button class="btn ghost" type="button" @click="act.closeModal()">关闭</button>' +
      '    <button class="btn primary" type="button" :disabled="busy" @click="execute">' +
      '      <fwb-icon name="play"/>{{ busy ? "执行中…" : "运行工具" }}' +
      "    </button>" +
      "  </div>" +

      '  <div v-if="result" class="runner-result">' +
      '    <div class="runner-summary" :style="result.ok === false ? \'background:var(--red-soft);border-color:var(--red-line);color:var(--red-ink)\' : null">' +
      '      <fwb-icon :name="result.ok === false ? \'alert\' : \'check\'"/><span>{{ result.summary }}</span>' +
      "    </div>" +
      '    <div v-if="result.metrics.length" class="runner-metrics">' +
      '      <div v-for="(m, i) in result.metrics" :key="i" class="runner-metric">' +
      '        <b>{{ m[1] }}</b><span>{{ m[0] }}<template v-if="m[2]">（{{ m[2] }}）</template></span>' +
      "      </div>" +
      "    </div>" +
      '    <pre v-if="result.text" class="runner-text">{{ result.text }}</pre>' +
      '    <div v-if="result.files.length" class="runner-files">' +
      '      <button v-for="(f, i) in result.files" :key="i" class="btn ghost sm" @click="download(f)">' +
      '        <fwb-icon name="download"/>{{ f.name }}（{{ humanSize(f.size) }}）' +
      "      </button>" +
      "    </div>" +
      "  </div>" +
      "</div>"
  });

  function openToolRunner(tool) {
    var key = toolKeyOf(tool);
    if (!key || !FWB.store.state.specs[key]) {
      FWB.store.act.toast("该工具暂无内置实现", "warn");
      return;
    }
    FWB.store.act.openModal({
      component: "fwb-tool-runner", wide: true,
      title: tool.name || "运行工具",
      props: { toolKey: key, toolName: tool.name || "" }
    });
  }

  /* =====================================================================
     设置面板
     ===================================================================== */
  var FwbSettings = defineComponent({
    name: "FwbSettings",
    components: { FwbIcon: FWB.components.FwbIcon },
    setup: function () {
      var store = FWB.store;
      return { S: store.state, act: store.act };
    },
    data: function () {
      return {
        form: Object.assign({}, this.S.profile),
        error: "", busy: false, importErr: ""
      };
    },
    methods: {
      async save() {
        if (!String(this.form.name || "").trim()) { this.error = "姓名不能为空"; return; }
        this.error = "";
        this.busy = true;
        try {
          await this.act.saveProfile({
            name: this.form.name.trim(), title: this.form.title, dept: this.form.dept,
            office: this.form.office, email: this.form.email
          });
          this.act.toast("设置已保存", "success");
          this.act.closeModal();
        } catch (e) {
          this.error = e.message;
        } finally {
          this.busy = false;
        }
      },
      async exportData() {
        try {
          var res = await fetch(FWB.api.exportUrl());
          var data = await res.json();
          var blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
          var a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = "faculty-workbench-backup-" + U.today() + ".json";
          document.body.appendChild(a);
          a.click();
          a.remove();
          setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
          this.act.toast("已导出数据备份", "success");
        } catch (e) {
          this.act.toast("导出失败：" + e.message, "error");
        }
      },
      async importFile(ev) {
        var file = ev.target.files && ev.target.files[0];
        if (!file) return;
        this.importErr = "";
        try {
          var text = await file.text();
          var data = JSON.parse(text);
          var yes = await this.act.confirm({
            title: "导入数据",
            msg: "导入将覆盖当前全部数据，确定继续？（建议先导出备份）",
            btn: "确认导入"
          });
          if (!yes) return;
          await this.act.importData(data);
          this.form = Object.assign({}, this.S.profile);
          this.act.toast("数据已导入", "success");
        } catch (e) {
          this.importErr = "导入失败：" + (e.message || String(e));
        } finally {
          ev.target.value = "";
        }
      },
      async resetData() {
        var yes = await this.act.confirm({
          title: "重置为演示数据",
          msg: "将清空所有本地修改并恢复为初始演示数据，此操作不可撤销。确定继续？",
          btn: "确认重置"
        });
        if (!yes) return;
        await this.act.resetData();
        this.form = Object.assign({}, this.S.profile);
        this.act.toast("已重置为演示数据", "success");
      }
    },
    template:
      "<div>" +
      '  <div v-if="error" class="form-error">{{ error }}</div>' +

      '  <div class="set-sec">' +
      '    <h4><fwb-icon name="users"/>个人信息</h4>' +
      '    <div class="form-row two">' +
      '      <div class="field"><label>姓名<span class="req">*</span></label>' +
      '        <input type="text" v-model="form.name" placeholder="教师姓名"></div>' +
      '      <div class="field"><label>职称</label>' +
      '        <input type="text" v-model="form.title" placeholder="如 教授"></div>' +
      '      <div class="field span2"><label>学院 / 部门</label>' +
      '        <input type="text" v-model="form.dept" placeholder="如 计算机科学与技术学院"></div>' +
      '      <div class="field"><label>办公室</label>' +
      '        <input type="text" v-model="form.office" placeholder="如 信息楼 A-513"></div>' +
      '      <div class="field"><label>邮箱</label>' +
      '        <input type="email" v-model="form.email" placeholder="如 name@university.edu.cn"></div>' +
      "    </div>" +
      "  </div>" +

      '  <div class="set-sec">' +
      '    <h4><fwb-icon name="palette"/>界面配色</h4>' +
      '    <p class="set-note">选择喜欢的界面配色，立即生效并保存在本机浏览器。</p>' +
      '    <fwb-theme-picker :hint="false"></fwb-theme-picker>' +
      "  </div>" +

      '  <div class="set-sec">' +
      '    <h4><fwb-icon name="database"/>数据管理</h4>' +
      '    <p class="set-note">数据保存在服务端 SQLite（账号 <code>data/users.db</code>，' +
      "      各教师数据 <code>data/tenants/&lt;uid&gt;.db</code>）。" +
      "      可导出 JSON 备份用于换机迁移；导入会覆盖当前全部数据。</p>" +
      '    <div class="set-actions">' +
      '      <button class="btn ghost" @click="exportData"><fwb-icon name="download"/>导出数据备份</button>' +
      '      <label class="btn ghost" style="cursor:pointer">' +
      '        <fwb-icon name="upload"/>导入数据恢复' +
      '        <input type="file" accept="application/json,.json" style="display:none" @change="importFile">' +
      "      </label>" +
      '      <button class="btn danger" @click="resetData"><fwb-icon name="rotate"/>重置为演示数据</button>' +
      "    </div>" +
      '    <div v-if="importErr" class="form-error" style="margin-top:12px">{{ importErr }}</div>' +
      "  </div>" +

      '  <div class="set-sec">' +
      '    <h4><fwb-icon name="info"/>关于</h4>' +
      '    <p class="set-note">高校教师工作台 · Vue 3 + Flask 版<br>' +
      "      11 个功能模块（科研 / 教学 / 学生指导 / 学术交流 / 成果 / 个人发展）与 12 项教研工具，<br>" +
      "      数据落库 SQLite，工具在服务端执行，产物可直接下载。</p>" +
      "  </div>" +

      '  <div class="modal-foot" style="padding:16px 0 0;border-top:1px solid var(--line);margin-top:18px">' +
      '    <button class="btn ghost" @click="act.closeModal()">关闭</button>' +
      '    <button class="btn primary" :disabled="busy" @click="save">{{ busy ? "保存中…" : "保存设置" }}</button>' +
      "  </div>" +
      "</div>"
  });

  function openSettings() {
    FWB.store.act.openModal({ component: "fwb-settings", title: "设置", props: {} });
  }

  /* =====================================================================
     全局搜索
     ===================================================================== */
  function openSearch(hits, q) {
    var act = FWB.store.act;
    var body = hits.length
      ? hits.map(function (h) {
        return '<div class="sr-item" data-page="' + h.page + '" data-coll="' + h.collection +
          '" data-id="' + h.id + '" data-label="' + U.esc(h.label) + '">' +
          '<span class="sr-ico">' + iconSvg(h.collection) + "</span>" +
          "<div><div class=\"sr-title\">" + U.esc(h.title) + "</div>" +
          '<div class="sr-sub">' + U.esc(h.label) + (h.sub ? " · " + U.esc(h.sub) : "") + "</div></div></div>";
      }).join("")
      : '<div class="empty"><p>没有找到与「' + U.esc(q) + "」相关的记录</p></div>";

    act.openModal({
      title: "搜索结果（" + hits.length + "）",
      body: body,
      foot: '<button class="btn ghost" data-close>关闭</button>',
      props: { fromSearch: true }
    });

    // 点击结果 -> 跳转详情
    setTimeout(function () {
      var nodes = document.querySelectorAll(".sr-item");
      Array.prototype.forEach.call(nodes, function (el) {
        el.addEventListener("click", function () {
          var page = el.getAttribute("data-page");
          var coll = el.getAttribute("data-coll");
          var id = el.getAttribute("data-id");
          act.closeModal();
          var detailMap = {
            projects: "project", literature: "lit", courses: "course", students: "student"
          };
          if (detailMap[coll]) act.openDetail(detailMap[coll], id);
          else act.go(page);
        });
      });
    }, 0);
  }

  function iconSvg(coll) {
    var map = {
      projects: "flask", literature: "book", courses: "cap", students: "users",
      events: "calendar", todos: "check", exchanges: "globe", teachings: "clipboard",
      achievements: "medal", developments: "trending", tools: "wrench"
    };
    var path = FWB.iconPath(map[coll] || "info");
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" ' +
      'stroke-linecap="round" stroke-linejoin="round">' + path + "</svg>";
  }

  FWB.forms = forms;
  FWB.components.FwbToolRunner = FwbToolRunner;
  FWB.components.FwbSettings = FwbSettings;
})(window);
