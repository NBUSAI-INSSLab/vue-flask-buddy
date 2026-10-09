/* =====================================================================
   pages/agent.js —— 智能助手（工作区独立页面）

   三个标签：
   - 对话：多会话聊天，智能体（LangChain/LangGraph ReAct）可查询登记
     工作台数据并检索个人知识库回答；工具调用轨迹在气泡下方展示
   - 知识库：上传 txt/md/pdf/docx 文档、列表管理与检索试测
   - 设置：大模型供应商（DeepSeek / 通义 / Kimi / Ollama / 自定义）
     的地址、密钥与模型配置，支持连通性测试
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  function fmtSize(n) {
    if (!n && n !== 0) return "—";
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / 1024 / 1024).toFixed(1) + " MB";
  }
  function fmtTime(iso) {
    if (!iso) return "—";
    return String(iso).replace("T", " ").slice(5, 16);
  }

  var Agent = {
    name: "PageAgent",
    setup: function () {
      var store = FWB.store;
      return { S: store.state, act: store.act, api: FWB.api, U: U };
    },
    data: function () {
      return {
        tab: "chat",              // chat | kb | settings
        /* 会话与消息 */
        sessions: [],
        sessionId: "",
        msgs: [],
        draft: "",
        busy: false,
        /* 知识库 */
        kbDocs: [],
        kbBusy: false,
        kbQuery: "",
        kbHits: [],
        kbSearched: false,
        /* 设置 */
        cfg: { provider: "deepseek", baseUrl: "", apiKey: "", model: "", temperature: 0.3 },
        providers: [],
        hasKey: false,
        keyMasked: "",
        cfgLoaded: false,
        cfgSaving: false,
        testing: false,
        testMsg: null
      };
    },
    created: function () {
      this.loadSessions();
      this.loadKb();
      this.loadSettings();
    },
    computed: {
      llmReady: function () { return this.cfgLoaded && (this.hasKey || !this.needKey); },
      needKey: function () {
        var self = this;
        var p = (this.providers || []).filter(function (x) { return x.key === self.cfg.provider; })[0];
        return !p || p.needKey;
      },
      current: function () {
        var id = this.sessionId, self = this;
        return this.sessions.filter(function (s) { return s.id === id; })[0] || null;
      },
      kbTotal: function () {
        return this.kbDocs.reduce(function (n, d) { return n + (Number(d.chunks) || 0); }, 0);
      }
    },
    methods: {
      fmtSize: fmtSize, fmtTime: fmtTime,

      /* ---------------- 会话与对话 ---------------- */
      loadSessions: function () {
        var self = this;
        this.api.agent.sessions().then(function (list) {
          self.sessions = list || [];
          if (!self.sessionId && self.sessions.length) self.select(self.sessions[0].id);
        }, function () { /* 未登录等场景交给全局处理 */ });
      },
      select: function (id) {
        var self = this;
        this.sessionId = id;
        this.api.agent.messages(id).then(function (list) {
          self.msgs = list || [];
          self.scrollBottom();
        }, function (e) { self.act.toast(e.message, "error"); });
      },
      newChat: function () {
        var self = this;
        this.api.agent.newSession().then(function (s) {
          self.sessions.unshift(s);
          self.msgs = [];
          self.sessionId = s.id;
          self.tab = "chat";
        });
      },
      delSession: function (s) {
        var self = this;
        this.act.confirmDelete("删除会话「" + (s.title || "未命名") + "」？聊天记录将一并清除。", function () {
          self.api.agent.dropSession(s.id).then(function () {
            self.sessions = self.sessions.filter(function (x) { return x.id !== s.id; });
            if (self.sessionId === s.id) {
              self.sessionId = "";
              self.msgs = [];
              if (self.sessions.length) self.select(self.sessions[0].id);
            }
          }, function (e) { self.act.toast(e.message, "error"); });
        });
      },
      send: function () {
        var self = this;
        var text = this.draft.trim();
        if (!text || this.busy) return;
        this.draft = "";
        this.busy = true;
        this.msgs.push({ id: "_local", role: "user", content: text, seq: 0 });
        this.scrollBottom();
        this.api.agent.chat(this.sessionId, text).then(function (res) {
          self.sessionId = res.sessionId;
          self.msgs.push(res.message);
          if (!self.sessions.some(function (s) { return s.id === res.sessionId; })) {
            self.loadSessions();
          }
          self.scrollBottom();
        }, function (e) {
          self.msgs.pop();   // 本地占位撤回
          self.draft = text; // 输入还原
          self.act.toast(e.message, "error");
          if (e.code === "llm_not_configured") self.tab = "settings";
        }).then(function () { self.busy = false; });
      },
      scrollBottom: function () {
        var self = this;
        this.$nextTick(function () {
          var el = document.querySelector(".ag-list");
          if (el) el.scrollTop = el.scrollHeight;
        });
      },

      /* ---------------- 知识库 ---------------- */
      loadKb: function () {
        var self = this;
        this.api.agent.kbDocs().then(function (list) { self.kbDocs = list || []; }, function () {});
      },
      onKbPick: function (ev) {
        // FileList 是活引用：先快照再清 input，防止后续清空连坐
        var files = ev.target.files;
        if (!files || !files.length) return;
        var arr = [];
        for (var i = 0; i < files.length; i++) arr.push(files[i]);
        ev.target.value = "";
        this.uploadKb(arr);
      },
      uploadKb: function (arr) {
        var self = this;
        this.kbBusy = true;
        this.api.agent.kbUpload(arr).then(function (res) {
          self.loadKb();
          var ok = (res.saved || []).length, bad = (res.failed || []).length;
          if (ok) self.act.toast("已导入 " + ok + " 篇文档");
          (res.failed || []).forEach(function (f) { self.act.toast(f.name + "：" + f.error, "warn"); });
          if (!ok && !bad) self.act.toast("未选择有效文件", "warn");
        }, function (e) { self.act.toast(e.message, "error"); }
        ).then(function () { self.kbBusy = false; });
      },
      delKb: function (d) {
        var self = this;
        this.act.confirmDelete("删除文档「" + d.name + "」及其全部分块？", function () {
          self.api.agent.kbDelete(d.id).then(function () {
            self.kbDocs = self.kbDocs.filter(function (x) { return x.id !== d.id; });
            self.kbSearched = false; self.kbHits = [];
            self.act.toast("已删除");
          }, function (e) { self.act.toast(e.message, "error"); });
        });
      },
      runKbSearch: function () {
        var self = this;
        var q = this.kbQuery.trim();
        if (!q) return;
        this.kbBusy = true;
        this.kbSearched = false;
        this.api.agent.kbSearch(q).then(function (res) {
          self.kbHits = res.hits || [];
          self.kbSearched = true;
        }, function (e) { self.act.toast(e.message, "error"); }
        ).then(function () { self.kbBusy = false; });
      },

      /* ---------------- 设置 ---------------- */
      loadSettings: function () {
        var self = this;
        this.api.agent.settings().then(function (cfg) {
          self.providers = cfg.providers || [];
          self.cfg.provider = cfg.provider;
          self.cfg.baseUrl = cfg.baseUrl;
          self.cfg.model = cfg.model;
          self.cfg.temperature = cfg.temperature;
          self.hasKey = !!cfg.hasKey;
          self.keyMasked = cfg.keyMasked || "";
          self.cfgLoaded = true;
        }, function () { self.cfgLoaded = true; });
      },
      pickProvider: function () {
        var self = this;
        var p = this.providers.filter(function (x) { return x.key === self.cfg.provider; })[0];
        if (p) { this.cfg.baseUrl = p.baseUrl; this.cfg.model = p.model; }
      },
      saveSettings: function () {
        var self = this;
        var payload = {
          provider: this.cfg.provider,
          baseUrl: this.cfg.baseUrl,
          model: this.cfg.model,
          temperature: this.cfg.temperature
        };
        var key = this.cfg.apiKey.trim();
        if (key) payload.apiKey = key;   // 留空 = 沿用已保存的 Key
        this.cfgSaving = true;
        this.api.agent.saveSettings(payload).then(function (cfg) {
          self.hasKey = !!cfg.hasKey;
          self.keyMasked = cfg.keyMasked || "";
          self.cfg.apiKey = "";
          self.act.toast("设置已保存");
        }, function (e) { self.act.toast(e.message, "error"); }
        ).then(function () { self.cfgSaving = false; });
      },
      testConn: function () {
        var self = this;
        var payload = {
          provider: this.cfg.provider, baseUrl: this.cfg.baseUrl,
          model: this.cfg.model, temperature: this.cfg.temperature
        };
        var key = this.cfg.apiKey.trim();
        if (key) payload.apiKey = key; else payload.apiKey = "***";
        this.testing = true;
        this.testMsg = null;
        this.api.agent.testSettings(payload).then(function (res) {
          self.testMsg = res;
        }, function (e) { self.testMsg = { ok: false, message: e.message }; }
        ).then(function () { self.testing = false; });
      }
    },

    template:
      "<div>" +
      '  <div class="tabs ag-tabs">' +
      '    <div class="tab" :class="{ active: tab === \'chat\' }" @click="tab = \'chat\'">对话</div>' +
      '    <div class="tab" :class="{ active: tab === \'kb\' }" @click="tab = \'kb\'">知识库（{{ kbDocs.length }}）</div>' +
      '    <div class="tab" :class="{ active: tab === \'settings\' }" @click="tab = \'settings\'">设置' +
      '      <span v-if="cfgLoaded && !llmReady" class="ag-dot" title="未配置大模型"></span></div>' +
      "  </div>" +

      /* ================= 对话 ================= */
      '  <div v-if="tab === \'chat\'" class="ag-layout">' +
      '    <aside class="ag-side card">' +
      '      <button class="btn primary sm ag-new" @click="newChat"><fwb-icon name="plus"/>新对话</button>' +
      '      <div class="ag-sessions">' +
      '        <div v-for="s in sessions" :key="s.id" class="ag-session" :class="{ on: s.id === sessionId }"' +
      '             @click="select(s.id)">' +
      '          <div class="ag-s-title">{{ s.title || "未命名" }}</div>' +
      '          <div class="ag-s-meta"><span>{{ fmtTime(s.updatedAt) }}</span>' +
      '            <button class="icon-btn ag-s-del" title="删除会话" @click.stop="delSession(s)"><fwb-icon name="trash"/></button>' +
      "          </div>" +
      "        </div>" +
      '        <div v-if="!sessions.length" class="ag-s-empty">暂无会话</div>' +
      "      </div>" +
      "    </aside>" +

      '    <div class="ag-main card">' +
      '      <div v-if="cfgLoaded && !llmReady" class="ag-guide">' +
      '        <fwb-icon name="bot" :size="22"/>' +
      '        <div><b>还没接入大模型</b>' +
      '          <p>在「设置」中选择供应商并填写 API Key 后，即可开始对话。</p></div>' +
      '        <button class="btn ghost sm" @click="tab = \'settings\'">去设置</button>' +
      "      </div>" +
      '      <div class="ag-list" v-else>' +
      '        <div v-if="!msgs.length" class="ag-welcome">' +
      '          <fwb-icon name="bot" :size="34"/>' +
      "          <b>你好，我是你的工作台助手</b>" +
      '          <p>可以试试：<span>「我最近有什么日程？」</span><span>「帮我安排周五下午 3 点组会」</span>' +
      '          <span>「根据知识库，课程考核要求是什么？」</span></p>' +
      "        </div>" +
      '        <div v-for="m in msgs" :key="m.id" class="ag-msg" :class="m.role">' +
      '          <div class="ag-avatar" v-if="m.role === \'assistant\'"><fwb-icon name="bot" :size="15"/></div>' +
      '          <div class="ag-bubble">' +
      '            <div v-if="m.role === \'assistant\'" class="ag-text ag-md" v-html="U.md(m.content)"></div>' +
      '            <div v-else class="ag-text">{{ m.content }}</div>' +
      '            <details v-if="m.steps && m.steps.length" class="ag-steps">' +
      '              <summary>使用了 {{ m.steps.length }} 个工具</summary>' +
      '              <div v-for="(st, i) in m.steps" :key="i" class="ag-step">' +
      '                <span class="ag-step-tool">{{ st.tool }}</span>' +
      '                <span class="ag-step-sum">{{ st.summary || "已执行" }}</span>' +
      "              </div>" +
      "            </details>" +
      "          </div>" +
      "        </div>" +
      '        <div v-if="busy" class="ag-msg assistant">' +
      '          <div class="ag-avatar"><fwb-icon name="bot" :size="15"/></div>' +
      '          <div class="ag-bubble ag-typing"><i></i><i></i><i></i></div>' +
      "        </div>" +
      "      </div>" +
      '      <div class="ag-input">' +
      '        <textarea rows="1" v-model="draft" placeholder="输入问题，Enter 发送（Shift+Enter 换行）"' +
      '          @keydown.enter.exact.prevent="send"></textarea>' +
      '        <button class="btn primary" :disabled="busy || !draft.trim()" @click="send">' +
      '          <fwb-icon name="send"/>发送</button>' +
      "      </div>" +
      "    </div>" +
      "  </div>" +

      /* ================= 知识库 ================= */
      '  <div v-if="tab === \'kb\'" class="ag-kb">' +
      '    <div class="ag-kb-top">' +
      '      <div class="mini-stats">' +
      '        <div class="mini-stat"><div class="ms-val">{{ kbDocs.length }}<small>篇</small></div><div class="ms-lab">文档</div></div>' +
      '        <div class="mini-stat"><div class="ms-val">{{ kbTotal }}<small>块</small></div><div class="ms-lab">分块</div></div>' +
      "      </div>" +
      '      <label class="btn primary" :class="{ disabled: kbBusy }">' +
      '        <fwb-icon name="upload"/>{{ kbBusy ? "导入中…" : "上传文档" }}' +
      '        <input type="file" hidden multiple accept=".txt,.md,.pdf,.docx" @change="onKbPick"></label>' +
      "    </div>" +
      '    <div class="lk-tip"><fwb-icon name="info"/>支持 txt / md / pdf / docx，单文件 ≤ 10 MB。导入后自动分块建立检索索引，智能体回答专业问题时会引用这里的内容。</div>' +
      '    <div class="card ag-kb-card">' +
      '      <table class="tbl" v-if="kbDocs.length">' +
      "        <thead><tr><th>文档</th><th>大小</th><th>分块</th><th>导入时间</th><th></th></tr></thead>" +
      "        <tbody>" +
      '          <tr v-for="d in kbDocs" :key="d.id">' +
      '            <td><div class="ag-doc"><fwb-icon name="doc"/>{{ d.name }}</div></td>' +
      "            <td>{{ fmtSize(d.size) }}</td>" +
      "            <td>{{ d.chunks }} 块</td>" +
      "            <td>{{ fmtTime(d.createdAt) }}</td>" +
      '            <td class="ops"><button class="icon-btn" title="删除" @click="delKb(d)"><fwb-icon name="trash"/></button></td>' +
      "          </tr>" +
      "        </tbody>" +
      "      </table>" +
      '      <div v-else class="ag-kb-empty"><fwb-icon name="doc" :size="30"/><p>还没有文档，上传第一份资料吧</p></div>' +
      "    </div>" +
      '    <div class="card ag-kb-test">' +
      '      <b>检索试测</b>' +
      '      <div class="ag-kb-q">' +
      '        <input type="text" v-model="kbQuery" placeholder="输入问题，查看知识库会命中的内容" @keydown.enter="runKbSearch">' +
      '        <button class="btn ghost" :disabled="kbBusy" @click="runKbSearch"><fwb-icon name="search"/>检索</button>' +
      "      </div>" +
      '      <div v-if="kbSearched && !kbHits.length" class="muted small">没有命中内容，试试换一种问法或先上传相关文档。</div>' +
      '      <div v-for="(h, i) in kbHits" :key="i" class="ag-hit">' +
      '        <div class="ag-hit-head"><span class="badge teal">{{ h.docName }}</span>' +
      '          <span class="muted small">片段 {{ h.idx + 1 }} · 相关度 {{ h.score }}</span></div>' +
      '        <p>{{ h.text }}</p>' +
      "      </div>" +
      "    </div>" +
      "  </div>" +

      /* ================= 设置 ================= */
      '  <div v-if="tab === \'settings\'" class="ag-set card">' +
      '    <div class="ag-set-head"><b>大模型接入</b>' +
      '      <span v-if="cfgLoaded" class="badge" :class="llmReady ? \'teal\' : \'amber\'">{{ llmReady ? "已就绪" : "未配置" }}</span></div>' +
      '    <div class="form-row"><label>供应商</label>' +
      '      <select v-model="cfg.provider" @change="pickProvider">' +
      '        <option v-for="p in providers" :key="p.key" :value="p.key">{{ p.label }}</option>' +
      "      </select></div>" +
      '    <div class="form-row"><label>接口地址（base_url）</label>' +
      '      <input type="text" v-model.trim="cfg.baseUrl" placeholder="https://api.deepseek.com/v1"></div>' +
      '    <div class="form-row"><label>API Key{{ hasKey ? "（已保存 " + keyMasked + "，留空则沿用）" : "" }}</label>' +
      "      <input type=\"password\" v-model=\"cfg.apiKey\" :placeholder=\"hasKey ? '不修改请留空' : 'sk-...'\"></div>" +
      '    <div class="form-row"><label>模型</label>' +
      '      <input type="text" v-model.trim="cfg.model" placeholder="deepseek-chat"></div>' +
      '    <div class="form-row"><label>回答随机性（temperature {{ cfg.temperature }}）</label>' +
      '      <input type="range" min="0" max="1.5" step="0.1" v-model.number="cfg.temperature"></div>' +
      '    <div class="ag-set-ops">' +
      '      <button class="btn ghost" :disabled="testing" @click="testConn">{{ testing ? "测试中…" : "测试连接" }}</button>' +
      '      <button class="btn primary" :disabled="cfgSaving" @click="saveSettings">{{ cfgSaving ? "保存中…" : "保存设置" }}</button>' +
      "    </div>" +
      '    <div v-if="testMsg" class="ag-test" :class="testMsg.ok ? \'ok\' : \'bad\'">{{ testMsg.message }}' +
      '      <span v-if="testMsg.model" class="muted">（{{ testMsg.model }}）</span></div>' +
      "  </div>" +
      "</div>"
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.agent = Agent;
})(window);
