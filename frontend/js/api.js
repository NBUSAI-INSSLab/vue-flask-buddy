/* =====================================================================
   api.js —— REST 客户端（薄封装 fetch，统一错误处理）
   后端约定：成功 {ok:true, data}，失败 {ok:false, error}
   ===================================================================== */
(function (global) {
  "use strict";

  var BASE = "";  // 与 Flask 同源，无需前缀

  async function request(method, path, body, isForm) {
    var opts = {
      method: method,
      headers: {},
      credentials: "same-origin"  // 携带会话 Cookie
    };
    if (body !== undefined && body !== null) {
      if (isForm) {
        opts.body = body;  // FormData：交给浏览器设置 Content-Type
      } else {
        opts.headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
      }
    }
    var res;
    try {
      res = await fetch(BASE + path, opts);
    } catch (e) {
      throw new Error("无法连接服务器，请确认后端已启动");
    }
    var payload = null;
    try { payload = await res.json(); } catch (e) { payload = null; }
    if (!res.ok || !payload || payload.ok === false) {
      var err = new Error((payload && payload.error) || ("请求失败（HTTP " + res.status + "）"));
      err.status = res.status;
      err.code = payload && payload.code;
      // 登录态失效：交给上层统一切回登录页
      if (res.status === 401 && global.FWB.store && global.FWB.store.act.onUnauthorized) {
        global.FWB.store.act.onUnauthorized();
      }
      throw err;
    }
    return payload.data;
  }

  var api = {
    /** 全量状态（前端启动时一次拉取） */
    state: function () { return request("GET", "/api/state"); },
    /** 12 工具字段规格 */
    specs: function () { return request("GET", "/api/tools/specs"); },

    /** 集合 CRUD */
    list: function (coll) { return request("GET", "/api/collections/" + coll); },
    create: function (coll, item) { return request("POST", "/api/collections/" + coll, item); },
    patch: function (coll, id, data) { return request("PATCH", "/api/collections/" + coll + "/" + id, data); },
    remove: function (coll, id) { return request("DELETE", "/api/collections/" + coll + "/" + id); },

    /** 个人信息 */
    profile: function () { return request("GET", "/api/profile"); },
    saveProfile: function (data) { return request("PUT", "/api/profile", data); },

    /** 统计 / 搜索 */
    stats: function () { return request("GET", "/api/stats"); },
    search: function (q) { return request("GET", "/api/search?q=" + encodeURIComponent(q)); },

    /** 数据管理 */
    exportUrl: function () { return BASE + "/api/export"; },
    importData: function (payload) { return request("POST", "/api/import", payload); },
    reset: function () { return request("POST", "/api/reset"); },

    /** 工具 */
    runTool: function (key, params, fileIds) {
      return request("POST", "/api/tools/" + key + "/run",
        { params: params || {}, files: fileIds || [] });
    },
    upload: function (fileList) {
      var fd = new FormData();
      for (var i = 0; i < fileList.length; i++) fd.append("files", fileList[i]);
      return request("POST", "/api/tools/upload", fd, true);
    },

    /** 课程开放与资料（教师端） */
    courses: {
      share: function (id) { return request("GET", "/api/courses/" + id + "/share"); },
      setVisibility: function (id, payload) {
        return request("POST", "/api/courses/" + id + "/visibility", payload);
      },
      uploadMaterials: function (id, fileList, opts) {
        var fd = new FormData();
        for (var i = 0; i < fileList.length; i++) fd.append("files", fileList[i]);
        if (opts && opts.type) fd.append("type", opts.type);
        if (opts && opts.date) fd.append("date", opts.date);
        return request("POST", "/api/courses/" + id + "/materials", fd, true);
      },
      deleteMaterial: function (id, mid) {
        return request("DELETE", "/api/courses/" + id + "/materials/" + mid);
      },
      /** 直链（同源携带会话 Cookie），用于 <a href> 下载 */
      materialUrl: function (id, mid) {
        return BASE + "/api/courses/" + id + "/materials/" + mid + "/download";
      },
      /** 课程联系方式概况：QQ 群 / 二维码 / 教学日历 */
      contact: function (id) { return request("GET", "/api/courses/" + id + "/contact"); },
      saveContact: function (id, payload) {
        return request("POST", "/api/courses/" + id + "/contact", payload);
      },
      uploadQr: function (id, file) {
        var fd = new FormData();
        fd.append("file", file);
        return request("POST", "/api/courses/" + id + "/qr", fd, true);
      },
      removeQr: function (id) { return request("DELETE", "/api/courses/" + id + "/qr"); },
      /** 群二维码直链（时间戳防缓存由调用方拼接） */
      qrUrl: function (id) { return BASE + "/api/courses/" + id + "/qr"; }
    },

    /** 个人简历（教师端；公开侧走 /api/public/cv/<token>） */
    cv: {
      /** 发布概况：固定链接 / 公开开关 / 区块开关与条目数 */
      overview: function () { return request("GET", "/api/cv"); },
      setVisibility: function (published) {
        return request("POST", "/api/cv/visibility", { published: !!published });
      },
      /** 区块显示开关：只传需要变更的键 */
      setSections: function (patch) { return request("POST", "/api/cv/sections", patch || {}); },
      /** 更换固定链接（旧链接立即失效） */
      rotateToken: function () { return request("POST", "/api/cv/token", {}); },
      /** 聚合后的简历数据（与公开页同源，供工作台内预览） */
      preview: function () { return request("GET", "/api/cv/preview"); },
      uploadAvatar: function (file) {
        var fd = new FormData();
        fd.append("file", file);
        return request("POST", "/api/cv/avatar", fd, true);
      },
      removeAvatar: function () { return request("DELETE", "/api/cv/avatar"); }
    },

    /** 常用网站图标（服务端抓取 + 缓存；抓不到时返回首字母头像，不会 404） */
    links: {
      iconUrl: function (url, name, bust) {
        var qs = "url=" + encodeURIComponent(url || "");
        if (name) qs += "&name=" + encodeURIComponent(name);
        if (bust) qs += "&t=" + bust;
        return BASE + "/api/links/favicon?" + qs;
      },
      /** 读取站点标题 / 主机名，供「添加网站」自动填充 */
      meta: function (url) {
        return request("GET", "/api/links/meta?url=" + encodeURIComponent(url || ""));
      },
      /** 直接取图标二进制：返回 {src, source}，source 为 site / fallback */
      probe: async function (url, name, bust) {
        var res = await fetch(api.links.iconUrl(url, name, bust), {
          credentials: "same-origin", cache: "no-store"
        });
        if (!res.ok) throw new Error("图标获取失败（HTTP " + res.status + "）");
        var blob = await res.blob();
        return {
          src: URL.createObjectURL(blob),
          source: res.headers.get("X-Favicon-Source") || "site"
        };
      }
    },

    /** 认证 */
    auth: {
      me: function () { return request("GET", "/api/auth/me"); },
      login: function (username, password) {
        return request("POST", "/api/auth/login", { username: username, password: password });
      },
      register: function (payload) { return request("POST", "/api/auth/register", payload); },
      logout: function () { return request("POST", "/api/auth/logout"); }
    },

    /** 管理端（需管理员角色） */
    admin: {
      overview: function () { return request("GET", "/api/admin/overview"); },
      teachers: function () { return request("GET", "/api/admin/teachers"); },
      teacher: function (id) { return request("GET", "/api/admin/teachers/" + id); },
      createTeacher: function (payload) { return request("POST", "/api/admin/teachers", payload); },
      updateTeacher: function (id, patch) { return request("PATCH", "/api/admin/teachers/" + id, patch); },
      resetPassword: function (id, password) {
        return request("POST", "/api/admin/teachers/" + id + "/password", { password: password });
      },
      deleteTeacher: function (id) { return request("DELETE", "/api/admin/teachers/" + id); },

      /** 成果审核 */
      achievements: function (params) {
        var p = params || {};
        var qs = [];
        if (p.status) qs.push("status=" + encodeURIComponent(p.status));
        if (p.teacher) qs.push("teacher=" + encodeURIComponent(p.teacher));
        if (p.q) qs.push("q=" + encodeURIComponent(p.q));
        return request("GET", "/api/admin/achievements" + (qs.length ? "?" + qs.join("&") : ""));
      },
      reviewAchievement: function (payload) {
        return request("POST", "/api/admin/achievements/review", payload);
      },
      batchReview: function (payload) {
        return request("POST", "/api/admin/achievements/batch-review", payload);
      }
    }
  };

  global.FWB = global.FWB || {};
  global.FWB.api = api;
})(window);
