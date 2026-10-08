/* =====================================================================
   pages/cv.js —— 个人简历（对外发布设置 + 简历专属信息维护）
   ---------------------------------------------------------------------
   简历正文由公开页 /cv/<token> 呈现，数据全部来自本工作台：
   项目 / 成果 / 学生 / 教学 从各自页面自动汇总，
   教育经历、社会服务在本页维护，联系方式与研究方向取自「简历基本信息」。
   本页不存副本 —— 在这里改完，访客刷新即可看到最新内容。
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  /* 展示区块顺序（与后端 cv.DEFAULT_SECTIONS 对齐） */
  var SECTION_ORDER = [
    "stats", "bio", "directions", "educations", "projects", "papers",
    "patents", "services", "students", "teachings", "honors"
  ];

  /* 区块 → 计数键；stats / bio 没有独立条目，不显示数字 */
  var SECTION_COUNT = {
    directions: "directions", educations: "educations", projects: "projects",
    papers: "papers", patents: "patents", services: "services",
    students: "students", teachings: "teachings", honors: "honors"
  };

  /* 简历内容的出处：简历上的数字都是从这些页面长出来的 */
  var SOURCES = [
    { key: "projects", page: "projects", text: "科研项目", icon: "flask" },
    { key: "papers", page: "achievements", text: "成果管理（论文 / 专利 / 奖励）", icon: "medal" },
    { key: "students", page: "students", text: "学生指导", icon: "users" },
    { key: "teachings", page: "teachings", text: "教学管理", icon: "clipboard" }
  ];

  /* 结束时间倒序；在读 / 在任（无结束时间）排最前 */
  function sortByFrom(list) {
    return (list || []).slice().sort(function (a, b) {
      var ao = a.to ? 0 : 1, bo = b.to ? 0 : 1;
      if (ao !== bo) return bo - ao;
      return String(b.from || "").localeCompare(String(a.from || ""));
    });
  }

  var CvSettings = {
    name: "PageCv",
    setup: function () {
      var s = FWB.store;
      return { S: s.state, act: s.act, U: U, forms: FWB.forms };
    },

    data: function () {
      return {
        busy: "",            // publish | rotate —— 正在保存的按钮
        avatarBusy: false,
        preview: "",         // 上传头像时的本地预览地址
        avatarFailed: false, // 头像加载失败（落回首字母）
        dragging: false
      };
    },

    computed: {
      cv: function () { return this.S.cv; },
      ready: function () { return !!this.cv; },
      profile: function () { return this.S.profile || {}; },
      counts: function () { return (this.cv && this.cv.counts) || {}; },
      published: function () { return !!(this.cv && this.cv.published); },
      link: function () { return (this.cv && this.cv.url) || ""; },
      avatar: function () { return (this.cv && this.cv.avatar) || { url: "", set: false }; },

      /* 头像地址：本地预览优先，其次接口地址 */
      avatarSrc: function () {
        if (this.avatarFailed) return "";
        return this.preview || this.avatar.url || "";
      },
      initial: function () {
        var n = String(this.profile.name || "").trim();
        return n ? n.charAt(0) : "师";
      },
      avatarTone: function () { return U.avatarColor(this.profile.name || "师"); },

      directions: function () {
        var d = this.profile.directions;
        return Array.isArray(d) ? d.filter(Boolean) : [];
      },

      /* 联系方式：有值才显示，避免一堆空行 */
      facts: function () {
        var p = this.profile, out = [];
        var push = function (icon, label, value, href) {
          if (value) out.push({ icon: icon, label: label, value: value, href: href || "" });
        };
        push("send", "邮箱", p.email, p.email ? "mailto:" + p.email : "");
        push("bell", "电话", p.phone);
        push("building", "学院", p.dept);
        push("pin", "办公室", p.office);
        push("pin", "通讯地址", p.address);
        push("globe", "个人主页", U.siteHost(p.homepage), p.homepage);
        push("user", "ORCID", p.orcid, p.orcid ? "https://orcid.org/" + p.orcid : "");
        push("book", "学术主页", U.siteHost(p.scholar), p.scholar);
        return out;
      },

      /* 简历条目总数（教育经历 + 社会服务 + 项目 + 成果 + 学生 + 教学） */
      totalItems: function () {
        var c = this.counts;
        return Object.keys(SECTION_COUNT).reduce(function (n, k) {
          return n + (Number(c[SECTION_COUNT[k]]) || 0);
        }, 0);
      },

      sectionRows: function () {
        var labels = (this.cv && this.cv.sectionLabels) || {};
        var on = (this.cv && this.cv.sections) || {};
        var counts = this.counts;
        return SECTION_ORDER.map(function (k) {
          var ck = SECTION_COUNT[k];
          var n = ck ? (Number(counts[ck]) || 0) : -1;
          return { key: k, label: labels[k] || k, on: !!on[k], count: n, empty: n === 0 };
        });
      },

      sources: function () {
        var counts = this.counts;
        return SOURCES.map(function (s) {
          return {
            key: s.key, page: s.page, text: s.text, icon: s.icon,
            count: Number(counts[s.key]) || 0
          };
        });
      },

      educations: function () { return sortByFrom(this.act.list("educations")); },
      services: function () { return sortByFrom(this.act.list("services")); },

      publishHint: function () {
        if (!this.published) return "简历当前未公开，任何人打开链接只会看到「暂未公开」提示。";
        return "任何人凭下方链接均可访问，内容随工作台数据实时更新。";
      }
    },

    watch: {
      "avatar.url": function () { this.avatarFailed = false; }
    },

    methods: {
      /* ---------------- 发布与链接 ---------------- */
      togglePublish: function () {
        if (this.busy) return;
        var self = this;
        var next = !this.published;
        this.busy = "publish";
        this.act.setCvPublished(next).then(function (cv) {
          self.act.toast(cv.published ? "简历已公开，链接现在可以访问" : "简历已关闭，链接将提示「暂未公开」");
        }, function (err) {
          self.act.toast((err && err.message) || "设置失败", "error");
        }).then(function () { self.busy = ""; });
      },

      copyLink: function () {
        var self = this, url = this.link;
        if (!url) return;
        var done = function () { self.act.toast("固定链接已复制，发给任何人都能打开"); };
        if (global.navigator && global.navigator.clipboard) {
          global.navigator.clipboard.writeText(url).then(done, function () {
            self.act.toast("复制失败，请手动选中链接", "error");
          });
        } else { done(); }
      },

      openLink: function () {
        if (this.link) global.open(this.link, "_blank", "noopener");
      },

      /* 打印 / 导出 PDF：让公开页自己触发打印，版式与访客看到的完全一致 */
      exportPdf: function () {
        if (this.link) global.open(this.link + "?print=1", "_blank", "noopener");
      },

      rotateLink: function () {
        var self = this;
        this.act.confirm({
          title: "更换固定链接",
          msg: "更换后旧链接立即失效 —— 已经发出去的链接将无法打开，需要重新发送新链接。确定继续？",
          btn: "确认更换"
        }).then(function (yes) {
          if (!yes) return;
          self.busy = "rotate";
          self.act.rotateCvToken().then(function () {
            self.act.toast("已生成新链接，请重新分享");
          }, function (err) {
            self.act.toast((err && err.message) || "更换失败", "error");
          }).then(function () { self.busy = ""; });
        });
      },

      /* ---------------- 展示区块开关 ---------------- */
      toggleSection: function (row) {
        var self = this, patch = {};
        patch[row.key] = !row.on;
        this.act.setCvSections(patch).then(function () {
          self.act.toast("「" + row.label + "」已" + (row.on ? "在简历中隐藏" : "在简历中显示"));
        }, function (err) {
          self.act.toast((err && err.message) || "设置失败", "error");
        });
      },

      /* ---------------- 头像 ---------------- */
      pickAvatar: function () { this.$refs.avatarFile.click(); },

      onAvatarError: function () { this.avatarFailed = true; },

      onAvatarPick: function (ev) {
        var file = ev.target.files && ev.target.files[0];
        ev.target.value = "";   // 先取文件再清空，允许重复选同一个文件
        if (file) this.uploadAvatar(file);
      },
      onDrop: function (ev) {
        this.dragging = false;
        var files = (ev.dataTransfer && ev.dataTransfer.files) || [];
        if (files.length) this.uploadAvatar(files[0]);
      },

      uploadAvatar: function (file) {
        var self = this;
        if (!file.type || file.type.indexOf("image/") !== 0) {
          this.act.toast("请选择图片文件（PNG / JPG / GIF / WebP / BMP）", "error");
          return;
        }
        if (file.size > 4 * 1024 * 1024) {
          this.act.toast("头像不能超过 4 MB", "error");
          return;
        }
        this.avatarBusy = true;
        this.avatarFailed = false;
        var url = (global.URL && URL.createObjectURL) ? URL.createObjectURL(file) : "";
        this.preview = url;   // 先本地预览，不用等接口回包
        this.act.uploadCvAvatar(file).then(function () {
          self.act.toast("头像已更新");
        }, function (err) {
          self.act.toast((err && err.message) || "上传失败", "error");
        }).then(function () {
          self.avatarBusy = false;
          if (url) URL.revokeObjectURL(url);
          self.preview = "";
        });
      },

      removeAvatar: function () {
        var self = this;
        this.avatarBusy = true;
        this.act.removeCvAvatar().then(function () {
          self.act.toast("头像已移除，简历将显示姓名首字");
        }, function (err) {
          self.act.toast((err && err.message) || "移除失败", "error");
        }).then(function () { self.avatarBusy = false; });
      },

      /* ---------------- 简历专属信息 ---------------- */
      editProfile: function () { this.forms.openCvProfile(); },
      addEducation: function () { this.forms.openForm("education", null); },
      editEducation: function (e) { this.forms.openForm("education", e); },
      removeEducation: function (e) { this.forms.remove("education", e); },
      addService: function () { this.forms.openForm("service", null); },
      editService: function (s) { this.forms.openForm("service", s); },
      removeService: function (s) { this.forms.remove("service", s); },

      go: function (page) { this.act.go(page); },

      /* ---------------- 展示辅助 ---------------- */
      /** 「2011-09 — 2016-06」；缺结束时间时用 ongoing 兜底（在读 / 至今） */
      period: function (from, to, ongoing) {
        var f = String(from || "").trim(), t = String(to || "").trim();
        if (!f && !t) return "";
        return (f || "—") + " — " + (t || ongoing || "—");
      }
    },

    template: `
<div>
  <!-- 概况未就绪时的占位，避免整页空白 -->
  <div v-if="!ready" class="card">
    <div class="empty">
      <fwb-icon name="user" :size="44"/>
      <p>正在读取简历发布状态…</p>
      <p class="muted small" style="margin-top:6px">若长时间无响应，请刷新页面重试。</p>
    </div>
  </div>

  <template v-else>
    <!-- ---------- 顶部数字 ---------- -->
    <div class="stat-grid">
      <div class="stat-card" :class="{ 'is-busy': busy === 'publish' }" @click="togglePublish">
        <div class="stat-ico" :class="published ? 'green' : 'amber'">
          <fwb-icon :name="published ? 'globe' : 'lock'"/>
        </div>
        <div class="stat-info">
          <div class="stat-val">{{ published ? "已公开" : "未公开" }}</div>
          <div class="stat-label">点击{{ published ? "暂停" : "开启" }}对外访问</div>
        </div>
      </div>

      <div class="stat-card" @click="editProfile">
        <div class="stat-ico blue"><fwb-icon name="database"/></div>
        <div class="stat-info">
          <div class="stat-val">{{ totalItems }}<small>条</small></div>
          <div class="stat-label">简历收录条目</div>
        </div>
      </div>

      <div class="stat-card" @click="go('achievements')">
        <div class="stat-ico violet"><fwb-icon name="seal"/></div>
        <div class="stat-info">
          <div class="stat-val">{{ counts.papers || 0 }}<small>篇</small></div>
          <div class="stat-label">论文发表</div>
        </div>
      </div>

      <div class="stat-card" @click="go('students')">
        <div class="stat-ico teal"><fwb-icon name="users"/></div>
        <div class="stat-info">
          <div class="stat-val">{{ counts.students || 0 }}<small>人</small></div>
          <div class="stat-label">学生指导</div>
        </div>
      </div>
    </div>

    <div class="dash-grid">
      <!-- ================= 左栏 ================= -->
      <div class="dash-col">

        <!-- 发布与固定链接 -->
        <div class="card">
          <div class="card-head">
            <h3><span class="ch-ico"><fwb-icon name="globe"/></span>发布与固定链接</h3>
            <span class="badge" :class="published ? 'green' : 'gray'">{{ published ? "访客可访问" : "访客不可见" }}</span>
          </div>
          <div class="card-body cs-form">
            <label class="cs-switch" :class="{ on: published }">
              <input type="checkbox" :checked="published" :disabled="busy === 'publish'" @change="togglePublish">
              <span class="css-track"><span class="css-dot"></span></span>
              <span class="css-text">
                <b>{{ published ? "允许任何人访问简历" : "简历已暂停对外访问" }}</b>
                <small>{{ publishHint }}</small>
              </span>
            </label>

            <div class="cs-link">
              <code>{{ link }}</code>
              <button class="btn ghost sm" @click="copyLink"><fwb-icon name="copy"/>复制</button>
              <button class="btn ghost sm" @click="openLink"><fwb-icon name="external"/>打开</button>
              <button class="btn ghost sm" @click="exportPdf"><fwb-icon name="download"/>打印 / PDF</button>
              <button class="btn ghost sm" :disabled="busy === 'rotate'" @click="rotateLink">
                <fwb-icon name="rotate"/>{{ busy === 'rotate' ? "更换中…" : "更换链接" }}
              </button>
            </div>

            <div class="lk-tip">
              <fwb-icon name="info"/>链接里的随机串与账号无关，生成后长期不变；
              内容每次访问时从工作台实时汇总，不需要任何「同步」操作。
            </div>
          </div>
        </div>

        <!-- 头像 -->
        <div class="card">
          <div class="card-head">
            <h3><span class="ch-ico"><fwb-icon name="user"/></span>简历头像</h3>
            <span class="card-note muted small">显示在简历首屏</span>
          </div>
          <div class="card-body">
            <div class="cvs-avatar-row" :class="{ dragging: dragging }"
                 @dragover.prevent="dragging = true"
                 @dragleave="dragging = false"
                 @drop.prevent="onDrop">
              <span class="cvs-avatar" :class="{ empty: !avatarSrc }"
                    :style="!avatarSrc ? { background: avatarTone } : null">
                <img v-if="avatarSrc" :src="avatarSrc" alt="" @error="onAvatarError">
                <template v-else>{{ initial }}</template>
              </span>
              <div class="cvs-avatar-side">
                <div class="row" style="gap:8px;flex-wrap:wrap">
                  <button class="btn primary sm" :disabled="avatarBusy" @click="pickAvatar">
                    <fwb-icon name="upload"/>{{ avatarBusy ? "处理中…" : (avatar.set ? "更换头像" : "上传头像") }}
                  </button>
                  <button v-if="avatar.set" class="btn ghost sm" :disabled="avatarBusy" @click="removeAvatar">
                    <fwb-icon name="trash"/>移除
                  </button>
                  <input ref="avatarFile" type="file" accept="image/*" hidden @change="onAvatarPick">
                </div>
                <p class="muted small cvs-avatar-tip">
                  支持 PNG / JPG / GIF / WebP / BMP，建议正方形，不超过 4 MB。也可以直接把图片拖到这里。
                  未设置时简历显示姓名首字。
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- 基本信息 -->
        <div class="card">
          <div class="card-head">
            <h3><span class="ch-ico"><fwb-icon name="edit"/></span>简历基本信息</h3>
            <span class="card-note more" @click="editProfile">编辑<fwb-icon name="right"/></span>
          </div>
          <div class="card-body">
            <div class="cvs-name">
              <b>{{ profile.name || "未填写姓名" }}</b>
              <span v-if="profile.ename" class="cvs-en">{{ profile.ename }}</span>
              <span v-if="profile.title" class="badge blue">{{ profile.title }}</span>
              <span v-if="profile.dept" class="badge gray">{{ profile.dept }}</span>
            </div>

            <p v-if="profile.tagline" class="cvs-tagline">{{ profile.tagline }}</p>
            <p v-else class="cvs-tagline cvs-tagline-empty">
              还没有一句话定位 —— 点右上角「编辑」补上，会显示在简历姓名下方。
            </p>

            <ul v-if="facts.length" class="cvs-facts">
              <li v-for="f in facts" :key="f.label">
                <fwb-icon :name="f.icon" :size="14"/>
                <span class="k">{{ f.label }}</span>
                <a v-if="f.href" :href="f.href" target="_blank" rel="noopener">{{ f.value }}</a>
                <span v-else class="v">{{ f.value }}</span>
              </li>
            </ul>
            <p v-else class="muted small">还没有联系方式，点右上角「编辑」补充。</p>

            <div class="cvs-block">
              <span class="cvs-block-lab">研究方向</span>
              <template v-if="directions.length">
                <span v-for="d in directions" :key="d" class="badge teal">{{ d }}</span>
              </template>
              <span v-else class="muted small">未填写 —— 简历会自动从文献方向与项目类型推断。</span>
            </div>

            <div class="cvs-block" v-if="profile.bio">
              <span class="cvs-block-lab">个人简介</span>
              <p class="cvs-bio">{{ profile.bio }}</p>
            </div>
          </div>
        </div>

        <!-- 教育经历 -->
        <div class="card">
          <div class="card-head">
            <h3><span class="ch-ico"><fwb-icon name="cap"/></span>教育经历</h3>
            <span class="card-note">
              <span class="muted small" style="margin-right:10px">{{ educations.length }} 条</span>
              <button class="btn ghost sm" @click="addEducation"><fwb-icon name="plus"/>新增</button>
            </span>
          </div>
          <div class="card-body">
            <div v-if="!educations.length" class="empty cvs-empty">
              <fwb-icon name="cap" :size="38"/>
              <p>还没有教育经历，简历里会跳过这一段</p>
            </div>
            <div v-else class="cvs-list">
              <div v-for="e in educations" :key="e.id" class="cvs-row">
                <div class="cvs-row-main">
                  <div class="cvs-row-title">
                    <b>{{ e.school }}</b>
                    <span v-if="e.major" class="cvs-row-sub">{{ e.major }}</span>
                    <span v-if="e.degree" class="badge indigo">{{ e.degree }}</span>
                  </div>
                  <div class="cvs-row-meta">
                    <span v-if="e.from || e.to">{{ period(e.from, e.to, "在读") }}</span>
                    <span v-if="e.supervisor">导师 {{ e.supervisor }}</span>
                    <span v-if="e.note" class="cvs-row-note">{{ e.note }}</span>
                  </div>
                </div>
                <div class="cvs-row-act">
                  <button class="btn text" @click="editEducation(e)">编辑</button>
                  <button class="btn text" style="color:var(--red)" @click="removeEducation(e)">删除</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 社会服务 -->
        <div class="card">
          <div class="card-head">
            <h3><span class="ch-ico"><fwb-icon name="globe"/></span>社会服务</h3>
            <span class="card-note">
              <span class="muted small" style="margin-right:10px">{{ services.length }} 条</span>
              <button class="btn ghost sm" @click="addService"><fwb-icon name="plus"/>新增</button>
            </span>
          </div>
          <div class="card-body">
            <div v-if="!services.length" class="empty cvs-empty">
              <fwb-icon name="globe" :size="38"/>
              <p>还没有社会服务记录（学会任职 / 审稿 / 评审 / 产业服务等）</p>
            </div>
            <div v-else class="cvs-list">
              <div v-for="s in services" :key="s.id" class="cvs-row">
                <div class="cvs-row-main">
                  <div class="cvs-row-title">
                    <span v-if="s.kind" class="badge violet">{{ s.kind }}</span>
                    <b>{{ s.org }}</b>
                    <span v-if="s.role" class="cvs-row-sub">{{ s.role }}</span>
                  </div>
                  <div class="cvs-row-meta">
                    <span v-if="s.from || s.to">{{ period(s.from, s.to, "至今") }}</span>
                    <span v-if="s.note" class="cvs-row-note">{{ s.note }}</span>
                  </div>
                </div>
                <div class="cvs-row-act">
                  <button class="btn text" @click="editService(s)">编辑</button>
                  <button class="btn text" style="color:var(--red)" @click="removeService(s)">删除</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ================= 右栏 ================= -->
      <div class="dash-col">

        <!-- 展示区块开关 -->
        <div class="card">
          <div class="card-head">
            <h3><span class="ch-ico"><fwb-icon name="layers"/></span>展示区块</h3>
            <span class="card-note muted small">关闭后访客看不到</span>
          </div>
          <div class="card-body cvs-toggles">
            <label v-for="r in sectionRows" :key="r.key"
                   class="cvs-toggle" :class="{ on: r.on, empty: r.empty }">
              <input type="checkbox" :checked="r.on" @change="toggleSection(r)">
              <span class="cvs-tg-track"><span class="cvs-tg-dot"></span></span>
              <span class="cvs-tg-label">{{ r.label }}</span>
              <span class="cvs-tg-count">{{ r.count < 0 ? "" : (r.count ? r.count + " 条" : "暂无") }}</span>
            </label>
          </div>
        </div>

        <!-- 内容来源 -->
        <div class="card">
          <div class="card-head">
            <h3><span class="ch-ico"><fwb-icon name="database"/></span>内容来源</h3>
            <span class="card-note muted small">本页不存副本</span>
          </div>
          <div class="card-body cvs-src">
            <div v-for="s in sources" :key="s.key" class="cvs-src-row" @click="go(s.page)">
              <span class="cvs-src-ico"><fwb-icon :name="s.icon"/></span>
              <span class="cvs-src-text">{{ s.text }}</span>
              <span class="cvs-src-num">{{ s.count }}</span>
              <fwb-icon name="right" :size="14"/>
            </div>
            <div class="lk-tip">
              <fwb-icon name="info"/>教育经历与社会服务在上方维护；
              项目、成果、学生、教学请到对应页面新增，简历会自动收录。
            </div>
          </div>
        </div>
      </div>
    </div>
  </template>
</div>`
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.cv = CvSettings;
})(window);
