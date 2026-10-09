/* =====================================================================
   app.js —— 根组件：登录分流、教师工作台、管理员管理端
   ===================================================================== */
(function (global) {
  "use strict";

  var Vue = global.Vue;
  var FWB = global.FWB;
  var U = FWB.util;

  /* ---------------------------- 教师端导航 ---------------------------- */
  var NAV_GROUPS = [
    {
      label: "工作区",
      items: [
        { key: "dashboard", text: "工作首页", icon: "dashboard" },
        { key: "schedule", text: "日程管理", icon: "calendar" },
        { key: "agent", text: "智能助手", icon: "bot" }
      ]
    },
    {
      label: "科研区",
      items: [
        { key: "projects", text: "科研项目", icon: "flask" },
        { key: "literature", text: "文献仓库", icon: "book" },
        { key: "exchanges", text: "学术交流", icon: "globe" },
        { key: "achievements", text: "成果管理", icon: "medal" }
      ]
    },
    {
      label: "教学区",
      items: [
        { key: "teachings", text: "教学管理", icon: "clipboard" },
        { key: "courses", text: "课程资源", icon: "cap" },
        { key: "students", text: "学生指导", icon: "users" }
      ]
    },
    {
      label: "发展区",
      items: [
        { key: "developments", text: "个人发展", icon: "trending" },
        { key: "cv", text: "个人简历", icon: "user" },
        { key: "links", text: "常用网站", icon: "link" },
        { key: "tools", text: "常用工具", icon: "wrench" }
      ]
    }
  ];

  /* ---------------------------- 快捷新建 ---------------------------- */
  var QUICK = [
    { label: "新建科研项目", tone: "blue", kind: "project" },
    { label: "收藏文献", tone: "violet", kind: "literature" },
    { label: "新增日程", tone: "teal", kind: "event" },
    { label: "新增待办", tone: "amber", kind: "todo" },
    { label: "登记成果", tone: "green", kind: "achievement" },
    { label: "新增学术交流", tone: "indigo", kind: "exchange" },
    { label: "新增教学任务", tone: "blue", kind: "teaching" },
    { label: "新增发展目标", tone: "violet", kind: "development" }
  ];

/* 管理端页面标题 */
var ADMIN_META = {
  overview: ["数据概览", "全院教师科研成果 / 学术交流 / 教学情况 / 学生指导总览"],
  teachers: ["教师管理", "查看教师简要信息，编辑资料、重置密码、停用或删除账号"],
  teacher: ["教师统计详情", "科研成果 · 学术交流 · 教学情况 · 学生指导"],
  reviews: ["成果审核", "审核全院教师登记的科研成果，通过后计入业绩统计"]
};

/* 审核状态标签页 */
var REVIEW_TABS = [
  { key: "待审核", text: "待审核", tone: "wait" },
  { key: "已退回", text: "已退回", tone: "off" },
  { key: "已通过", text: "已通过", tone: "ok" },
  { key: "", text: "全部成果", tone: "" }
];

/* 审核状态 → 徽标配色 */
var AUDIT_TONE = { "待审核": "wait", "已通过": "ok", "已退回": "off" };

/* 图表配色（全部走主题变量，切换配色时自动跟随） */
var RING_COLORS = [
  "var(--primary)", "var(--violet)", "var(--amber)",
  "var(--teal)", "var(--indigo)", "var(--red)", "var(--text-3)"
];

/* 详情未就绪时的安全空结构，避免模板访问 undefined */
var EMPTY_DETAIL = {
  research: { projects: { list: [] }, achievements: {}, literature: {} },
  exchanges: { recent: [] },
  teaching: { list: [] },
  students: { list: [] },
  audit: { history: [] }
};

  var Fallback = {
    name: "PageMissing",
    template:
      '<div class="card"><div class="empty" style="padding:70px 0">' +
      '<fwb-icon name="alert" :size="42"/><p>页面不存在或尚未实现</p>' +
      '<button class="btn ghost mt-2" @click="act.go(\'dashboard\')">返回工作首页</button>' +
      "</div></div>",
    setup: function () { return { act: FWB.store.act }; }
  };

  var App = {
    name: "FwbApp",

    setup: function () {
      var s = FWB.store;
      return { S: s.state, UI: s.ui, act: s.act, forms: FWB.forms, U: U };
    },

    data: function () {
      return { navGroups: NAV_GROUPS, quickItems: QUICK };
    },

    computed: {
      /* ---------------- 认证分流 ---------------- */
      authChecked: function () { return this.S.auth.checked; },
      authed: function () { return !!this.S.auth.user; },
      authUser: function () { return this.S.auth.user || {}; },
      isAdmin: function () { return this.authed && this.S.auth.user.role === "admin"; },

      /* ---------------- 管理端 ---------------- */
      adminPage: function () { return this.S.admin.page; },
      adminRows: function () { return this.S.admin.rows || []; },
      adminTotals: function () { return this.S.admin.totals; },
      adminDetail: function () { return this.S.admin.detail; },

      d: function () {
        var detail = this.S.admin.detail && this.S.admin.detail.detail;
        return detail || EMPTY_DETAIL;
      },

      adminQ: {
        get: function () { return this.S.admin.q; },
        set: function (v) { this.S.admin.q = v; }
      },

      /* 顶栏搜索框：在成果审核页检索成果，其余管理页检索教师 */
      adminSearch: {
        get: function () {
          return this.S.admin.page === "reviews" ? this.S.admin.reviewQ : this.S.admin.q;
        },
        set: function (v) {
          if (this.S.admin.page === "reviews") this.S.admin.reviewQ = v;
          else this.S.admin.q = v;
        }
      },

      adminSearchPlaceholder: function () {
        return this.S.admin.page === "reviews"
          ? "搜索成果名称 / 教师 / 类型…"
          : "搜索教师 / 学院 / 邮箱…";
      },

      /* ---------------- 成果审核 ---------------- */
      reviewRows: function () { return this.S.admin.reviews || []; },
      reviewStats: function () { return this.S.admin.reviewStats || null; },
      reviewAllStats: function () { return this.S.admin.reviewAllStats || null; },
      reviewTeachers: function () { return this.S.admin.reviewTeachers || []; },
      reviewStatus: function () { return this.S.admin.reviewStatus; },
      reviewTeacher: function () { return this.S.admin.reviewTeacher; },
      reviewSelectedCount: function () { return (this.S.admin.selected || []).length; },

      reviewTabs: function () {
        var s = this.S.admin.reviewAllStats || {};
        var counts = {
          "待审核": s.pending || 0, "已退回": s.rejected || 0,
          "已通过": s.approved || 0, "": s.total || 0
        };
        return REVIEW_TABS.map(function (t) {
          return { key: t.key, text: t.text, tone: t.tone, count: counts[t.key] || 0 };
        });
      },

      /* 已勾选集合（键值查表，避免模板里做数组查找） */
      selectedMap: function () {
        var map = {};
        (this.S.admin.selected || []).forEach(function (k) {
          map[k.teacherId + "|" + k.id] = true;
        });
        return map;
      },

      allRowsSelected: function () {
        var rows = this.S.admin.reviews || [];
        if (!rows.length) return false;
        var map = this.selectedMap;
        for (var i = 0; i < rows.length; i++) {
          if (!map[rows[i].teacherId + "|" + rows[i].id]) return false;
        }
        return true;
      },

      reviewEmptyText: function () {
        if (this.S.admin.reviewLoading) return "正在加载成果数据…";
        if (this.S.admin.reviewQ) return "没有匹配的成果，试试调整关键词";
        if (this.S.admin.reviewStatus === "待审核") return "太好了，当前没有待审核的成果";
        return "当前筛选条件下没有成果";
      },

      adminMeta: function () { return ADMIN_META[this.S.admin.page] || ["管理中心", ""]; },

      adminAvatar: function () {
        var n = String(this.authUser.name || "");
        return n ? n.charAt(0) : "管";
      },

      filteredTeachers: function () {
        var q = String(this.S.admin.q || "").trim().toLowerCase();
        var rows = this.S.admin.rows || [];
        if (!q) return rows;
        return rows.filter(function (t) {
          return [t.name, t.dept, t.email, t.username, t.title, t.office]
            .join(" ").toLowerCase().indexOf(q) >= 0;
        });
      },

      activeCount: function () {
        return (this.S.admin.rows || []).filter(function (t) { return t.active; }).length;
      },

      projectList: function () {
        return (this.d.research.projects && this.d.research.projects.list) || [];
      },

      teachingList: function () {
        return (this.d.teaching && this.d.teaching.list) || [];
      },

      /* ---------------- 成果审核：全局指标 ---------------- */
      reviewKpis: function () {
        var s = this.S.admin.reviewAllStats || {};
        return [
          { icon: "clock", tone: "amber", lab: "待审核成果", val: s.pending || 0, unit: "项",
            hint: "涉及 " + (s.pendingTeachers || 0) + " 位教师" },
          { icon: "seal", tone: "green", lab: "已通过成果", val: s.approved || 0, unit: "项",
            hint: "业绩分 " + (s.approvedScore || 0) },
          { icon: "undo", tone: "red", lab: "已退回成果", val: s.rejected || 0, unit: "项",
            hint: (s.rejectedTeachers || 0) + " 位教师需修改" },
          { icon: "star", tone: "violet", lab: "待审业绩分", val: s.pendingScore || 0, unit: "分",
            hint: "最高单条 " + (s.pendingScoreMax || 0) + " 分" }
        ];
      },

      /* ---------------- 教师统计详情：统一的指标卡数据 ---------------- */
      detailUser: function () {
        return (this.S.admin.detail && this.S.admin.detail.user) || {};
      },

      dAudit: function () { return this.d.audit || {}; },

      auditHistory: function () { return this.dAudit.history || []; },

      /* 名片上的四个核心指标 */
      heroMetrics: function () {
        var s = (this.S.admin.detail && this.S.admin.detail.summary) || {};
        var c = s.counts || {};
        return [
          { lab: "科研项目", val: c.projects || 0, unit: "项" },
          { lab: "成果业绩分", val: s.score || 0, unit: "分", em: true },
          { lab: "教学学时", val: s.teachingHours || c.hours || 0, unit: "学时" },
          { lab: "指导学生", val: c.students || 0, unit: "人" }
        ];
      },

      researchKpis: function () {
        var r = this.d.research || {};
        var p = r.projects || {}, a = r.achievements || {}, l = r.literature || {};
        return [
          { icon: "flask", tone: "blue", lab: "科研项目", val: p.total,
            hint: "主持 " + (p.leading || 0) + " 项 · 在研 " + (p.active || 0) + " 项" },
          { icon: "database", tone: "teal", lab: "项目经费", val: p.funding, unit: "万元",
            hint: "已结题 " + (p.finished || 0) + " 项" },
          { icon: "medal", tone: "violet", lab: "成果总数", val: a.total,
            hint: "已落地 " + (a.published || 0) + " 项" },
          { icon: "star", tone: "amber", lab: "业绩分合计", val: a.score, unit: "分", em: true,
            hint: "文献 " + (l.total || 0) + " 篇" }
        ];
      },

      /* 该教师成果的审核概况（教师详情页 · 科研成果区块内） */
      auditKpis: function () {
        var u = this.dAudit || {};
        return [
          { icon: "seal", tone: "green", lab: "已通过", val: u.approved,
            hint: "占全部成果 " + (u.approveRate || 0) + "%" },
          { icon: "clock", tone: "amber", lab: "待审核", val: u.pending,
            hint: "待审业绩分 " + (u.pendingScore || 0) },
          { icon: "undo", tone: "red", lab: "已退回", val: u.rejected,
            hint: "需教师修改后重提" },
          { icon: "star", tone: "violet", lab: "已通过业绩分", val: u.approvedScore, unit: "分" }
        ];
      },

      exchangeKpis: function () {
        var x = this.d.exchanges || {};
        return [
          { icon: "globe", tone: "blue", lab: "交流总数", val: x.total,
            hint: "本年度 " + (x.thisYear || 0) + " 次" },
          { icon: "send", tone: "teal", lab: "已确认 / 进行中", val: x.upcoming },
          { icon: "check", tone: "green", lab: "已完成", val: x.finished },
          { icon: "star", tone: "amber", lab: "国际交流", val: x.international,
            hint: "合作机构 " + (x.organizers || 0) + " 家" }
        ];
      },

      teachingKpis: function () {
        var g = this.d.teaching || {};
        return [
          { icon: "clipboard", tone: "blue", lab: "教学任务", val: g.tasks,
            hint: "进行中 " + (g.ongoing || 0) + " 门" },
          { icon: "cap", tone: "violet", lab: "课程资源", val: g.courses },
          { icon: "clock", tone: "teal", lab: "学时合计", val: g.hours, unit: "学时",
            hint: "学生 " + (g.students || 0) + " 人次" },
          { icon: "star", tone: "amber", lab: "评教均分", val: g.evalAvg === null || g.evalAvg === undefined ? "—" : g.evalAvg,
            em: true }
        ];
      },

      studentKpis: function () {
        var s = this.d.students || {};
        return [
          { icon: "users", tone: "blue", lab: "指导学生", val: s.total,
            hint: "硕士 " + (s.master || 0) + " · 博士 " + (s.phd || 0) },
          { icon: "target", tone: "teal", lab: "平均进度", val: s.avgProgress, unit: "%" },
          { icon: "check", tone: "green", lab: "里程碑完成率", val: (s.milestones || {}).rate, unit: "%",
            hint: "共 " + ((s.milestones || {}).total || 0) + " 项" },
          { icon: "bell", tone: "amber", lab: "本周待沟通", val: s.needMeeting, unit: "人" }
        ];
      },

      /* 学生进度条 + 里程碑概况 */
      studentNeedList: function () { return (this.d.students && this.d.students.needMeetingList) || []; },

      /* 环形图：成果类型分布（取前 5 项，其余合并） */
      typeRing: function () {
        var src = (this.d.research && this.d.research.achievements && this.d.research.achievements.byType) || {};
        return this.buildRing(src);
      },

      levelRing: function () {
        var src = (this.d.research && this.d.research.achievements && this.d.research.achievements.byLevel) || {};
        return this.buildRing(src);
      },

      /* 柱状图：近四年成果 / 交流 */
      yearBars: function () {
        var src = (this.d.research && this.d.research.achievements && this.d.research.achievements.byYear) || {};
        return this.buildBars(src);
      },

      exchangeStatusBars: function () {
        var src = (this.d.exchanges && this.d.exchanges.byStatus) || {};
        return this.buildBars(src);
      },

      teachingStageBars: function () {
        var src = (this.d.teaching && this.d.teaching.byStage) || {};
        return this.buildBars(src);
      },

      studentStageBars: function () {
        var src = (this.d.students && this.d.students.byStage) || {};
        return this.buildBars(src);
      },

      /* ---------------- 教师工作台 ---------------- */
      ready: function () { return this.S.ready; },
      profile: function () { return this.S.profile; },
      stats: function () { return this.S.stats; },
      route: function () { return this.S.page; },

      /* 详情页高亮其所属列表页 */
      navParent: function () { return U.NAV_PARENT[this.S.page] || this.S.page; },

      meta: function () { return U.PAGE_META[this.S.page] || ["教师工作台", ""]; },

      pageComponent: function () {
        return (FWB.pages && FWB.pages[this.S.page]) || Fallback;
      },

      avatarChar: function () {
        var n = String(this.profile.name || "");
        return n ? n.charAt(0) : "师";
      },

      /* 顶栏搜索框（双向绑定到全局状态） */
      searchQ: {
        get: function () { return this.S.searchQ; },
        set: function (v) { this.S.searchQ = v; }
      },

      /* 快捷新建菜单开关（映射到 UI 状态） */
      quickMenu: {
        get: function () { return this.UI.quickMenu; },
        set: function (v) { this.UI.quickMenu = v; }
      }
    },

    methods: {
      /* ---------------- 认证 ---------------- */
      doLogout: async function () {
        await this.act.logout();
        this.act.toast("已退出登录", "info");
      },

      /* ---------------- 教师端 ---------------- */
      go: function (key) { this.act.go(key); },

      /* 导航徽标：0 时返回 null 以隐藏 */
      navCount: function (key) {
        var d = this.S.data;
        var n = null;
        switch (key) {
          case "projects":
            n = (d.projects || []).filter(function (p) { return p.status !== "已结题"; }).length; break;
          case "literature":
            n = (d.literature || []).filter(function (l) { return l.status !== "已读"; }).length; break;
          case "students":
            n = (d.students || []).length; break;
          case "exchanges":
            n = (d.exchanges || []).filter(function (x) {
              return x.status !== "已完成" && x.status !== "已取消";
            }).length; break;
          case "teachings":
            n = (d.teachings || []).filter(function (g) {
              return g.stage !== "已完成" && g.stage !== "结课归档";
            }).length; break;
          case "achievements":
            n = (d.achievements || []).length; break;
          case "developments":
            n = (d.developments || []).filter(function (x) { return x.status !== "已完成"; }).length; break;
          default:
            n = null;
        }
        return n ? n : null;
      },

      openSettings: function () { this.forms.openSettings(); },

      /* 界面配色：随时可切换（教师端 / 管理端通用） */
      openTheme: function () {
        this.act.openModal({
          component: "fwb-theme-picker",
          title: "界面配色",
          props: { modal: true }
        });
      },

      runQuick: function (q) {
        this.quickMenu = false;
        this.forms.openForm(q.kind, null);
      },

      async doSearch() {
        var q = String(this.searchQ || "").trim();
        if (!q) { this.act.toast("请输入搜索关键词", "warn"); return; }
        try {
          await this.act.search(q);
          this.forms.openSearch(this.S.searchResults || [], q);
        } catch (e) {
          this.act.toast("搜索失败：" + (e.message || e), "error");
        }
      },

      /* ---------------- 管理端 ---------------- */
      avatarColor: function (name) { return U.avatarColor(name); },

      /* 管理端导航：进入成果审核时按当前筛选加载 */
      adminNav: function (page) {
        this.act.adminGo(page);
        if (page === "reviews") this.loadReviews();
      },

      auditTone: function (status) { return AUDIT_TONE[status] || "gray"; },

      /* ISO 时间 → 友好显示（2026-10-08T11:06:40 → 2026-10-08 11:06） */
      fmtTime: function (value) {
        var s = String(value || "");
        var m = s.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
        return m ? m[1] + " " + m[2] : (s || "—");
      },

      /* 统计分布 → 带百分比的降序行，供条形图渲染 */
      distRows: function (obj) {
        if (!obj) return [];
        var rows = Object.keys(obj).map(function (k) {
          return { k: k, v: Number(obj[k]) || 0 };
        }).sort(function (a, b) { return b.v - a.v || a.k.localeCompare(b.k); });
        var max = rows.reduce(function (m, r) { return Math.max(m, r.v); }, 0);
        return rows.map(function (r) {
          return { k: r.k, v: r.v, pct: max > 0 ? Math.max(4, Math.round(r.v / max * 100)) : 0 };
        });
      },

      /* 环形图数据：按占比切分圆周 */
      buildRing: function (obj) {
        var rows = Object.keys(obj || {}).map(function (k) {
          return { k: k, v: Number(obj[k]) || 0 };
        }).sort(function (a, b) { return b.v - a.v || a.k.localeCompare(b.k); });
        var shown = rows.slice(0, 6);
        if (rows.length > 6) {
          var rest = rows.slice(6).reduce(function (s, r) { return s + r.v; }, 0);
          if (rest > 0) shown.push({ k: "其他", v: rest });
        }
        var total = shown.reduce(function (s, r) { return s + r.v; }, 0);
        var C = 2 * Math.PI * 52;
        var acc = 0;
        var slices = shown.map(function (r, i) {
          var pct = total ? r.v / total * 100 : 0;
          var seg = {
            k: r.k, v: r.v, pct: Math.round(pct * 10) / 10,
            color: RING_COLORS[i % RING_COLORS.length],
            dash: (pct / 100 * C).toFixed(2),
            offset: (-acc / 100 * C).toFixed(2)
          };
          acc += pct;
          return seg;
        });
        return { total: total, slices: slices, circumference: C.toFixed(2) };
      },

      /* 柱状图数据：横向条形，最大值为满格 */
      buildBars: function (obj) {
        var rows = Object.keys(obj || {}).map(function (k) {
          return { k: k, v: Number(obj[k]) || 0 };
        });
        var max = rows.reduce(function (m, r) { return Math.max(m, r.v); }, 0);
        return {
          max: max,
          rows: rows.map(function (r) {
            return { k: r.k, v: r.v,
                     pct: max > 0 && r.v > 0 ? Math.max(8, Math.round(r.v / max * 100)) : 0 };
          })
        };
      },

      /* 详情页锚点：滚动到指定统计分区 */
      scrollToSection: function (id) {
        var box = document.querySelector(".content");
        var el = document.getElementById(id);
        if (!box || !el) return;
        box.scrollTo({ top: el.offsetTop - 12, behavior: "smooth" });
      },

      newTeacher: function () { this.forms.openTeacherForm(null); },
      editTeacher: function (t) { this.forms.openTeacherForm(t); },
      resetPwd: function (t) { this.forms.openResetPwd(t); },

      /* ---------------- 成果审核 ---------------- */
      loadReviews: function () {
        var self = this;
        return this.act.loadReviews().catch(function (e) {
          self.act.toast("加载成果失败：" + (e.message || e), "error");
        });
      },

      setReviewStatus: function (key) {
        this.S.admin.reviewStatus = key;
        this.act.reviewClearSelection();
        this.loadReviews();
      },

      setReviewTeacher: function (id) {
        this.S.admin.reviewTeacher = id || "";
        this.act.reviewClearSelection();
        this.loadReviews();
      },

      toggleRow: function (row) {
        var key = row.teacherId + "|" + row.id;
        this.act.reviewToggleSelect(row.teacherId, row.id, !this.selectedMap[key]);
      },

      toggleSelectAll: function () {
        this.act.reviewSelectAll(this.reviewRows, !this.allRowsSelected);
      },

      openReviewDetail: function (row) {
        this.S.admin.reviewDetail = row;
        this.act.openModal({
          component: "fwb-review-detail",
          title: "成果审核详情",
          wide: true,
          props: { row: row }
        });
      },

      /* 单条审核：通过 / 退回 / 撤回 */
      reviewOne: async function (row, action, note) {
        try {
          await this.act.reviewOne(row.teacherId, row.id, action, note);
          var word = action === "approve" ? "已通过" : (action === "reject" ? "已退回" : "已撤回审核");
          this.act.toast(word + "：" + row.title, action === "reject" ? "warn" : "success");
        } catch (e) {
          this.act.toast("审核失败：" + (e.message || e), "error");
        }
      },

      approve: function (row) { return this.reviewOne(row, "approve", ""); },

      reject: async function (row) {
        var self = this;
        var state = { note: "" };
        var done = await this.act.confirm({
          title: "退回成果",
          msg: "退回后 " + row.teacherName + " 会在成果管理中看到审核意见，可在修改后重新提交。",
          btn: "确认退回",
          input: { placeholder: "请填写退回原因（必填，教师可见）", required: true, key: "note" },
          state: state
        });
        if (!done) return;
        if (!state.note) { this.act.toast("请填写退回原因", "warn"); return; }
        self.reviewOne(row, "reject", state.note);
      },

      resetReview: async function (row) {
        var yes = await this.act.confirm({
          title: "撤回审核", msg: "将「" + row.title + "」重新置为待审核状态。", btn: "确认撤回"
        });
        if (!yes) return;
        this.reviewOne(row, "reset", "");
      },

      /* 批量审核 */
      batchReview: async function (action) {
        var self = this;
        var items = this.S.admin.selected || [];
        if (!items.length) { this.act.toast("请先勾选要审核的成果", "warn"); return; }
        var word = action === "approve" ? "通过" : "退回";
        var state = { note: "" };
        var done = await this.act.confirm({
          title: "批量" + word + "成果",
          msg: "将对已勾选的 " + items.length + " 条成果执行「" + word + "」操作。",
          btn: "确认" + word,
          danger: action !== "approve",
          input: action === "reject"
            ? { placeholder: "请填写退回原因（必填，教师可见）", required: true, key: "note" }
            : { placeholder: "审核备注（选填）", key: "note" },
          state: state
        });
        if (!done) return;
        if (action === "reject" && !state.note) { this.act.toast("请填写退回原因", "warn"); return; }
        try {
          var res = await this.act.reviewBatch(items, action, state.note);
          this.act.reviewClearSelection();
          this.act.toast("已" + word + " " + res.reviewed + " 条成果", "success");
        } catch (e) {
          self.act.toast("批量审核失败：" + (e.message || e), "error");
        }
      },

      // 教师详情：一键跳到该教师的成果审核
      reviewOfTeacher: function () {
        var u = this.detailUser;
        this.S.admin.reviewTeacher = u.id || "";
        this.S.admin.reviewStatus = "待审核";
        this.act.reviewClearSelection();
        this.act.adminGo("reviews");
        this.loadReviews();
      },

      toggleActive: async function (t) {
        var yes = await this.act.confirm({
          title: t.active ? "停用账号" : "启用账号",
          msg: (t.active ? "停用后 " : "启用后 ") + t.name + " 将" +
               (t.active ? "无法登录工作台，其数据仍会保留。" : "可以重新登录工作台。"),
          btn: t.active ? "确认停用" : "确认启用"
        });
        if (!yes) return;
        try {
          await this.act.adminUpdateTeacher(t.id, { active: !t.active });
          this.act.toast(t.active ? "已停用 " + t.name : "已启用 " + t.name, "success");
        } catch (e) {
          this.act.toast("操作失败：" + (e.message || e), "error");
        }
      },

      removeTeacher: async function (t) {
        var yes = await this.act.confirm({
          title: "删除教师账号",
          msg: "将删除「" + t.name + "」的账号及其全部工作台数据（项目、文献、学生、成果等），" +
               "该操作不可撤销。",
          btn: "确认删除"
        });
        if (!yes) return;
        try {
          await this.act.adminDeleteTeacher(t.id);
          this.act.toast("已删除 " + t.name, "success");
        } catch (e) {
          this.act.toast("删除失败：" + (e.message || e), "error");
        }
      },

      /* ---------------- 通用交互 ---------------- */
      onDocClick: function (ev) {
        if (!this.quickMenu) return;
        var t = ev.target;
        if (t && t.closest && t.closest(".quick-menu, #quickBtn")) return;
        this.quickMenu = false;
      },

      onKey: function (ev) {
        if (ev.key === "Escape") {
          if (this.UI.modal.open) this.act.closeModal();
          this.quickMenu = false;
          return;
        }
        if ((ev.ctrlKey || ev.metaKey) && String(ev.key).toLowerCase() === "k") {
          ev.preventDefault();
          var input = document.querySelector(".search-box input");
          if (input) input.focus();
        }
      }
    },

    watch: {
      /* 成果审核页的关键词检索：防抖 300ms，避免逐字打请求 */
      "S.admin.reviewQ": function (val, old) {
        if (val === old) return;
        if (this.S.admin.page !== "reviews") return;
        var self = this;
        clearTimeout(this._rqTimer);
        this._rqTimer = setTimeout(function () { self.loadReviews(); }, 300);
      }
    },

    mounted: function () {
      var self = this;
      /* 供弹窗等子组件回调根组件上的业务动作（如审核后的列表刷新） */
      FWB.root = self;
      document.addEventListener("click", this.onDocClick);
      document.addEventListener("keydown", this.onKey);

      /* 先确认登录态，再按角色加载数据 */
      this.act.checkAuth().then(function (user) {
        if (!user) return;
        if (user.role === "admin") return self.act.loadAdmin();
        return self.act.loadAll();
      }).catch(function (e) {
        self.act.toast("加载失败：" + (e.message || e), "error");
      });
    },

    beforeUnmount: function () {
      document.removeEventListener("click", this.onDocClick);
      document.removeEventListener("keydown", this.onKey);
    },

    template: document.getElementById("app").innerHTML
  };

  /* ---------------------------- 启动应用 ---------------------------- */
  var app = Vue.createApp(App);

  /* 全局注册通用组件（含 FwbToolRunner / FwbSettings） */
  Object.keys(FWB.components).forEach(function (name) {
    app.component(name, FWB.components[name]);
  });
  /* 登录页（整屏视图，直接用在根模板里） */
  app.component("page-login", FWB.pages.login);
  app.component("fwb-page-missing", Fallback);

  /* 暴露全局状态，便于调试与组件内部按需访问 */
  app.config.globalProperties.$S = FWB.store.state;
  app.config.globalProperties.$ui = FWB.store.ui;
  app.config.globalProperties.$act = FWB.store.act;

  global.FWB.app = app;
  app.mount("#app");

  /* 挂载完成后移除 v-cloak（该属性在容器上，不随模板渲染自动清除） */
  var mountEl = document.getElementById("app");
  if (mountEl) mountEl.removeAttribute("v-cloak");
})(window);
