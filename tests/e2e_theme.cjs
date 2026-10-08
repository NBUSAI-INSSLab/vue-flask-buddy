/* =====================================================================
   e2e_theme.cjs —— 配色主题 + 登录页改版 浏览器验收
   运行：node tests/e2e_theme.cjs [baseUrl]
   ===================================================================== */
const { createRequire } = require("node:module");
const path = require("node:path");
const req = createRequire(__filename);
const { chromium } = req("C:/Users/norbert/.workbuddy/binaries/node/workspace/node_modules/playwright");

const CHROME = "C:/Users/norbert/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe";
const BASE = process.argv[2] || "http://127.0.0.1:5173";
const SHOT_DIR = path.resolve(__dirname, "..", "docs", "screenshots");

const THEMES = ["mint", "orange", "blue", "orangeblue", "graphite"];
const LABELS = { mint: "薄荷绿", orange: "橙色", blue: "蓝色", orangeblue: "橙蓝", graphite: "灰黑" };

let pass = 0, fail = 0;
const failures = [];
function check(cond, name, extra) {
  if (cond) { pass++; console.log("  \u2713 " + name); }
  else { fail++; failures.push(name + (extra ? "  [" + extra + "]" : "")); console.log("  \u2717 " + name + (extra ? "  \u2192 " + extra : "")); }
}

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 940 } });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on("console", m => { if (m.type() === "error") consoleErrors.push(m.text()); });
  page.on("pageerror", e => consoleErrors.push("pageerror: " + e.message));

  const shot = async (name, full) => page.screenshot({ path: path.join(SHOT_DIR, name + ".png"), fullPage: !!full });
  const attr = () => page.evaluate(() => document.documentElement.getAttribute("data-theme"));
  const primary = () => page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--primary").trim());
  const bg = () => page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--bg").trim());

  /* ---------------- 1. 登录页（新 UI） ---------------- */
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForSelector(".login-page", { timeout: 15000 });
  check((await page.locator(".login-page").count()) === 1, "登录页渲染");
  check((await page.locator(".login-shell").count()) === 1, "登录页采用统一外壳布局（不再左右割裂）");
  check((await page.locator(".login-bg .lb-orb").count()) === 3, "背景含主题色光晕装饰");
  check((await page.locator(".li-headline em").count()) === 1, "左侧标题含主题色强调词");
  check((await page.locator(".li-feats li").count()) === 4, "左侧 4 项能力卡片");
  check((await page.locator(".login-card").count()) === 1, "登录卡片渲染");
  check((await page.locator(".lc-top .brand-mark").count()) === 1, "卡片头部含品牌标识");
  check((await page.locator(".lc-hint").count()) === 1, "登录表单含副提示文案");
  check((await page.locator(".lc-form input").count()) === 2, "登录表单 2 个输入框");
  await shot("16-login-mint");

  /* 输入框：前置图标 + 统一外观；按钮：文字居中 */
  check((await page.locator(".lc-input").count()) === 2, "登录输入框包在统一容器内");
  check((await page.locator(".lc-input > svg").count()) === 2, "输入框含前置图标");
  const inputBox = await page.locator(".lc-input input").first().evaluate(el => {
    const cs = getComputedStyle(el);
    return { h: Math.round(el.getBoundingClientRect().height), r: cs.borderRadius, pl: parseInt(cs.paddingLeft) };
  });
  check(inputBox.h >= 44 && inputBox.pl >= 36, "输入框高度与左内边距达标（为图标留白）", JSON.stringify(inputBox));
  const btnAlign = await page.locator(".lc-submit").evaluate(el => getComputedStyle(el).justifyContent);
  check(btnAlign === "center", "登录按钮文字居中", btnAlign);
  check((await page.locator(".lc-submit svg").count()) === 1, "登录按钮含右侧箭头图标");

  /* 密码可见性切换 */
  check((await page.locator(".lc-eye").count()) === 1, "密码框提供显示 / 隐藏切换");
  check((await page.locator(".lc-input.pwd input").getAttribute("type")) === "password", "密码默认掩码显示");
  await page.locator(".lc-eye").click();
  await page.waitForTimeout(120);
  check((await page.locator(".lc-input.pwd input").getAttribute("type")) === "text", "点击后明文显示密码");
  await page.locator(".lc-eye").click();
  await page.waitForTimeout(120);
  check((await page.locator(".lc-input.pwd input").getAttribute("type")) === "password", "再次点击恢复掩码");

  /* 注册态表单同样走统一输入样式 */
  await page.locator(".lc-tabs button", { hasText: "注册" }).click();
  await page.waitForTimeout(250);
  check((await page.locator(".lc-form input").count()) === 9, "注册表单 8 个输入框 + 1 个复选框");
  check((await page.locator(".lc-input").count()) === 8, "注册 8 个字段均带图标容器");
  check((await page.locator(".lc-eye").count()) === 2, "注册两个密码框均可切换可见性");
  const regBtnAlign = await page.locator(".lc-submit").evaluate(el => getComputedStyle(el).justifyContent);
  check(regBtnAlign === "center", "「注册并进入」按钮文字居中", regBtnAlign);
  await shot("16b-login-register");
  await page.locator(".lc-tabs button", { hasText: "登录" }).click();
  await page.waitForTimeout(250);

  /* ---------------- 2. 登录页即可切换配色 ---------------- */
  check((await page.locator(".lc-theme .theme-dot").count()) === 5, "登录卡片提供 5 套配色入口");
  check((await page.locator(".lc-theme .theme-name").count()) === 5, "配色名称完整展示");
  check((await page.locator(".lc-theme .theme-name", { hasText: "灰色" }).count()) === 0, "灰色配色已移除");
  check((await attr()) === "mint", "默认配色为薄荷绿", await attr());

  const mintPrimary = await primary();
  await page.locator(".lc-theme .theme-cell", { hasText: "橙色" }).locator(".theme-dot").click();
  await page.waitForTimeout(250);
  const orangePrimary = await primary();
  check((await attr()) === "orange", "点击后切换到橙色主题", await attr());
  check(orangePrimary !== mintPrimary, "主色变量随主题变化", mintPrimary + " → " + orangePrimary);
  check((await page.locator(".lc-theme-title span").innerText()).trim() === "橙色", "卡片显示当前配色名");
  check((await page.locator(".toast").count()) >= 1, "切换配色有提示反馈");
  await shot("17-login-orange");

  /* 选择持久化 */
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector(".login-page", { timeout: 15000 });
  check((await attr()) === "orange", "刷新后保持上次选择（localStorage 持久化）", await attr());

  /* ---------------- 3. 教师工作台逐套配色 ---------------- */
  await page.locator(".lc-form input").nth(0).fill("jiangxl");
  await page.locator(".lc-form input").nth(1).fill("123456");
  await page.locator(".lc-submit").click();
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });
  check(true, "教师登录进入工作台");
  check((await attr()) === "orange", "进入工作台后主题保持");

  const seen = {};
  for (const key of THEMES) {
    await page.locator(".icon-btn[title='界面配色']").click();
    await page.waitForSelector(".modal-mask.show .theme-dots", { timeout: 8000 });
    await page.locator(".modal-mask.show .theme-cell", { hasText: LABELS[key] }).locator(".theme-dot").click();
    await page.waitForTimeout(320);
    const cur = await primary();
    seen[key] = cur;
    check((await attr()) === key, `工作台切换到「${LABELS[key]}」`, await attr());
    await page.locator(".modal-mask.show .modal-foot .btn.primary").click();
    await page.waitForTimeout(200);
    await shot("18-theme-dash-" + key);
  }
  const uniq = new Set(Object.values(seen));
  check(uniq.size === 5, "5 套配色主色互不相同", JSON.stringify(seen));

  /* 深色主题的对比度：正文色应明显亮于背景 */
  await page.locator(".icon-btn[title='界面配色']").click();
  await page.waitForSelector(".modal-mask.show .theme-dots", { timeout: 8000 });
  await page.locator(".modal-mask.show .theme-cell", { hasText: "灰黑" }).locator(".theme-dot").click();
  await page.waitForTimeout(320);
  await page.locator(".modal-mask.show .modal-foot .btn.primary").click();
  const dark = await page.evaluate(() => {
    const cs = getComputedStyle(document.documentElement);
    const lum = (hex) => {
      const m = hex.match(/[0-9a-f]{2}/gi) || [];
      const [r, g, b] = m.map(x => parseInt(x, 16) / 255).map(v => (v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4)));
      return .2126 * r + .7152 * g + .0722 * b;
    };
    const bgv = cs.getPropertyValue("--bg").trim();
    const txv = cs.getPropertyValue("--text").trim();
    return { bgv, txv, ratio: (lum(txv) + .05) / (lum(bgv) + .05) };
  });
  check(dark.ratio > 7, "灰黑主题正文与背景对比度充足", "ratio=" + dark.ratio.toFixed(1));
  check((await bg()).indexOf("#14") === 0, "灰黑主题为深色背景", dark.bgv);
  await shot("19-theme-dark-kiosk");
  /* 深色下正文可读性：抽样卡片文字颜色 */
  const darkText = await page.evaluate(() => {
    const el = document.querySelector(".stat-val") || document.querySelector(".page-title");
    return el ? getComputedStyle(el).color : "";
  });
  check(/rgb\((2[0-9]{2}|1[5-9][0-9])/.test(darkText), "深色主题下标题文字为浅色", darkText);

  /* 浏览若干页面确认无「白底黑字残留」 */
  for (const nav of ["科研项目", "教学管理", "学生指导", "常用工具"]) {
    await page.locator(".nav-item", { hasText: nav }).first().click();
    await page.waitForTimeout(200);
  }
  await shot("20-theme-dark-tools", true);

  /* 恢复默认，便于后续截图与人工查看 */
  await page.locator(".icon-btn[title='界面配色']").click();
  await page.waitForSelector(".modal-mask.show .theme-dots", { timeout: 8000 });
  await page.locator(".modal-mask.show .theme-cell", { hasText: "薄荷绿" }).locator(".theme-dot").click();
  await page.waitForTimeout(250);
  await page.locator(".modal-mask.show .modal-foot .btn.primary").click();
  await shot("21-theme-back-mint", true);

  /* ---------------- 4. 设置面板内嵌配色 ---------------- */
  await page.locator(".user-card .icon-btn[title='设置']").click();
  await page.waitForSelector(".modal-mask.show .set-sec", { timeout: 8000 });
  const secs = await page.locator(".modal-mask.show .set-sec h4").allInnerTexts();
  check(secs.join("|").indexOf("界面配色") >= 0, "设置面板含「界面配色」分区", secs.join("|"));
  check((await page.locator(".modal-mask.show .theme-dot").count()) === 5, "设置面板内嵌 5 套配色");
  await shot("22-settings-theme");
  await page.locator(".modal-mask.show .modal-head button[data-close]").click();
  await page.waitForTimeout(250);

  /* ---------------- 5. 管理端也可切换配色 ---------------- */
  await page.locator(".user-card .icon-btn[title='退出登录']").click();
  await page.waitForSelector(".login-page", { timeout: 8000 });
  await page.locator(".lc-demo-row").first().click();
  await page.locator(".lc-submit").click();
  await page.waitForSelector(".stat-grid .stat-card", { timeout: 15000 });
  check(true, "管理员进入管理中心");
  await page.locator(".icon-btn[title='界面配色']").click();
  await page.waitForSelector(".modal-mask.show .theme-dots", { timeout: 8000 });
  await page.locator(".modal-mask.show .theme-cell", { hasText: "蓝色" }).locator(".theme-dot").click();
  await page.waitForTimeout(300);
  check((await attr()) === "blue", "管理端可切换配色", await attr());
  await page.locator(".modal-mask.show .modal-foot .btn.primary").click();
  await page.waitForTimeout(200);
  await shot("23-admin-blue", true);

  /* 管理端深色主题 */
  await page.locator(".icon-btn[title='界面配色']").click();
  await page.waitForSelector(".modal-mask.show .theme-dots", { timeout: 8000 });
  await page.locator(".modal-mask.show .theme-cell", { hasText: "灰黑" }).locator(".theme-dot").click();
  await page.waitForTimeout(300);
  await page.locator(".modal-mask.show .modal-foot .btn.primary").click();
  await page.waitForTimeout(200);
  await shot("24-admin-dark", true);
  check((await attr()) === "graphite", "管理端深色主题生效");

  /* ---------------- 6. 控制台 ---------------- */
  const realErrors = consoleErrors.filter(t => !/status of 40[13]\s*\((UNAUTHORIZED|FORBIDDEN)\)/.test(t));
  check(realErrors.length === 0, "浏览器控制台无报错", realErrors.slice(0, 3).join(" | "));

  console.log("\n通过 " + pass + " / " + (pass + fail) + " 项");
  if (failures.length) console.log("失败项：\n  - " + failures.join("\n  - "));
  console.log("截图目录：" + SHOT_DIR);
  await browser.close();
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error("E2E 异常：", e); process.exit(1); });
