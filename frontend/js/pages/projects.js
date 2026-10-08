/* =====================================================================
   pages/projects.js —— 科研项目（列表 + 详情）
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  function base() {
    var store = FWB.store;
    return { S: store.state, act: store.act, U: U, forms: FWB.forms };
  }

  /* -------------------- 列表 -------------------- */
  var ProjectList = {
    name: "PageProjects",
    setup: base,
    computed: {
      items: function () { return this.act.list("projects"); },
      filtered: function () {
        var f = this.S.filters.project;
        if (f === "all") return this.items;
        return this.items.filter(function (p) { return p.status === f; });
      },
      counts: function () {
        var out = { all: this.items.length };
        this.items.forEach(function (p) { out[p.status] = (out[p.status] || 0) + 1; });
        return out;
      },
      statusTabs: function () {
        var self = this;
        return ["all", "在研", "验收中", "已结题"].map(function (k) {
          return { key: k, text: k === "all" ? "全部" : k, count: self.counts[k] || 0 };
        });
      },
      totalFunding: function () {
        return this.items.reduce(function (s, p) { return s + (parseFloat(p.funding) || 0); }, 0);
      },
      outcomeCount: function () {
        return this.items.reduce(function (s, p) { return s + ((p.outcomes || []).length); }, 0);
      }
    },
    methods: {
      dueClass: function (d) {
        var n = U.daysUntil(d);
        if (n === null) return "";
        if (n < 0) return "urgent";
        if (n <= 15) return "warn";
        return "";
      },
      setFilter: function (k) { this.S.filters.project = k; },
      phaseClass: function (p) { return p.done ? "done" : (p.active ? "active" : ""); }
    },
    template:
      "<div>" +
      '  <div class="mini-stats">' +
      '    <div class="mini-stat"><div class="ms-val">{{ items.length }}<small>项</small></div><div class="ms-lab">项目总数</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ counts["在研"] || 0 }}<small>项</small></div><div class="ms-lab">在研中</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ totalFunding.toFixed(0) }}<small>万元</small></div><div class="ms-lab">经费合计</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ outcomeCount }}<small>项</small></div><div class="ms-lab">成果产出</div></div>' +
      "  </div>" +

      '  <div class="toolbar">' +
      '    <div class="chips">' +
      '      <div v-for="t in statusTabs" :key="t.key" class="chip" :class="{ active: S.filters.project === t.key }" @click="setFilter(t.key)">' +
      '        {{ t.text }}<span class="cnt">{{ t.count }}</span></div>' +
      "    </div>" +
      '    <div class="spacer"></div>' +
      '    <button class="btn primary" @click="forms.openForm(\'project\', null)"><fwb-icon name="plus"/>新建项目</button>' +
      "  </div>" +

      '  <div v-if="!filtered.length" class="card"><div class="empty"><fwb-icon name="flask" :size="44"/>' +
      "    <p>该分类下暂无项目</p></div></div>" +

      '  <div class="proj-grid">' +
      '    <div v-for="p in filtered" :key="p.id" class="proj-card" @click="act.openDetail(\'project\', p.id)">' +
      '      <div class="pc-head"><div class="pc-name">{{ p.name }}</div>' +
      '        <span class="badge" :class="U.TONES.projStatus[p.status] || \'gray\'">{{ p.status }}</span></div>' +
      '      <div class="pc-code">{{ p.code || "—" }} · {{ p.type }}</div>' +
      '      <div class="pc-meta">' +
      '        <div>本人角色 <b>{{ p.role || "—" }}</b></div>' +
      '        <div>经费 <b>{{ p.funding || "—" }} 万元</b></div>' +
      '        <div>进度 <b>{{ p.progress || 0 }}%</b></div>' +
      "      </div>" +
      '      <div class="pc-phase">' +
      '        <span v-for="(ph, i) in (p.phases || [])" :key="i" class="phase-pill" :class="phaseClass(ph)">{{ ph.name }}</span>' +
      "      </div>" +
      '      <fwb-progress :value="p.progress || 0"/>' +
      '      <div class="pc-foot">' +
      '        <span class="pc-due" :class="dueClass(p.deadline)"><fwb-icon name="clock"/>{{ U.dueText(p.deadline) }}</span>' +
      '        <span class="badge">{{ (p.outcomes || []).length }} 项成果</span>' +
      "      </div>" +
      "    </div>" +
      "  </div>" +
      "</div>"
  };

  /* -------------------- 详情 -------------------- */
  var ProjectDetail = {
    name: "PageProjectDetail",
    setup: base,
    data: function () { return { tab: "phases" }; },
    computed: {
      item: function () { return this.act.get("projects", this.S.detailId); }
    },
    methods: {
      phaseClass: function (p) { return p.done ? "done" : (p.active ? "active" : ""); },
      dueClass: function (d) {
        var n = U.daysUntil(d);
        if (n === null) return "";
        if (n < 0) return "urgent";
        if (n <= 15) return "warn";
        return "";
      },
      edit: function () { this.forms.openForm("project", this.item); },
      del: function () { this.forms.remove("project", this.item); },
      togglePhase: async function (i) {
        var phases = JSON.parse(JSON.stringify(this.item.phases || []));
        phases[i].done = !phases[i].done;
        if (phases[i].done) phases[i].active = false;
        var done = phases.filter(function (x) { return x.done; }).length;
        var progress = phases.length ? Math.round((done / phases.length) * 100) : this.item.progress;
        await this.act.update("projects", this.item.id, { phases: phases, progress: progress });
      }
    },
    template:
      '<div v-if="item">' +
      '  <div class="detail-head">' +
      '    <button class="icon-btn ghost back-btn" @click="act.go(\'projects\')"><fwb-icon name="back"/></button>' +
      '    <div class="detail-title"><h2>{{ item.name }}</h2>' +
      '      <div class="dt-meta">' +
      '        <span class="badge" :class="U.TONES.projStatus[item.status] || \'gray\'">{{ item.status }}</span>' +
      '        <span class="badge blue">{{ item.type }}</span>' +
      '        <span class="badge">{{ item.code || "—" }}</span>' +
      '        <span class="badge gray">{{ item.role || "—" }}</span>' +
      "      </div></div>" +
      '    <div class="row">' +
      '      <button class="btn ghost" @click="edit"><fwb-icon name="edit"/>编辑</button>' +
      '      <button class="btn danger" @click="del"><fwb-icon name="trash"/>删除</button>' +
      "    </div>" +
      "  </div>" +

      '  <div class="card"><div class="card-body">' +
      '    <div class="kv-grid">' +
      '      <div class="kv"><div class="kv-lab">项目经费</div><div class="kv-val">{{ item.funding || "—" }} 万元</div></div>' +
      '      <div class="kv"><div class="kv-lab">开始日期</div><div class="kv-val">{{ item.startDate || "—" }}</div></div>' +
      '      <div class="kv"><div class="kv-lab">截止日期</div><div class="kv-val">{{ item.deadline || "—" }}</div></div>' +
      '      <div class="kv"><div class="kv-lab">剩余时间</div><div class="kv-val" :class="dueClass(item.deadline)">{{ U.dueText(item.deadline) }}</div></div>' +
      "    </div>" +
      '    <div class="detail-sec">' +
      '      <div class="section-title">完成进度（{{ item.progress || 0 }}%）<span class="st-line"></span></div>' +
      '      <fwb-progress :value="item.progress || 0"/>' +
      "    </div>" +
      '    <div v-if="item.desc" class="detail-sec">' +
      '      <div class="section-title">项目简介<span class="st-line"></span></div>' +
      '      <p style="font-size:13px;color:var(--text-2);line-height:1.8">{{ item.desc }}</p>' +
      "    </div>" +
      "  </div></div>" +

      '  <div class="tabs" style="margin-top:18px">' +
      '    <div class="tab" :class="{ active: tab === \'phases\' }" @click="tab = \'phases\'">阶段任务（{{ (item.phases || []).length }}）</div>' +
      '    <div class="tab" :class="{ active: tab === \'outcomes\' }" @click="tab = \'outcomes\'">成果产出（{{ (item.outcomes || []).length }}）</div>' +
      "  </div>" +

      '  <div v-if="tab === \'phases\'" class="card"><div class="card-body">' +
      '    <div class="milestones">' +
      '      <div v-for="(ph, i) in (item.phases || [])" :key="i" class="ms-item" :class="phaseClass(ph)">' +
      '        <div class="between"><div class="ms-title">{{ ph.name }}</div>' +
      '          <button class="btn text" @click="togglePhase(i)">{{ ph.done ? "标记未完成" : "标记完成" }}</button></div>' +
      '        <div class="ms-meta">截止 {{ ph.dueDate || "—" }}</div>' +
      "      </div>" +
      "    </div>" +
      '    <div v-if="!(item.phases || []).length" class="empty"><p>暂无阶段任务</p></div>' +
      "  </div></div>" +

      '  <div v-else class="card"><div class="card-body">' +
      '    <table v-if="(item.outcomes || []).length" class="tbl">' +
      "      <thead><tr><th>类型</th><th>成果名称</th><th>状态</th><th>日期</th></tr></thead>" +
      "      <tbody><tr v-for=\"(o, i) in item.outcomes\" :key=\"i\">" +
      '        <td><span class="badge" :class="U.TONES.achType[o.type] || \'gray\'">{{ o.type }}</span></td>' +
      '        <td class="strong">{{ o.title }}</td><td>{{ o.status }}</td><td>{{ o.date || "—" }}</td>' +
      "      </tr></tbody>" +
      "    </table>" +
      '    <div v-else class="empty"><p>暂无成果产出</p></div>' +
      "  </div></div>" +
      "</div>" +
      '<div v-else class="empty"><fwb-icon name="alert" :size="42"/><p>项目不存在或已删除</p>' +
      '  <button class="btn ghost mt-2" @click="act.go(\'projects\')">返回项目列表</button></div>'
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.projects = ProjectList;
  FWB.pages["project-detail"] = ProjectDetail;
})(window);
