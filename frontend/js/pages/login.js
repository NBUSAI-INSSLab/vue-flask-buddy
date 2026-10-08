/* =====================================================================
   pages/login.js —— 登录 / 注册页（未登录时的整屏视图）
   ===================================================================== */
(function (global) {
  "use strict";

  var vue = global.Vue;
  var FWB = global.FWB;

  /* NBUSAI 徽标：字母 N 即一条神经网络链路（与 index.html 中一致） */
  var MARK =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M6 18.5V5.5l12 13V5.5"/>' +
    '<circle cx="6" cy="5.5" r="1.85" fill="currentColor" stroke="none"/>' +
    '<circle cx="6" cy="18.5" r="1.85" fill="currentColor" stroke="none"/>' +
    '<circle cx="18" cy="5.5" r="1.85" fill="currentColor" stroke="none"/>' +
    '<circle cx="18" cy="18.5" r="1.85" fill="currentColor" stroke="none"/>' +
    "</svg>";

  var PageLogin = vue.defineComponent({
    name: "PageLogin",

    setup: function () {
      return { act: FWB.store.act };
    },

    data: function () {
      return {
        mode: "login",
        busy: false,
        error: "",
        showPwd: false,
        showPwd2: false,
        mark: MARK,
        themeKey: FWB.theme.current(),
        form: {
          username: "", password: "",
          name: "", title: "讲师", dept: "计算机科学与技术学院",
          email: "", office: "",
          password2: "", withDemo: true
        }
      };
    },

    computed: {
      /* 卡片内配色区显示当前配色名 */
      themeLabel: function () { return FWB.theme.byKey(this.themeKey).label; }
    },

    mounted: function () {
      var self = this;
      this._onTheme = function (ev) { self.themeKey = ev.detail.key; };
      window.addEventListener("fwb:theme", this._onTheme);
      var el = document.querySelector(".login-card input");
      if (el) el.focus();
    },

    beforeUnmount: function () {
      if (this._onTheme) window.removeEventListener("fwb:theme", this._onTheme);
    },

    methods: {
      switchMode: function (m) {
        this.mode = m;
        this.error = "";
        this.showPwd = false;
        this.showPwd2 = false;
      },

      fill: function (kind) {
        if (kind === "admin") {
          this.mode = "login";
          this.form.username = "admin";
          this.form.password = "admin123";
        } else {
          this.mode = "login";
          this.form.username = "jiangxl";
          this.form.password = "123456";
        }
        this.error = "";
      },

      submit: async function () {
        if (this.busy) return;
        var f = this.form;
        this.error = "";

        if (!f.username.trim()) { this.error = "请输入用户名"; return; }
        if (!f.password) { this.error = "请输入密码"; return; }

        if (this.mode === "register") {
          if (!f.name.trim()) { this.error = "请输入姓名"; return; }
          if (f.password.length < 6) { this.error = "密码至少 6 位"; return; }
          if (f.password !== f.password2) { this.error = "两次输入的密码不一致"; return; }
        }

        this.busy = true;
        try {
          if (this.mode === "login") {
            var user = await this.act.login(f.username.trim(), f.password);
            this.act.toast("欢迎回来，" + user.name + "（" + user.roleLabel + "）", "success");
          } else {
            var created = await this.act.register({
              username: f.username.trim(),
              password: f.password,
              name: f.name.trim(),
              title: f.title.trim(),
              dept: f.dept.trim(),
              email: f.email.trim(),
              office: f.office.trim(),
              withDemo: !!f.withDemo
            });
            this.act.toast("注册成功，欢迎加入，" + created.name, "success");
          }
        } catch (e) {
          this.error = e.message || String(e);
        } finally {
          this.busy = false;
        }
      }
    },

    template:
      '<div class="login-page">' +
      /* 背景装饰：柔和光晕 + 细网格（跟随主题色） */
      '  <div class="login-bg" aria-hidden="true">' +
      '    <span class="lb-orb lb-orb-1"></span>' +
      '    <span class="lb-orb lb-orb-2"></span>' +
      '    <span class="lb-orb lb-orb-3"></span>' +
      '    <span class="lb-grid"></span>' +
      "  </div>" +

      '  <div class="login-shell">' +
      /* ---------- 左：品牌与能力概览 ---------- */
      '    <section class="login-intro">' +
      '      <div class="li-brand">' +
      '        <div class="brand-mark" v-html="mark"></div>' +
      '        <div>' +
      '          <div class="li-title">NBUSAI 教师工作台</div>' +
      '          <div class="li-sub">高校教师科研 · 教学 · 学生指导一体化平台</div>' +
      "        </div>" +
      "      </div>" +
      '      <h1 class="li-headline">科研、教学与学生指导<br><em>一个平台</em>全部搞定</h1>' +
      '      <p class="li-desc">从科研项目、文献仓库、学术交流到成果登记、教学管理、课程资源与学生指导，' +
      "        11 个业务模块与 12 项常用工具覆盖教师日常工作的完整链路；管理员还可在管理中心横向查看全院统计。</p>" +
      '      <ul class="li-feats">' +
      '        <li><i class="li-feat-ico"><fwb-icon name="flask"></fwb-icon></i>' +
      '          <div><b>科研全流程</b><span>项目 · 文献 · 交流 · 成果</span></div></li>' +
      '        <li><i class="li-feat-ico"><fwb-icon name="clipboard"></fwb-icon></i>' +
      '          <div><b>教学与学生</b><span>教学任务 · 课程 · 学生指导</span></div></li>' +
      '        <li><i class="li-feat-ico"><fwb-icon name="wrench"></fwb-icon></i>' +
      '          <div><b>12 项内置工具</b><span>日历编排 · 成绩 · 经费 · 统计</span></div></li>' +
      '        <li><i class="li-feat-ico"><fwb-icon name="palette"></fwb-icon></i>' +
      '          <div><b>5 套界面配色</b><span>薄荷绿 · 橙 · 蓝 · 橙蓝 · 灰黑</span></div></li>' +
      "      </ul>" +
      '      <div class="li-foot">' +
      '        <span class="li-pill">11 个业务页面</span>' +
      '        <span class="li-pill">12 个内置工具</span>' +
      '        <span class="li-pill">管理端横向统计</span>' +
      '        <span class="li-pill">数据存于本机</span>' +
      "      </div>" +
      "    </section>" +

      /* ---------- 右：登录 / 注册卡片 ---------- */
      '    <section class="login-panel">' +
      '      <div class="login-card">' +
      '        <div class="lc-top">' +
      '          <div class="brand-mark" v-html="mark"></div>' +
      '          <div class="lc-top-text">' +
      '            <div class="lc-top-title">NBUSAI 教师工作台</div>' +
      "          </div>" +
      "        </div>" +

      '        <div class="lc-tabs">' +
      '          <button type="button" :class="{ on: mode === \'login\' }" @click="switchMode(\'login\')">登录</button>' +
      '          <button type="button" :class="{ on: mode === \'register\' }" @click="switchMode(\'register\')">注册</button>' +
      "        </div>" +

      '        <form v-if="mode === \'login\'" class="lc-form" @submit.prevent="submit">' +
      '          <h2 class="lc-title">欢迎回来</h2>' +
      '          <div class="lc-hint">使用教师或管理员账号登录工作台</div>' +
      '          <div class="field lc-field">' +
      '            <label>用户名</label>' +
      '            <div class="lc-input">' +
      '              <fwb-icon name="user"></fwb-icon>' +
      '              <input v-model="form.username" autocomplete="username" placeholder="请输入用户名" aria-label="用户名">' +
      "            </div>" +
      "          </div>" +
      '          <div class="field lc-field">' +
      '            <label>密码</label>' +
      '            <div class="lc-input pwd">' +
      '              <fwb-icon name="key"></fwb-icon>' +
      '              <input :type="showPwd ? \'text\' : \'password\'" v-model="form.password"' +
      '                     autocomplete="current-password" placeholder="请输入密码" aria-label="密码">' +
      '              <button type="button" class="lc-eye" :class="{ on: showPwd }" @click="showPwd = !showPwd"' +
      '                      :aria-label="showPwd ? \'隐藏密码\' : \'显示密码\'">' +
      '                <fwb-icon :name="showPwd ? \'eye_off\' : \'eye\'"></fwb-icon>' +
      "              </button>" +
      "            </div>" +
      "          </div>" +
      '          <div v-if="error" class="form-error">{{ error }}</div>' +
      '          <button class="btn primary lc-submit" type="submit" :disabled="busy">' +
      '            <span>{{ busy ? "登录中…" : "登录" }}</span>' +
      '            <fwb-icon v-if="!busy" name="right"></fwb-icon>' +
      "          </button>" +
      '          <div class="lc-demo">' +
      '            <div class="lc-demo-title">演示账号（点击自动填充）</div>' +
      '            <button type="button" class="lc-demo-row" @click="fill(\'admin\')">' +
      '              <b>管理员</b><span>admin / admin123</span>' +
      "            </button>" +
      '            <button type="button" class="lc-demo-row" @click="fill(\'teacher\')">' +
      '              <b>教师</b><span>jiangxl / 123456</span>' +
      "            </button>" +
      "          </div>" +
      "        </form>" +

      '        <form v-else class="lc-form" @submit.prevent="submit">' +
      '          <h2 class="lc-title">注册教师账号</h2>' +
      '          <div class="lc-hint">注册后立即进入属于你自己的工作台</div>' +
      '          <div class="lc-grid">' +
      '            <div class="field lc-field"><label>用户名</label>' +
      '              <div class="lc-input"><fwb-icon name="user"></fwb-icon>' +
      '                <input v-model="form.username" placeholder="3-20 位，字母开头" aria-label="注册用户名"></div></div>' +
      '            <div class="field lc-field"><label>姓名</label>' +
      '              <div class="lc-input"><fwb-icon name="cap"></fwb-icon>' +
      '                <input v-model="form.name" placeholder="真实姓名" aria-label="姓名"></div></div>' +
      '            <div class="field lc-field"><label>职称</label>' +
      '              <div class="lc-input"><fwb-icon name="award"></fwb-icon>' +
      '                <input v-model="form.title" placeholder="讲师 / 副教授 / 教授"></div></div>' +
      '            <div class="field lc-field"><label>所属学院</label>' +
      '              <div class="lc-input"><fwb-icon name="building"></fwb-icon>' +
      '                <input v-model="form.dept" placeholder="如 计算机科学与技术学院"></div></div>' +
      '            <div class="field lc-field"><label>邮箱</label>' +
      '              <div class="lc-input"><fwb-icon name="send"></fwb-icon>' +
      '                <input v-model="form.email" placeholder="选填"></div></div>' +
      '            <div class="field lc-field"><label>办公室</label>' +
      '              <div class="lc-input"><fwb-icon name="pin"></fwb-icon>' +
      '                <input v-model="form.office" placeholder="选填"></div></div>' +
      '            <div class="field lc-field"><label>密码</label>' +
      '              <div class="lc-input pwd"><fwb-icon name="key"></fwb-icon>' +
      '                <input :type="showPwd ? \'text\' : \'password\'" v-model="form.password"' +
      '                       autocomplete="new-password" placeholder="至少 6 位">' +
      '                <button type="button" class="lc-eye" :class="{ on: showPwd }" @click="showPwd = !showPwd"' +
      '                        aria-label="显示或隐藏密码">' +
      '                  <fwb-icon :name="showPwd ? \'eye_off\' : \'eye\'"></fwb-icon></button></div></div>' +
      '            <div class="field lc-field"><label>确认密码</label>' +
      '              <div class="lc-input pwd"><fwb-icon name="shield"></fwb-icon>' +
      '                <input :type="showPwd2 ? \'text\' : \'password\'" v-model="form.password2"' +
      '                       autocomplete="new-password" placeholder="再次输入密码">' +
      '                <button type="button" class="lc-eye" :class="{ on: showPwd2 }" @click="showPwd2 = !showPwd2"' +
      '                        aria-label="显示或隐藏确认密码">' +
      '                  <fwb-icon :name="showPwd2 ? \'eye_off\' : \'eye\'"></fwb-icon></button></div></div>' +
      "          </div>" +
      '          <label class="check-line lc-check">' +
      '            <input type="checkbox" v-model="form.withDemo"><span>使用演示数据初始化（便于快速体验）</span>' +
      "          </label>" +
      '          <div v-if="error" class="form-error">{{ error }}</div>' +
      '          <button class="btn primary lc-submit" type="submit" :disabled="busy">' +
      '            <span>{{ busy ? "注册中…" : "注册并进入" }}</span>' +
      '            <fwb-icon v-if="!busy" name="right"></fwb-icon>' +
      "          </button>" +
      "        </form>" +

      /* 卡片内配色切换：登录前也能选主题 */
      '        <div class="lc-theme">' +
      '          <div class="lc-theme-title">界面配色<span>{{ themeLabel }}</span></div>' +
      "          <fwb-theme-picker :hint=\"false\"></fwb-theme-picker>" +
      "        </div>" +
      "      </div>" +
      "    </section>" +
      "  </div>" +
      "</div>"
  });

  FWB.pages = FWB.pages || {};
  FWB.pages.login = PageLogin;
})(window);
