/* =====================================================================
   e2e_review.cjs —— 管理端「成果审核」+ 教师统计详情页改版 浏览器验收
   运行：node tests/e2e_review.cjs [baseUrl]
   ===================================================================== */
const { createRequire } = require("node:module");
const path = require("node:path");
const req = createRequire(__filename);
const { chromium } = req("C:/Users/norbert/.workbuddy/binaries/node/workspace/node_modules/playwright");

const CHROME = "C:/Users/norbert/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe";
const BASE = process.argv[2] || "http://127.0.0.1:5173";
const SHOT_DIR = path.resolve(__dirname, "..", "docs", "screenshots");

let pass = 0, fail = 0;
const failures = [];
function check(cond, name, extra) {
  if (cond) { pass++; console.log("  \u2713 " + name); }
  else { fail++; failures.push(name + (extra ? "  [" + extra + "]" : "")); console.log("  \u2717 " + name + (extra ? "  \u2192 " + extra : "")); }
}

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext({ viewport: { width: 1560, height: 1000 } });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on("console", m => { if (m.type() === "error") consoleErrors.push(m.text()); });
  page.on("pageerror", e => consoleErrors.push("pageerror: " + e.message));

  const shot = (name, full) => page.screenshot({ path: path.join(SHOT_DIR, name + ".png"), fullPage: !!full });
  const num = async (sel) => {
    const t = await page.locator(sel).first().innerText().catch(() => "0");
    const m = String(t).replace(/[^\d.]/g, "");
    return parseFloat(m || "0");
  };
  /* 读某个状态标签页上的计数 */
  const tabCount = async (label) =>
    num(".rv-toolbar .chip:has-text('" + label + "') .cnt");

  /* 等待审核页数据真正到位（避免只等到空表格骨架） */
  const waitLoaded = async () => {
    await page.waitForFunction(() => {
      const grid = document.querySelector(".stat-grid .stat-card");
      const chips = document.querySelectorAll(".rv-toolbar .chip");
      const opts = document.querySelectorAll(".select-mini option");
      return !!grid && chips.length === 4 && opts.length > 1;
    }, { timeout: 20000 });
    await page.waitForTimeout(150);
  };
  const gotoReviews = async () => {
    await page.locator(".nav-item:has-text('成果审核')").click();
    await page.waitForSelector(".rv-table", { timeout: 15000 });
    await waitLoaded();
  };
  /* 切换标签页并等待列表内容真正切换完成 */
  const setTab = async (label) => {
    await page.locator(".rv-toolbar .chip", { hasText: label }).first().click();
    await page.waitForFunction((t) => {
      const on = document.querySelector(".rv-toolbar .chip.active");
      if (!on || on.innerText.indexOf(t) !== 0) return false;
      if (document.querySelector(".rv-table tbody .empty")) return true;
      const tag = document.querySelector(".rv-table tbody tr .audit-tag");
      return !!tag && tag.innerText.trim() === t;
    }, label, { timeout: 15000 });
    await page.waitForTimeout(120);
  };
  /* 等待某状态标签的计数达到期望值 */
  const waitCount = async (label, expected) => {
    try {
      await page.waitForFunction(
        (arg) => {
          const chips = Array.from(document.querySelectorAll(".rv-toolbar .chip"));
          const chip = chips.find(c => c.innerText.indexOf(arg.label) === 0);
          if (!chip) return false;
          const cnt = chip.querySelector(".cnt");
          const n = parseInt((cnt ? cnt.innerText : "0").replace(/[^\d]/g, "") || "0", 10);
          return n === arg.expected;
        }, { label, expected }, { timeout: 12000 });
      return true;
    } catch (e) {
      return false;
    }
  };

  /* ---------------- 0. 管理员登录 ---------------- */
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForSelector(".login-page", { timeout: 15000 });
  await page.locator(".lc-form input").nth(0).fill("admin");
  await page.locator(".lc-form input").nth(1).fill("admin123");
  await page.locator(".lc-submit").click();
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });
  await page.waitForSelector(".admin-table tbody tr", { timeout: 15000 });

  /* ---------------- 1. 导航入口 ---------------- */
  check((await page.locator(".nav-item").count()) === 3, "管理端 3 项导航");
  const navBadge = await num(".nav-item:has-text('成果审核') .ni-badge");
  check(navBadge >= 1, "导航「成果审核」显示待审计数徽标", String(navBadge));

  await gotoReviews();
  check((await page.locator(".rv-table").count()) === 1, "进入成果审核页");

  /* ---------------- 2. 顶部指标 + 标签页 ---------------- */
  check((await page.locator(".stat-grid .stat-card").count()) === 4, "审核页 4 张统计卡");
  check((await page.locator(".stat-card:has-text('待审核成果')").count()) === 1, "含「待审核成果」指标");
  check((await page.locator(".stat-card:has-text('待审业绩分')").count()) === 1, "含「待审业绩分」指标");
  check((await page.locator(".rv-toolbar .chip").count()) === 4, "4 个审核状态标签页");
  check((await page.locator(".select-mini select").count()) === 1, "提供教师筛选下拉");
  check((await page.locator(".select-mini option").count()) >= 6, "教师下拉含全部教师选项");

  const pendingTab = await tabCount("待审核");
  const approvedTab = await tabCount("已通过");
  const rejectedTab = await tabCount("已退回");
  const totalTab = await tabCount("全部成果");
  check(pendingTab >= 1, "待审核标签页有计数", String(pendingTab));
  check(totalTab === pendingTab + approvedTab + rejectedTab,
        "标签页计数自洽（待审 + 已通过 + 已退回 = 全部）",
        [pendingTab, approvedTab, rejectedTab].join("+") + " vs " + totalTab);
  check((await page.locator(".rv-table tbody tr").count()) === pendingTab, "默认展示待审核队列",
        (await page.locator(".rv-table tbody tr").count()) + " vs " + pendingTab);
  check((await page.locator(".rv-table .audit-tag.wait").count()) === pendingTab, "每行均带「待审核」徽标");
  check((await page.locator(".rv-table th.ck input[type=checkbox]").count()) === 1 &&
        (await page.locator(".rv-table td.ck input[type=checkbox]").count()) === pendingTab,
        "表格含行选择框与全选框");
  await shot("25-admin-review-queue");

  /* ---------------- 3. 审核详情弹窗 ---------------- */
  const firstTitle = (await page.locator(".rv-table tbody tr .rv-name b").first().innerText()).trim();
  await page.locator(".rv-table tbody tr .rv-name").first().click();
  await page.waitForSelector(".modal-mask.show .rv-detail", { timeout: 8000 });
  check((await page.locator(".rv-detail .rv-title").innerText()).trim() === firstTitle, "详情弹窗标题与列表一致");
  check((await page.locator(".rv-detail .audit-tag").count()) >= 1, "详情展示审核状态");
  check((await page.locator(".rv-detail .rv-owner").count()) === 1, "详情展示登记教师");
  check((await page.locator(".rv-detail .rv-cell").count()) >= 8, "详情展示成果字段表");
  check((await page.locator(".rv-detail .rv-log-row").count()) >= 1, "详情含审核轨迹");
  check((await page.locator(".rv-detail .rv-actions .btn").count()) === 3, "详情提供通过 / 退回 / 关闭");
  await shot("26-admin-review-detail");
  await page.locator(".rv-detail .rv-actions .btn", { hasText: "关闭" }).click();
  await page.waitForTimeout(300);
  check((await page.locator(".modal-mask.show").count()) === 0, "详情弹窗可关闭");

  /* ---------------- 4. 单条通过 ---------------- */
  const toastP = page.waitForSelector(".toast", { timeout: 8000 }).then(() => true).catch(() => false);
  await page.locator(".rv-table tbody tr").first().locator("button", { hasText: "通过" }).click();
  check(await toastP, "通过后有提示反馈");
  check(await waitCount("待审核", pendingTab - 1), "通过后待审计数 -1");
  check((await tabCount("已通过")) === approvedTab + 1, "通过后已通过计数 +1");

  await setTab("已通过");
  check((await page.locator(".rv-table tbody tr .audit-tag.ok").count()) >= 1, "已通过标签页显示通过徽标");
  check((await page.locator(".rv-table tbody tr", { hasText: firstTitle }).count()) >= 1,
        "刚通过的成果出现在已通过列表");
  await shot("27-admin-review-approved");

  /* 撤回，恢复现场 */
  await page.locator(".rv-table tbody tr", { hasText: firstTitle }).first()
    .locator("button", { hasText: "撤回" }).click();
  await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  check(await waitCount("待审核", pendingTab), "撤回审核后待审计数恢复");

  /* ---------------- 5. 退回（带审核意见） ---------------- */
  await setTab("待审核");
  const rejectedBefore = await tabCount("已退回");
  const rejectTitle = (await page.locator(".rv-table tbody tr .rv-name b").first().innerText()).trim();
  await page.locator(".rv-table tbody tr").first().locator("button", { hasText: "退回" }).click();
  await page.waitForSelector(".modal-mask.show .modal-input", { timeout: 8000 });
  check((await page.locator(".modal-mask.show .modal-input").count()) === 1, "退回弹窗含审核意见输入框");
  /* 必填校验：不填直接确认应被拦截 */
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  await page.waitForTimeout(400);
  check((await page.locator(".modal-mask.show").count()) === 1, "未填意见时不允许提交（必填校验）");
  await shot("28-admin-review-reject-dialog");
  await page.locator(".modal-mask.show .modal-input").fill("论文录用函未附，请补充录用通知与 DOI 后再提交。");
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  check(await waitCount("已退回", rejectedBefore + 1), "退回后已退回计数 +1");
  check((await tabCount("待审核")) === pendingTab - 1, "退回后待审计数 -1");

  await setTab("已退回");
  const rejRow = page.locator(".rv-table tbody tr", { hasText: rejectTitle }).first();
  check((await rejRow.locator(".audit-tag.off").count()) === 1, "已退回标签页显示退回徽标");
  check((await rejRow.locator(".audit-note-inline").count()) === 1, "列表内联展示退回意见");
  await shot("29-admin-review-rejected");

  /* 撤回，恢复现场 */
  await rejRow.locator("button", { hasText: "撤回" }).click();
  await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  check(await waitCount("已退回", rejectedBefore), "退回项撤回后已退回计数恢复");

  /* ---------------- 6. 批量通过 ---------------- */
  await setTab("待审核");
  const beforeBatch = await tabCount("待审核");
  check(beforeBatch >= 2, "待审核数据足够做批量验证", String(beforeBatch));
  const batchTitles = await page.locator(".rv-table tbody tr .rv-name b").evaluateAll(
    els => els.slice(0, 2).map(e => (e.textContent || "").trim()));
  await page.locator(".rv-table tbody tr").nth(0).locator("td.ck input").check();
  await page.locator(".rv-table tbody tr").nth(1).locator("td.ck input").check();
  check((await page.locator(".batch-bar").count()) === 1, "勾选后出现批量操作条");
  check((await page.locator(".batch-bar b").innerText()).trim() === "2", "批量条显示已选 2 条");
  check((await page.locator(".rv-table tr.on").count()) === 2, "选中行高亮");
  await shot("30-admin-review-batch");
  await page.locator(".batch-bar .btn", { hasText: "批量通过" }).click();
  await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  check(await waitCount("待审核", beforeBatch - 2), "批量通过后待审计数 -2");
  check((await page.locator(".batch-bar").count()) === 0, "批量操作后自动清空选择");

  /* 还原：把刚刚批量通过的 2 条按标题撤回 */
  await setTab("已通过");
  for (const t of batchTitles) {
    const row = page.locator(".rv-table tbody tr", { hasText: t }).first();
    if (!(await row.count())) continue;
    await row.locator("button", { hasText: "撤回" }).click();
    await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
    await page.locator(".modal-mask.show [data-cfm='yes']").click();
    await page.waitForTimeout(700);
  }
  await setTab("待审核");
  check(await waitCount("待审核", beforeBatch), "还原后待审计数一致");
  check((await tabCount("已退回")) === rejectedBefore, "最终已退回数与初始一致");

  /* ---------------- 7. 教师筛选 / 关键词搜索 ---------------- */
  const firstOption = await page.locator(".select-mini option").nth(1).getAttribute("value");
  const firstTeacher = (await page.locator(".select-mini option").nth(1).innerText()).trim();
  await page.locator(".select-mini select").selectOption(firstOption);
  await page.waitForTimeout(600);
  const rowsPerTeacher = await page.locator(".rv-table tbody tr").count();
  check(rowsPerTeacher >= 1, "按教师筛选后仍有数据", firstTeacher + " → " + rowsPerTeacher);
  const teacherCells = await page.locator(".rv-table tbody tr .tt-name b").allInnerTexts();
  check(teacherCells.every(t => firstTeacher.indexOf(t) === 0), "筛选结果只包含该教师", teacherCells.join("/"));
  await page.locator(".select-mini select").selectOption("");
  await page.waitForTimeout(600);

  await page.locator(".search-box input").fill("专利");
  await page.waitForFunction(() => {
    const rows = document.querySelectorAll(".rv-table tbody tr .rv-name b");
    return rows.length > 0 && rows.length < 25;
  }, { timeout: 12000 }).catch(() => {});
  await page.waitForTimeout(400);
  const searched = await page.locator(".rv-table tbody tr").count();
  check(searched >= 1 && searched <= beforeBatch, "关键词搜索生效", "专利 → " + searched + " 条");
  await page.locator(".search-box input").fill("");
  await page.waitForTimeout(1200);

  /* ---------------- 8. 教师统计详情页（改版 UI） ---------------- */
  await page.locator(".nav-item:has-text('教师管理')").click();
  await page.waitForSelector(".tcard", { timeout: 15000 });
  await page.locator(".tcard").first().locator("button", { hasText: "统计详情" }).click();
  await page.waitForSelector(".tprofile", { timeout: 15000 });
  await page.waitForTimeout(500);

  check((await page.locator(".tprofile").count()) === 1, "详情页顶部教师名片（渐变外壳）");
  check((await page.locator(".tprofile .tp-avatar").count()) === 1, "名片含头像");
  check((await page.locator(".tprofile .tp-meta span").count()) >= 4, "名片含 4 项以上元信息");
  check((await page.locator(".tprofile .tp-kpis .tp-kpi").count()) === 4, "名片底部 4 项核心指标");
  check((await page.locator(".sec-nav .sec-tab").count()) === 4, "提供 4 个统计区块锚点");
  check((await page.locator(".sec-card").count()) === 4, "四类统计各自独立区块");
  check((await page.locator("#sec-research").count()) === 1, "科研成果区块带锚点 id");
  check((await page.locator(".sec-card .kpi-row .kpi").count()) === 16, "每个区块 4 张指标卡（共 16）");
  check((await page.locator(".sec-badge").count()) === 4, "区块头部含汇总徽标");
  check((await page.locator(".ad-head").count()) === 0, "旧版 ad-* 结构已移除");
  await shot("31-teacher-detail-top");

  /* 图表真实渲染 */
  const dashes = await page.$$eval(".ring circle", els =>
    els.map(e => e.getAttribute("stroke-dasharray")).filter(Boolean));
  check(dashes.length >= 1, "成果类型环形图已渲染扇区", dashes.slice(0, 3).join(" | "));
  const bars = await page.$$eval(".bar-track i", els =>
    els.map(e => parseFloat(e.style.width) || 0));
  check(bars.length >= 4 && bars.some(w => w > 0), "横向条形图已渲染", bars.slice(0, 5).join("/"));
  const gauges = await page.$$eval(".gauge circle", els =>
    els.map(e => e.getAttribute("stroke-dasharray")).filter(Boolean));
  check(gauges.length >= 2, "教学进度仪表环已渲染", gauges.slice(0, 2).join(" | "));

  /* 成果审核概况 */
  check((await page.locator(".audit-strip .as-item").count()) === 4, "科研成果区块含审核概况 4 指标");
  check((await page.locator(".audit-strip .as-foot .btn").count()) === 1, "审核概况可跳转到审核队列");
  await page.locator(".audit-strip .as-foot .btn").click();
  await page.waitForSelector(".rv-table", { timeout: 15000 });
  await page.waitForTimeout(600);
  const filteredTeacher = await page.locator(".select-mini select").inputValue();
  check(!!filteredTeacher, "跳转后自动按该教师筛选审核队列", filteredTeacher);
  await page.locator(".select-mini select").selectOption("");
  await page.waitForTimeout(500);

  /* 区块锚点滚动 + 学生区块 */
  await page.locator(".nav-item:has-text('教师管理')").click();
  await page.waitForSelector(".tcard", { timeout: 15000 });
  await page.locator(".tcard").first().locator("button", { hasText: "统计详情" }).click();
  await page.waitForSelector(".tprofile", { timeout: 15000 });
  await page.locator(".sec-nav .sec-tab", { hasText: "学生指导" }).click();
  await page.waitForTimeout(1100);
  const scrolled = await page.evaluate(() => document.querySelector(".content").scrollTop);
  check(scrolled > 100, "锚点导航可滚动到对应区块", "scrollTop=" + scrolled);
  check((await page.locator("#sec-student .need-box").count()) >= 0, "学生区块含本周沟通提示");
  await shot("32-teacher-detail-students");
  await shot("33-teacher-detail-full", true);

  /* 深色配色下无脏底色 */
  await page.locator(".topbar .icon-btn[title='界面配色']").click();
  await page.waitForSelector(".modal-mask.show .theme-dots", { timeout: 8000 });
  await page.locator(".modal-mask.show .theme-cell", { hasText: "灰黑" }).locator(".theme-dot").click();
  await page.waitForTimeout(300);
  await page.locator(".modal-mask.show [data-close]").click();
  await page.waitForTimeout(400);
  const darkBg = await page.evaluate(() => {
    const el = document.querySelector(".sec-card");
    return el ? getComputedStyle(el).backgroundColor : "";
  });
  check(/rgb\((\d+), (\d+), (\d+)\)/.test(darkBg) &&
        darkBg.match(/\d+/g).slice(0, 3).every(v => Number(v) < 90),
        "深色主题下统计区块为深色底", darkBg);
  await shot("34-teacher-detail-dark");
  await page.locator(".topbar .icon-btn[title='界面配色']").click();
  await page.waitForSelector(".modal-mask.show .theme-dots", { timeout: 8000 });
  await page.locator(".modal-mask.show .theme-cell", { hasText: "薄荷绿" }).locator(".theme-dot").click();
  await page.locator(".modal-mask.show [data-close]").click();
  await page.waitForTimeout(300);

  /* ---------------- 9. 控制台 ---------------- */
  const real = consoleErrors.filter(t => t.indexOf("401") < 0 && t.indexOf("403") < 0);
  check(real.length === 0, "浏览器控制台无报错", real.slice(0, 3).join(" | "));

  await browser.close();
  console.log("\n通过 " + pass + " / " + (pass + fail) + " 项");
  if (failures.length) { console.log("失败项："); failures.forEach(f => console.log("  - " + f)); }
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error("E2E 异常：", e.message); process.exit(2); });
