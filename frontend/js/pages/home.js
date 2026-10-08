/* =====================================================================
   pages/home.js —— 工作首页
   ===================================================================== */
(function (global) {
  "use strict";

  var vue = global.Vue;
  var FWB = global.FWB;
  var U = FWB.util;

  var QUICK = [
    { label: "新建项目", icon: "flask", tone: "blue", action: "form-project" },
    { label: "新增文献", icon: "book", tone: "violet", action: "form-literature" },
    { label: "登记成果", icon: "medal", tone: "amber", action: "form-achievement" },
    { label: "记日程", icon: "calendar", tone: "green", action: "form-event" },
    { label: "加待办", icon: "check", tone: "indigo", action: "form-todo" },
    { label: "学术交流", icon: "globe", tone: "teal", action: "nav-exchanges" },
    { label: "常用工具", icon: "wrench", tone: "amber", action: "nav-tools" },
    { label: "学生指导", icon: "users", tone: "green", action: "nav-students" },
    { label: "常用网站", icon: "link", tone: "blue", action: "nav-links" }
  ];

  var Home = {
    name: "PageHome",
    setup: function () {
      var store = FWB.store;
      return { S: store.state, act: store.act, U: U, forms: FWB.forms };
    },
    computed: {
      teacherName: function () { return ((this.S.profile && this.S.profile.name) || "老师").charAt(0); },
      greet: function () { return U.greeting(); },
      todayLabel: function () { return U.cnDate(U.today()); },
      todayEvents: function () {
        var t = U.today();
        return this.act.list("events")
          .filter(function (e) { return e.date === t; })
          .sort(function (a, b) { return String(a.start || "").localeCompare(String(b.start || "")); });
      },
      openTodos: function () {
        return this.act.list("todos").filter(function (t) { return !t.done; });
      },
      projects: function () {
        return this.act.list("projects").slice()
          .sort(function (a, b) { return String(a.deadline || "").localeCompare(String(b.deadline || "")); })
          .slice(0, 4);
      },

      /* ---------------- 常用网站 ---------------- */
      /* 网站导航已拆为独立页面（发展区 → 常用网站），首页只保留概览与快捷入口 */

      statCards: function () {
        var st = this.S.stats;
        return [
          { key: "projects", label: "在研项目", value: st.activeProjects || 0, unit: "项", icon: "flask", tone: "blue" },
          { key: "students", label: "指导学生", value: st.students || 0, unit: "人", icon: "users", tone: "violet" },
          { key: "literature", label: "待读文献", value: st.unreadLits || 0, unit: "篇", icon: "book", tone: "green" },
          { key: "schedule", label: "本周日程", value: st.weekEvents || 0, unit: "项", icon: "calendar", tone: "amber" }
        ];
      }
    },
    template:
      "<div>" +
      /* 问候横幅 */
      '  <section class="hero"><div class="hero-inner">' +
      '    <div><div class="hero-greet">{{ greet }}，<span>{{ teacherName }}老师</span></div>' +
      '      <div class="hero-sub">{{ todayLabel }} · 今天有 {{ todayEvents.length }} 项日程、{{ openTodos.length }} 项待办待处理</div></div>' +
      '    <div class="hero-chips">' +
      '      <div class="hero-chip"><span class="hc-ico"><fwb-icon name="flask"/></span>' +
      '        <div><b>{{ S.stats.activeProjects || 0 }}</b> <small>在研项目</small></div></div>' +
      '      <div class="hero-chip"><span class="hc-ico"><fwb-icon name="users"/></span>' +
      '        <div><b>{{ S.stats.students || 0 }}</b> <small>指导学生</small></div></div>' +
      '      <div class="hero-chip"><span class="hc-ico"><fwb-icon name="book"/></span>' +
      '        <div><b>{{ S.stats.unreadLits || 0 }}</b> <small>待读文献</small></div></div>' +
      "    </div></div></section>" +

      /* 统计卡 */
      '  <div class="stat-grid">' +
      '    <div v-for="c in statCards" :key="c.key" class="stat-card" @click="act.go(c.key)">' +
      '      <div class="stat-ico" :class="c.tone"><fwb-icon :name="c.icon"/></div>' +
      '      <div class="stat-info"><div class="stat-val">{{ c.value }}<small>{{ c.unit }}</small></div>' +
      '        <div class="stat-label">{{ c.label }}</div></div>' +
      "    </div>" +
      "  </div>" +

      '  <div class="dash-grid">' +
      '    <div class="dash-col">' +
      /* 今日时间线 */
      '      <div class="card"><div class="card-head"><h3><span class="ch-ico"><fwb-icon name="clock"/></span>今日日程</h3>' +
      '        <span class="more" @click="act.go(\'schedule\')">查看全部<fwb-icon name="right"/></span></div>' +
      '        <div class="card-body">' +
      '          <div v-if="!todayEvents.length" class="empty" style="padding:26px 0"><p>今天没有安排，可专注科研与备课</p></div>' +
      '          <div class="timeline">' +
      '            <div v-for="e in todayEvents" :key="e.id" class="tl-item" :class="{ done: e.done }">' +
      '              <div class="tl-time">{{ e.start || "--:--" }}<small>{{ e.end || "" }}</small></div>' +
      '              <div class="tl-dot" :style="{ color: dotColor(e.type) }"></div>' +
      '              <div class="tl-body"><div class="tl-title">{{ e.title }}</div>' +
      '                <div class="tl-meta">' +
      '                  <span v-if="e.location"><fwb-icon name="pin"/>{{ e.location }}</span>' +
      '                  <span v-if="e.note">{{ e.note }}</span>' +
      "                </div></div></div>" +
      "          </div>" +
      "        </div></div>" +

      /* 项目进度 */
      '      <div class="card"><div class="card-head"><h3><span class="ch-ico"><fwb-icon name="flask"/></span>项目进度</h3>' +
      '        <span class="more" @click="act.go(\'projects\')">全部项目<fwb-icon name="right"/></span></div>' +
      '        <div class="card-body">' +
      '          <div v-if="!projects.length" class="empty" style="padding:26px 0"><p>暂无项目</p></div>' +
      '          <div v-for="p in projects" :key="p.id" class="proj-prog-item">' +
      '            <div class="pp-top"><div class="pp-name"><span class="dot"></span>{{ p.name }}</div>' +
      '              <div class="pp-pct">{{ p.progress || 0 }}%</div></div>' +
      '            <fwb-progress :value="p.progress || 0"/>' +
      '            <div class="pp-bottom"><span class="pp-due">截止 {{ p.deadline || "—" }}</span>' +
      '              <span class="pp-due" :class="dueClass(p.deadline)">{{ U.dueText(p.deadline) }}</span></div>' +
      "          </div>" +
      "        </div></div>" +
      "    </div>" +

      '    <div class="dash-col">' +
      /* 待办 */
      '      <div class="card"><div class="card-head"><h3><span class="ch-ico"><fwb-icon name="check"/></span>待办事项</h3>' +
      '        <span class="more" @click="forms.openForm(\'todo\', null)">新增<fwb-icon name="plus"/></span></div>' +
      '        <div class="card-body">' +
      '          <div v-if="!openTodos.length" class="empty" style="padding:26px 0"><p>没有待办，节奏很好</p></div>' +
      '          <div v-for="t in openTodos" :key="t.id" class="todo-item" :class="{ done: t.done }">' +
      '            <div class="todo-check" @click="toggleTodo(t)"><fwb-icon name="check"/></div>' +
      '            <div class="todo-body"><div class="todo-title">{{ t.title }}</div>' +
      '              <div class="todo-meta"><span class="pri" :class="priClass(t.priority)">{{ U.PRIORITY[t.priority] || "中" }}</span>' +
      '                <span>{{ U.dueText(t.due) }}</span><span v-if="t.tag">· {{ t.tag }}</span></div></div>' +
      "          </div>" +
      "        </div></div>" +

      /* 快捷入口 */
      '      <div class="card"><div class="card-head"><h3><span class="ch-ico"><fwb-icon name="sparkle"/></span>快捷入口</h3></div>' +
      '        <div class="card-body"><div class="quick-grid">' +
      '          <div v-for="q in QUICK" :key="q.label" class="quick-tile" @click="runQuick(q)">' +
      '            <div class="qt-ico" :class="\'tone-\' + q.tone"><fwb-icon :name="q.icon"/></div>' +
      '            <div class="qt-label">{{ q.label }}</div>' +
      "          </div>" +
      "        </div></div></div>" +
      "    </div>" +
      "  </div>" +
      "</div>",
    data: function () {
      return { QUICK: QUICK };
    },
    methods: {
      dotColor: function (type) {
        return {
          "上课": "var(--primary)", "组会": "var(--violet)", "会议": "var(--amber)",
          "答辩": "var(--teal)", "申报": "var(--indigo)"
        }[type] || "var(--text-3)";
      },
      priClass: function (p) { return p === "high" ? "high" : p === "low" ? "low" : "mid"; },
      dueClass: function (d) {
        var n = U.daysUntil(d);
        if (n === null) return "";
        if (n < 0) return "urgent";
        if (n <= 7) return "warn";
        return "";
      },
      async toggleTodo(t) {
        await this.act.update("todos", t.id, { done: !t.done });
        await this.act.refreshStats();
      },
      runQuick: function (q) {
        if (q.action.indexOf("form-") === 0) this.forms.openForm(q.action.slice(5), null);
        else if (q.action.indexOf("nav-") === 0) this.act.go(q.action.slice(4));
      }
    }
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.dashboard = Home;
})(window);
