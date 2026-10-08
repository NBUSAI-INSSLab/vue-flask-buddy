/* =====================================================================
   pages/exchanges.js —— 学术交流
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  var Exchanges = {
    name: "PageExchanges",
    setup: function () { var s = FWB.store; return { S: s.state, act: s.act, U: U, forms: FWB.forms }; },
    computed: {
      all: function () { return this.act.list("exchanges"); },
      counts: function () {
        var out = { all: this.all.length };
        this.all.forEach(function (x) { out[x.kind] = (out[x.kind] || 0) + 1; });
        return out;
      },
      kindTabs: function () {
        var self = this;
        var keys = ["学术会议", "期刊审稿", "基金评审", "企业交流", "学术报告"];
        return [{ key: "all", text: "全部", count: self.all.length }].concat(
          keys.filter(function (k) { return self.counts[k]; }).map(function (k) {
            return { key: k, text: k, count: self.counts[k] };
          }));
      },
      items: function () {
        var f = this.S.filters.exch;
        var arr = f === "all" ? this.all : this.all.filter(function (x) { return x.kind === f; });
        return arr.slice().sort(function (a, b) {
          return String(a.start || "").localeCompare(String(b.start || ""));
        });
      },
      activeCount: function () {
        return this.all.filter(function (x) { return x.status === "已确认" || x.status === "进行中"; }).length;
      },
      reviewCount: function () {
        return this.all.filter(function (x) { return x.kind === "期刊审稿" || x.kind === "基金评审"; }).length;
      }
    },
    methods: {
      setKind: function (k) { this.S.filters.exch = k; },
      tone: function (kind) { return U.TONES.exchKind[kind] || "gray"; },
      statusTone: function (st) { return U.TONES.exchStatus[st] || "gray"; },
      range: function (x) {
        if (!x.start) return "待定";
        return x.end && x.end !== x.start ? x.start + " ~ " + x.end : x.start;
      }
    },
    template:
      "<div>" +
      '  <div class="mini-stats">' +
      '    <div class="mini-stat"><div class="ms-val">{{ all.length }}<small>项</small></div><div class="ms-lab">交流活动</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ activeCount }}<small>项</small></div><div class="ms-lab">进行中 / 已确认</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ reviewCount }}<small>项</small></div><div class="ms-lab">审稿与评审</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ counts["学术会议"] || 0 }}<small>项</small></div><div class="ms-lab">学术会议</div></div>' +
      "  </div>" +

      '  <div class="toolbar">' +
      '    <div class="chips">' +
      '      <div v-for="t in kindTabs" :key="t.key" class="chip" :class="{ active: S.filters.exch === t.key }" @click="setKind(t.key)">' +
      '        {{ t.text }}<span class="cnt">{{ t.count }}</span></div>' +
      "    </div>" +
      '    <div class="spacer"></div>' +
      '    <button class="btn primary" @click="forms.openForm(\'exchange\', null)"><fwb-icon name="plus"/>新增交流</button>' +
      "  </div>" +

      '  <div v-if="!items.length" class="card"><div class="empty"><fwb-icon name="globe" :size="44"/><p>该分类下暂无记录</p></div></div>' +

      '  <div class="card-grid-2">' +
      '    <div v-for="x in items" :key="x.id" class="xc-card" :class="\'ac-\' + tone(x.kind)">' +
      '      <div class="xc-head"><div class="xc-title">{{ x.title }}</div>' +
      '        <span class="badge" :class="statusTone(x.status)">{{ x.status }}</span></div>' +
      '      <div class="xc-org">{{ x.organizer || "—" }}</div>' +
      '      <div class="xc-meta">' +
      '        <span class="badge" :class="tone(x.kind)">{{ x.kind }}</span>' +
      '        <span class="badge gray" v-if="x.role">{{ x.role }}</span>' +
      '        <span class="badge gray" v-if="x.level">{{ x.level }}</span>' +
      "      </div>" +
      '      <div class="xc-topic" v-if="x.topic">{{ x.topic }}</div>' +
      '      <div class="xc-foot">' +
      '        <span class="xc-when"><fwb-icon name="calendar"/>{{ range(x) }}</span>' +
      '        <div class="row" style="gap:6px">' +
      '          <button class="btn text" @click="forms.openForm(\'exchange\', x)">编辑</button>' +
      '          <button class="btn text" style="color:var(--red)" @click="forms.remove(\'exchange\', x)">删除</button>' +
      "        </div>" +
      "      </div>" +
      '      <div v-if="x.location" class="xc-when" style="margin-top:8px"><fwb-icon name="pin"/>{{ x.location }}</div>' +
      "    </div>" +
      "  </div>" +
      "</div>"
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.exchanges = Exchanges;
})(window);
