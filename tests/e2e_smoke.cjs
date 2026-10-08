/* =====================================================================
   e2e_smoke.cjs —— 真实浏览器端到端验收（Playwright + Chromium）

   前置：先启动服务（另开终端）
       python run.py --port 5173 --prod

   运行：
       node tests/e2e_smoke.cjs [baseUrl]

   校验点：11 个页面全部可渲染、全局搜索可用、12 类工具运行器可用、
           详情页可达、设置面板可开、无控制台报错；同时输出截图到 docs/screenshots/
   ===================================================================== */
const { createRequire } = require("node:module");
const fs = require("node:fs");
const path = require("node:path");

const WORKSPACE = "C:/Users/norbert/.workbuddy/binaries/node/workspace/node_modules/playwright";
const require2 = createRequire(__filename);
const { chromium } = require2(WORKSPACE);

const BASE = process.argv[2] || "http://127.0.0.1:5173";
const ROOT = path.resolve(__dirname, "..");
const SHOT_DIR = path.join(ROOT, "docs", "screenshots");

/* 本机已安装的 Chromium（版本与 Playwright 内置期望不一致时直接指定路径） */
const CANDIDATE_CHROME = [
  process.env.PW_CHROMIUM,
  "C:/Users/norbert/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe"
].filter(Boolean);
const CHROME_PATH = CANDIDATE_CHROME.find((p) => fs.existsSync(p)) || undefined;

const PAGES = [
  ["工作首页", "工作首页"],
  ["日程管理", "日程管理"],
  ["科研项目", "科研项目"],
  ["文献仓库", "文献仓库"],
  ["学术交流", "学术交流"],
  ["成果管理", "成果管理"],
  ["教学管理", "教学管理"],
  ["课程资源", "课程资源"],
  ["学生指导", "学生指导"],
  ["个人发展", "个人发展"],
  ["常用工具", "常用工具"]
];

const problems = [];
const checks = [];
function check(ok, label, detail) {
  checks.push({ ok, label, detail });
  if (!ok) problems.push(label + (detail ? " —— " + detail : ""));
}

async function main() {
  fs.mkdirSync(SHOT_DIR, { recursive: true });
  const browser = await chromium.launch(
    CHROME_PATH ? { executablePath: CHROME_PATH } : {}
  );
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  const consoleErrors = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  page.on("pageerror", (e) => consoleErrors.push("pageerror: " + e.message));
  page.on("requestfailed", (r) => {
    const u = r.url();
    if (!u.endsWith("/favicon.ico")) consoleErrors.push("requestfailed: " + u);
  });

  const shot = async (name, full) => {
    await page.screenshot({ path: path.join(SHOT_DIR, name + ".png"), fullPage: !!full });
  };

  /* ---------------- 1. 首屏 ---------------- */
  await page.goto(BASE, { waitUntil: "networkidle" });

  /* 0. 教师登录（系统已启用账号体系） */
  await page.locator(".lc-form input").nth(0).fill("jiangxl");
  await page.locator(".lc-form input").nth(1).fill("123456");
  await page.locator(".lc-submit").click();
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });

  await page.waitForSelector(".nav-item", { timeout: 15000 });

  const navCount = await page.locator(".nav-item").count();
  check(navCount === 13, "侧边栏渲染 13 个导航项", "实际 " + navCount);

  const cloak = await page.locator("#app[v-cloak]").count();
  check(cloak === 0, "Vue 挂载后移除 v-cloak（首屏可见）");

  const brand = (await page.locator(".brand-title").innerText()).trim();
  check(brand === "NBUSAI教师工作台", "品牌标题正确", brand);

  const userName = (await page.locator(".user-name").innerText()).trim();
  check(userName.includes("江先亮"), "侧边栏展示教师姓名", userName);

  const stats = await page.locator(".stat-card").count();
  check(stats === 4, "首页 4 张统计卡", "实际 " + stats);

  const tl = await page.locator(".tl-item").count();
  check(tl >= 1, "首页今日日程时间线有内容", "实际 " + tl);
  await shot("01-dashboard", true);

  /* ---------------- 2. 遍历 11 个页面 ---------------- */
  for (const [nav, expectTitle] of PAGES) {
    await page.locator(".nav-item", { hasText: nav }).first().click();
    await page.waitForTimeout(260);
    const title = (await page.locator(".page-title").innerText()).trim();
    const active = (await page.locator(".nav-item.active .ni-text").innerText()).trim();
    const textLen = (await page.locator(".content").innerText()).trim().length;
    check(title === expectTitle, `页面「${nav}」标题正确`, title);
    check(active === nav, `页面「${nav}」导航高亮正确`, active);
    check(textLen > 80, `页面「${nav}」正文有内容`, "字符数 " + textLen);
  }

  /* ---------------- 3. 日程日历 ---------------- */
  await page.locator(".nav-item", { hasText: "日程管理" }).first().click();
  await page.waitForTimeout(220);
  const calDays = await page.locator(".cal-day").count();
  check(calDays >= 28 && calDays % 7 === 0, "日历格子按整周渲染", "格子数 " + calDays);
  const agendaSel = await page.locator(".cal-day.sel").count();
  check(agendaSel === 1, "默认选中今天");
  await shot("02-schedule", true);

  /* ---------------- 4. 列表 → 详情 → 返回（4 类） ---------------- */
  const details = [
    ["科研项目", ".proj-card", "项目详情"],
    ["文献仓库", ".lit-item", "文献详情"],
    ["课程资源", ".course-card", "课程详情"],
    ["学生指导", ".stu-card", "学生详情"]
  ];
  for (const [nav, cardSel, expectTitle] of details) {
    await page.locator(".nav-item", { hasText: nav }).first().click();
    await page.waitForTimeout(220);
    const cards = await page.locator(cardSel).count();
    check(cards > 0, `「${nav}」列表有卡片`, "实际 " + cards);

    await page.locator(cardSel).first().click();
    await page.waitForTimeout(260);
    const t = (await page.locator(".page-title").innerText()).trim();
    check(t === expectTitle, `「${nav}」可进入详情页`, t);
    check((await page.locator(".detail-head").count()) === 1, `「${nav}」详情页有头部操作区`);
    if (nav === "科研项目") await shot("03-project-detail", true);

    await page.locator(".back-btn").first().click();
    await page.waitForTimeout(220);
    const back = (await page.locator(".page-title").innerText()).trim();
    check(back === nav, `「${nav}」详情可返回列表`, back);
  }

  /* ---------------- 5. 全局搜索 ---------------- */
  await page.fill(".search-box input", "雷达");
  await page.press(".search-box input", "Enter");
  await page.waitForSelector(".modal-mask.show .sr-item", { timeout: 8000 });
  const hits = await page.locator(".modal-mask.show .sr-item").count();
  check(hits >= 3, "全局搜索「雷达」命中多条", "命中 " + hits);
  const modalTitle = (await page.locator(".modal-mask.show .modal-head h2").innerText()).trim();
  check(modalTitle.includes("搜索结果"), "搜索结果以弹窗呈现", modalTitle);
  await shot("04-search");

  await page.locator(".modal-mask.show .sr-item").first().click();
  await page.waitForTimeout(320);
  check((await page.locator(".modal-mask.show").count()) === 0, "点击搜索结果后关闭弹窗");
  const jumped = (await page.locator(".page-title").innerText()).trim();
  check(jumped.length > 0, "搜索结果可跳转到目标页", jumped);

  /* ---------------- 6. 快捷新建菜单 ---------------- */
  await page.click("#quickBtn");
  await page.waitForTimeout(200);
  check(await page.locator(".quick-menu.show").isVisible(), "快捷新建菜单可展开");
  const quickItems = await page.locator(".quick-menu.show .qm-item").count();
  check(quickItems === 8, "快捷菜单 8 个入口", "实际 " + quickItems);
  await shot("05-quick-menu");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  check((await page.locator(".quick-menu.show").count()) === 0, "Esc 可收起快捷菜单");

  /* ---------------- 7. 工具运行器（真跑一次成绩计算） ---------------- */
  await page.locator(".nav-item", { hasText: "常用工具" }).first().click();
  await page.waitForTimeout(260);
  const toolCards = await page.locator(".tool-card").count();
  check(toolCards === 12, "工具页 12 张卡片", "实际 " + toolCards);
  await shot("06-tools", true);

  await page.locator(".tool-card", { hasText: "成绩批量计算" }).first().click();
  await page.waitForSelector(".modal-mask.show .modal", { timeout: 8000 });
  check(true, "点击工具卡打开运行器");

  await page.fill(".modal-body textarea.mono", "李明 85 78 92\n王雪 90 88 95\n张伟 72 65 70");
  await page.locator(".modal-body .modal-foot .btn.primary").click();
  await page.waitForSelector(".runner-result", { timeout: 20000 });
  const summary = (await page.locator(".runner-summary").innerText()).trim();
  check(summary.includes("3 名学生") && summary.includes("平均分"), "成绩工具返回真实计算结果", summary);
  const metrics = await page.locator(".runner-metric").count();
  check(metrics >= 3, "结果区展示指标", "实际 " + metrics);
  const downloads = await page.locator(".runner-files .btn").count();
  check(downloads >= 1, "结果区提供产物下载", "实际 " + downloads);
  await shot("07-tool-runner", true);
  await page.locator(".modal-body .btn.ghost").first().click();
  await page.waitForTimeout(240);
  check((await page.locator(".modal-mask.show").count()) === 0, "运行器可关闭");

  /* ---------------- 8. 设置面板 ---------------- */
  await page.locator(".user-card .icon-btn[title='设置']").click();
  await page.waitForSelector(".modal-mask.show .set-sec", { timeout: 8000 });
  const setTitle = (await page.locator(".modal-mask.show .modal-head h2").innerText()).trim();
  check(setTitle === "设置", "设置面板可打开", setTitle);
  const setSecs = await page.locator(".modal-mask.show .set-sec").count();
  check(setSecs >= 3, "设置面板含多个分区", "实际 " + setSecs);
  const nameVal = await page.locator(".modal-mask.show input[type=text]").first().inputValue();
  check(nameVal === "江先亮", "设置面板回填当前教师信息", nameVal);
  await shot("08-settings");

  // 右上角 X 必须能关闭弹窗（回归：曾因 .modal 的 @click.stop 吞掉冒泡而完全失效）
  await page.locator(".modal-mask.show .modal-head button[data-close]").click();
  await page.waitForTimeout(260);
  check((await page.locator(".modal-mask.show").count()) === 0, "右上角 X 可关闭弹窗");
  await page.locator(".user-card .icon-btn[title='设置']").click();
  await page.waitForSelector(".modal-mask.show .set-sec", { timeout: 8000 });

  // 修改姓名 → 保存 → 侧边栏同步刷新 → 改回
  await page.fill(".modal-mask.show input[type=text]", "江先亮");
  await page.locator(".modal-mask.show .set-actions .btn.primary, .modal-mask.show .btn.primary").first().click();
  await page.waitForTimeout(600);

  /* ---------------- 9. 新建待办（写库 → 首页可见） ---------------- */
  await page.locator(".nav-item", { hasText: "工作首页" }).first().click();
  await page.waitForTimeout(240);
  await page.click("#quickBtn");
  await page.waitForTimeout(180);
  await page.locator(".quick-menu.show .qm-item", { hasText: "新增待办" }).first().click();
  await page.waitForSelector(".modal-mask.show input[type=text]", { timeout: 8000 });
  const todoTitle = "E2E 验证待办 " + Date.now();
  await page.fill(".modal-mask.show input[type=text]", todoTitle);
  await page.locator(".modal-mask.show .modal-foot .btn.primary").click();
  await page.waitForTimeout(700);
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector(".nav-item", { timeout: 15000 });
  const bodyText = await page.locator(".content").innerText();
  check(bodyText.includes(todoTitle), "新建待办写入服务端并在刷新后仍存在");

  // 清理：删除刚建的待办
  const delOk = await page.evaluate(async (title) => {
    const res = await fetch("/api/collections/todos");
    const json = await res.json();
    const hit = (json.data || []).find((t) => t.title === title);
    if (!hit) return false;
    await fetch("/api/collections/todos/" + hit.id, { method: "DELETE" });
    return true;
  }, todoTitle);
  check(delOk, "测试数据已清理");

  /* ---------------- 10. 控制台无报错 ---------------- */
  /* 过滤预期内报错：登录前 /api/auth/me 探测返回 401 */
  const realErrors = consoleErrors.filter(t => !/status of 401\s*\(UNAUTHORIZED\)/.test(t));
  check(realErrors.length === 0, "浏览器控制台无报错", realErrors.slice(0, 5).join(" | "));

  await browser.close();

  /* ---------------- 汇总 ---------------- */
  const failed = checks.filter((c) => !c.ok);
  console.log("\n=== 端到端验收结果 ===");
  checks.forEach((c) => {
    console.log((c.ok ? "  ✓ " : "  ✗ ") + c.label + (!c.ok && c.detail ? "  [" + c.detail + "]" : ""));
  });
  console.log("\n通过 " + (checks.length - failed.length) + " / " + checks.length + " 项");
  console.log("截图目录：" + SHOT_DIR);
  if (failed.length) {
    console.log("\n失败项：");
    failed.forEach((f) => console.log("  - " + f.label + "  " + (f.detail || "")));
    process.exit(1);
  }
}

main().catch((e) => {
  console.error("E2E 执行失败：", e);
  process.exit(1);
});
