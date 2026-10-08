/* =====================================================================
   components.js —— 基础组件
   fwb-icon / fwb-progress / fwb-modal / fwb-toasts / fwb-form（通用表单引擎）
   ===================================================================== */
(function (global) {
  "use strict";

  var vue = global.Vue;
  var defineComponent = vue.defineComponent;
  var FWB = global.FWB;

  /* -------------------- 图标 -------------------- */
  var FwbIcon = defineComponent({
    name: "FwbIcon",
    props: { name: { type: String, default: "info" }, size: { type: [Number, String], default: 0 } },
    computed: {
      path: function () { return FWB.iconPath(this.name); }
    },
    template:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" ' +
      'stroke-linecap="round" stroke-linejoin="round" :style="size ? {width: size + \'px\', height: size + \'px\'} : null" ' +
      'v-html="path" aria-hidden="true"></svg>'
  });

  /* -------------------- 进度条 -------------------- */
  var FwbProgress = defineComponent({
    name: "FwbProgress",
    props: { value: { type: Number, default: 0 }, tone: { type: String, default: "" } },
    computed: {
      w: function () { return Math.max(0, Math.min(100, Number(this.value) || 0)); }
    },
    template: '<div class="progress" :class="tone"><i :style="{ width: w + \'%\' }"></i></div>'
  });

  /* -------------------- 星级 -------------------- */
  var FwbStars = defineComponent({
    name: "FwbStars",
    props: { value: { type: Number, default: 0 }, max: { type: Number, default: 5 } },
    methods: { isOn: function (i) { return i <= this.value; } },
    template:
      '<span class="stars">' +
      '<svg v-for="i in max" :key="i" :class="{ off: !isOn(i) }" viewBox="0 0 24 24" ' +
      'fill="currentColor" stroke="none"><path d="M12 2.5l2.9 5.9 6.5.95-4.7 4.6 1.1 6.45L12 17.9l-5.8 3.05 1.1-6.45-4.7-4.6 6.5-.95z"/></svg>' +
      "</span>"
  });

  /* -------------------- 弹窗 -------------------- */
  var FwbModal = defineComponent({
    name: "FwbModal",
    setup: function () {
      var store = FWB.store;
      return { ui: store.ui, act: store.act };
    },
    methods: {
      onFootClick: function (ev) {
        var props = this.ui.modal.props || {};
        var btn = ev.target.closest ? ev.target.closest("[data-cfm]") : null;
        if (btn) {
          var yes = btn.getAttribute("data-cfm") === "yes";
          // 带输入框的确认弹窗：先把内容写回调用方，再关闭
          if (yes && props.input) {
            var box = document.querySelector(".modal-mask.show .modal-input");
            var val = box ? String(box.value || "").trim() : "";
            if (props.input.required && !val) {
              if (box) { box.classList.add("invalid"); box.focus(); }
              this.act.toast("请填写必填内容", "warn");
              return;
            }
            if (props.state) props.state[props.input.key || "value"] = val;
          }
          this.act.closeModal();
          if (props.resolve) props.resolve(yes);
          return;
        }
        var close = ev.target.closest ? ev.target.closest("[data-close]") : null;
        if (close) { this.act.closeModal(); return; }
        if (ev.target.classList && ev.target.classList.contains("modal-mask")) this.act.closeModal();
      }
    },
    template:
      '<div class="modal-mask" :class="{ show: ui.modal.open }" @click="onFootClick">' +
      '  <div class="modal" :class="{ wide: ui.modal.wide }" @click.stop>' +
      '    <div class="modal-head">' +
      '      <h2>{{ ui.modal.title }}</h2>' +
      '      <button class="icon-btn ghost" data-close title="关闭" @click.stop="onFootClick"><fwb-icon name="x"/></button>' +
      "    </div>" +
      '    <div class="modal-body">' +
      '      <component v-if="ui.modal.component" :is="ui.modal.component" v-bind="ui.modal.props"/>' +
      '      <div v-else v-html="ui.modal.body"></div>' +
      "    </div>" +
      '    <div v-if="ui.modal.foot" class="modal-foot" v-html="ui.modal.foot" @click="onFootClick"></div>' +
      "  </div>" +
      "</div>"
  });

  /* -------------------- Toast -------------------- */
  var FwbToasts = defineComponent({
    name: "FwbToasts",
    setup: function () {
      var store = FWB.store;
      return { ui: store.ui };
    },
    methods: {
      icon: function (t) {
        return { success: "check", info: "info", warn: "alert", error: "alert" }[t] || "info";
      }
    },
    template:
      '<div class="toast-wrap">' +
      '  <div v-for="t in ui.toasts" :key="t.id" class="toast" :class="t.type">' +
      '    <fwb-icon :name="icon(t.type)"/><span>{{ t.msg }}</span>' +
      "  </div>" +
      "</div>"
  });

  /* -------------------- 单个表单字段 -------------------- */
  var FwbField = defineComponent({
    name: "FwbField",
    props: {
      spec: { type: Object, required: true },
      modelValue: { default: "" }
    },
    emits: ["update:modelValue"],
    computed: {
      m: {
        get: function () { return this.modelValue; },
        set: function (v) { this.$emit("update:modelValue", v); }
      },
      wide: function () {
        var t = this.spec.type;
        return this.spec.span === 2 || t === "mono" || t === "textarea" || t === "file";
      }
    },
    methods: {
      onFile: function (ev) {
        this.$emit("update:modelValue", ev.target.files);
      }
    },
    template:
      '<div class="field" :class="{ span2: wide }">' +
      '  <label v-if="spec.label">{{ spec.label }}<span v-if="spec.req" class="req">*</span></label>' +

      '  <select v-if="spec.type === \'select\'" v-model="m">' +
      '    <option v-for="o in spec.opts" :key="o" :value="o">{{ o }}</option>' +
      "  </select>" +

      '  <input v-else-if="spec.type === \'date\'" type="date" v-model="m">' +
      '  <input v-else-if="spec.type === \'number\'" type="number" v-model="m">' +
      '  <input v-else-if="spec.type === \'email\'" type="email" v-model="m" :placeholder="spec.ph || \'\'">' +
      '  <input v-else-if="spec.type === \'password\'" type="password" v-model="m" :placeholder="spec.ph || \'\'" autocomplete="new-password">' +
      '  <input v-else-if="spec.type === \'file\'" type="file" :accept="spec.accept || \'\'" multiple @change="onFile">' +

      '  <textarea v-else-if="spec.type === \'textarea\'" v-model="m" :rows="spec.rows || 3" :placeholder="spec.ph || \'\'"></textarea>' +
      '  <textarea v-else-if="spec.type === \'mono\'" class="mono" v-model="m" :rows="spec.rows || 6" :placeholder="spec.ph || \'\'"></textarea>' +

      '  <label v-else-if="spec.type === \'check\'" class="check-line">' +
      '    <input type="checkbox" v-model="m"> <span>{{ spec.ph || "启用" }}</span>' +
      "  </label>" +

      '  <input v-else type="text" v-model="m" :placeholder="spec.ph || \'\'">' +

      '  <div v-if="spec.hint" class="hint">{{ spec.hint }}</div>' +
      "</div>"
  });

  /* -------------------- 通用表单引擎 -------------------- */
  var FwbForm = defineComponent({
    name: "FwbForm",
    components: { FwbField: FwbField, FwbIcon: FwbIcon },
    props: {
      spec: { type: Object, required: true },
      initial: { type: Object, default: function () { return {}; } }
    },
    setup: function () {
      var store = FWB.store;
      return { act: store.act };
    },
    data: function () {
      var spec = this.spec;
      var model = {};
      (spec.fields || []).forEach(function (f) {
        var v = this.initial[f.name];
        if (v === undefined || v === null || v === "") {
          v = f.type === "check" ? !!f.value : (f.value !== undefined ? f.value : "");
        }
        model[f.name] = v;
      }, this);
      var dyns = {};
      (spec.dynamic || []).forEach(function (d) {
        var arr = this.initial[d.key];
        dyns[d.key] = Array.isArray(arr) ? JSON.parse(JSON.stringify(arr)) : [];
      }, this);
      return { model: model, dyns: dyns, files: {}, error: "", busy: false };
    },
    methods: {
      addRow: function (d) {
        var row = {};
        d.cols.forEach(function (c) {
          row[c.name] = c.value !== undefined ? c.value : (c.type === "check" ? false : "");
        });
        this.dyns[d.key].push(row);
      },
      delRow: function (d, i) { this.dyns[d.key].splice(i, 1); },
      setVal: function (f, v) {
        this.model[f.name] = v;
        if (f.type === "file") this.files[f.name] = v;
      },
      async submit() {
        var spec = this.spec;
        // 必填校验
        var missing = (spec.fields || []).filter(function (f) {
          if (!f.req) return false;
          if (f.type === "file") return false;
          var v = this.model[f.name];
          return v === undefined || v === null || String(v).trim() === "";
        }, this);
        if (missing.length) {
          this.error = "请填写：" + missing.map(function (f) { return f.label; }).join("、");
          return;
        }
        this.error = "";
        this.busy = true;
        try {
          var payload = spec.fromModel
            ? spec.fromModel(this.model, this.dyns)
            : Object.assign({}, this.model);
          await spec.onSubmit(payload, this.files);
          this.act.closeModal();
        } catch (e) {
          this.error = e.message || String(e);
        } finally {
          this.busy = false;
        }
      },
      cancel: function () { this.act.closeModal(); }
    },
    template:
      "<div>" +
      '  <div v-if="error" class="form-error">{{ error }}</div>' +
      '  <div class="form-row two">' +
      '    <fwb-field v-for="f in (spec.fields || [])" :key="f.name" :spec="f" ' +
      '       :modelValue="model[f.name]" @update:modelValue="v => setVal(f, v)"/>' +
      "  </div>" +

      '  <div v-for="d in (spec.dynamic || [])" :key="d.key" class="form-row">' +
      '    <div class="section-title">{{ d.label }}<span class="st-line"></span></div>' +
      '    <div class="dyn-list">' +
      '      <div v-for="(row, i) in dyns[d.key]" :key="i" class="dyn-row">' +
      '        <template v-for="c in d.cols" :key="c.name">' +
      '          <select v-if="c.type === \'select\'" v-model="row[c.name]" :style="c.width ? {flex: c.width} : null">' +
      '            <option v-for="o in c.opts" :key="o" :value="o">{{ o }}</option>' +
      "          </select>" +
      '          <input v-else-if="c.type === \'check\'" type="checkbox" v-model="row[c.name]" style="flex:0 0 auto;width:auto">' +
      '          <input v-else :type="c.type === \'date\' ? \'date\' : (c.type === \'number\' ? \'number\' : \'text\')" ' +
      '                 v-model="row[c.name]" :placeholder="c.ph || \'\'" :style="c.width ? {flex: c.width} : null">' +
      "        </template>" +
      '        <button class="dyn-del" type="button" title="删除本行" @click="delRow(d, i)"><fwb-icon name="trash"/></button>' +
      "      </div>" +
      "    </div>" +
      '    <button class="add-row-btn" type="button" @click="addRow(d)"><fwb-icon name="plus"/>{{ d.addLabel || "添加一行" }}</button>' +
      "  </div>" +

      '  <div class="modal-foot" style="padding:16px 0 0;border-top:1px solid var(--line);margin-top:18px">' +
      '    <button class="btn ghost" type="button" @click="cancel">取消</button>' +
      '    <button class="btn primary" type="button" :disabled="busy" @click="submit">' +
      '      {{ busy ? "提交中…" : (spec.submitLabel || "保存") }}' +
      "    </button>" +
      "  </div>" +
      "</div>"
  });

  /* -------------------- 配色主题选择器 -------------------- */
  /* 两种用法：① 以弹窗组件方式打开（modal=true，带说明与关闭按钮）；
     ② 内嵌在设置面板 / 登录卡片里（默认）。 */
  var FwbThemePicker = defineComponent({
    name: "FwbThemePicker",
    components: { FwbIcon: FwbIcon },
    props: {
      modal: { type: Boolean, default: false },
      hint: { type: Boolean, default: true }
    },
    setup: function () {
      return { act: FWB.store.act };
    },
    data: function () {
      return { themes: FWB.theme.list, cur: FWB.theme.current() };
    },
    methods: {
      pick: function (key) {
        this.cur = FWB.theme.apply(key);
        this.act.toast(FWB.theme.toast(this.cur), "success");
      }
    },
    template:
      '<div class="theme-picker">' +
      '  <div v-if="hint" class="theme-hint">' +
      "    平台提供 {{ themes.length }} 套配色，点击色块即时切换，选择会自动保存到本机。" +
      "  </div>" +
      '  <div class="theme-dots">' +
      '    <div v-for="t in themes" :key="t.key" class="theme-cell" :class="{ on: t.key === cur }">' +
      '      <button type="button" class="theme-dot" :class="{ on: t.key === cur }"' +
      '              :title="t.label + \' · \' + t.desc" @click="pick(t.key)">' +
      '        <i :style="{ background: \'linear-gradient(140deg,\' + t.colors[0] + \',\' + t.colors[2] + \')\' }"></i>' +
      "      </button>" +
      '      <span class="theme-name">{{ t.label }}</span>' +
      "    </div>" +
      "  </div>" +
      '  <div v-if="modal" class="modal-foot" style="padding:16px 0 0;border-top:1px solid var(--line);margin-top:18px">' +
      '    <button class="btn primary" type="button" @click="act.closeModal()">完成</button>' +
      "  </div>" +
      "</div>"
  });

  /* -------------------- 成果审核详情（弹窗内容） -------------------- */
  var AUDIT_TONE = { "待审核": "wait", "已通过": "ok", "已退回": "off" };

  var FwbReviewDetail = defineComponent({
    name: "FwbReviewDetail",
    components: { FwbIcon: FwbIcon },
    props: { row: { type: Object, default: null } },
    setup: function () {
      return { act: FWB.store.act };
    },
    computed: {
      r: function () { return this.row || {}; },
      tone: function () { return AUDIT_TONE[this.r.auditStatus] || "gray"; },
      facts: function () {
        var r = this.r;
        return [
          { k: "成果类型", v: r.type || "—" },
          { k: "级别", v: r.level || "—" },
          { k: "成果状态", v: r.status || "—" },
          { k: "日期", v: r.date || "未定" },
          { k: "发表 / 授权单位", v: r.venue || "—" },
          { k: "作者", v: r.authors || "—" },
          { k: "本人角色", v: r.role || "—" },
          { k: "DOI / 登记号", v: r.doi || "—" },
          { k: "关联项目", v: r.projectName || "—" },
          { k: "业绩分", v: r.score },
          { k: "最近审核人", v: r.auditBy || "—" },
          { k: "最近审核时间", v: r.auditAt || "—" }
        ];
      },
      log: function () { return this.r.auditLog || []; }
    },
    methods: {
      approve: function () {
        this.act.closeModal();
        FWB.root.reviewOne(this.row, "approve", "");
      },
      reject: function () {
        this.act.closeModal();
        FWB.root.reject(this.row);
      },
      reset: function () {
        this.act.closeModal();
        FWB.root.resetReview(this.row);
      }
    },
    template:
      '<div class="rv-detail">' +
      '  <div class="rv-top">' +
      '    <div class="rv-title">{{ r.title }}</div>' +
      '    <span class="audit-tag" :class="tone">{{ r.auditStatus }}</span>' +
      "  </div>" +
      '  <div class="rv-owner">' +
      '    <span class="avatar sm">{{ (r.teacherName || "?").charAt(0) }}</span>' +
      '    <span><b>{{ r.teacherName }}</b>' +
      '      <small>{{ r.teacherTitle || "" }}{{ r.teacherDept ? " · " + r.teacherDept : "" }}</small></span>' +
      "  </div>" +
      '  <div class="rv-grid">' +
      '    <div v-for="f in facts" :key="f.k" class="rv-cell">' +
      '      <span class="rv-k">{{ f.k }}</span><span class="rv-v">{{ f.v }}</span>' +
      "    </div>" +
      "  </div>" +
      '  <div v-if="r.note" class="rv-note"><b>成果说明</b><p>{{ r.note }}</p></div>' +
      '  <div v-if="r.auditNote" class="rv-note warn"><b>审核意见</b><p>{{ r.auditNote }}</p>' +
      '    <span class="rv-by">{{ r.auditBy }} · {{ r.auditAt }}</span></div>' +
      '  <div class="rv-log">' +
      "    <h4>审核轨迹</h4>" +
      '    <div v-if="!log.length" class="muted">暂无审核记录</div>' +
      '    <div v-for="(e, i) in log" :key="i" class="rv-log-row">' +
      '      <span class="rv-log-dot" :class="e.action === \'退回\' ? \'off\' : (e.action === \'通过\' ? \'ok\' : \'wait\')"></span>' +
      '      <span class="rv-log-act">{{ e.action }}</span>' +
      '      <span class="rv-log-time">{{ e.at }} · {{ e.by }}</span>' +
      '      <span class="rv-log-note" v-if="e.note">{{ e.note }}</span>' +
      "    </div>" +
      "  </div>" +
      '  <div class="rv-actions">' +
      '    <button class="btn ghost" @click="act.closeModal()">关闭</button>' +
      '    <button class="btn ghost danger-text" v-if="r.auditStatus === \'已退回\'" @click="reset">' +
      '      <fwb-icon name="undo"/>撤回审核</button>' +
      '    <button class="btn danger" @click="reject"><fwb-icon name="x"/>退回修改</button>' +
      '    <button class="btn primary" @click="approve"><fwb-icon name="check"/>审核通过</button>' +
      "  </div>" +
      "</div>"
  });

  /* ------------------------------------------------------------------ */
  /* 课程「学生访问设置」弹窗                                             */
  /* ------------------------------------------------------------------ */
  var FwbCourseShare = defineComponent({
    name: "FwbCourseShare",
    components: { FwbIcon: FwbIcon },
    props: { courseId: { type: String, default: "" } },
    setup: function () {
      var store = FWB.store;
      return { S: store.state, act: store.act, U: FWB.util };
    },
    data: function () {
      return { published: false, openFrom: "", openUntil: "", busy: false, ready: false };
    },
    computed: {
      share: function () { return this.S.courseShare; },
      url: function () {
        if (!this.share || !this.share.token) return "";
        var origin = (window.location && window.location.origin) || "";
        return origin + "/c/" + this.share.token;
      },
      /* 用当前表单值即时预演保存后的学生侧状态，避免「保存了才知道」 */
      preview: function () {
        return this.U.courseVisibility({
          published: this.published, openFrom: this.openFrom, openUntil: this.openUntil
        });
      },
      dirty: function () {
        var s = this.share || {};
        return !!this.published !== !!s.published
          || (this.openFrom || "") !== (s.openFrom || "")
          || (this.openUntil || "") !== (s.openUntil || "");
      }
    },
    mounted: function () {
      var self = this;
      var fill = function (res) {
        self.published = !!res.published;
        self.openFrom = res.openFrom || "";
        self.openUntil = res.openUntil || "";
        self.ready = true;
      };
      if (this.share) {
        fill(this.share);
      } else if (this.courseId) {
        this.act.loadCourseShare(this.courseId).then(fill, function () { self.ready = true; });
      } else {
        this.ready = true;
      }
    },
    methods: {
      copy: function () {
        var self = this;
        if (!this.url) return;
        if (window.navigator && window.navigator.clipboard) {
          window.navigator.clipboard.writeText(this.url).then(
            function () { self.act.toast("课程链接已复制到剪贴板"); },
            function () { self.act.toast("复制失败，请手动选中链接", "error"); }
          );
        } else {
          self.act.toast("当前浏览器不支持自动复制");
        }
      },
      close: function () { this.act.closeModal(); },
      save: function () {
        var self = this;
        if (this.openFrom && this.openUntil && this.openFrom > this.openUntil) {
          this.act.toast("开放起始日期不能晚于结束日期", "error");
          return;
        }
        this.busy = true;
        this.act.setCourseVisibility(this.courseId, {
          published: this.published,
          openFrom: this.openFrom,
          openUntil: this.openUntil
        }).then(function (res) {
          self.act.closeModal();
          self.act.toast(res.visibility.visible ? "已保存：学生现在可以访问" : "已保存：学生当前不可见");
        }, function (err) {
          self.act.toast(err.message || "保存失败", "error");
        }).then(function () { self.busy = false; });
      }
    },
    template:
      '<div class="cs-form">' +
      '  <label class="cs-switch" :class="{ on: published }">' +
      '    <input type="checkbox" v-model="published">' +
      '    <span class="css-track"><span class="css-dot"></span></span>' +
      '    <span class="css-text">' +
      '      <b>{{ published ? "允许学生访问" : "已关闭学生访问" }}</b>' +
      '      <small>{{ published ? "学生可通过课程链接查看大纲并下载已上传的资料" : "学生打开链接只会看到「暂未开放」提示" }}</small>' +
      "    </span>" +
      "  </label>" +

      '  <div class="cs-range">' +
      '    <div class="cs-range-head"><b>开放时间范围</b><span>两项均可留空，表示不限制</span></div>' +
      '    <div class="cs-range-row">' +
      '      <label class="field"><span class="cs-lab">开始日期</span>' +
      '        <input type="date" v-model="openFrom"></label>' +
      '      <span class="cs-tilde">至</span>' +
      '      <label class="field"><span class="cs-lab">结束日期</span>' +
      '        <input type="date" v-model="openUntil"></label>' +
      "    </div>" +
      '    <div class="cs-range-hint">到点自动生效 / 失效，无需手动开关；关闭开关后时间范围不再生效。</div>' +
      "  </div>" +

      '  <div class="cs-preview" :class="\'st-\' + preview.state">' +
      '    <fwb-icon :name="preview.visible ? \'globe\' : \'lock\'" :size="18"/>' +
      "    <div>" +
      '      <b>保存后学生看到：{{ preview.label }}</b>' +
      '      <p>{{ preview.visible ? "可查看教学大纲，并下载已上传的课程资料。" : preview.detail }}</p>' +
      "    </div>" +
      "  </div>" +

      '  <div v-if="url" class="cs-link">' +
      "    <code>{{ url }}</code>" +
      '    <button class="btn ghost xs" @click="copy"><fwb-icon name="copy"/>复制链接</button>' +
      "  </div>" +

      '  <div class="modal-actions">' +
      '    <button class="btn ghost" @click="close">取消</button>' +
      '    <button class="btn primary" :disabled="busy || !ready" @click="save">' +
      '      {{ busy ? "保存中…" : (dirty ? "保存设置" : "已是最新") }}</button>' +
      "  </div>" +
      "</div>"
  });

  /* ------------------------------------------------------------------ */
  /* 常用网站：新增 / 编辑弹窗                                            */
  /* ------------------------------------------------------------------ */
  var FwbLinkEdit = defineComponent({
    name: "FwbLinkEdit",
    components: { FwbIcon: FwbIcon },
    props: {
      link: { type: Object, default: null },
      groups: { type: Array, default: null }
    },
    setup: function () {
      return { act: FWB.store.act, api: FWB.api, U: FWB.util };
    },
    data: function () {
      var l = this.link || {};
      return {
        name: l.name || "",
        url: l.url || "",
        group: l.group || "学术资源",
        note: l.note || "",
        busy: false,
        probing: false,
        metaMsg: "",
        metaTone: "",
        iconSrc: "",
        iconSource: "",
        iconMsg: "",
        autoNamed: !l.name           // 名称是否仍由系统自动填充
      };
    },
    computed: {
      editing: function () { return !!(this.link && this.link.id); },
      groupOptions: function () {
        var list = (this.groups && this.groups.length ? this.groups : this.U.LINK_GROUPS).slice();
        if (this.group && list.indexOf(this.group) < 0) list.unshift(this.group);
        return list;
      },
      previewName: function () { return this.name || this.U.siteHost(this.url); },
      canSave: function () {
        return !this.busy && this.name.trim().length > 0 && this.url.trim().length > 0;
      }
    },
    watch: {
      url: function () {
        // 网址变化：清掉旧预览，稍后自动探测站点信息
        this.iconSrc = "";
        this.iconMsg = "";
        clearTimeout(this._t);
        if (!this.url.trim()) { this.metaMsg = ""; return; }
        var self = this;
        this._t = setTimeout(function () { self.probe(); }, 700);
      }
    },
    mounted: function () {
      if (this.url.trim()) this.iconSrc = this.api.links.iconUrl(this.url, this.previewName);
    },
    beforeUnmount: function () {
      clearTimeout(this._t);
      this.revoke();
    },
    methods: {
      revoke: function () {
        if (this._blob && this.iconSrc && this.iconSrc.indexOf("blob:") === 0) {
          URL.revokeObjectURL(this.iconSrc);
        }
        this._blob = null;
      },
      /** 探测站点：标题 + 图标（顺带把服务端图标缓存预热） */
      probe: async function (force) {
        var url = this.url.trim();
        if (!url) { this.metaMsg = ""; return; }
        this.probing = true;
        this.iconMsg = "正在抓取站点图标…";
        this.metaTone = "";
        this.metaMsg = "";
        var self = this;
        // 图标：直接取二进制，既能立刻显示，又能从响应头判断是真实图标还是头像
        try {
          var icon = await this.api.links.probe(url, this.previewName, force ? Date.now() : "");
          self.revoke();
          self.iconSrc = icon.src;
          self._blob = true;
          self.iconSource = icon.source;
          self.iconMsg = icon.source === "site" ? "已抓取到站点图标" : "该站点未提供图标，使用首字母头像";
        } catch (e) {
          self.iconMsg = "图标抓取失败，将使用首字母头像";
        }
        // 站点信息：标题用于自动填充名称
        try {
          var info = await this.api.links.meta(url);
          if (info && info.title) {
            if (self.autoNamed || !self.name.trim()) {
              self.name = info.title;
              self.autoNamed = true;
            }
            self.metaMsg = "已获取站点标题：" + info.title;
            self.metaTone = "ok";
          } else {
            self.metaMsg = "未能读取站点标题，请手动填写名称";
            self.metaTone = "warn";
          }
        } catch (e) {
          self.metaMsg = (e && e.message) || "未能读取站点信息，请手动填写";
          self.metaTone = "warn";
        } finally {
          self.probing = false;
        }
      },
      onName: function () { this.autoNamed = false; },
      save: function () {
        if (!this.canSave) return;
        var url = this.url.trim();
        if (!/^([a-zA-Z][a-zA-Z0-9+.-]*:\/\/)/.test(url) && url.indexOf("//") !== 0) {
          url = "https://" + url.replace(/^\/+/, "");
        }
        var payload = {
          name: this.name.trim(),
          url: url,
          group: this.group || "其他",
          note: this.note.trim()
        };
        var self = this;
        this.busy = true;
        var task = this.editing
          ? this.act.updateSiteLink(this.link.id, payload)
          : this.act.addSiteLink(payload);
        task.then(function () {
          self.act.closeModal();
          self.act.toast(self.editing ? "网站已更新" : "已添加「" + payload.name + "」", "success");
        }, function (err) {
          self.act.toast((err && err.message) || "保存失败", "error");
        }).then(function () { self.busy = false; });
      },
      close: function () { this.act.closeModal(); }
    },
    template:
      '<div class="lk-form">' +
      '  <div class="lk-preview">' +
      '    <span class="lk-ico">' +
      '      <span class="lk-fb" :style="{ background: U.siteTone(previewName, url) }">{{ U.siteLetter(previewName, url) }}</span>' +
      '      <img v-if="iconSrc" :src="iconSrc" alt="" @error="iconSrc = \'\'">' +
      "    </span>" +
      '    <div class="lk-pv-info">' +
      '      <b>{{ previewName || "待填写网站" }}</b>' +
      '      <small>{{ U.siteHost(url) || "填写网址后自动识别主机名" }}</small>' +
      '      <span class="lk-ico-msg" v-if="iconMsg" :class="iconSource === \'site\' ? \'ok\' : \'warn\'">' +
      '        <fwb-icon :name="iconSource === \'site\' ? \'check\' : \'info\'"/>{{ iconMsg }}</span>' +
      "    </div>" +
      '    <button class="btn ghost xs" type="button" :disabled="probing || !url.trim()" @click="probe(true)">' +
      '      <fwb-icon name="rotate"/>{{ probing ? "抓取中…" : "重新抓取" }}</button>' +
      "  </div>" +

      '  <div class="form-row two">' +
      '    <div class="field">' +
      '      <label>网站名称<span class="req">*</span></label>' +
      '      <input type="text" v-model="name" placeholder="例如：中国知网" maxlength="24" @input="onName">' +
      "    </div>" +
      '    <div class="field">' +
      '      <label>网址<span class="req">*</span></label>' +
      '      <input type="text" v-model="url" placeholder="例如：https://www.cnki.net" spellcheck="false">' +
      '      <div class="hint" v-if="metaMsg" :class="metaTone">{{ metaMsg }}</div>' +
      "    </div>" +
      '    <div class="field">' +
      "      <label>分组</label>" +
      '      <select v-model="group">' +
      '        <option v-for="g in groupOptions" :key="g" :value="g">{{ g }}</option>' +
      "      </select>" +
      "    </div>" +
      '    <div class="field">' +
      "      <label>备注</label>" +
      '      <input type="text" v-model="note" placeholder="选填，鼠标悬停时提示" maxlength="30">' +
      "    </div>" +
      "  </div>" +

      '  <div class="lk-tip"><fwb-icon name="info"/>图标由服务端自动抓取并缓存，抓不到时显示首字母头像，不会影响使用。</div>' +

      '  <div class="modal-actions">' +
      '    <button class="btn ghost" type="button" @click="close">取消</button>' +
      '    <button class="btn primary" type="button" :disabled="!canSave" @click="save">' +
      '      {{ busy ? "保存中…" : (editing ? "保存修改" : "添加网站") }}</button>' +
      "  </div>" +
      "</div>"
  });

  FWB.components = {
    FwbIcon: FwbIcon, FwbProgress: FwbProgress, FwbStars: FwbStars,
    FwbModal: FwbModal, FwbToasts: FwbToasts, FwbField: FwbField, FwbForm: FwbForm,
    FwbThemePicker: FwbThemePicker, FwbReviewDetail: FwbReviewDetail,
    FwbCourseShare: FwbCourseShare, FwbLinkEdit: FwbLinkEdit
  };
})(window);
