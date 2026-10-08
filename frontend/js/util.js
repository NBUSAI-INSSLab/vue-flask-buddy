/* =====================================================================
   util.js —— 日期、格式化、枚举色板映射、页面元信息
   ===================================================================== */
(function (global) {
  "use strict";

  var WEEK = ["日", "一", "二", "三", "四", "五", "六"];

  function pad(n) { return n < 10 ? "0" + n : "" + n; }
  function today() { var d = new Date(); return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function dayOffset(n) { var d = new Date(); d.setDate(d.getDate() + n); return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function parse(dateStr) {
    if (!dateStr) return null;
    var d = new Date(String(dateStr).slice(0, 10) + "T00:00:00");
    return isNaN(d.getTime()) ? null : d;
  }
  function daysUntil(dateStr) {
    var d = parse(dateStr);
    if (!d) return null;
    return Math.round((d - parse(today())) / 86400000);
  }
  function cnDate(dateStr) {
    var d = parse(dateStr);
    if (!d) return "";
    return (d.getMonth() + 1) + "月" + d.getDate() + "日 周" + WEEK[d.getDay()];
  }
  function cnDateShort(dateStr) {
    var d = parse(dateStr);
    return d ? (d.getMonth() + 1) + "/" + d.getDate() : "";
  }
  function dueText(dateStr) {
    var n = daysUntil(dateStr);
    if (n === null) return "无截止日期";
    if (n < 0) return "已逾期 " + Math.abs(n) + " 天";
    if (n === 0) return "今天截止";
    if (n === 1) return "明天截止";
    return "剩 " + n + " 天";
  }
  function greeting() {
    var h = new Date().getHours();
    if (h < 6) return "凌晨好";
    if (h < 11) return "早上好";
    if (h < 13) return "中午好";
    if (h < 18) return "下午好";
    return "晚上好";
  }
  function num(v, d) { var f = parseFloat(v); return isNaN(f) ? (d || 0) : f; }
  function pct(part, whole) {
    if (!whole) return 0;
    return Math.max(0, Math.min(100, Math.round((part / whole) * 100)));
  }

  /* -------------------- 枚举 -> 色调（与样式表 .badge./.ac- 对应） -------------------- */
  var TONES = {
    exchKind: { "学术会议": "blue", "期刊审稿": "violet", "基金评审": "indigo", "企业交流": "amber", "学术报告": "teal", "访问交流": "green" },
    exchStatus: { "待确认": "gray", "已确认": "blue", "进行中": "amber", "已完成": "green", "已取消": "red" },
    teachStage: { "备课中": "amber", "进行中": "blue", "结课归档": "indigo", "已完成": "green", "选题阶段": "amber" },
    achType: { "期刊论文": "blue", "会议论文": "teal", "发明专利": "violet", "软件著作权": "indigo", "技术报告": "gray", "科技奖励": "amber", "学位论文": "green" },
    devCat: { "职称晋升": "violet", "人才项目": "blue", "培训进修": "teal", "产学研": "amber", "考核述职": "indigo", "其他": "gray" },
    devStatus: { "规划中": "gray", "准备中": "amber", "进行中": "blue", "已完成": "green", "已暂停": "red" },
    toolCat: { "教学": "blue", "科研": "violet", "学生": "green", "文档": "amber", "行政": "indigo", "其他": "gray" },
    projStatus: { "在研": "blue", "验收中": "amber", "已结题": "green", "待启动": "gray", "已暂停": "red" },
    evType: { "上课": "blue", "组会": "violet", "会议": "amber", "答辩": "teal", "申报": "indigo", "其他": "gray" }
  };

  var PRIORITY = { high: "高", mid: "中", low: "低" };

  /* -------------------- 页面元信息 -------------------- */
  var PAGE_META = {
    dashboard: ["工作首页", "总览今日科研、教学与学生指导工作"],
    projects: ["科研项目", "管理项目阶段任务、成果产出与经费进度"],
    "project-detail": ["项目详情", "科研项目 · 阶段与成果"],
    literature: ["文献仓库", "收藏论文、记录阅读笔记、整理研究方向"],
    "lit-detail": ["文献详情", "文献仓库 · 阅读笔记"],
    courses: ["课程资源", "管理课程资料、教学大纲、课件与案例"],
    "course-detail": ["课程详情", "课程资源 · 教学材料"],
    students: ["学生指导", "记录学生信息、论文进度与沟通记录"],
    "student-detail": ["学生详情", "学生指导 · 论文与沟通"],
    schedule: ["日程管理", "记录会议、申报、答辩等重要事项"],
    exchanges: ["学术交流", "统筹学术会议、审稿、评审与企业交流活动"],
    teachings: ["教学管理", "跟进教学任务、大纲进度与教学待办"],
    achievements: ["成果管理", "登记论文、专利、软著与奖励，统计业绩分"],
    developments: ["个人发展", "职称晋升、人才项目、培训进修与考核规划"],
    tools: ["常用工具", "教学科研高频工具，点击卡片即可运行"]
  };

  var NAV_PARENT = {
    dashboard: "dashboard", schedule: "schedule",
    projects: "projects", "project-detail": "projects",
    literature: "literature", "lit-detail": "literature",
    exchanges: "exchanges", achievements: "achievements",
    teachings: "teachings",
    courses: "courses", "course-detail": "courses",
    students: "students", "student-detail": "students",
    developments: "developments", tools: "tools"
  };

  /* 常用网站分组（新增 / 编辑时的下拉项，顺序即展示顺序） */
  var LINK_GROUPS = ["学术资源", "教学平台", "科研工具", "公共服务", "其他"];

  /* 主机名：去掉协议、路径、www. 前缀 */
  function siteHost(url) {
    var s = String(url == null ? "" : url).trim()
      .replace(/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//, "")
      .replace(/^\/\//, "");
    s = s.split("/")[0].split("?")[0].split("#")[0].replace(/^www\./i, "");
    return s;
  }

  /* 首字母：优先取名称里的第一个字母 / 汉字 */
  function siteLetter(name, url) {
    var text = String(name == null ? "" : name).trim();
    if (text) {
      for (var i = 0; i < text.length; i++) {
        var ch = text.charAt(i);
        if (/[0-9a-zA-Z\u4e00-\u9fff]/.test(ch)) return ch.toUpperCase();
      }
    }
    var host = siteHost(url);
    return host ? host.charAt(0).toUpperCase() : "网";
  }

  /* 头像配色：首色跟随主题主色，其余为固定辅助色 */
  var avatarTones = [
    "var(--primary)", "var(--teal)", "var(--violet)", "var(--indigo)",
    "var(--amber)", "#0f6ea8", "#c2410c"
  ];

  global.FWB = global.FWB || {};
  global.FWB.util = {
    pad: pad, today: today, dayOffset: dayOffset, parse: parse,
    daysUntil: daysUntil, cnDate: cnDate, cnDateShort: cnDateShort, dueText: dueText,
    greeting: greeting, num: num, pct: pct, TONES: TONES, PRIORITY: PRIORITY,
    PAGE_META: PAGE_META, NAV_PARENT: NAV_PARENT,
    LINK_GROUPS: LINK_GROUPS, siteHost: siteHost, siteLetter: siteLetter,
    siteTone: function (name, url) {
      var s = 0, str = siteHost(url) || String(name || "");
      for (var i = 0; i < str.length; i++) s += str.charCodeAt(i);
      return avatarTones[s % avatarTones.length];
    },
    avatarColor: function (name) {
      var s = 0, str = String(name || "");
      for (var i = 0; i < str.length; i++) s += str.charCodeAt(i);
      return avatarTones[s % avatarTones.length];
    },
    esc: function (s) {
      return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
      });
    },
    /* 课程对学生可见性：与 backend/courses.py::visibility 保持同一判定规则。
       前端只用它渲染徽标与列表预览，真正的准入判定仍在服务端。 */
    courseVisibility: function (course) {
      var LABEL = { open: "已开放", closed: "已关闭", scheduled: "定时开放", expired: "已结束" };
      var c = course || {};
      var frm = String(c.openFrom || "").slice(0, 10);
      var until = String(c.openUntil || "").slice(0, 10);
      var now = today();
      var out = {
        visible: false, state: "closed", label: LABEL.closed,
        detail: "本课程暂未开放，请联系任课教师。", openFrom: frm, openUntil: until
      };
      if (!c.published) return out;
      if (frm && now < frm) {
        out.state = "scheduled";
        out.label = LABEL.scheduled;
        out.detail = "本课程将于 " + frm + " 起开放，届时可查看教学大纲与下载课程资料。";
        return out;
      }
      if (until && now > until) {
        out.state = "expired";
        out.label = LABEL.expired;
        out.detail = "本课程已于 " + until + " 结束开放，如有需要请联系任课教师。";
        return out;
      }
      out.visible = true;
      out.state = "open";
      out.label = LABEL.open;
      out.detail = "";
      return out;
    }
  };
})(window);
