/* =====================================================================
   pages/developments.js —— 个人发展（职称 / 人才项目 / 培训 / 考核）
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  var CATS = ["职称晋升", "人才项目", "培训进修", "产学研", "考核述职", "其他"];

  var Developments = {
    name: "PageDevelopments",
    setup: function () { var s = FWB.store; return { S: s.state, act: s.act, U: U, forms: FWB.forms }; },

    computed: {
      all: function () { return this.act.list("developments"); },

      filterKey: function () { return this.S.filters.dev; },

      items: function () {
        var f = this.filterKey;
        return f === "all" ? this.all : this.all.filter(function (d) { return d.category === f; });
      },

      counts: function () {
        var out = { all: this.all.length };
        this.all.forEach(function (d) { out[d.category] = (out[d.category] || 0) + 1; });
        return out;
      },

      catTabs: function () {
        var self = this;
        return [{ key: "all", text: "全部", count: this.all.length }].concat(
          CATS.filter(function (c) { return self.counts[c]; })
            .map(function (c) { return { key: c, text: c, count: self.counts[c] }; })
        );
      },

      avgProgress: function () {
        if (!this.all.length) return 0;
        return Math.round(this.all.reduce(function (a, d) {
          return a + (parseInt(d.progress, 10) || 0);
        }, 0) / this.all.length);
      },

      running: function () {
        return this.all.filter(function (d) {
          return d.status === "进行中" || d.status === "准备中";
        }).length;
      },

      done: function () { return this.all.filter(function (d) { return d.status === "已完成"; }).length; },

      nearDeadline: function () {
        return this.all.filter(function (d) {
          if (d.status === "已完成") return false;
          var n = U.daysUntil(d.deadline);
          return n !== null && n >= 0 && n <= 30;
        }).length;
      }
    },

    methods: {
      catTone: function (c) { return U.TONES.devCat[c] || "gray"; },
      statusTone: function (s) { return U.TONES.devStatus[s] || "gray"; },

      setCat: function (k) { this.S.filters.dev = k; },

      progTone: function (p) {
        var n = parseInt(p, 10) || 0;
        if (n >= 100) return "green";
        if (n < 30) return "amber";
        return "";
      },

      metric: function (m) {
        var cur = parseFloat(m.current) || 0;
        var tgt = parseFloat(m.target) || 0;
        var p = tgt > 0 ? Math.min(100, Math.round((cur / tgt) * 100)) : 0;
        return { pct: p, hit: tgt > 0 && cur >= tgt, label: m.current + "/" + m.target + " " + (m.unit || "") };
      },

      deadlineClass: function (d) {
        if (d.status === "已完成") return "";
        var n = U.daysUntil(d.deadline);
        if (n === null) return "";
        if (n < 0) return "urgent";
        return n <= 30 ? "warn" : "";
      },

      remove: function (d) { this.forms.remove("development", d); }
    },

    template: `
<div>
  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-ico blue"><fwb-icon name="trending"/></div>
      <div class="stat-info"><div class="stat-val">{{ all.length }}<small>项</small></div>
        <div class="stat-label">发展目标</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-ico amber"><fwb-icon name="clock"/></div>
      <div class="stat-info"><div class="stat-val">{{ running }}<small>项</small></div>
        <div class="stat-label">推进中</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-ico green"><fwb-icon name="check"/></div>
      <div class="stat-info"><div class="stat-val">{{ done }}<small>项</small></div>
        <div class="stat-label">已完成</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-ico violet"><fwb-icon name="chart"/></div>
      <div class="stat-info"><div class="stat-val">{{ avgProgress }}<small>%</small></div>
        <div class="stat-label">整体进度</div></div>
    </div>
  </div>

  <div class="toolbar">
    <div class="chips">
      <div v-for="c in catTabs" :key="c.key" class="chip" :class="{ active: filterKey === c.key }"
           @click="setCat(c.key)">{{ c.text }}<span class="cnt">{{ c.count }}</span></div>
    </div>
    <div class="spacer"></div>
    <span class="muted small" v-if="nearDeadline">{{ nearDeadline }} 项目标将在 30 天内到期</span>
    <button class="btn primary" @click="forms.openForm('development', null)"><fwb-icon name="plus"/>新增目标</button>
  </div>

  <div v-if="!items.length" class="card">
    <div class="empty"><fwb-icon name="trending" :size="44"/><p>该分类下暂无发展目标</p></div>
  </div>

  <div class="card-grid-2">
    <div v-for="d in items" :key="d.id" class="dev-card" :class="catTone(d.category) !== 'blue' ? 'ac-' + catTone(d.category) : ''"
         @click="forms.openForm('development', d)">
      <div class="dev-head">
        <div class="dev-title">{{ d.title }}</div>
        <span class="badge" :class="statusTone(d.status)">{{ d.status }}</span>
      </div>

      <div class="dev-goal" v-if="d.target"><b>目标</b>　{{ d.target }}</div>
      <div class="dev-goal" v-if="d.current"><b>当前</b>　{{ d.current }}</div>

      <div class="dev-prog">
        <div class="progress" :class="progTone(d.progress)"><i :style="{ width: (parseInt(d.progress, 10) || 0) + '%' }"></i></div>
        <span>{{ parseInt(d.progress, 10) || 0 }}%</span>
      </div>

      <div v-for="(m, i) in (d.metrics || [])" :key="i" class="metric-row" :class="{ hit: metric(m).hit }">
        <span class="mr-name" :title="m.name">{{ m.name }}</span>
        <div class="progress"><i :style="{ width: metric(m).pct + '%' }"></i></div>
        <span class="mr-val">{{ metric(m).label }}</span>
      </div>

      <div class="dev-foot">
        <span class="badge gray">{{ d.category || "其他" }}</span>
        <span :class="deadlineClass(d)">{{ U.dueText(d.deadline) }}</span>
      </div>

      <div class="dev-actions" @click.stop>
        <button class="btn text" @click="forms.openForm('development', d)">编辑</button>
        <button class="btn text" style="color:var(--red)" @click="remove(d)">删除</button>
      </div>
    </div>
  </div>
</div>`
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.developments = Developments;
})(window);
