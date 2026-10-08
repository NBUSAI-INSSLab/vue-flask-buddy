/* =====================================================================
   pages/teachings.js —— 教学管理
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  var Teachings = {
    name: "PageTeachings",
    setup: function () { var s = FWB.store; return { S: s.state, act: s.act, U: U, forms: FWB.forms }; },
    computed: {
      all: function () { return this.act.list("teachings"); },
      counts: function () {
        var out = { all: this.all.length };
        this.all.forEach(function (g) { out[g.stage] = (out[g.stage] || 0) + 1; });
        return out;
      },
      stageTabs: function () {
        var self = this;
        return [{ key: "all", text: "全部", count: self.all.length }].concat(
          ["备课中", "进行中", "结课归档", "选题阶段"].filter(function (k) { return self.counts[k]; })
            .map(function (k) { return { key: k, text: k, count: self.counts[k] }; }));
      },
      items: function () {
        var f = this.S.filters.teach;
        return f === "all" ? this.all : this.all.filter(function (g) { return g.stage === f; });
      },
      totalStudents: function () {
        return this.all.reduce(function (s, g) { return s + (parseInt(g.students, 10) || 0); }, 0);
      },
      totalHours: function () {
        return this.all.reduce(function (s, g) { return s + (parseInt(parseFloat(g.hours), 10) || 0); }, 0);
      },
      courseCount: function () {
        return this.all.filter(function (g) { return g.stage === "进行中" || g.stage === "备课中"; }).length;
      }
    },
    methods: {
      setStage: function (k) { this.S.filters.teach = k; },
      tone: function (stage) { return U.TONES.teachStage[stage] || "blue"; },
      sylPct: function (g) {
        return g.syllabusTotal ? Math.round(((g.syllabusDone || 0) / g.syllabusTotal) * 100) : 0;
      },
      dueClass: function (d) {
        var n = U.daysUntil(d);
        if (n === null) return "";
        return n < 0 ? "urgent" : (n <= 7 ? "warn" : "");
      },
      async toggleTask(g, i) {
        var tasks = JSON.parse(JSON.stringify(g.tasks || []));
        tasks[i].done = !tasks[i].done;
        await this.act.update("teachings", g.id, { tasks: tasks });
      }
    },
    template:
      "<div>" +
      '  <div class="mini-stats">' +
      '    <div class="mini-stat"><div class="ms-val">{{ all.length }}<small>门</small></div><div class="ms-lab">教学任务</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ courseCount }}<small>门</small></div><div class="ms-lab">本学期在授</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ totalStudents }}<small>人</small></div><div class="ms-lab">学生总人次</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ totalHours }}<small>学时</small></div><div class="ms-lab">工作量</div></div>' +
      "  </div>" +

      '  <div class="toolbar">' +
      '    <div class="chips">' +
      '      <div v-for="t in stageTabs" :key="t.key" class="chip" :class="{ active: S.filters.teach === t.key }" @click="setStage(t.key)">' +
      '        {{ t.text }}<span class="cnt">{{ t.count }}</span></div>' +
      "    </div>" +
      '    <div class="spacer"></div>' +
      '    <button class="btn primary" @click="forms.openForm(\'teaching\', null)"><fwb-icon name="plus"/>新增教学任务</button>' +
      "  </div>" +

      '  <div v-if="!items.length" class="card"><div class="empty"><fwb-icon name="clipboard" :size="44"/><p>该阶段下暂无教学任务</p></div></div>' +

      '  <div class="card-grid-2">' +
      '    <div v-for="g in items" :key="g.id" class="teach-card" :class="\'ac-\' + tone(g.stage)">' +
      '      <div class="teach-head"><div class="teach-name">{{ g.name }}<small>{{ g.code }} · {{ g.semester }}</small></div>' +
      '        <span class="badge" :class="tone(g.stage)">{{ g.stage }}</span></div>' +
      '      <div class="teach-info">' +
      '        <span class="badge gray">{{ g.type }}</span>' +
      '        <span class="badge gray">{{ g.students }} 人</span>' +
      '        <span class="badge gray">{{ g.hours }} 学时</span>' +
      '        <span class="badge gray" v-if="g.evalScore !== \'—\'">评教 {{ g.evalScore }}</span>' +
      "      </div>" +
      '      <div class="teach-prog"><div class="progress"><i :style="{ width: sylPct(g) + \'%\' }"></i></div>' +
      '        <span>大纲 {{ g.syllabusDone }}/{{ g.syllabusTotal }}</span></div>' +
      '      <div v-for="(t, i) in (g.tasks || [])" :key="i" class="teach-task" :class="{ done: t.done }">' +
      '        <span class="tk-check" @click="toggleTask(g, i)"></span>' +
      '        <span>{{ t.name }}</span><span class="tk-due" :class="dueClass(t.due)">{{ U.dueText(t.due) }}</span>' +
      "      </div>" +
      '      <div class="teach-foot">' +
      '        <span class="muted">{{ g.examType || "—" }}</span>' +
      '        <div class="row" style="gap:6px">' +
      '          <button class="btn text" @click="forms.openForm(\'teaching\', g)">编辑</button>' +
      '          <button class="btn text" style="color:var(--red)" @click="forms.remove(\'teaching\', g)">删除</button>' +
      "        </div>" +
      "      </div>" +
      "    </div>" +
      "  </div>" +
      "</div>"
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.teachings = Teachings;
})(window);
