/* =====================================================================
   pages/tools.js —— 常用工具（内置工具集 + 执行留痕）
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  /* 工具 key -> 图标（与后端工具注册表一一对应） */
  var TOOL_ICON = {
    teaching_calendar: "calendar", grade_calc: "chart", cite_convert: "book",
    budget_calc: "target", submission_track: "send", student_board: "users",
    duty_log: "edit", meeting_note: "notebook", pdf_toolkit: "file",
    achievement_export: "medal", ppt_theme: "ppt", device_lend: "briefcase"
  };

  var Tools = {
    name: "PageTools",
    setup: function () { var s = FWB.store; return { S: s.state, act: s.act, U: U, forms: FWB.forms }; },

    computed: {
      all: function () { return this.act.list("tools"); },

      filterKey: function () { return this.S.filters.tool; },

      /* 卡片按使用频次降序（高频工具优先触达） */
      items: function () {
        var f = this.filterKey;
        var list = f === "all" ? this.all.slice()
          : this.all.filter(function (t) { return (t.category || "其他") === f; });
        return list.sort(function (a, b) { return (b.freq || 0) - (a.freq || 0); });
      },

      counts: function () {
        var out = { all: this.all.length };
        this.all.forEach(function (t) {
          var c = t.category || "其他";
          out[c] = (out[c] || 0) + 1;
        });
        return out;
      },

      catTabs: function () {
        var self = this;
        var keys = Object.keys(this.counts).filter(function (k) { return k !== "all"; });
        keys.sort(function (a, b) { return self.counts[b] - self.counts[a]; });
        return [{ key: "all", text: "全部", count: this.all.length }].concat(
          keys.map(function (k) { return { key: k, text: k, count: self.counts[k] }; })
        );
      },

      totalFreq: function () {
        return this.all.reduce(function (s, t) { return s + (parseInt(t.freq, 10) || 0); }, 0);
      },

      runs: function () { return this.act.list("tool_runs"); },

      recentRuns: function () { return this.runs.slice(0, 8); },

      /* 覆盖率：内置实现可用的工具占比 */
      builtinCount: function () {
        return this.all.filter(function (t) { return t.builtin; }).length;
      }
    },

    methods: {
      tone: function (c) { return U.TONES.toolCat[c || "其他"] || "gray"; },

      setCat: function (k) { this.S.filters.tool = k; },

      iconOf: function (t) {
        var key = this.keyOf(t);
        return TOOL_ICON[key] || "wrench";
      },

      keyOf: function (t) {
        var url = String(t.url || "");
        var m = /^internal:\/\/(.+)$/.exec(url);
        return m ? m[1].replace(/-/g, "_") : "";
      },

      available: function (t) {
        var key = this.keyOf(t);
        return !!(key && this.S.specs[key]);
      },

      run: function (t) {
        if (!this.available(t)) { this.act.toast("该工具暂无内置实现", "warn"); return; }
        this.forms.openToolRunner(t);
      }
    },

    template: `
<div>
  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-ico blue"><fwb-icon name="wrench"/></div>
      <div class="stat-info"><div class="stat-val">{{ all.length }}<small>个</small></div>
        <div class="stat-label">收录工具</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-ico violet"><fwb-icon name="play"/></div>
      <div class="stat-info"><div class="stat-val">{{ totalFreq }}<small>次</small></div>
        <div class="stat-label">累计运行</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-ico green"><fwb-icon name="check"/></div>
      <div class="stat-info"><div class="stat-val">{{ runs.length }}<small>条</small></div>
        <div class="stat-label">执行记录</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-ico amber"><fwb-icon name="layers"/></div>
      <div class="stat-info"><div class="stat-val">{{ catTabs.length - 1 }}<small>类</small></div>
        <div class="stat-label">覆盖分类</div></div>
    </div>
  </div>

  <div class="toolbar">
    <div class="chips">
      <div v-for="c in catTabs" :key="c.key" class="chip" :class="{ active: filterKey === c.key }"
           @click="setCat(c.key)">{{ c.text }}<span class="cnt">{{ c.count }}</span></div>
    </div>
    <div class="spacer"></div>
    <span class="muted small">{{ builtinCount }} 个工具已内置实现，点击卡片即可运行</span>
  </div>

  <div v-if="!items.length" class="card">
    <div class="empty"><fwb-icon name="wrench" :size="44"/><p>该分类下暂无工具</p></div>
  </div>

  <div class="tool-grid">
    <div v-for="t in items" :key="t.id" class="tool-card" :class="{ 'tool-off': !available(t) }" @click="run(t)">
      <div class="tool-top">
        <div class="tool-ico" :class="'tone-' + tone(t.category)">
          <fwb-icon :name="iconOf(t)"/>
        </div>
        <div class="tool-name">{{ t.name }}</div>
      </div>
      <div class="tool-desc">{{ t.desc }}</div>
      <div class="tool-foot">
        <span class="tool-freq">已用 {{ t.freq || 0 }} 次</span>
        <span class="tool-run"><fwb-icon name="play"/>运行</span>
      </div>
    </div>
  </div>

  <div class="card" style="margin-top:18px" v-if="recentRuns.length">
    <div class="card-head">
      <h3><span class="ch-ico"><fwb-icon name="clock"/></span>最近执行记录</h3>
      <span class="muted small">共 {{ runs.length }} 条</span>
    </div>
    <div class="card-body">
      <div v-for="r in recentRuns" :key="r.id" class="run-item">
        <span class="ri-date">{{ r.created }}</span>
        <span class="ri-title">{{ r.title }}<template v-if="r.memo"> — {{ r.memo }}</template></span>
      </div>
    </div>
  </div>
</div>`
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.tools = Tools;
})(window);
