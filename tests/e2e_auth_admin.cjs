/* =====================================================================
   e2e_auth_admin.cjs —— 登录 / 注册 / 角色分流 / 管理端 浏览器验收
   运行：node tests/e2e_auth_admin.cjs [baseUrl]
   ===================================================================== */
const { createRequire } = require("node:module");
const path = require("node:path");
const req = createRequire(__filename);
const { chromium } = req("C:/Users/norbert/.workbuddy/binaries/node/workspace/node_modules/playwright");

const CHROME = "C:/Users/norbert/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe";
const BASE = process.argv[2] || "http://127.0.0.1:5173";
const SHOT_DIR = path.resolve(__dirname, "..", "docs", "screenshots");

const STAMP = Date.now().toString().slice(-6);
const NEW_TEACHER = "e2e_t" + STAMP;
const REG_TEACHER = "e2e_r" + STAMP;

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

  const shot = async (name, full) => {
    await page.screenshot({ path: path.join(SHOT_DIR, name + ".png"), fullPage: !!full });
  };
  const field = sel => page.locator(".modal-mask.show " + sel);

  /* ---------------- 1. 未登录 → 登录页 ---------------- */
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForSelector(".login-page", { timeout: 15000 });
  check(true, "未登录时展示登录页");
  check((await page.locator(".login-card").count()) === 1, "登录卡片渲染");
  check((await page.locator(".lc-demo-row").count()) === 2, "提供两个演示账号快捷入口");
  check((await page.locator(".app").count()) === 0, "未登录时不渲染工作台");
  await shot("11-login");

  /* ---------------- 2. 未登录访问受保护资源 ---------------- */
  const anonState = await page.evaluate(async () => {
    const r = await fetch("/api/state");
    return r.status;
  });
  check(anonState === 401, "未登录调用 /api/state 返回 401", "实际 " + anonState);

  /* ---------------- 3. 教师登录 → 工作台 ---------------- */
  await page.locator(".lc-form input").nth(0).fill("jiangxl");
  await page.locator(".lc-form input").nth(1).fill("123456");
  await page.locator(".lc-submit").click();
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });
  await page.waitForSelector(".brand-title", { timeout: 8000 });
  const brand = (await page.locator(".brand-title").innerText()).trim();
  check(brand === "NBUSAI教师工作台", "教师端品牌文案正确", brand);
  const navN = await page.locator(".sidebar .nav-item").count();
  check(navN === 14, "教师端 14 项导航", "实际 " + navN);
  check((await page.locator(".user-card .icon-btn[title='退出登录']").count()) === 1, "教师端提供退出入口");
  const teacherName = (await page.locator(".user-name").innerText()).trim();
  check(teacherName.indexOf("江老师") === 0, "侧边栏显示登录教师", teacherName);
  check((await page.locator(".stat-grid .stat-card").count()) === 4, "工作首页统计卡正常");

  /* 教师越权 */
  const forbidden = await page.evaluate(async () => {
    const r = await fetch("/api/admin/overview");
    return r.status;
  });
  check(forbidden === 403, "教师访问管理端接口被拒（403）", "实际 " + forbidden);

  /* 教师端功能仍可用：搜索 */
  await page.fill(".search-box input", "雷达");
  await page.press(".search-box input", "Enter");
  await page.waitForTimeout(700);
  check((await page.locator(".modal-mask.show").count()) > 0, "教师端全局搜索仍可用");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);

  /* ---------------- 4. 登出 ---------------- */
  await page.locator(".user-card .icon-btn[title='退出登录']").click();
  await page.waitForSelector(".login-page", { timeout: 8000 });
  check(true, "退出登录回到登录页");

  /* ---------------- 5. 管理员登录 → 管理端 ---------------- */
  await page.locator(".lc-demo-row").first().click();   // 填充 admin
  const filledUser = await page.locator(".lc-form input").nth(0).inputValue();
  check(filledUser === "admin", "演示账号一键填充", filledUser);
  await page.locator(".lc-submit").click();
  /* 等待概览数据真正加载完成（统计卡与对比表随 adminTotals 一起渲染） */
  await page.waitForSelector(".stat-grid .stat-card", { timeout: 15000 });
  await page.waitForFunction(
    () => document.querySelectorAll(".admin-table tbody tr.clickable").length > 0,
    { timeout: 15000 }
  );
  const adminBrand = (await page.locator(".brand-title").innerText()).trim();
  check(adminBrand === "NBUSAI管理中心", "管理员端品牌文案正确", adminBrand);
  check((await page.locator(".sidebar .nav-item").count()) === 3, "管理端 3 项导航");
  check((await page.locator(".stat-grid .stat-card").count()) === 8, "管理端概览 8 张统计卡");
  const rowN = await page.locator(".admin-table tbody tr.clickable").count();
  check(rowN === 5, "概览对比表 5 位教师", "实际 " + rowN);
  const overviewText = await page.locator(".content").innerText();
  check(overviewText.indexOf("在册教师") >= 0, "概览含在册教师指标");
  check((await page.locator(".user-role").first().innerText()).trim() === "系统管理员", "管理端显示管理员身份");
  await shot("12-admin-overview", true);

  /* ---------------- 6. 教师管理列表 ---------------- */
  await page.locator(".nav-item", { hasText: "教师管理" }).first().click();
  await page.waitForSelector(".tcard", { timeout: 8000 });
  const cardN = await page.locator(".tcard").count();
  check(cardN === 5, "教师管理 5 张卡片", "实际 " + cardN);
  const cardText = await page.locator(".tcard").first().innerText();
  check(cardText.indexOf("项目") >= 0 && cardText.indexOf("学时") >= 0, "教师卡片含简要统计");
  await shot("13-admin-teachers", true);

  /* ---------------- 7. 教师统计详情 ---------------- */
  await page.locator(".tcard").first().locator("button", { hasText: "统计详情" }).click();
  await page.waitForSelector(".tprofile", { timeout: 8000 });
  await page.waitForSelector(".sec-card .kpi-row .kpi", { timeout: 8000 });
  const heroName = (await page.locator(".tp-name b").innerText()).trim();
  check(heroName.length > 0, "教师详情头部渲染", heroName);
  const heads = await page.locator(".sec-title h3").allInnerTexts();
  const joined = heads.join("|");
  check(joined.indexOf("科研成果") >= 0, "含科研成果统计区块");
  check(joined.indexOf("学术交流") >= 0, "含学术交流统计区块");
  check(joined.indexOf("教学情况") >= 0, "含教学情况统计区块");
  check(joined.indexOf("学生指导") >= 0, "含学生指导统计区块");
  const secCards = await page.locator(".sec-card").count();
  check(secCards === 4, "四类统计各有一张区块卡", "实际 " + secCards);
  const kpiCards = await page.locator(".sec-card .kpi-row .kpi").count();
  check(kpiCards >= 12, "四类统计指标卡已渲染", "实际 " + kpiCards);
  const distRows = await page.locator(".bar-track").count();
  check(distRows > 6, "分布条形图已渲染", "实际 " + distRows);
  check((await page.locator(".sec-nav .sec-tab").count()) === 4, "区块导航 4 个锚点");
  const projRows = await page.locator(".admin-table").first().locator("tbody tr").count();
  check(projRows > 0, "项目清单有数据", "实际 " + projRows);
  await shot("14-admin-teacher-detail", true);

  /* 返回列表 */
  await page.locator("button", { hasText: "返回教师列表" }).click();
  await page.waitForSelector(".tcard", { timeout: 8000 });
  check(true, "可从详情返回教师列表");

  /* ---------------- 8. 新建教师账号 ---------------- */
  await page.locator(".icon-btn[title='新建账号']").click();
  await page.waitForSelector(".modal-mask.show .modal", { timeout: 8000 });
  check((await page.locator(".modal-mask.show .modal-head h2").innerText()).trim() === "新建账号",
        "新建账号弹窗标题正确");
  await field("input[type=text]").nth(0).fill(NEW_TEACHER);
  await field("input[type=text]").nth(1).fill("测试教师");
  await field("input[type=password]").first().fill("test123456");
  await page.locator(".modal-mask.show .modal-foot .btn.primary").click();
  await page.waitForTimeout(1200);
  const afterCreate = await page.locator(".tcard").count();
  check(afterCreate === 6, "新建后列表出现 6 张卡片", "实际 " + afterCreate);
  const listText = await page.locator(".content").innerText();
  check(listText.indexOf("测试教师") >= 0, "新建教师出现在列表中");

  /* X 关闭回归 */
  await page.locator(".icon-btn[title='新建账号']").click();
  await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
  await page.locator(".modal-mask.show .modal-head button[data-close]").click();
  await page.waitForTimeout(300);
  check((await page.locator(".modal-mask.show").count()) === 0, "管理端弹窗 X 可关闭");

  /* ---------------- 9. 重置密码 / 停用 ---------------- */
  const card = page.locator(".tcard", { hasText: "测试教师" }).first();
  await card.locator("button", { hasText: "重置密码" }).click();
  await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
  await field("input[type=password]").nth(0).fill("reset98765");
  await field("input[type=password]").nth(1).fill("reset98765");
  await page.locator(".modal-mask.show .modal-foot .btn.primary").click();
  await page.waitForTimeout(1000);
  check((await page.locator(".modal-mask.show").count()) === 0, "重置密码提交成功");

  await card.locator("button", { hasText: "停用" }).click();
  await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  await page.waitForTimeout(1200);
  const cardText2 = await page.locator(".tcard", { hasText: "测试教师" }).first().innerText();
  check(cardText2.indexOf("已停用") >= 0, "停用后卡片标记为已停用");

  /* ---------------- 10. 教师搜索过滤 ---------------- */
  await page.fill(".search-box input", "测试教师");
  await page.waitForTimeout(400);
  check((await page.locator(".tcard").count()) === 1, "教师搜索过滤生效",
        "实际 " + (await page.locator(".tcard").count()));
  await page.fill(".search-box input", "");
  await page.waitForTimeout(400);

  /* ---------------- 11. 删除临时教师 ---------------- */
  const delLog = [];
  const onDelResp = r => {
    if (r.url().includes("/api/admin/")) {
      delLog.push(r.request().method() + " " + r.url().replace(BASE, "") + " -> " + r.status());
    }
  };
  page.on("response", onDelResp);
  await page.locator(".tcard", { hasText: "测试教师" }).first()
    .locator("button", { hasText: "删除" }).click();
  await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  /* 等待列表真正刷新（删除接口成功后 loadAdmin 重渲染） */
  await page.waitForFunction(
    () => {
      const cards = [...document.querySelectorAll(".tcard")];
      return cards.length === 5 && !cards.some(c => c.innerText.includes("测试教师"));
    },
    { timeout: 10000 }
  ).catch(() => {});
  page.off("response", onDelResp);
  const listText3 = await page.locator(".content").innerText();
  check(listText3.indexOf("测试教师") < 0, "删除后教师从列表移除",
        "cards=" + (await page.locator(".tcard").count()) + " api=[" + delLog.join(" ; ") + "]");
  check((await page.locator(".tcard").count()) === 5, "删除后回到 5 位教师",
        "实际 " + (await page.locator(".tcard").count()) + " api=[" + delLog.join(" ; ") + "]");

  /* ---------------- 12. 注册新教师 → 独立工作台 ---------------- */
  await page.locator(".user-card .icon-btn[title='退出登录']").click();
  await page.waitForSelector(".login-page", { timeout: 8000 });
  await page.locator(".lc-tabs button", { hasText: "注册" }).click();
  await page.waitForTimeout(300);
  const regInputs = page.locator(".lc-form input");
  await regInputs.nth(0).fill(REG_TEACHER);        // 用户名
  await regInputs.nth(1).fill("注册教师");          // 姓名
  await regInputs.nth(2).fill("讲师");
  await regInputs.nth(3).fill("人工智能学院");
  await regInputs.nth(4).fill("reg@university.edu.cn");
  await regInputs.nth(5).fill("信息楼 101");
  await regInputs.nth(6).fill("reg123456");
  await regInputs.nth(7).fill("reg123456");
  // 取消勾选「使用演示数据初始化」→ 空工作台
  const demoBox = page.locator(".lc-check input[type=checkbox]");
  if (await demoBox.isChecked()) await demoBox.uncheck();
  await page.locator(".lc-submit").click();
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });
  await page.waitForTimeout(800);
  const regName = (await page.locator(".user-name").innerText()).trim();
  check(regName.indexOf("注册教师") === 0, "注册后进入自己的工作台", regName);
  const regState = await page.evaluate(async () => {
    const r = await fetch("/api/state");
    const j = await r.json();
    return { projects: j.data.projects.length, tools: j.data.tools.length, name: j.data.profile.name };
  });
  check(regState.projects === 0, "新注册教师工作台为空（未使用演示数据）", "projects=" + regState.projects);
  check(regState.tools === 12, "新注册教师保留 12 项工具清单", "tools=" + regState.tools);
  check(regState.name === "注册教师", "新账号 profile 使用注册信息");
  const emptyText = await page.locator(".content").innerText();
  check(emptyText.length > 0, "空工作台首页正常渲染");
  await shot("15-workbench-new-teacher");

  /* ---------------- 13. 清理：管理员删除注册账号 ---------------- */
  await page.locator(".user-card .icon-btn[title='退出登录']").click();
  await page.waitForSelector(".login-page", { timeout: 8000 });
  await page.locator(".lc-demo-row").first().click();
  await page.locator(".lc-submit").click();
  await page.waitForSelector(".tcard, .admin-table", { timeout: 15000 });
  await page.locator(".nav-item", { hasText: "教师管理" }).first().click();
  await page.waitForSelector(".tcard", { timeout: 8000 });
  await page.locator(".tcard", { hasText: "注册教师" }).first()
    .locator("button", { hasText: "删除" }).click();
  await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  /* 等待列表真正刷新 */
  await page.waitForFunction(
    () => {
      const cards = [...document.querySelectorAll(".tcard")];
      return cards.length === 5 && !cards.some(c => c.innerText.includes("注册教师"));
    },
    { timeout: 10000 }
  ).catch(() => {});
  const finalList = await page.locator(".content").innerText();
  check(finalList.indexOf("注册教师") < 0, "测试账号已清理");
  check((await page.locator(".tcard").count()) === 5, "最终恢复 5 位种子教师",
        "实际 " + (await page.locator(".tcard").count()));

  /* ---------------- 14. 控制台 ---------------- */
  /* 过滤预期内的资源报错：未登录探测 401、教师越权探测 403 */
  const realErrors = consoleErrors.filter(
    t => !/status of 40[13]\s*\((UNAUTHORIZED|FORBIDDEN)\)/.test(t)
  );
  check(realErrors.length === 0, "浏览器控制台无报错",
        realErrors.slice(0, 3).join(" | "));

  console.log("\n通过 " + pass + " / " + (pass + fail) + " 项");
  if (failures.length) console.log("失败项：\n  - " + failures.join("\n  - "));
  console.log("截图目录：" + SHOT_DIR);
  await browser.close();
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error("E2E 异常：", e); process.exit(1); });
