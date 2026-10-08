/* =====================================================================
   pages/links.js —— 常用网站（发展区独立页面）

   从工作首页拆出：首页只保留概览，网站导航独立成页，便于长期维护。
   - 默认视图按分组分节展示（像一份「个人网站导航」）
   - 支持关键词搜索（名称 / 备注 / 域名）与分组筛选
   - 管理模式：卡片可拖动排序、就地增删改
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = global.FWB;
  var U = FWB.util;

  var Links = {
    name: "PageLinks",
    setup: function () {
      var store = FWB.store;
      return { S: store.state, act: store.act, U: U };
    },
    computed: {
      /* 全部网站：sort 升序（手工拖拽顺序），缺失时按名称兜底 */
      allSites: function () {
        return this.act.list("links").slice().sort(function (a, b) {
          var d = (Number(a.sort) || 0) - (Number(b.sort) || 0);
          return d !== 0 ? d : String(a.name || "").localeCompare(String(b.name || ""));
        });
      },
      /* 分组标签：顺序优先按 LINK_GROUPS 约定，未登记的自定义分组排其后 */
      tabs: function () {
        var counts = {}, order = [];
        this.allSites.forEach(function (s) {
          var g = (s && s.group) || "其他";
          if (!(g in counts)) { counts[g] = 0; order.push(g); }
          counts[g] += 1;
        });
        order.sort(function (a, b) {
          var ia = U.LINK_GROUPS.indexOf(a), ib = U.LINK_GROUPS.indexOf(b);
          if (ia < 0) ia = 99;
          if (ib < 0) ib = 99;
          return ia - ib || a.localeCompare(b);
        });
        return order.map(function (g) { return { key: g, label: g, count: counts[g] }; });
      },
      groupCount: function () { return this.tabs.length; },

      /* 关键词命中：名称 / 备注 / 域名任一命中即可 */
      matched: function () {
        var kw = this.keyword.trim().toLowerCase();
        if (!kw) return this.allSites;
        return this.allSites.filter(function (s) {
          var hay = [s.name, s.note, U.siteHost(s.url)].join(" ").toLowerCase();
          return hay.indexOf(kw) >= 0;
        });
      },
      /* 分组筛选作用在命中结果之上 */
      sites: function () {
        if (this.group === "all") return this.matched;
        var g = this.group;
        return this.matched.filter(function (s) { return ((s && s.group) || "其他") === g; });
      },
      filtered: function () { return !!this.keyword.trim() || this.group !== "all"; },
      /* 分节视图：仅默认状态（无搜索、无分组筛选、非管理模式）启用 */
      grouped: function () {
        return !this.manage && this.group === "all" && !this.keyword.trim();
      },

      /* 渲染节点流：分组标题与网站卡片共用一个网格，标题横跨整行 */
      nodes: function () {
        var out = [];
        var push = function (s) { out.push({ type: "site", key: s.id, site: s }); };
        if (!this.grouped) {
          this.sites.forEach(push);
          return out;
        }
        var byGroup = {};
        this.sites.forEach(function (s) {
          var g = (s && s.group) || "其他";
          (byGroup[g] = byGroup[g] || []).push(s);
        });
        this.tabs.forEach(function (t) {
          var items = byGroup[t.key] || [];
          if (!items.length) return;
          out.push({ type: "head", key: "h:" + t.key, label: t.label, count: items.length });
          items.forEach(push);
        });
        return out;
      },

      emptyTitle: function () {
        if (!this.allSites.length) return "还没有常用网站";
        if (this.keyword.trim()) return "没有匹配「" + this.keyword.trim() + "」的网站";
        return "该分组下暂无网站";
      }
    },
    data: function () {
      return {
        keyword: "",
        group: "all",       // all | 具体分组
        manage: false,      // 管理模式：可拖动排序与增删改
        dragId: "",         // 正在拖动的网站 id
        overId: "",         // 拖动悬停的目标网站 id
        iconOk: {},         // 图标加载成功（渐显）
        iconFailed: {}      // 图标加载失败（保留首字母头像）
      };
    },
    methods: {
      iconOf: function (s) { return FWB.api.links.iconUrl(s.url, s.name); },
      siteTip: function (s) {
        return s.name + (s.note ? " · " + s.note : "") + "\n" + s.url;
      },
      /* 管理模式：链接不跳转，避免误点离开工作台 */
      onSiteClick: function (ev) { if (this.manage) ev.preventDefault(); },

      resetFilter: function () { this.keyword = ""; this.group = "all"; },

      openLinkForm: function (link) {
        this.act.openModal({
          component: "fwb-link-edit",
          title: link ? "编辑网站" : "添加网站",
          props: { link: link, groups: U.LINK_GROUPS }
        });
      },
      addSite: function () { this.openLinkForm(null); },
      editSite: function (s) { this.openLinkForm(s); },

      delSite: function (s) {
        var self = this;
        this.act.confirmDelete("确定删除「" + s.name + "」吗？", function () {
          return self.act.removeSiteLink(s.id);
        }).then(function () {
          // 删掉的正好是当前筛选分组里的最后一个 → 回到「全部」，避免看到空列表
          if (self.group === "all") return;
          var left = self.matched.filter(function (x) {
            return ((x && x.group) || "其他") === self.group;
          });
          if (!left.length) self.group = "all";
        });
      },

      /* ---------------- 拖动排序（仅管理模式） ---------------- */
      onDragStart: function (s, ev) {
        if (!this.manage) return;
        this.dragId = s.id;
        if (ev.dataTransfer) {
          ev.dataTransfer.effectAllowed = "move";
          try { ev.dataTransfer.setData("text/plain", s.id); } catch (e) { /* 忽略 */ }
        }
      },
      onDragOver: function (s) {
        if (!this.manage || !this.dragId || this.dragId === s.id) return;
        this.overId = s.id;
      },
      onDrop: function (s) {
        var from = this.dragId;
        this.onDragEnd();
        if (!this.manage || !from || from === s.id) return;
        // 排序基准始终是「全部网站」，避免筛选态下只重排子集而打乱其他分组
        var ids = this.allSites.map(function (x) { return x.id; });
        var fi = ids.indexOf(from), ti = ids.indexOf(s.id);
        if (fi < 0 || ti < 0) return;
        ids.splice(ti, 0, ids.splice(fi, 1)[0]);
        this.act.reorderSiteLinks(ids).catch(function (e) {
          FWB.store.act.toast("排序保存失败：" + ((e && e.message) || e), "error");
        });
      },
      onDragEnd: function () { this.dragId = ""; this.overId = ""; }
    },
    template:
      "<div>" +
      '  <div class="mini-stats">' +
      '    <div class="mini-stat"><div class="ms-val">{{ allSites.length }}<small>个</small></div><div class="ms-lab">网站总数</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ groupCount }}<small>类</small></div><div class="ms-lab">分组数量</div></div>' +
      '    <div class="mini-stat"><div class="ms-val">{{ sites.length }}<small>个</small></div>' +
      '      <div class="ms-lab">{{ filtered ? "当前筛选命中" : "当前展示" }}</div></div>' +
      "  </div>" +

      '  <div class="toolbar">' +
      '    <label class="mini-search">' +
      '      <fwb-icon name="search"/>' +
      '      <input type="text" v-model="keyword" placeholder="搜索名称 / 备注 / 域名">' +
      "    </label>" +
      '    <button v-if="filtered" class="btn ghost sm" @click="resetFilter">' +
      '      <fwb-icon name="x"/>清空筛选</button>' +
      '    <div class="spacer"></div>' +
      '    <button v-if="manage" class="btn ghost" @click="manage = false">' +
      '      <fwb-icon name="check"/>完成管理</button>' +
      '    <button v-else class="btn ghost" @click="manage = true">' +
      '      <fwb-icon name="edit"/>管理网站</button>' +
      '    <button class="btn primary" @click="addSite"><fwb-icon name="plus"/>添加网站</button>' +
      "  </div>" +

      '  <div class="site-tabs" v-if="tabs.length > 1 && !manage">' +
      '    <button class="site-tab" :class="{ on: group === \'all\' }" @click="group = \'all\'">' +
      "      全部<b>{{ allSites.length }}</b></button>" +
      '    <button v-for="t in tabs" :key="t.key" class="site-tab"' +
      '            :class="{ on: group === t.key }" @click="group = t.key">' +
      "      {{ t.label }}<b>{{ t.count }}</b></button>" +
      "  </div>" +

      /* 空态 */
      '  <div v-if="!sites.length" class="card"><div class="empty lks-empty">' +
      '    <fwb-icon :name="allSites.length ? \'search\' : \'globe\'" :size="42"/>' +
      "    <p>{{ emptyTitle }}</p>" +
      '    <button v-if="filtered" class="btn ghost sm mt-2" @click="resetFilter">清空筛选</button>' +
      '    <button v-else class="btn ghost sm mt-2" @click="addSite"><fwb-icon name="plus"/>添加网站</button>' +
      "  </div></div>" +

      /* 卡片网格：分组标题横跨整行（grid-column: 1 / -1） */
      '  <div v-else class="site-grid">' +
      '    <template v-for="n in nodes" :key="n.key">' +
      '      <div v-if="n.type === \'head\'" class="lks-group-h">' +
      '        <span>{{ n.label }}</span><b>{{ n.count }}</b><i class="lks-line"></i>' +
      "      </div>" +
      '      <div v-else class="site-card"' +
      '           :class="{ editing: manage, dragging: dragId === n.site.id, over: overId === n.site.id }"' +
      '           :title="siteTip(n.site)" :draggable="manage"' +
      '           @dragstart="onDragStart(n.site, $event)" @dragover.prevent="onDragOver(n.site, $event)"' +
      '           @drop.prevent="onDrop(n.site, $event)" @dragend="onDragEnd">' +
      '        <a class="sc-link" :href="n.site.url" target="_blank" rel="noopener noreferrer"' +
      '           @click="onSiteClick($event)">' +
      '          <span class="sc-ico">' +
      '            <span class="sc-fb" :style="{ background: U.siteTone(n.site.name, n.site.url) }">' +
      "              {{ U.siteLetter(n.site.name, n.site.url) }}</span>" +
      '            <img v-if="!iconFailed[n.site.id]" :key="n.site.url" :src="iconOf(n.site)" :alt="n.site.name"' +
      '                 @load="iconOk[n.site.id] = true" :class="{ on: iconOk[n.site.id] }"' +
      '                 @error="iconFailed[n.site.id] = true">' +
      "          </span>" +
      '          <span class="sc-meta">' +
      '            <b class="sc-name">{{ n.site.name }}</b>' +
      '            <small class="sc-host">{{ n.site.note || U.siteHost(n.site.url) }}</small>' +
      "          </span>" +
      '          <span class="sc-go" v-if="!manage"><fwb-icon name="external"/></span>' +
      "        </a>" +
      '        <span class="sc-ops" v-if="manage">' +
      '          <button class="sc-op" title="编辑" @click="editSite(n.site)"><fwb-icon name="edit"/></button>' +
      '          <button class="sc-op del" title="删除" @click="delSite(n.site)"><fwb-icon name="trash"/></button>' +
      "        </span>" +
      "      </div>" +
      "    </template>" +
      '    <button v-if="manage" class="site-card site-add" @click="addSite">' +
      '      <fwb-icon name="plus"/><span>添加网站</span></button>' +
      "  </div>" +

      '  <p class="site-hint" v-if="manage">' +
      '    <fwb-icon name="info"/>拖动卡片可调整顺序（按「全部」顺序保存）；图标由服务端自动抓取并缓存，' +
      "    抓不到时显示首字母头像。</p>" +
      "</div>"
  };

  FWB.pages = FWB.pages || {};
  FWB.pages.links = Links;
})(window);
