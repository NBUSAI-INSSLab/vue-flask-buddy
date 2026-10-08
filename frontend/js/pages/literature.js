/* =====================================================================
   pages/literature.js —— 文献仓库（列表 + 详情）
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  var LitList = {
    name: "PageLiterature",
    setup: function () { var s = FWB.store; return { S: s.state, act: s.act, U: U, forms: FWB.forms }; },
    methods: {
      setDir: function (d) { this.S.filters.lit = d; },
      kw: function (l) {
        return [l.title, l.authors, l.journal, l.direction].join(" ").toLowerCase();
      }
    },
    computed: {
      all: function () { return this.act.list("literature"); },
      directions: function () {
        var out = { all: this.all.length };
        this.all.forEach(function (l) {
          var d = l.direction || "未分类";
          out[d] = (out[d] || 0) + 1;
        });
        return out;
      },
      dirTabs: function () {
        var self = this;
        return Object.keys(this.directions).sort(function (a, b) {
          return a === "all" ? -1 : self.directions[b] - self.directions[a];
        }).map(function (k) {
          return { key: k, text: k === "all" ? "全部方向" : k, count: self.directions[k] };
        });
      },
      items: function () {
        var f = this.S.filters.lit;
        return f === "all" ? this.all : this.all.filter(function (l) { return (l.direction || "未分类") === f; });
      },
      readCount: function () { return this.all.filter(function (l) { return l.status === "已读"; }).length; },
      avgRating: function () {
        if (!this.all.length) return 0;
        return this.all.reduce(function (s, l) { return s + (Number(l.rating) || 0); }, 0) / this.all.length;
      }
    },
    template:
      "<div>" +
      '  <div class="mini-stats">' +
      '    <div class="mini-stat"><div class="ms-val">{{ all.length }}<small>篇</small></div><div class="ms-lab">文献总量</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ readCount }}<small>篇</small></div><div class="ms-lab">已精读</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ (all.length - readCount) }}<small>篇</small></div><div class="ms-lab">待读 / 在读</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ avgRating.toFixed(1) }}<small>/5</small></div><div class="ms-lab">平均评分</div></div>' +
      "  </div>" +

      '  <div class="toolbar">' +
      '    <div class="chips">' +
      '      <div v-for="t in dirTabs" :key="t.key" class="chip" :class="{ active: S.filters.lit === t.key }" @click="setDir(t.key)">' +
      '        {{ t.text }}<span class="cnt">{{ t.count }}</span></div>' +
      "    </div>" +
      '    <div class="spacer"></div>' +
      '    <button class="btn primary" @click="forms.openForm(\'literature\', null)"><fwb-icon name="plus"/>新增文献</button>' +
      "  </div>" +

      '  <div v-if="!items.length" class="card"><div class="empty"><fwb-icon name="book" :size="44"/><p>该方向下暂无文献</p></div></div>' +

      '  <div class="lit-list">' +
      '    <div v-for="l in items" :key="l.id" class="lit-item" @click="act.openDetail(\'lit\', l.id)">' +
      '      <div class="lit-main">' +
      '        <div class="lit-title">{{ l.title }}</div>' +
      '        <div class="lit-authors"><b>{{ l.authors || "—" }}</b></div>' +
      '        <div class="lit-journal">{{ l.journal || "" }} · {{ l.year || "" }}</div>' +
      '        <div class="lit-tags">' +
      '          <span class="badge" :class="l.status === \'已读\' ? \'green\' : (l.status === \'在读\' ? \'blue\' : \'gray\')">{{ l.status }}</span>' +
      '          <span class="badge violet" v-if="l.direction">{{ l.direction }}</span>' +
      '          <span v-for="t in (l.tags || [])" :key="t" class="badge gray">{{ t }}</span>' +
      "        </div>" +
      '        <div v-if="l.note" class="lit-note-preview">{{ l.note }}</div>' +
      "      </div>" +
      '      <div class="lit-side">' +
      '        <fwb-stars :value="Number(l.rating) || 0"/>' +
      '        <span class="badge gray">{{ l.addedDate || "" }}</span>' +
      "      </div>" +
      "    </div>" +
      "  </div>" +
      "</div>"
  };

  var LitDetail = {
    name: "PageLitDetail",
    setup: function () { var s = FWB.store; return { S: s.state, act: s.act, U: U, forms: FWB.forms }; },
    computed: {
      item: function () { return this.act.get("literature", this.S.detailId); }
    },
    methods: {
      edit: function () { this.forms.openForm("literature", this.item); },
      del: function () { this.forms.remove("literature", this.item); },
      async setStatus(s) { await this.act.update("literature", this.item.id, { status: s }); }
    },
    template:
      '<div v-if="item">' +
      '  <div class="detail-head">' +
      '    <button class="icon-btn ghost back-btn" @click="act.go(\'literature\')"><fwb-icon name="back"/></button>' +
      '    <div class="detail-title"><h2>{{ item.title }}</h2>' +
      '      <div class="dt-meta">' +
      '        <span class="badge" :class="item.status === \'已读\' ? \'green\' : (item.status === \'在读\' ? \'blue\' : \'gray\')">{{ item.status }}</span>' +
      '        <span class="badge violet" v-if="item.direction">{{ item.direction }}</span>' +
      '        <fwb-stars :value="Number(item.rating) || 0"/>' +
      "      </div></div>" +
      '    <div class="row">' +
      '      <button class="btn ghost sm" @click="setStatus(\'未读\')">未读</button>' +
      '      <button class="btn ghost sm" @click="setStatus(\'在读\')">在读</button>' +
      '      <button class="btn ghost sm" @click="setStatus(\'已读\')">已读</button>' +
      '      <button class="btn ghost" @click="edit"><fwb-icon name="edit"/>编辑</button>' +
      '      <button class="btn danger" @click="del"><fwb-icon name="trash"/>删除</button>' +
      "    </div>" +
      "  </div>" +

      '  <div class="card"><div class="card-body">' +
      '    <div class="kv-list">' +
      '      <div class="kv-row"><div class="kv-k">作者</div><div class="kv-v">{{ item.authors || "—" }}</div></div>' +
      '      <div class="kv-row"><div class="kv-k">期刊 / 会议</div><div class="kv-v">{{ item.journal || "—" }}</div></div>' +
      '      <div class="kv-row"><div class="kv-k">年份</div><div class="kv-v">{{ item.year || "—" }}</div></div>' +
      '      <div class="kv-row"><div class="kv-k">DOI</div><div class="kv-v">{{ item.doi || "—" }}</div></div>' +
      '      <div class="kv-row"><div class="kv-k">收录日期</div><div class="kv-v">{{ item.addedDate || "—" }}</div></div>' +
      '      <div class="kv-row"><div class="kv-k">标签</div><div class="kv-v">' +
      '        <span v-for="t in (item.tags || [])" :key="t" class="badge gray" style="margin-right:6px">{{ t }}</span>' +
      '        <span v-if="!(item.tags || []).length">—</span></div></div>' +
      "    </div>" +
      "  </div></div>" +

      '  <div class="card mt-2"><div class="card-head"><h3><span class="ch-ico"><fwb-icon name="notebook"/></span>阅读笔记</h3></div>' +
      '    <div class="card-body"><p style="font-size:13.5px;color:var(--text-2);line-height:1.85;white-space:pre-wrap">{{ item.note || "（暂无笔记）" }}</p></div>' +
      "  </div>" +
      "</div>" +
      '<div v-else class="empty"><fwb-icon name="alert" :size="42"/><p>文献不存在或已删除</p>' +
      '  <button class="btn ghost mt-2" @click="act.go(\'literature\')">返回文献仓库</button></div>'
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.literature = LitList;
  FWB.pages["lit-detail"] = LitDetail;
})(window);
