/* =====================================================================
   pages/courses.js —— 课程资源（列表 + 详情 + 学生开放）
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  /* 资料类型 -> 徽标配色 */
  function kindTone(t) {
    return {
      "教学大纲": "blue", "课件": "violet", "案例": "amber",
      "实验": "teal", "习题": "indigo", "参考书": "gray", "其他": "gray"
    }[t] || "gray";
  }
  function fileIcon(t) {
    return t === "课件" ? "ppt" : (t === "实验" ? "flask" : "file");
  }
  /* 课程对学生可见状态 -> 提示条配色 */
  var VIS_TONE = { open: "ok", closed: "off", scheduled: "wait", expired: "wait" };

  var MATERIAL_TYPES = ["教学大纲", "课件", "案例", "实验", "习题", "参考书", "其他"];

  /* ------------------------------------------------------------------ */
  /* 列表                                                                */
  /* ------------------------------------------------------------------ */
  var CourseList = {
    name: "PageCourses",
    setup: function () { var s = FWB.store; return { S: s.state, act: s.act, U: U, forms: FWB.forms }; },
    computed: {
      items: function () { return this.act.list("courses"); },
      totalStudents: function () {
        return this.items.reduce(function (s, c) { return s + (Number(c.students) || 0); }, 0);
      },
      materialCount: function () {
        return this.items.reduce(function (s, c) { return s + ((c.materials || []).length); }, 0);
      },
      chapterCount: function () {
        return this.items.reduce(function (s, c) { return s + ((c.syllabus || []).length); }, 0);
      },
      openCount: function () {
        var self = this;
        return this.items.filter(function (c) { return self.visOf(c).visible; }).length;
      }
    },
    methods: {
      visOf: function (c) { return U.courseVisibility(c); },
      visTone: function (c) { return VIS_TONE[this.visOf(c).state] || "gray"; },
      openDetail: function (c) { this.act.openDetail("course", c.id); }
    },
    template:
      "<div>" +
      '  <div class="mini-stats">' +
      '    <div class="mini-stat"><div class="ms-val">{{ items.length }}<small>门</small></div><div class="ms-lab">课程总数</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ openCount }}<small>门</small></div><div class="ms-lab">学生可见</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ chapterCount }}<small>章</small></div><div class="ms-lab">大纲章节</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ materialCount }}<small>份</small></div><div class="ms-lab">课程资料</div></div>' +
      "  </div>" +

      '  <div class="toolbar">' +
      '    <div class="tb-hint">课程资料支持直接上传文件，学生可在公开课程页下载</div>' +
      '    <div class="spacer"></div>' +
      '    <button class="btn primary" @click="forms.openForm(\'course\', null)"><fwb-icon name="plus"/>新增课程</button>' +
      "  </div>" +

      '  <div v-if="!items.length" class="card"><div class="empty"><fwb-icon name="cap" :size="44"/><p>暂无课程，点击右上角新增</p></div></div>' +

      '  <div class="course-grid">' +
      '    <div v-for="c in items" :key="c.id" class="course-card" @click="openDetail(c)">' +
      '      <div class="course-banner" :style="{ background: c.color }">' +
      '        <div class="cb-code">{{ c.code }}</div>' +
      '        <div class="cb-name">{{ c.name }}</div>' +
      '        <div class="cb-sem">{{ c.semester }}</div>' +
      '        <span class="cb-vis" :class="visTone(c)">' +
      '          <fwb-icon :name="visOf(c).visible ? \'globe\' : \'lock\'"/>' +
      "          {{ visOf(c).label }}</span>" +
      "      </div>" +
      '      <div class="course-info">' +
      '        <div class="ci"><div class="ci-val">{{ c.students }}<small>人</small></div><div class="ci-lab">学生</div></div>' +
      '        <div class="ci"><div class="ci-val">{{ c.credits }}<small>分</small></div><div class="ci-lab">学分</div></div>' +
      '        <div class="ci"><div class="ci-val">{{ c.hours }}<small>时</small></div><div class="ci-lab">学时</div></div>' +
      "      </div>" +
      '      <div class="course-res-count">' +
      '        <span class="badge blue">{{ (c.syllabus || []).length }} 章</span>' +
      '        <span class="badge violet">{{ (c.materials || []).length }} 份资料</span>' +
      '        <span class="badge teal">{{ (c.assistants || []).length }} 位助教</span>' +
      "      </div>" +
      "    </div>" +
      "  </div>" +
      "</div>"
  };

  /* ------------------------------------------------------------------ */
  /* 详情                                                                */
  /* ------------------------------------------------------------------ */
  var CourseDetail = {
    name: "PageCourseDetail",
    setup: function () { var s = FWB.store; return { S: s.state, act: s.act, U: U, forms: FWB.forms }; },
    data: function () {
      return { tab: "syllabus", uploadType: "课件", uploading: false, matTypes: MATERIAL_TYPES };
    },
    computed: {
      item: function () { return this.act.get("courses", this.S.detailId); },
      mats: function () { return (this.item && this.item.materials) || []; },
      calRows: function () { return (this.item && this.item.calendar) || []; },
      tas: function () { return (this.item && this.item.assistants) || []; },
      calHours: function () {
        return this.calRows.reduce(function (s, r) {
          var n = parseInt(parseFloat(r.hours), 10);
          return s + (isNaN(n) ? 0 : n);
        }, 0);
      },
      hasContact: function () {
        var it = this.item || {};
        return !!(it.qqGroup || it.hasQr || (it.assistants || []).length);
      },
      fileCount: function () {
        return this.mats.filter(function (m) { return !!m.stored; }).length;
      },
      totalHours: function () {
        return ((this.item && this.item.syllabus) || [])
          .reduce(function (s, c) { return s + (parseInt(parseFloat(c.hours), 10) || 0); }, 0);
      },
      share: function () { return this.S.courseShare; },
      vis: function () { return (this.share && this.share.visibility) || this.U.courseVisibility(this.item); },
      visTone: function () { return VIS_TONE[this.vis.state] || "gray"; },
      shareUrl: function () {
        if (!this.share || !this.share.token) return "";
        var origin = (global.location && global.location.origin) || "";
        return origin + "/c/" + this.share.token;
      },
      /** 状态条说明文案：把「为什么学生现在看不到」讲清楚 */
      shareHint: function () {
        var v = this.vis;
        if (v.state === "open") {
          if (v.openFrom || v.openUntil) {
            return "开放期 " + (v.openFrom || "不限") + " 至 " + (v.openUntil || "不限")
              + "，学生凭下方链接可查看大纲并下载资料。";
          }
          return "长期开放，学生凭下方链接可查看教学大纲并下载课程资料。";
        }
        if (v.state === "scheduled") return "尚未到开放时间：" + v.detail;
        if (v.state === "expired") return v.detail;
        return "已关闭，学生打开链接将看到「暂未开放」提示。";
      }
    },
    mounted: function () {
      var self = this;
      if (this.S.detailId) {
        this.act.loadCourseShare(this.S.detailId).catch(function () { /* 详情页照常可用 */ });
      }
      this._copied = false;
      void self;
    },
    methods: {
      kindTone: kindTone,
      fileIcon: fileIcon,
      matUrl: function (mf) { return FWB.api.courses.materialUrl(this.S.detailId, mf.id); },
      edit: function () { this.forms.openForm("course", this.item); },
      del: function () { this.forms.remove("course", this.item); },
      openShare: function () {
        var self = this;
        this.act.openModal({
          title: "学生访问设置",
          component: "fwb-course-share",
          props: { courseId: this.S.detailId }
        });
        void self;
      },
      preview: function () {
        if (this.shareUrl) global.open(this.shareUrl, "_blank", "noopener");
      },
      copyLink: function () {
        var self = this;
        var url = this.shareUrl;
        if (!url) return;
        var done = function () { self.act.toast("课程链接已复制到剪贴板"); };
        if (global.navigator && global.navigator.clipboard) {
          global.navigator.clipboard.writeText(url).then(done, function () { self.act.toast("复制失败，请手动选中链接", "error"); });
        } else {
          done();
        }
      },
      pickFiles: function () { this.$refs.fileInput.click(); },
      onPick: function (e) {
        var files = Array.prototype.slice.call(e.target.files || []);
        e.target.value = "";
        if (files.length) this.doUpload(files);
      },
      doUpload: function (files) {
        var self = this;
        this.uploading = true;
        this.act.uploadCourseMaterials(this.S.detailId, files, { type: this.uploadType })
          .then(function (res) {
            self.act.toast("已上传 " + res.added + " 份资料");
          })
          .catch(function (err) {
            self.act.toast(err.message || "上传失败", "error");
          })
          .then(function () { self.uploading = false; });
      },
      removeMaterial: function (mf) {
        var self = this;
        var msg = "确定删除《" + mf.name + "》吗？" +
          (mf.stored ? "服务器上的文件将同时删除，学生页面也会同步移除。" : "");
        return this.act.confirmDelete(msg, function () {
          return self.act.deleteCourseMaterial(self.S.detailId, mf.id);
        });
      },
      runCalendar: function () {
        var tool = this.act.list("tools").filter(function (t) {
          return t.url === "internal://teaching-calendar";
        })[0];
        this.forms.openToolRunner(tool || { name: "教学日历编排", url: "internal://teaching-calendar" });
      },
      /** 打开「助教与联系方式」编辑弹窗（助教 / QQ 群 / 教学日历三块） */
      openContact: function () {
        this.act.openModal({
          title: "助教与联系方式",
          wide: true,
          component: "fwb-course-contact",
          props: { courseId: this.S.detailId }
        });
      },
      /** 演示工具入口保留，但主编辑路径走「日历与联系方式」弹窗 */
      calDate: function (d) {
        var m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(String(d || ""));
        if (!m) return String(d || "");
        return ("0" + m[2]).slice(-2) + "." + ("0" + m[3]).slice(-2);
      },
      /** 电话 → tel: 链接（去掉空格与连字符） */
      telOf: function (v) { return String(v || "").replace(/[\s-]/g, ""); },
      calWeekday: function (d) {
        var m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(String(d || ""));
        if (!m) return "";
        return "周" + "日一二三四五六".charAt(new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).getDay());
      }
    },
    template:
      '<div v-if="item">' +
      '  <div class="detail-head">' +
      '    <button class="icon-btn ghost back-btn" @click="act.go(\'courses\')"><fwb-icon name="back"/></button>' +
      '    <div class="detail-title"><h2>{{ item.name }}</h2>' +
      '      <div class="dt-meta">' +
      '        <span class="badge blue">{{ item.code }}</span>' +
      '        <span class="badge gray">{{ item.semester }}</span>' +
      '        <span class="badge gray">{{ item.students }} 人</span>' +
      '        <span class="badge gray">{{ item.credits }} 学分 / {{ item.hours }} 学时</span>' +
      "      </div></div>" +
      '    <div class="row">' +
      '      <button class="btn ghost" @click="openContact"><fwb-icon name="chat"/>助教与联系' +
      '        <span v-if="hasContact" class="badge teal" style="margin-left:4px">已配置</span></button>' +
      '      <button class="btn ghost" @click="edit"><fwb-icon name="edit"/>编辑</button>' +
      '      <button class="btn danger" @click="del"><fwb-icon name="trash"/>删除</button>' +
      "    </div>" +
      "  </div>" +

      /* ---------- 学生访问状态条 ---------- */
      '  <div class="share-strip" :class="\'st-\' + vis.state">' +
      '    <div class="ss-ico"><fwb-icon :name="vis.visible ? \'globe\' : \'lock\'" :size="20"/></div>' +
      '    <div class="ss-main">' +
      '      <div class="ss-head">' +
      '        <b>学生访问</b>' +
      '        <span class="audit-tag" :class="visTone">{{ vis.label }}</span>' +
      '        <span v-if="share && share.fileCount" class="ss-sub">可下载资料 {{ share.fileCount }} 份</span>' +
      "      </div>" +
      '      <div class="ss-hint">{{ shareHint }}</div>' +
      '      <div v-if="shareUrl" class="ss-link">' +
      "        <code>{{ shareUrl }}</code>" +
      '        <button class="btn ghost xs" @click="copyLink"><fwb-icon name="copy"/>复制</button>' +
      '        <button class="btn ghost xs" @click="preview"><fwb-icon name="external"/>预览</button>' +
      "      </div>" +
      "    </div>" +
      '    <div class="ss-ops">' +
      '      <button class="btn ghost" @click="openShare"><fwb-icon name="settings"/>开放设置</button>' +
      "    </div>" +
      "  </div>" +

      '  <div class="card" v-if="item.intro"><div class="card-body">' +
      '    <div class="section-title">课程简介<span class="st-line"></span></div>' +
      '    <p style="font-size:13px;color:var(--text-2);line-height:1.8">{{ item.intro }}</p>' +
      "  </div></div>" +

      '  <div class="tabs" style="margin-top:18px">' +
      '    <div class="tab" :class="{ active: tab === \'syllabus\' }" @click="tab = \'syllabus\'">教学大纲（{{ (item.syllabus || []).length }}）</div>' +
      '    <div class="tab" :class="{ active: tab === \'calendar\' }" @click="tab = \'calendar\'">教学日历（{{ calRows.length }}）</div>' +
      '    <div class="tab" :class="{ active: tab === \'materials\' }" @click="tab = \'materials\'">课程资料（{{ mats.length }}）</div>' +
      '    <div class="tab" :class="{ active: tab === \'ta\' }" @click="tab = \'ta\'">课程助教（{{ tas.length }}）</div>' +
      "  </div>" +

      '  <div v-if="tab === \'syllabus\'" class="card">' +
      '    <table class="tbl" v-if="(item.syllabus || []).length">' +
      "      <thead><tr><th>章节</th><th>学时</th><th>形式</th><th>教学要点</th></tr></thead>" +
      "      <tbody><tr v-for=\"(s, i) in item.syllabus\" :key=\"i\">" +
      '        <td class="strong">{{ s.chapter }}</td><td>{{ s.hours }}</td>' +
      '        <td><span class="badge gray">{{ s.type }}</span></td><td>{{ s.point }}</td>' +
      "      </tr></tbody>" +
      '      <tfoot><tr><td class="strong">合计</td><td class="strong">{{ totalHours }} 学时</td><td></td><td></td></tr></tfoot>' +
      "    </table>" +
      '    <div v-else class="card-body"><div class="empty"><p>暂无教学大纲</p></div></div>' +
      "  </div>" +

      /* ---------- 教学日历 ---------- */
      '  <div v-else-if="tab === \'calendar\'" class="card">' +
      '    <div class="cal-toolbar">' +
      '      <div class="mh-hint">按周展示教学安排，学生公开页同步显示；QQ 群号与二维码也在此维护</div>' +
      '      <button class="btn ghost sm" @click="openContact"><fwb-icon name="edit"/>编辑日历与联系方式</button>' +
      "    </div>" +
      '    <table class="tbl" v-if="calRows.length">' +
      "      <thead><tr><th>周次</th><th>日期</th><th>教学内容</th><th>学时</th><th>形式</th><th>备注</th></tr></thead>" +
      "      <tbody><tr v-for=\"(r, i) in calRows\" :key=\"i\">" +
      '        <td class="strong">{{ r.week }}</td>' +
      '        <td class="cal-cell-date">{{ calDate(r.date) }}<small v-if="calWeekday(r.date)">{{ calWeekday(r.date) }}</small></td>' +
      "        <td>{{ r.topic }}</td>" +
      '        <td>{{ r.hours || "—" }}</td>' +
      '        <td><span class="badge gray">{{ r.type || "—" }}</span></td>' +
      '        <td class="muted">{{ r.note || "—" }}</td>' +
      "      </tr></tbody>" +
      '      <tfoot><tr><td class="strong">合计</td><td></td><td class="strong">{{ calRows.length }} 周</td>' +
      '        <td class="strong">{{ calHours }} 学时</td><td></td><td></td></tr></tfoot>' +
      "    </table>" +
      '    <div v-else class="card-body"><div class="empty"><fwb-icon name="calendar" :size="40"/>' +
      "      <p>暂无教学日历，可从教学大纲一键生成</p>" +
      '      <button class="btn ghost sm mt-2" @click="openContact"><fwb-icon name="edit"/>去添加</button></div></div>' +
      "  </div>" +

      /* ---------- 课程助教 ---------- */
      '  <div v-else-if="tab === \'ta\'" class="card">' +
      '    <div class="cal-toolbar">' +
      '      <div class="mh-hint">助教的姓名与联系方式会显示在学生公开页，学生可直接拨打或发邮件咨询</div>' +
      '      <button class="btn ghost sm" @click="openContact"><fwb-icon name="edit"/>编辑助教信息</button>' +
      "    </div>" +
      '    <table class="tbl" v-if="tas.length">' +
      "      <thead><tr><th>姓名</th><th>身份 / 分工</th><th>电话</th><th>邮箱</th><th>QQ</th><th>值班与备注</th></tr></thead>" +
      "      <tbody><tr v-for=\"(t, i) in tas\" :key=\"i\">" +
      '        <td class="strong">{{ t.name || "—" }}</td>' +
      '        <td><span class="badge teal">{{ t.role || "助教" }}</span></td>' +
      '        <td><a v-if="t.phone" class="ta-link" :href="\'tel:\' + telOf(t.phone)">{{ t.phone }}</a>' +
      '          <span v-else class="muted">—</span></td>' +
      '        <td><a v-if="t.email" class="ta-link" :href="\'mailto:\' + t.email">{{ t.email }}</a>' +
      '          <span v-else class="muted">—</span></td>' +
      '        <td>{{ t.qq || "—" }}</td>' +
      '        <td class="muted">{{ t.note || "—" }}</td>' +
      "      </tr></tbody>" +
      "    </table>" +
      '    <div v-else class="card-body"><div class="empty"><fwb-icon name="users" :size="40"/>' +
      "      <p>暂无助教信息，添加后会同步展示在学生公开页</p>" +
      '      <button class="btn ghost sm mt-2" @click="openContact"><fwb-icon name="edit"/>去添加</button></div></div>' +
      "  </div>" +

      '  <div v-else class="card">' +
      '    <div class="mat-head">' +
      '      <div>' +
      '        <div class="mh-title">课程资料</div>' +
      '        <div class="mh-hint">已上传 {{ fileCount }} 份可下载文件，共 {{ mats.length }} 条记录</div>' +
      "      </div>" +
      '      <div class="mh-ops">' +
      '        <select class="select-mini" v-model="uploadType" aria-label="资料类型">' +
      '          <option v-for="t in matTypes" :key="t" :value="t">{{ t }}</option>' +
      "        </select>" +
      '        <input ref="fileInput" type="file" multiple hidden @change="onPick">' +
      '        <button class="btn primary" :disabled="uploading" @click="pickFiles">' +
      '          <fwb-icon name="upload"/>{{ uploading ? "上传中…" : "上传资料" }}' +
      "        </button>" +
      "      </div>" +
      "    </div>" +
      '    <div class="card-body">' +
      '      <div v-if="!mats.length" class="empty"><fwb-icon name="folder" :size="40"/>' +
      "        <p>暂无课程资料，点击右上角「上传资料」添加</p></div>" +
      '      <div v-for="mf in mats" :key="mf.id" class="file-item">' +
      '        <div class="file-ico" :class="\'tone-\' + kindTone(mf.type)"><fwb-icon :name="fileIcon(mf.type)"/></div>' +
      '        <div class="file-main"><div class="file-name">{{ mf.name }}</div>' +
      '          <div class="file-meta">{{ mf.type }} · {{ mf.size || "未知大小" }} · {{ mf.date || "未标注日期" }}' +
      '            <span v-if="mf.uploadedBy"> · 由 {{ mf.uploadedBy }} 上传</span></div></div>' +
      '        <span v-if="mf.stored" class="badge teal">可下载</span>' +
      '        <span v-else class="badge gray">未上传文件</span>' +
      '        <div class="file-ops">' +
      '          <a v-if="mf.stored" class="icon-btn ghost" :href="matUrl(mf)" title="下载"><fwb-icon name="download"/></a>' +
      '          <button class="icon-btn ghost danger" title="删除" @click="removeMaterial(mf)"><fwb-icon name="trash"/></button>' +
      "        </div>" +
      "      </div>" +
      "    </div>" +
      "  </div>" +
      "</div>" +
      '<div v-else class="empty"><fwb-icon name="alert" :size="42"/><p>课程不存在或已删除</p>' +
      '  <button class="btn ghost mt-2" @click="act.go(\'courses\')">返回课程资源</button></div>'
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.courses = CourseList;
  FWB.pages["course-detail"] = CourseDetail;
})(window);
