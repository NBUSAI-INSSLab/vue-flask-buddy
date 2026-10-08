/* =====================================================================
   store.js —— 全局响应式状态 + 动作
   通过 app.config.globalProperties 暴露为 $S（数据）/ $ui（界面）/ $act（动作）
   ===================================================================== */
(function (global) {
  "use strict";

  var vue = global.Vue;
  var api = global.FWB.api;
  var U = global.FWB.util;

  /* -------------------- 数据状态 -------------------- */
  var state = vue.reactive({
    ready: false,

    /* 登录态：user 为 null 表示未登录 */
    auth: { user: null, checked: false },

    /* 管理端状态（仅管理员使用） */
    admin: {
      page: "overview",     // overview | teachers | teacher | reviews
      detailId: "",
      rows: [],             // 教师列表（含 summary）
      totals: null,         // 全校汇总
      detail: null,         // 某位教师的统计详情
      loading: false,
      q: "",

      /* 成果审核 */
      reviews: [],          // 当前筛选条件下的成果清单
      reviewStats: null,    // 当前筛选条件下的统计
      reviewAllStats: null, // 全部成果的统计（不受筛选影响）
      reviewTeachers: [],   // 教师筛选项
      reviewLoading: false,
      reviewStatus: "待审核",// 待审核 | 已通过 | 已退回 | ""
      reviewTeacher: "",
      reviewQ: "",
      selected: [],         // 已勾选的成果 [{teacherId, id}]
      reviewDetail: null    // 审核详情弹窗中的成果
    },

    profile: {},
    courseShare: null,   // 当前课程详情页的开放概况（令牌 / 可见性 / 资料计数）
    cv: null,            // 个人简历发布概况（固定链接 / 公开开关 / 区块开关与条目数）
    data: {
      projects: [], literature: [], courses: [], students: [], events: [], todos: [],
      exchanges: [], teachings: [], achievements: [], developments: [], tools: [], tool_runs: [],
      educations: [], services: [],
      links: []
    },
    stats: {},
    specs: {},
    // 视图状态
    page: "dashboard",
    detailId: "",
    filters: { lit: "all", exch: "all", teach: "all", ach: "all", dev: "all", tool: "all", project: "all" },
    searchQ: "",
    searchResults: null,
    toolResult: null,
    toolRunning: false
  });

  /* -------------------- 界面状态 -------------------- */
  var ui = vue.reactive({
    modal: { open: false, title: "", wide: false, body: "", foot: "", component: null, props: {} },
    toasts: [],
    quickMenu: false
  });

  var toastSeq = 0;

  var actions = {
    /* ---------------- 认证 ---------------- */
    async checkAuth() {
      try {
        var res = await api.auth.me();
        state.auth.user = res.user;
      } catch (e) {
        state.auth.user = null;
      }
      state.auth.checked = true;
      return state.auth.user;
    },

    async login(username, password) {
      var res = await api.auth.login(username, password);
      state.auth.user = res.user;
      state.auth.checked = true;
      if (res.user.role === "admin") {
        await actions.loadAdmin();
      } else {
        await actions.loadAll();
      }
      return res.user;
    },

    async register(payload) {
      var res = await api.auth.register(payload);
      state.auth.user = res.user;
      state.auth.checked = true;
      await actions.loadAll();
      return res.user;
    },

    async logout() {
      try { await api.auth.logout(); } catch (e) { /* 忽略：本地状态照样清理 */ }
      state.auth.user = null;
      state.ready = false;
      state.admin.page = "overview";
      state.admin.detailId = "";
      state.admin.rows = [];
      state.admin.totals = null;
      state.admin.detail = null;
      state.admin.reviews = [];
      state.admin.reviewStats = null;
      state.admin.reviewAllStats = null;
      state.admin.reviewTeachers = [];
      state.admin.selected = [];
      state.admin.reviewDetail = null;
    },

    /* 任何接口返回 401 时由 api.js 回调 */
    onUnauthorized() {
      if (!state.auth.user) return;
      state.auth.user = null;
      state.ready = false;
      actions.toast("登录已过期，请重新登录", "warn");
    },

    /* ---------------- 管理端 ---------------- */
    async loadAdmin() {
      state.admin.loading = true;
      try {
        var res = await api.admin.overview();
        state.admin.totals = res.totals;
        state.admin.rows = res.teachers;
        // 总览顺带带回审核统计，导航徽标立即可用
        if (res.audit) {
          state.admin.reviewAllStats = res.audit;
          if (!state.admin.reviewStats) state.admin.reviewStats = res.audit;
        }
      } finally {
        state.admin.loading = false;
      }
    },

    /* ---------------- 成果审核 ---------------- */
    async loadReviews() {
      var a = state.admin;
      a.reviewLoading = true;
      try {
        var res = await api.admin.achievements({
          status: a.reviewStatus, teacher: a.reviewTeacher, q: a.reviewQ
        });
        a.reviews = res.rows || [];
        a.reviewStats = res.stats || null;
        a.reviewAllStats = res.allStats || null;
        a.reviewTeachers = res.teachers || [];
        // 勾选状态与最新列表求交集，避免残留已失效的选择
        var keys = {};
        a.reviews.forEach(function (r) { keys[r.teacherId + "|" + r.id] = r; });
        a.selected = a.selected.filter(function (k) {
          return keys[k.teacherId + "|" + k.id];
        });
      } finally {
        a.reviewLoading = false;
      }
    },

    /* 审核结果直接就地更新，省掉一次全量重载 */
    async reviewOne(teacherId, id, action, note) {
      var res = await api.admin.reviewAchievement({
        teacherId: teacherId, id: id, action: action, note: note || ""
      });
      await actions.refreshAfterReview();
      return res;
    },

    async reviewBatch(items, action, note) {
      var res = await api.admin.batchReview({
        items: items, action: action, note: note || ""
      });
      await actions.refreshAfterReview();
      return res;
    },

    async refreshAfterReview() {
      await actions.loadReviews();
      try {
        var res = await api.admin.overview();
        state.admin.totals = res.totals;
        state.admin.rows = res.teachers;
      } catch (e) { /* 忽略：总览刷新失败不影响审核结果 */ }
    },

    reviewToggleSelect(teacherId, id, on) {
      var a = state.admin;
      var key = teacherId + "|" + id;
      var next = (a.selected || []).filter(function (k) {
        return (k.teacherId + "|" + k.id) !== key;
      });
      if (on) next.push({ teacherId: teacherId, id: id });
      a.selected = next;
    },

    reviewSelectAll(rows, on) {
      state.admin.selected = on
        ? (rows || []).map(function (r) { return { teacherId: r.teacherId, id: r.id }; })
        : [];
    },

    reviewClearSelection() { state.admin.selected = []; },

    adminGo(page) {
      state.admin.page = page;
      if (page !== "teacher") state.admin.detailId = "";
      if (page !== "reviews") state.admin.selected = [];
      var content = document.querySelector(".content");
      if (content) content.scrollTop = 0;
    },

    async openTeacher(id) {
      state.admin.page = "teacher";
      state.admin.detailId = id;
      state.admin.detail = null;
      state.admin.detail = await api.admin.teacher(id);
      var content = document.querySelector(".content");
      if (content) content.scrollTop = 0;
    },

    async adminCreateTeacher(payload) {
      var res = await api.admin.createTeacher(payload);
      await actions.loadAdmin();
      return res.user;
    },

    async adminUpdateTeacher(id, patch) {
      var res = await api.admin.updateTeacher(id, patch);
      await actions.loadAdmin();
      if (state.admin.detailId === id) await actions.openTeacher(id);
      return res.user;
    },

    adminResetPassword(id, password) {
      return api.admin.resetPassword(id, password);
    },

    async adminDeleteTeacher(id) {
      await api.admin.deleteTeacher(id);
      if (state.admin.detailId === id) {
        state.admin.page = "teachers";
        state.admin.detailId = "";
        state.admin.detail = null;
      }
      await actions.loadAdmin();
    },

    /* ---------------- 加载 ---------------- */
    async loadAll() {
      var res = await api.state();
      for (var k in state.data) {
        if (Array.isArray(res[k])) state.data[k] = res[k];
      }
      state.profile = res.profile || {};
      state.stats = res.stats || {};
      var specs = await api.specs();
      state.specs = specs || {};
      state.ready = true;
      await actions.loadCv();   // 简历发布概况（失败不影响工作台其余部分）
    },

    async refresh() {
      var res = await api.state();
      for (var k in state.data) {
        if (Array.isArray(res[k])) state.data[k] = res[k];
      }
      state.profile = res.profile || state.profile;
      state.stats = res.stats || {};
    },

    list(coll) { return state.data[coll] || []; },
    get(coll, id) {
      var arr = state.data[coll] || [];
      for (var i = 0; i < arr.length; i++) if (arr[i].id === id) return arr[i];
      return null;
    },

    /* ---------------- 集合 CRUD ---------------- */
    async create(coll, item) {
      var created = await api.create(coll, item);
      var arr = state.data[coll];
      if (arr) arr.unshift(created);
      await actions.refreshStats();
      return created;
    },
    async update(coll, id, patch) {
      var updated = await api.patch(coll, id, patch);
      var arr = state.data[coll] || [];
      for (var i = 0; i < arr.length; i++) {
        if (arr[i].id === id) { arr.splice(i, 1, updated); break; }
      }
      return updated;
    },
    async remove(coll, id) {
      await api.remove(coll, id);
      state.data[coll] = (state.data[coll] || []).filter(function (x) { return x.id !== id; });
      await actions.refreshStats();
    },
    async refreshStats() {
      try {
        var res = await api.state();
        state.stats = res.stats || {};
      } catch (e) { /* 忽略：统计刷新失败不影响主流程 */ }
    },

    /* ---------------- 个人信息 ---------------- */
    async saveProfile(data) {
      state.profile = await api.saveProfile(data);
      return state.profile;
    },

    /* ---------------- 个人简历 ---------------- */
    /** 拉取发布概况（公开开关 / 固定链接 / 区块开关与条目数） */
    async loadCv() {
      try {
        state.cv = await api.cv.overview();
      } catch (e) {
        state.cv = null;
      }
      return state.cv;
    },
    async setCvPublished(published) {
      state.cv = await api.cv.setVisibility(published);
      return state.cv;
    },
    async setCvSections(patch) {
      state.cv = await api.cv.setSections(patch);
      return state.cv;
    },
    /** 更换固定链接：旧链接立即失效，需要重新发给别人 */
    async rotateCvToken() {
      var res = await api.cv.rotateToken();
      if (state.cv) {
        state.cv.token = res.token;
        state.cv.path = res.path;
        state.cv.url = res.url;
      }
      return res;
    },
    /** 保存简历基本信息（/api/profile 合并写入，name 必填） */
    async saveCvProfile(payload) {
      var next = Object.assign({}, state.profile, payload, { name: (payload.name || state.profile.name || "").trim() });
      state.profile = await api.saveProfile(next);
      await actions.loadCv();
      return state.profile;
    },
    async uploadCvAvatar(file) {
      var res = await api.cv.uploadAvatar(file);
      state.profile.avatar = (res.avatar || {}).stored || "";
      await actions.loadCv();
      return res;
    },
    async removeCvAvatar() {
      await api.cv.removeAvatar();
      state.profile.avatar = "";
      await actions.loadCv();
    },

    /* ---------------- 数据管理 ---------------- */
    async importData(payload) { await api.importData(payload); await actions.refresh(); },
    async resetData() { await api.reset(); await actions.refresh(); },

    async search(q) {
      state.searchQ = q || "";
      if (!q || !q.trim()) { state.searchResults = null; return; }
      state.searchResults = await api.search(q.trim());
    },

    /* ---------------- 工具 ---------------- */
    async runTool(key, params, files) {
      state.toolRunning = true;
      try {
        var res = await api.runTool(key, params, files);
        state.toolResult = res;
        return res;
      } finally {
        state.toolRunning = false;
      }
    },

    /* ---------------- 课程开放与资料 ---------------- */
    /** 拉取课程分享概况（访问令牌 + 可见性），写入全局状态供详情页与弹窗共用 */
    async loadCourseShare(id) {
      try {
        var res = await api.courses.share(id);
        state.courseShare = res;
        actions.syncCourseDoc(res.course);
        return res;
      } catch (e) {
        state.courseShare = null;
        throw e;
      }
    },
    /** 保存开放设置（开关 / 起止日期），返回最新分享概况 */
    async setCourseVisibility(id, payload) {
      var res = await api.courses.setVisibility(id, payload);
      state.courseShare = res;
      actions.syncCourseDoc(res.course);
      return res;
    },
    async uploadCourseMaterials(id, files, opts) {
      var res = await api.courses.uploadMaterials(id, files, opts);
      actions.syncCourseDoc({ id: id, materials: res.materials });
      await actions.refreshStats();
      return res;
    },
    async deleteCourseMaterial(id, mid) {
      var res = await api.courses.deleteMaterial(id, mid);
      actions.syncCourseDoc({ id: id, materials: res.materials });
      await actions.refreshStats();
      return res;
    },
    /** 保存助教名单、联系方式与教学日历（助教 / QQ 群 / 日历行同步回课程文档） */
    async saveCourseContact(id, payload) {
      var res = await api.courses.saveContact(id, payload);
      actions.syncCourseDoc({
        id: id, calendar: res.calendar, qqGroup: res.qqGroup, assistants: res.assistants
      });
      return res;
    },
    async uploadCourseQr(id, file) {
      var res = await api.courses.uploadQr(id, file);
      actions.syncCourseDoc({
        id: id, calendar: res.calendar, qqGroup: res.qqGroup,
        assistants: res.assistants, hasQr: true
      });
      return res;
    },
    async removeCourseQr(id) {
      var res = await api.courses.removeQr(id);
      actions.syncCourseDoc({ id: id, hasQr: false });
      return res;
    },
    /** 把课程文档的部分字段合并回本地列表，避免整表重拉 */
    syncCourseDoc(patch) {
      var arr = state.data.courses || [];
      for (var i = 0; i < arr.length; i++) {
        if (arr[i].id === patch.id) {
          arr.splice(i, 1, Object.assign({}, arr[i], patch));
          return arr[i];
        }
      }
      return null;
    },

    /* ---------------- 常用网站 ---------------- */
    /** 新增网站：排在列表末尾（sort 递增，列表按 sort 升序展示） */
    addSiteLink(payload) {
      var list = state.data.links || [];
      var max = list.reduce(function (m, x) { return Math.max(m, Number(x.sort) || 0); }, -1);
      return actions.create("links", Object.assign({ sort: max + 1 }, payload));
    },
    updateSiteLink(id, patch) { return actions.update("links", id, patch); },
    removeSiteLink(id) { return actions.remove("links", id); },
    /** 站点信息（标题 / 主机名），供表单自动填充 */
    siteMeta(url) { return api.links.meta(url); },
    /**
     * 按新的顺序落库：逐条 PATCH 变化的 sort。
     * 网站数量在几十条量级，逐条更新比新增批量接口更省事，也不会写坏数据。
     */
    async reorderSiteLinks(orderedIds) {
      var list = state.data.links || [];
      var byId = {};
      list.forEach(function (x) { byId[x.id] = x; });
      for (var i = 0; i < orderedIds.length; i++) {
        var item = byId[orderedIds[i]];
        if (!item || Number(item.sort) === i) continue;
        var updated = await api.patch("links", item.id, { sort: i });
        for (var j = 0; j < list.length; j++) {
          if (list[j].id === item.id) { list.splice(j, 1, updated); break; }
        }
      }
    },

    /* ---------------- 导航 ---------------- */
    go(key) {
      state.page = key;
      state.detailId = "";
      state.searchResults = null;
      state.courseShare = null;
      ui.quickMenu = false;
      var content = document.querySelector(".content");
      if (content) content.scrollTop = 0;
    },
    openDetail(kind, id) {
      state.detailId = id;
      state.page = kind + "-detail";
      if (kind !== "course") state.courseShare = null;
      var content = document.querySelector(".content");
      if (content) content.scrollTop = 0;
    },

    /* ---------------- 提示 ---------------- */
    toast(msg, type) {
      var id = ++toastSeq;
      ui.toasts.push({ id: id, msg: msg, type: type || "success" });
      setTimeout(function () {
        for (var i = 0; i < ui.toasts.length; i++) {
          if (ui.toasts[i].id === id) { ui.toasts.splice(i, 1); break; }
        }
      }, 2600);
    },

    /* ---------------- 弹窗 ---------------- */
    openModal(opts) {
      ui.modal.open = true;
      ui.modal.title = opts.title || "";
      ui.modal.wide = !!opts.wide;
      ui.modal.body = opts.body || "";
      ui.modal.foot = opts.foot || "";
      ui.modal.component = opts.component || null;
      ui.modal.props = opts.props || {};
    },
    closeModal() {
      ui.modal.open = false;
      ui.modal.component = null;
      ui.modal.body = "";
      ui.modal.foot = "";
    },
    confirm(opts) {
      return new Promise(function (resolve) {
        var input = opts.input || null;
        var state = opts.state || {};
        ui.modal.open = true;
        ui.modal.title = opts.title || "确认操作";
        ui.modal.wide = !!opts.wide;
        ui.modal.component = null;
        ui.modal.body =
          "<p style='font-size:14px;color:var(--text-2);line-height:1.7'>" +
          U.esc(opts.msg || "") + "</p>" +
          (input
            ? "<div class='cfm-input'>" +
              "<textarea class='modal-input' rows='" + (input.rows || 3) + "' " +
              "placeholder='" + U.esc(input.placeholder || "") + "'></textarea>" +
              "<span class='cfm-hint'>" + (input.required ? "必填，将同步给教师" : "选填") + "</span>" +
              "</div>"
            : "");
        ui.modal.foot =
          "<button class='btn ghost' data-cfm='no'>取消</button>" +
          "<button class='btn " + (opts.danger === false ? "primary" : "danger") +
          "' data-cfm='yes'>" + U.esc(opts.btn || "确认") + "</button>";
        ui.modal.props = { resolve: resolve, input: input, state: state };
      });
    },

    /* 供组件使用：确认后删除 */
    async confirmDelete(msg, fn) {
      var yes = await actions.confirm({ title: "确认删除", msg: msg, btn: "确认删除" });
      if (yes) { await fn(); actions.toast("已删除", "success"); }
    }
  };

  global.FWB.store = { state: state, ui: ui, act: actions };
})(window);
