/* =====================================================================
   pages/schedule.js —— 日程管理（月历 + 当日安排）
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  var TYPES = ["上课", "组会", "会议", "答辩", "申报", "其他"];

  var Schedule = {
    name: "PageSchedule",
    setup: function () { var s = FWB.store; return { S: s.state, act: s.act, U: U, forms: FWB.forms }; },

    data: function () {
      var now = new Date();
      return {
        calMonth: new Date(now.getFullYear(), now.getMonth(), 1),
        calSel: U.today()
      };
    },

    computed: {
      all: function () { return this.act.list("events"); },

      filterKey: function () { return this.S.filters.ev || "all"; },

      filtered: function () {
        var f = this.filterKey;
        if (f === "all") return this.all;
        return this.all.filter(function (e) { return e.type === f; });
      },

      counts: function () {
        var out = { all: this.all.length };
        this.all.forEach(function (e) { out[e.type] = (out[e.type] || 0) + 1; });
        return out;
      },

      typeTabs: function () {
        var self = this;
        return [{ key: "all", text: "全部", count: this.all.length }].concat(
          TYPES.filter(function (t) { return self.counts[t]; })
            .map(function (t) { return { key: t, text: t, count: self.counts[t] }; })
        );
      },

      todayYmd: function () { return U.today(); },

      monthLabel: function () {
        return this.calMonth.getFullYear() + " 年 " + (this.calMonth.getMonth() + 1) + " 月";
      },

      dow: function () { return ["一", "二", "三", "四", "五", "六", "日"]; },

      /* 完整日历格子（周一为第一列） */
      cells: function () {
        var y = this.calMonth.getFullYear();
        var m = this.calMonth.getMonth();
        var startOffset = (new Date(y, m, 1).getDay() + 6) % 7;
        var daysInMonth = new Date(y, m + 1, 0).getDate();
        var prevDays = new Date(y, m, 0).getDate();
        var out = [];
        var i, d, ymd;

        for (i = 0; i < startOffset; i++) {
          out.push({ other: true, n: prevDays - startOffset + i + 1, ymd: "", events: [] });
        }
        for (d = 1; d <= daysInMonth; d++) {
          ymd = y + "-" + U.pad(m + 1) + "-" + U.pad(d);
          out.push({ other: false, n: d, ymd: ymd, events: this.eventsOf(ymd) });
        }
        var tail = (7 - (out.length % 7)) % 7;
        for (i = 1; i <= tail; i++) {
          out.push({ other: true, n: i, ymd: "", events: [] });
        }
        return out;
      },

      agendaDay: function () { return U.cnDate(this.calSel); },

      agenda: function () {
        return this.eventsOf(this.calSel).slice().sort(function (a, b) {
          return String(a.start || "").localeCompare(String(b.start || ""));
        });
      },

      todayCount: function () { return this.eventsOf(U.today()).length; },

      weekCount: function () {
        var a = U.today(), b = U.dayOffset(7);
        return this.all.filter(function (e) {
          var d = String(e.date || "");
          return d >= a && d <= b;
        }).length;
      },

      undone: function () { return this.all.filter(function (e) { return !e.done; }).length; },

      overdue: function () {
        var self = this;
        var t = U.today();
        return this.all.filter(function (e) {
          return !e.done && String(e.date || "") < t && self.isPastSlot(e);
        }).length;
      }
    },

    methods: {
      tone: function (type) { return U.TONES.evType[type] || "gray"; },

      eventsOf: function (ymd) {
        if (!ymd) return [];
        return this.filtered.filter(function (e) { return e.date === ymd; });
      },

      /* 同一天内已过时间也算逾期，便于提示 */
      isPastSlot: function (e) {
        var now = new Date();
        var hhmm = U.pad(now.getHours()) + ":" + U.pad(now.getMinutes());
        return String(e.end || e.start || "23:59") < hhmm;
      },

      setType: function (k) { this.S.filters.ev = k; },

      sel: function (ymd) { if (ymd) this.calSel = ymd; },

      prevMonth: function () {
        this.calMonth = new Date(this.calMonth.getFullYear(), this.calMonth.getMonth() - 1, 1);
      },

      nextMonth: function () {
        this.calMonth = new Date(this.calMonth.getFullYear(), this.calMonth.getMonth() + 1, 1);
      },

      goToday: function () {
        var now = new Date();
        this.calMonth = new Date(now.getFullYear(), now.getMonth(), 1);
        this.calSel = U.today();
      },

      async toggleDone(e) {
        await this.act.update("events", e.id, { done: !e.done });
      }
    },

    template: `
<div>
  <div class="mini-stats">
    <div class="mini-stat"><div class="ms-val">{{ todayCount }}<small>项</small></div><div class="ms-lab">今日安排</div></div>
    <div class="mini-stat"><div class="ms-val">{{ weekCount }}<small>项</small></div><div class="ms-lab">未来 7 天</div></div>
    <div class="mini-stat"><div class="ms-val">{{ undone }}<small>项</small></div><div class="ms-lab">未完成</div></div>
    <div class="mini-stat"><div class="ms-val" :style="overdue ? 'color:var(--red)' : null">{{ overdue }}<small>项</small></div>
      <div class="ms-lab">已逾期</div></div>
  </div>

  <div class="toolbar">
    <div class="chips">
      <div v-for="t in typeTabs" :key="t.key" class="chip" :class="{ active: filterKey === t.key }"
           @click="setType(t.key)">{{ t.text }}<span class="cnt">{{ t.count }}</span></div>
    </div>
    <div class="spacer"></div>
    <button class="btn primary" @click="forms.openForm('event', null)"><fwb-icon name="plus"/>新建日程</button>
  </div>

  <div class="sched-grid">
    <div class="card">
      <div class="cal-head">
        <div class="cal-title">{{ monthLabel }}</div>
        <div class="cal-nav">
          <button class="btn ghost sm" @click="goToday">今天</button>
          <button class="icon-btn" title="上个月" @click="prevMonth"><fwb-icon name="left"/></button>
          <button class="icon-btn" title="下个月" @click="nextMonth"><fwb-icon name="right"/></button>
        </div>
      </div>
      <div class="cal-grid">
        <div v-for="d in dow" :key="d" class="cal-dow">{{ d }}</div>
        <div v-for="(c, i) in cells" :key="i" class="cal-day"
             :class="{ other: c.other, today: c.ymd === todayYmd, sel: c.ymd === calSel }"
             :style="c.ymd ? 'cursor:pointer' : null" @click="sel(c.ymd)">
          <div class="cd-num">{{ c.n }}</div>
          <div v-if="c.events.length" class="cd-events">
            <div v-for="e in c.events.slice(0, 2)" :key="e.id" class="cd-event" :class="tone(e.type)"
                 :title="e.title">{{ e.start }} {{ e.title }}</div>
            <div v-if="c.events.length > 2" class="cd-more">+{{ c.events.length - 2 }} 项</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="agenda-day">{{ agendaDay }}
        <span class="badge blue" v-if="calSel === todayYmd" style="margin-left:6px">今天</span></div>
      <div v-if="!agenda.length" class="empty" style="padding:44px 20px">
        <fwb-icon name="calendar" :size="40"/><p>这一天暂无安排</p></div>
      <div v-for="e in agenda" :key="e.id" class="agenda-item" @click="forms.openForm('event', e)">
        <div class="ag-time">{{ e.start || "--:--" }}<small>{{ e.end || "" }}</small></div>
        <div class="ag-bar" :class="tone(e.type)"></div>
        <div class="ag-body">
          <div class="ag-title" :style="e.done ? 'text-decoration:line-through;color:var(--text-3)' : null">{{ e.title }}</div>
          <div class="ag-meta">
            <span><fwb-icon name="clock"/>{{ e.start || "—" }} - {{ e.end || "—" }}</span>
            <span><fwb-icon name="pin"/>{{ e.location || "—" }}</span>
            <span class="badge" :class="tone(e.type)">{{ e.type }}</span>
          </div>
          <div v-if="e.note" class="small muted mt-1">{{ e.note }}</div>
        </div>
        <button class="icon-btn ghost" :title="e.done ? '标记为未完成' : '标记为已完成'"
                @click.stop="toggleDone(e)">
          <fwb-icon :name="e.done ? 'rotate' : 'check'"/>
        </button>
      </div>
    </div>
  </div>
</div>`
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.schedule = Schedule;
})(window);
