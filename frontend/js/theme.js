/* =====================================================================
   theme.js —— 前端配色主题引擎
   切换 <html data-theme="…"> 即可整体换色；选择保存在 localStorage。
   必须在首屏渲染前执行（index.html 中置于所有 UI 脚本之前）。
   ===================================================================== */
(function (global) {
  "use strict";

  var FWB = (global.FWB = global.FWB || {});
  var STORAGE_KEY = "fwb-theme";
  var DEFAULT_KEY = "mint";

  /* 每套主题给出 3 个代表色，用于界面上的配色圆点 */
  var THEMES = [
    {
      key: "mint", label: "薄荷绿", desc: "默认配色，清新沉稳",
      colors: ["#189d5b", "#27ae6d", "#0c6b3d"]
    },
    {
      key: "orange", label: "橙色", desc: "温暖醒目，活力感强",
      colors: ["#ea6a12", "#f98430", "#b04a06"]
    },
    {
      key: "blue", label: "蓝色", desc: "理性专业，学术蓝调",
      colors: ["#1f6feb", "#3b86f7", "#1449a0"]
    },
    {
      key: "orangeblue", label: "橙蓝", desc: "撞色搭配，层次鲜明",
      colors: ["#f26a1b", "#1f6feb", "#b0450a"]
    },
    {
      key: "graphite", label: "灰黑", desc: "深色界面，夜间护眼",
      colors: ["#8d99a8", "#3a424c", "#14171c"]
    }
  ];

  var KEYS = THEMES.map(function (t) { return t.key; });

  function isDark(key) { return key === "graphite"; }

  function read() {
    try {
      var k = global.localStorage.getItem(STORAGE_KEY);
      return KEYS.indexOf(k) >= 0 ? k : DEFAULT_KEY;
    } catch (e) {
      return DEFAULT_KEY;
    }
  }

  function apply(key) {
    if (KEYS.indexOf(key) < 0) key = DEFAULT_KEY;
    var el = document.documentElement;
    el.setAttribute("data-theme", key);
    el.style.colorScheme = isDark(key) ? "dark" : "light";
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      var t = byKey(key);
      meta.setAttribute("content", t.colors[0]);
    }
    try { global.localStorage.setItem(STORAGE_KEY, key); } catch (e) { /* 隐私模式忽略 */ }
    try {
      global.dispatchEvent(new CustomEvent("fwb:theme", { detail: { key: key } }));
    } catch (e) { /* 老浏览器忽略 */ }
    return key;
  }

  function byKey(key) {
    for (var i = 0; i < THEMES.length; i++) if (THEMES[i].key === key) return THEMES[i];
    return THEMES[0];
  }

  function current() { return read(); }

  FWB.theme = {
    list: THEMES,
    keys: KEYS,
    DEFAULT: DEFAULT_KEY,
    byKey: byKey,
    isDark: isDark,
    apply: apply,
    current: current,
    toast: function (key) { return "已切换为「" + byKey(key).label + "」配色"; }
  };

  /* 立即应用（首屏前），避免主题闪烁 */
  apply(read());
})(window);
