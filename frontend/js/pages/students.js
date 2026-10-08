/* =====================================================================
   pages/students.js —— 学生指导（列表 + 详情）
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  var Students = {
    name: "PageStudents",
    setup: function () { var s = FWB.store; return { S: s.state, act: s.act, U: U, forms: FWB.forms }; },
    computed: {
      items: function () { return this.act.list("students"); },
      masters: function () { return this.items.filter(function (s) { return s.degree === "硕士"; }).length; },
      doctors: function () { return this.items.filter(function (s) { return s.degree === "博士"; }).length; },
      avgProgress: function () {
        if (!this.items.length) return 0;
        return Math.round(this.items.reduce(function (a, s) { return a + (Number(s.progress) || 0); }, 0) / this.items.length);
      },
      lagging: function () { return this.items.filter(function (s) { return (Number(s.progress) || 0) < 50; }).length; }
    },
    methods: {
      avatarColor: function (n) { return U.avatarColor(n); },
      msDone: function (s) {
        var ms = s.milestones || [];
        return ms.filter(function (m) { return m.done; }).length + "/" + ms.length;
      },
      nextTone: function (d) {
        var n = U.daysUntil(d);
        if (n === null) return "gray";
        if (n <= 3) return "amber";
        return "gray";
      }
    },
    template:
      "<div>" +
      '  <div class="mini-stats">' +
      '    <div class="mini-stat"><div class="ms-val">{{ items.length }}<small>人</small></div><div class="ms-lab">指导学生</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ masters }}<small>人</small></div><div class="ms-lab">硕士生</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ doctors }}<small>人</small></div><div class="ms-lab">博士生</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ avgProgress }}<small>%</small></div><div class="ms-lab">平均论文进度</div></div>' +
      "  </div>" +

      '  <div class="toolbar">' +
      '    <span class="muted small">{{ lagging }} 名学生进度低于 50%，建议优先沟通</span>' +
      '    <div class="spacer"></div>' +
      '    <button class="btn primary" @click="forms.openForm(\'student\', null)"><fwb-icon name="plus"/>新增学生</button>' +
      "  </div>" +

      '  <div v-if="!items.length" class="card"><div class="empty"><fwb-icon name="users" :size="44"/><p>暂无学生信息</p></div></div>' +

      '  <div class="stu-grid">' +
      '    <div v-for="s in items" :key="s.id" class="stu-card" @click="act.openDetail(\'student\', s.id)">' +
      '      <div class="stu-head">' +
      '        <div class="stu-avatar" :style="{ background: avatarColor(s.name) }">{{ s.name.charAt(0) }}</div>' +
      '        <div style="flex:1;min-width:0"><div class="stu-name">{{ s.name }}' +
      '          <span class="badge" :class="s.degree === \'博士\' ? \'violet\' : \'blue\'">{{ s.degree }}</span></div>' +
      '          <div class="stu-sub">{{ s.grade }} · {{ s.direction }}</div></div>' +
      "      </div>" +
      '      <div class="stu-field"><div class="sf-lab">学位论文</div><div class="sf-val">{{ s.thesisTitle || "—" }}</div></div>' +
      '      <div class="stu-field"><div class="sf-lab">论文进度 · 里程碑 {{ msDone(s) }}</div>' +
      '        <fwb-progress :value="Number(s.progress) || 0"/></div>' +
      '      <div class="stu-foot">' +
      '        <span class="badge gray">{{ s.stage }}</span>' +
      '        <span class="stu-meet"><fwb-icon name="calendar"/>{{ U.cnDate(s.nextMeeting) }}</span>' +
      "      </div>" +
      "    </div>" +
      "  </div>" +
      "</div>"
  };

  var StudentDetail = {
    name: "PageStudentDetail",
    setup: function () { var s = FWB.store; return { S: s.state, act: s.act, U: U, forms: FWB.forms }; },
    computed: {
      item: function () { return this.act.get("students", this.S.detailId); },
      logs: function () {
        return ((this.item && this.item.logs) || []).slice().sort(function (a, b) {
          return String(b.date || "").localeCompare(String(a.date || ""));
        });
      }
    },
    methods: {
      avatarColor: function (n) { return U.avatarColor(n); },
      msClass: function (m) { return m.done ? "done" : (m.active ? "active" : ""); },
      edit: function () { this.forms.openForm("student", this.item); },
      del: function () { this.forms.remove("student", this.item); },
      async toggleMs(i) {
        var ms = JSON.parse(JSON.stringify(this.item.milestones || []));
        ms[i].done = !ms[i].done;
        if (ms[i].done) ms[i].active = false;
        await this.act.update("students", this.item.id, { milestones: ms });
      },
      logTone: function (t) { return t === "组会" ? "violet" : (t === "个别指导" ? "blue" : "gray"); },
      addLog: function () {
        var self = this;
        var act = this.act;
        act.openModal({
          component: "fwb-form", wide: false,
          title: "记录沟通 / 指导",
          props: {
            spec: {
              title: "记录沟通 / 指导",
              submitLabel: "保存记录",
              fields: [
                { name: "date", label: "日期", type: "date", value: U.today() },
                { name: "type", label: "类型", type: "select", opts: ["组会", "个别指导", "邮件沟通", "答辩"], value: "个别指导" },
                { name: "content", label: "沟通内容与教师意见", type: "textarea", rows: 4, ph: "学生汇报内容 / 存在的问题 / 教师指导意见…" }
              ],
              onSubmit: async function (payload) {
                if (!String(payload.content || "").trim()) throw new Error("请填写沟通内容");
                var logs = JSON.parse(JSON.stringify(self.item.logs || []));
                logs.unshift(payload);
                await act.update("students", self.item.id, { logs: logs });
                act.toast("已记录", "success");
              }
            },
            initial: {}
          }
        });
      }
    },
    template:
      '<div v-if="item">' +
      '  <div class="detail-head">' +
      '    <button class="icon-btn ghost back-btn" @click="act.go(\'students\')"><fwb-icon name="back"/></button>' +
      '    <div class="stu-avatar" :style="{ background: avatarColor(item.name), width: \'46px\', height: \'46px\', fontSize: \'18px\' }">' +
      "      {{ item.name.charAt(0) }}</div>" +
      '    <div class="detail-title"><h2 style="font-size:18px">{{ item.name }}</h2>' +
      '      <div class="dt-meta">' +
      '        <span class="badge" :class="item.degree === \'博士\' ? \'violet\' : \'blue\'">{{ item.degree }}</span>' +
      '        <span class="badge gray">{{ item.grade }}</span>' +
      '        <span class="badge gray">{{ item.direction }}</span>' +
      '        <span class="badge blue">{{ item.stage }}</span>' +
      "      </div></div>" +
      '    <div class="row">' +
      '      <button class="btn ghost" @click="addLog"><fwb-icon name="plus"/>记录沟通</button>' +
      '      <button class="btn ghost" @click="edit"><fwb-icon name="edit"/>编辑</button>' +
      '      <button class="btn danger" @click="del"><fwb-icon name="trash"/>删除</button>' +
      "    </div>" +
      "  </div>" +

      '  <div class="grid-2">' +
      '    <div class="col" style="display:flex;flex-direction:column;gap:16px">' +
      '      <div class="card"><div class="card-body">' +
      '        <div class="kv-list">' +
      '          <div class="kv-row"><div class="kv-k">学位论文</div><div class="kv-v">{{ item.thesisTitle || "—" }}</div></div>' +
      '          <div class="kv-row"><div class="kv-k">邮箱</div><div class="kv-v">{{ item.email || "—" }}</div></div>' +
      '          <div class="kv-row"><div class="kv-k">下次沟通</div><div class="kv-v">{{ U.cnDate(item.nextMeeting) || "未安排" }}</div></div>' +
      "        </div>" +
      '        <div class="detail-sec">' +
      '          <div class="section-title">论文进度 {{ item.progress || 0 }}%<span class="st-line"></span></div>' +
      '          <fwb-progress :value="Number(item.progress) || 0"/>' +
      "        </div>" +
      "      </div></div>" +

      '      <div class="card"><div class="card-head"><h3><span class="ch-ico"><fwb-icon name="target"/></span>论文里程碑</h3></div>' +
      '        <div class="card-body"><div class="milestones">' +
      '          <div v-for="(m, i) in (item.milestones || [])" :key="i" class="ms-item" :class="msClass(m)">' +
      '            <div class="between"><div class="ms-title">{{ m.name }}</div>' +
      '              <button class="btn text" @click="toggleMs(i)">{{ m.done ? "撤销" : "完成" }}</button></div>' +
      '            <div class="ms-meta">{{ m.date }}</div>' +
      "          </div>" +
      "        </div></div></div>" +
      "    </div>" +

      '    <div class="card"><div class="card-head"><h3><span class="ch-ico"><fwb-icon name="notebook"/></span>沟通记录（{{ logs.length }}）</h3>' +
      '      <span class="more" @click="addLog">新增<fwb-icon name="plus"/></span></div>' +
      '      <div class="card-body">' +
      '        <div v-if="!logs.length" class="empty" style="padding:26px 0"><p>暂无沟通记录</p></div>' +
      '        <div v-for="(l, i) in logs" :key="i" class="log-item">' +
      '          <div class="log-date">{{ U.cnDateShort(l.date) }}<small>{{ l.date }}</small></div>' +
      '          <div class="log-body"><div class="log-tag"><span class="badge" :class="logTone(l.type)">{{ l.type }}</span></div>' +
      '            <div class="log-content">{{ l.content }}</div></div>' +
      "        </div>" +
      "      </div></div>" +
      "  </div>" +
      "</div>" +
      '<div v-else class="empty"><fwb-icon name="alert" :size="42"/><p>学生信息不存在</p>' +
      '  <button class="btn ghost mt-2" @click="act.go(\'students\')">返回学生指导</button></div>'
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.students = Students;
  FWB.pages["student-detail"] = StudentDetail;
})(window);
