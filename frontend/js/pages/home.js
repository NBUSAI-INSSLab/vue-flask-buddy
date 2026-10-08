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
    { label: "学生指导", icon: "users", tone: "green", action: "nav-students" }
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
      allSites: function () {
        return this.act.list("links").slice().sort(function (a, b) {
          var d = (Number(a.sort) || 0) - (Number(b.sort) || 0);
          return d !== 0 ? d : String(a.name || "").localeCompare(String(b.name || ""));
        });
      },
      /* 管理模式下显示全部（便于拖动排序），平时按分组过滤 */
      sites: function () {
        if (this.siteEdit || this.siteGroup === "all") return this.allSites;
        var g = this.siteGroup;
        return this.allSites.filter(function (s) { return (s.group || "其他") === g; });
      },
      siteTabs: function () {
        var counts = {};
        this.allSites.forEach(function (s) {
          var g = s.group || "其他";
          counts[g] = (counts[g] || 0) + 1;
        });
        var order = U.LINK_GROUPS;
        return order.filter(function (g) { return counts[g]; }).map(function (g) {
          return { key: g, label: g, count: counts[g] };
        });
      },
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

      /* 常用网站（手动维护 + 自动抓取图标） */
      '  <section class="card site-section">' +
      '    <div class="card-head">' +
      '      <h3><span class="ch-ico"><fwb-icon name="globe"/></span>常用网站' +
      '        <small class="sh-count" v-if="allSites.length">共 {{ allSites.length }} 个</small></h3>' +
      '      <div class="site-tools">' +
      '        <template v-if="siteEdit">' +
      '          <button class="btn ghost sm" @click="addSite"><fwb-icon name="plus"/>添加网站</button>' +
      '          <button class="btn primary sm" @click="siteEdit = false"><fwb-icon name="check"/>完成</button>' +
      "        </template>" +
      '        <button v-else class="btn ghost sm" @click="siteEdit = true"><fwb-icon name="edit"/>管理网站</button>' +
      "      </div>" +
      "    </div>" +
      '    <div class="card-body">' +
      '      <div class="site-tabs" v-if="siteTabs.length > 1 && !siteEdit">' +
      '        <button class="site-tab" :class="{ on: siteGroup === \'all\' }" @click="siteGroup = \'all\'">' +
      "          全部<b>{{ allSites.length }}</b></button>" +
      '        <button v-for="t in siteTabs" :key="t.key" class="site-tab"' +
      '                :class="{ on: siteGroup === t.key }" @click="siteGroup = t.key">' +
      "          {{ t.label }}<b>{{ t.count }}</b></button>" +
      "      </div>" +

      '      <div v-if="!allSites.length" class="empty" style="padding:30px 0">' +
      '        <fwb-icon name="globe" :size="38"/><p>还没有常用网站，添加后可一键直达</p>' +
      '        <button class="btn ghost sm mt-2" @click="addSite"><fwb-icon name="plus"/>添加网站</button>' +
      "      </div>" +
      '      <div v-else-if="!sites.length" class="empty" style="padding:30px 0"><p>该分组下暂无网站</p></div>' +

      '      <div v-else class="site-grid">' +
      '        <div v-for="s in sites" :key="s.id" class="site-card"' +
      '             :class="{ editing: siteEdit, dragging: dragId === s.id, over: overId === s.id }"' +
      '             :title="siteTip(s)" :draggable="siteEdit"' +
      '             @dragstart="onDragStart(s, $event)" @dragover.prevent="onDragOver(s, $event)"' +
      '             @drop.prevent="onDrop(s, $event)" @dragend="onDragEnd">' +
      '          <a class="sc-link" :href="s.url" target="_blank" rel="noopener noreferrer"' +
      '             @click="onSiteClick($event)">' +
      '            <span class="sc-ico">' +
      '              <span class="sc-fb" :style="{ background: U.siteTone(s.name, s.url) }">{{ U.siteLetter(s.name, s.url) }}</span>' +
      '              <img v-if="!iconFailed[s.id]" :key="s.url" :src="iconOf(s)" :alt="s.name"' +
      '                   @load="iconOk[s.id] = true" :class="{ on: iconOk[s.id] }"' +
      '                   @error="iconFailed[s.id] = true">' +
      "            </span>" +
      '            <span class="sc-meta">' +
      '              <b class="sc-name">{{ s.name }}</b>' +
      '              <small class="sc-host">{{ U.siteHost(s.url) }}</small>' +
      "            </span>" +
      '            <span class="sc-go" v-if="!siteEdit"><fwb-icon name="external"/></span>' +
      "          </a>" +
      '          <span class="sc-ops" v-if="siteEdit">' +
      '            <button class="sc-op" title="编辑" @click="editSite(s)"><fwb-icon name="edit"/></button>' +
      '            <button class="sc-op del" title="删除" @click="delSite(s)"><fwb-icon name="trash"/></button>' +
      "          </span>" +
      "        </div>" +
      '        <button v-if="siteEdit" class="site-card site-add" @click="addSite">' +
      '          <fwb-icon name="plus"/><span>添加网站</span></button>' +
      "      </div>" +

      '      <p class="site-hint" v-if="siteEdit">' +
      '        <fwb-icon name="info"/>拖动卡片可调整顺序；图标由服务端自动抓取并缓存，抓不到时显示首字母头像。</p>' +
      "    </div>" +
      "  </section>" +
      "</div>",
    data: function () {
      return {
        QUICK: QUICK,
        siteEdit: false,     // 是否处于「管理」模式
        siteGroup: "all",    // 当前分组筛选
        dragId: "",          // 正在拖动的网站 id
        overId: "",          // 拖动悬停的目标网站 id
        iconOk: {},          // 图标加载成功（渐显）
        iconFailed: {}       // 图标加载失败（保留首字母头像）
      };
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
      },

      /* ---------------- 常用网站 ---------------- */
      iconOf: function (s) { return FWB.api.links.iconUrl(s.url, s.name); },
      siteTip: function (s) {
        return s.name + (s.note ? " · " + s.note : "") + "\n" + s.url;
      },
      /* 管理模式：链接不跳转，避免误点离开工作台 */
      onSiteClick: function (ev) { if (this.siteEdit) ev.preventDefault(); },

      openLinkForm: function (link) {
        this.act.openModal({
          component: "fwb-link-edit",
          title: link ? "编辑网站" : "添加网站",
          props: { link: link, groups: U.LINK_GROUPS }
        });
      },
      addSite: function () { this.openLinkForm(null); },
      editSite: function (s) { this.openLinkForm(s); },

      delSite: async function (s) {
        var self = this;
        await this.act.confirmDelete("确定从首页移除「" + s.name + "」吗？", async function () {
          await self.act.removeSiteLink(s.id);
        });
        // 删掉的正好是当前筛选分组里的最后一个 → 回到「全部」，避免看到空列表
        if (this.siteGroup !== "all" && !this.allSites.some(function (x) {
          return (x.group || "其他") === self.siteGroup;
        })) this.siteGroup = "all";
      },

      /* ---------------- 拖动排序 ---------------- */
      onDragStart: function (s, ev) {
        if (!this.siteEdit) return;
        this.dragId = s.id;
        if (ev.dataTransfer) {
          ev.dataTransfer.effectAllowed = "move";
          try { ev.dataTransfer.setData("text/plain", s.id); } catch (e) { /* 忽略 */ }
        }
      },
      onDragOver: function (s) {
        if (!this.siteEdit || !this.dragId || this.dragId === s.id) return;
        this.overId = s.id;
      },
      onDrop: function (s) {
        var from = this.dragId;
        this.onDragEnd();
        if (!this.siteEdit || !from || from === s.id) return;
        var ids = this.allSites.map(function (x) { return x.id; });
        var fi = ids.indexOf(from), ti = ids.indexOf(s.id);
        if (fi < 0 || ti < 0) return;
        ids.splice(ti, 0, ids.splice(fi, 1)[0]);
        this.act.reorderSiteLinks(ids).catch(function (e) {
          FWB.store.act.toast("排序保存失败：" + ((e && e.message) || e), "error");
        });
      },
      onDragEnd: function () { this.dragId = ""; this.overId = ""; }
    }
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.dashboard = Home;
})(window);
