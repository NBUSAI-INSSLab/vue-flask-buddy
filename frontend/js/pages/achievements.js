/* =====================================================================
   pages/achievements.js —— 成果管理
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  var Achievements = {
    name: "PageAchievements",
    setup: function () { var s = FWB.store; return { S: s.state, act: s.act, U: U, forms: FWB.forms }; },
    computed: {
      all: function () { return this.act.list("achievements"); },
      counts: function () {
        var out = { all: this.all.length };
        this.all.forEach(function (a) { out[a.type] = (out[a.type] || 0) + 1; });
        return out;
      },
      typeTabs: function () {
        var self = this;
        return [{ key: "all", text: "全部", count: self.all.length }].concat(
          Object.keys(self.counts).filter(function (k) { return k !== "all"; })
            .sort(function (a, b) { return self.counts[b] - self.counts[a]; })
            .map(function (k) { return { key: k, text: k, count: self.counts[k] }; }));
      },
      items: function () {
        var f = this.S.filters.ach;
        var arr = f === "all" ? this.all : this.all.filter(function (a) { return a.type === f; });
        return arr.slice().sort(function (a, b) {
          return String(b.date || "0000").localeCompare(String(a.date || "0000"));
        });
      },
      totalScore: function () {
        return this.all.reduce(function (s, a) { return s + (parseFloat(a.score) || 0); }, 0);
      },
      publishedCount: function () {
        var done = ["已发表", "已录用", "已授权", "已登记", "已交付", "已获奖"];
        return this.all.filter(function (a) { return done.indexOf(a.status) >= 0; }).length;
      },
      projName: function () {
        var map = {};
        this.act.list("projects").forEach(function (p) { map[p.id] = p.name; });
        return map;
      },
      pendingCount: function () { return this.all.filter(function (a) { return (a.auditStatus || "待审核") === "待审核"; }).length; },
      rejectedCount: function () { return this.all.filter(function (a) { return a.auditStatus === "已退回"; }).length; }
    },
    methods: {
      setType: function (k) { this.S.filters.ach = k; },
      tone: function (type) { return U.TONES.achType[type] || "gray"; },
      /* 注意：带参数，必须是 methods 而非 computed */
      auditOf: function (a) { return (a && a.auditStatus) || "待审核"; },
      auditTone: function (st) {
        return { "待审核": "wait", "已通过": "ok", "已退回": "off" }[st || "待审核"] || "gray";
      },
      statusTone: function (st) {
        if (["已发表", "已录用", "已授权", "已登记", "已交付", "已获奖"].indexOf(st) >= 0) return "green";
        if (["审稿中", "撰写中", "实质审查", "申报中"].indexOf(st) >= 0) return "amber";
        return "gray";
      }
    },
    template:
      "<div>" +
      '  <div class="mini-stats">' +
      '    <div class="mini-stat"><div class="ms-val">{{ all.length }}<small>项</small></div><div class="ms-lab">成果总数</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ publishedCount }}<small>项</small></div><div class="ms-lab">已发表 / 授权</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ totalScore.toFixed(1) }}<small>分</small></div><div class="ms-lab">业绩分合计</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ counts["期刊论文"] || 0 }}<small>篇</small></div><div class="ms-lab">期刊论文</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ pendingCount }}<small>项</small></div><div class="ms-lab">待学院审核</div></div>' +
      '    <div class="mini-stat"><div class="ms-val" :class="{ \'em\': rejectedCount }">{{ rejectedCount }}<small>项</small></div><div class="ms-lab">已退回待修改</div></div>' +
      "  </div>" +

      '  <div class="toolbar">' +
      '    <div class="chips">' +
      '      <div v-for="t in typeTabs" :key="t.key" class="chip" :class="{ active: S.filters.ach === t.key }" @click="setType(t.key)">' +
      '        {{ t.text }}<span class="cnt">{{ t.count }}</span></div>' +
      "    </div>" +
      '    <div class="spacer"></div>' +
      '    <button class="btn primary" @click="forms.openForm(\'achievement\', null)"><fwb-icon name="plus"/>登记成果</button>' +
      "  </div>" +

      '  <div v-if="!items.length" class="card"><div class="empty"><fwb-icon name="medal" :size="44"/><p>该类型下暂无成果</p></div></div>' +

      '  <div class="lit-list">' +
      '    <div v-for="a in items" :key="a.id" class="ach-card" :class="\'ac-\' + tone(a.type)">' +
      '      <div class="ach-head"><div class="ach-title">{{ a.title }}</div>' +
      '        <span class="audit-tag" :class="auditTone(auditOf(a))">学院{{ auditOf(a) }}</span>' +
      '        <span class="badge" :class="statusTone(a.status)">{{ a.status }}</span></div>' +
      '      <div class="ach-authors"><b>{{ a.authors || "—" }}</b>' +
      '        <span v-if="a.role" class="muted"> · {{ a.role }}</span></div>' +
      '      <div class="ach-meta">' +
      '        <span class="badge" :class="tone(a.type)">{{ a.type }}</span>' +
      '        <span class="badge gray" v-if="a.level">{{ a.level }}</span>' +
      '        <span class="badge gray" v-if="a.venue">{{ a.venue }}</span>' +
      "      </div>" +
      '      <div v-if="a.note" class="ach-note">{{ a.note }}</div>' +
      '      <div v-if="a.auditStatus === \'已退回\' && a.auditNote" class="ach-audit-note">' +
      '        <fwb-icon name="alert"/><span>学院审核意见：{{ a.auditNote }}</span></div>' +
      '      <div v-else-if="a.auditStatus === \'已通过\' && a.auditBy" class="ach-audit-note ok">' +
      '        <fwb-icon name="check"/><span>{{ a.auditBy }} 于 {{ a.auditAt }} 审核通过</span></div>' +
      '      <div class="ach-foot">' +
      '        <span class="muted small">{{ a.date || "未定" }}<template v-if="projName[a.projectId]"> · {{ projName[a.projectId] }}</template></span>' +
      '        <div class="row" style="gap:8px">' +
      '          <span class="ach-score">业绩分 {{ a.score || 0 }}</span>' +
      '          <button class="btn text" @click="forms.openForm(\'achievement\', a)">编辑</button>' +
      '          <button class="btn text" style="color:var(--red)" @click="forms.remove(\'achievement\', a)">删除</button>' +
      "        </div>" +
      "      </div>" +
      "    </div>" +
      "  </div>" +
      "</div>"
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.achievements = Achievements;
})(window);
