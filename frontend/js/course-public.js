/* =====================================================================
   course-public.js —— 学生公开课程页（免登录）
   入口：/c/<token>，页面自取 /api/public/courses/<token>
   只读：不含任何写操作与教师私有数据
   ===================================================================== */
(function (global) {
  "use strict";

  var vue = global.Vue;
  var FWB = global.FWB;

  /* 极简图标组件（与工作台内 FwbIcon 同源，避免引入整包组件） */
  var Icon = vue.defineComponent({
    name: "PubIcon",
    props: { name: { type: String, default: "info" }, size: { type: [Number, String], default: 0 } },
    computed: {
      path: function () { return FWB.iconPath(this.name); }
    },
    template:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" ' +
      'stroke-linecap="round" stroke-linejoin="round" ' +
      ':style="size ? {width: size + \'px\', height: size + \'px\'} : null" ' +
      'v-html="path" aria-hidden="true"></svg>'
  });

  var TONE = {
    "教学大纲": "blue", "课件": "violet", "案例": "amber",
    "实验": "teal", "习题": "indigo", "参考书": "gray", "其他": "gray"
  };

  function token() {
    var m = /^\/c\/([0-9a-zA-Z]+)\/?$/.exec(global.location.pathname || "");
    return m ? m[1] : "";
  }

  var App = vue.createApp({
    components: { FwbIcon: Icon },
    data: function () {
      return {
        loading: true,
        data: null,
        state: "invalid",      // invalid | closed | scheduled | expired | error
        message: "",
        lockedCourse: {},
        toast: ""
      };
    },
    computed: {
      lockedTitle: function () {
        return {
          invalid: "课程链接无效",
          closed: "课程暂未开放",
          scheduled: "课程尚未开放",
          expired: "课程已结束开放",
          error: "页面加载失败"
        }[this.state] || "暂时无法访问";
      },
      totalHours: function () {
        if (!this.data) return 0;
        return this.data.syllabus.reduce(function (s, x) {
          return s + (parseInt(parseFloat(x.hours), 10) || 0);
        }, 0);
      },
      openWindow: function () {
        if (!this.data) return "";
        var v = this.data.visibility;
        if (!v.openFrom && !v.openUntil) return "长期开放，无时间限制。";
        return "开放期 " + (v.openFrom || "不限") + " 至 " + (v.openUntil || "不限") + "。";
      }
    },
    methods: {
      tone: function (t) { return TONE[t] || "gray"; },
      icon: function (t) { return t === "课件" ? "ppt" : (t === "实验" ? "flask" : "file"); },
      fileUrl: function (m) {
        return "/api/public/courses/" + token() + "/materials/" + encodeURIComponent(m.id) + "/download";
      },
      say: function (msg) {
        var self = this;
        this.toast = msg;
        global.setTimeout(function () { self.toast = ""; }, 2600);
      },
      load: function () {
        var self = this;
        var tk = token();
        if (!tk) {
          this.loading = false;
          this.state = "invalid";
          this.message = "链接格式不正确，请向任课教师索取完整课程链接。";
          return;
        }
        fetch("/api/public/courses/" + tk, { credentials: "omit" })
          .then(function (res) {
            return res.json().catch(function () { return null; }).then(function (body) {
              return { res: res, body: body };
            });
          })
          .then(function (out) {
            var body = out.body || {};
            if (out.res.ok && body.ok) {
              self.data = body.data;
              self.loading = false;
              return;
            }
            self.loading = false;
            var vis = body.visibility || {};
            self.lockedCourse = body.course || {};
            self.state = out.res.status === 403 ? (vis.state || "closed")
              : (out.res.status === 404 ? "invalid" : "error");
            self.message = body.error || "暂时无法加载课程信息，请稍后再试。";
          })
          .catch(function () {
            self.loading = false;
            self.state = "error";
            self.message = "网络异常，请检查网络连接后刷新页面。";
          });
      }
    },
    mounted: function () {
      this.load();
    }
  });

  App.mount("#course");
})(window);
