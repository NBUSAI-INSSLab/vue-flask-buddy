/* =====================================================================
   cv-public.js —— 个人简历公开页（免登录）
   入口：/cv/<token>，页面自取 /api/public/cv/<token>
   只读：不含任何写操作；所有数据由后端按白名单下发
   ===================================================================== */
(function (global) {
  "use strict";

  var vue = global.Vue;
  var FWB = global.FWB;

  /* 极简图标组件（与工作台内 FwbIcon 同源，避免引入整包组件） */
  var Icon = vue.defineComponent({
    name: "CvIcon",
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

  /* 章节导航定义：id 与 cv.html 里各 <section> 的 id 一一对应 */
  var NAV_DEF = [
    { id: "bio", text: "简介", key: "bio" },
    { id: "directions", text: "研究方向", key: "directions" },
    { id: "education", text: "教育经历", key: "educations" },
    { id: "projects", text: "科研项目", key: "projects" },
    { id: "publications", text: "论文发表", key: "papers" },
    { id: "patents", text: "专利软著", key: "patents" },
    { id: "services", text: "社会服务", key: "services" },
    { id: "students", text: "学生指导", key: "students" },
    { id: "teaching", text: "教学经历", key: "teachings" },
    { id: "honors", text: "荣誉奖励", key: "honors" }
  ];

  /* 社会服务的分组顺序（与后端 seed.SERVICE_KINDS 一致） */
  var SERVICE_ORDER = ["学会任职", "学术兼职", "期刊审稿", "基金评审", "产业服务", "公共服务"];

  /* 视为「已落地」的成果状态，用于区分「已发表」与「审稿中」的呈现 */
  var DONE_STATES = ["已发表", "已录用", "已授权", "已登记", "已交付", "已获奖"];

  function token() {
    var m = /^\/cv\/([0-9a-f]{16})\/?$/.exec(global.location.pathname || "");
    return m ? m[1] : "";
  }

  /* "2011-09" / "2016-06-30" → "2011.09" / "2016.06" */
  function ym(v) {
    var s = String(v == null ? "" : v).trim();
    var m = /^(\d{4})-(\d{2})/.exec(s);
    return m ? m[1] + "." + m[2] : s;
  }

  var App = vue.createApp({
    components: { FwbIcon: Icon },
    data: function () {
      return {
        loading: true,
        data: null,
        state: "invalid",       // invalid | private | error
        message: "",
        avatarFailed: false,
        activeId: "",
        _raf: 0
      };
    },
    computed: {
      lockedTitle: function () {
        return {
          invalid: "简历链接无效",
          private: "该简历暂未公开",
          error: "页面加载失败"
        }[this.state] || "暂时无法访问";
      },

      avatarUrl: function () {
        if (this.avatarFailed || !this.data) return "";
        var a = this.data.avatar || {};
        return a.set ? (a.url || "") : "";
      },

      statRows: function () {
        if (!this.data || !this.data.sections.stats) return [];
        var s = this.data.stats || {};
        var rows = [
          { icon: "flask", tone: "blue", lab: "科研项目", val: s.projects || 0, unit: "项" },
          { icon: "medal", tone: "violet", lab: "发表论文", val: s.papers || 0, unit: "篇" },
          { icon: "seal", tone: "teal", lab: "专利软著", val: s.patents || 0, unit: "项" },
          { icon: "users", tone: "amber", lab: "指导学生", val: s.students || 0, unit: "人" },
          { icon: "clipboard", tone: "indigo", lab: "教学学时", val: s.hours || 0, unit: "学时" }
        ];
        return rows.filter(function (r) { return r.val > 0; });
      },

      /* 导航项：区块被关闭、或该区块没有内容时不出现在导航里 */
      navItems: function () {
        var d = this.data, self = this;
        if (!d) return [];
        return NAV_DEF.map(function (n) {
          if (!self.on(n.key)) return null;
          if (n.key === "bio") {
            return d.profile.bio ? { id: n.id, text: n.text, count: 0 } : null;
          }
          var arr = d[n.key] || [];
          if (!arr.length) return null;
          return { id: n.id, text: n.text, count: arr.length };
        }).filter(Boolean);
      },

      /* 论文按年份分组，编号按「最近在前」连续编下去（[1] 为最新一篇） */
      paperGroups: function () {
        if (!this.data) return [];
        var groups = [], index = {};
        (this.data.papers || []).forEach(function (p, i) {
          var y = String(p.date || "").slice(0, 4) || "";
          if (index[y] === undefined) {
            index[y] = groups.length;
            groups.push({ year: y, items: [] });
          }
          groups[index[y]].items.push(Object.assign({ no: i + 1 }, p));
        });
        return groups;
      },

      /* 收录级别概览，如「SCI 二区 2 篇 · SCI 三区 1 篇」 */
      levelNote: function () {
        if (!this.data) return "";
        var lv = (this.data.stats || {}).paperLevels || {};
        var rows = Object.keys(lv).map(function (k) { return { k: k, v: lv[k] }; });
        if (rows.length < 2) return "";
        rows.sort(function (a, b) { return b.v - a.v || a.k.localeCompare(b.k); });
        return rows.slice(0, 3).map(function (r) { return r.k + " " + r.v + " 篇"; }).join(" · ");
      },

      serviceGroups: function () {
        if (!this.data) return [];
        var map = {}, keys = [];
        (this.data.services || []).forEach(function (s) {
          var k = s.kind || "其他";
          if (!map[k]) { map[k] = []; keys.push(k); }
          map[k].push(s);
        });
        keys.sort(function (a, b) {
          var ia = SERVICE_ORDER.indexOf(a), ib = SERVICE_ORDER.indexOf(b);
          return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
        });
        return keys.map(function (k) { return { kind: k, items: map[k] }; });
      },

      /* 所有区块都空时给一句说明，避免页面只有头尾 */
      isEmpty: function () {
        if (!this.data) return false;
        var d = this.data;
        if (this.on("bio") && d.profile.bio) return false;
        if (this.on("directions") && d.directions.length) return false;
        return !["educations", "projects", "papers", "patents", "services",
                 "students", "teachings", "honors"].some(function (k) {
          return d[k] && d[k].length;
        });
      }
    },
    methods: {
      /* 区块是否展示（后端已按 profile.cvSections 下发，这里只做兜底） */
      on: function (key) {
        return !this.data || this.data.sections[key] !== false;
      },

      period: function (from, to) {
        var a = ym(from), b = ym(to);
        if (a && b) return a + " – " + b;
        if (a) return a + " 至今";
        if (b) return "至 " + b;
        return "";
      },

      /* 经费展示：教师可能填「一」「—」这类非数字，只有含数字才显示 */
      fundingText: function (v) {
        var s = String(v == null ? "" : v).trim();
        return /\d/.test(s) ? s : "";
      },

      hostOf: function (url) {
        return String(url || "").replace(/^https?:\/\//, "").replace(/\/$/, "");
      },

      /* DOI 号（10.xxxx/...）转可点击链接；专利号、软著登记号等原样展示 */
      doiUrl: function (v) {
        var s = String(v || "").trim();
        return /^10\.\d{4,9}\/\S+$/.test(s) ? "https://doi.org/" + s : "";
      },

      isDone: function (status) {
        return DONE_STATES.indexOf(String(status || "")) >= 0;
      },

      /* 把作者串里本人的名字切出来加粗（不用 v-html，避免注入） */
      authorParts: function (authors) {
        var text = String(authors == null ? "" : authors);
        var me = String((this.data && this.data.name) || "");
        if (!me || text.indexOf(me) < 0) return [{ t: text, me: false }];
        var out = [], i = 0;
        for (;;) {
          var at = text.indexOf(me, i);
          if (at < 0) {
            if (i < text.length) out.push({ t: text.slice(i), me: false });
            break;
          }
          if (at > i) out.push({ t: text.slice(i, at), me: false });
          out.push({ t: me, me: true });
          i = at + me.length;
        }
        return out;
      },

      print: function () { global.print(); },

      /* 滚动高亮当前章节（简单的「最后一个越过阈值」判定，比观察器更稳） */
      onScroll: function () {
        var self = this;
        if (this._raf) return;
        this._raf = global.requestAnimationFrame(function () {
          self._raf = 0;
          var secs = document.querySelectorAll(".cv-sec");
          var line = global.scrollY + 150, cur = "";
          for (var i = 0; i < secs.length; i++) {
            if (secs[i].offsetTop <= line) cur = secs[i].id;
          }
          if (cur !== self.activeId) self.activeId = cur;
        });
      },

      load: function () {
        var self = this;
        var tk = token();
        if (!tk) {
          this.loading = false;
          this.state = "invalid";
          this.message = "链接格式不正确，请向本人索取完整简历链接。";
          return;
        }
        fetch("/api/public/cv/" + tk, { credentials: "omit" })
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
              if (body.data.name) document.title = body.data.name + " · 个人简历";
              // ?print=1：工作台点「打印 / PDF」时直接唤起打印（等一帧让版式落定）
              if (/(?:^|[?&])print=1(?:&|$)/.test(global.location.search || "")) {
                self.$nextTick(function () {
                  global.setTimeout(function () { global.print(); }, 260);
                });
              }
              return;
            }
            self.loading = false;
            self.state = out.res.status === 403 ? "private"
              : (out.res.status === 404 ? "invalid" : "error");
            self.message = body.error || "暂时无法加载简历，请稍后再试。";
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
      global.addEventListener("scroll", this.onScroll, { passive: true });
    },
    beforeUnmount: function () {
      global.removeEventListener("scroll", this.onScroll);
      if (this._raf) global.cancelAnimationFrame(this._raf);
    }
  });

  App.mount("#cv");
})(window);
