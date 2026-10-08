/* =====================================================================
   e2e_links.cjs —— 「常用网站」独立页面端到端验收（Playwright + Chromium）

   前置：先启动服务（另开终端）
       python run.py --port 5173 --prod

   运行：
       node tests/e2e_links.cjs [baseUrl]

   校验点：独立页面渲染与分组筛选、图标真实抓取、新增/编辑/删除、
           拖动排序落库、管理模式交互、深色主题与移动端适配、控制台无报错
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

const CANDIDATE_CHROME = [
  process.env.PW_CHROMIUM,
  "C:/Users/norbert/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe"
].filter(Boolean);
const CHROME_PATH = CANDIDATE_CHROME.find((p) => fs.existsSync(p)) || undefined;

const checks = [];
const problems = [];
function check(ok, label, detail) {
  checks.push({ ok, label, detail });
  if (!ok) problems.push(label + (detail ? " —— " + detail : ""));
}

/* 新建的测试网站（跑完必须清掉）。选国内稳定可达的站点，标题抓取才可断言 */
const TEST_SITE = { name: "学信网", url: "https://www.chsi.com.cn", title: "学信网" };
const NEW_NAME = "学信网 · 学历查询";

async function main() {
  fs.mkdirSync(SHOT_DIR, { recursive: true });
  const browser = await chromium.launch(CHROME_PATH ? { executablePath: CHROME_PATH } : {});
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  const consoleErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
  page.on("pageerror", (e) => consoleErrors.push("pageerror: " + e.message));

  const shot = async (name, full) =>
    page.screenshot({ path: path.join(SHOT_DIR, name + ".png"), fullPage: !!full });

  /* ---------------- 0. 登录 ---------------- */
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.locator(".lc-form input").nth(0).fill("jiangxl");
  await page.locator(".lc-form input").nth(1).fill("123456");
  await page.locator(".lc-submit").click();
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });
  /* 自愈：清掉上一次中断留下的测试网站，保证列表就是 12 条种子 */
  await page.evaluate(async (urls) => {
    const res = await fetch("/api/collections/links");
    for (const row of (await res.json()).data) {
      if (urls.indexOf(row.url) >= 0 || /^学信网/.test(row.name)) {
        await fetch("/api/collections/links/" + row.id, { method: "DELETE" });
      }
    }
  }, [TEST_SITE.url]);
  await page.reload({ waitUntil: "networkidle" });   // 让前端重新拉一次，丢弃被删掉的残留
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });
  /* 网站导航已从首页拆出：入口在侧边栏「发展区 → 常用网站」 */
  const goLinks = async () => {
    await page.locator(".sidebar .nav-item", { hasText: "常用网站" }).first().click();
    await page.waitForSelector(".site-grid", { timeout: 10000 });
  };
  await goLinks();

  const cardSel = ".site-grid .site-card:not(.site-add)";
  /* 记下起始顺序，用例结束原样还原（排序用例会真的改库） */
  const orderBefore = await page.locator(cardSel + " .sc-name").allInnerTexts();
  const setOrder = async (names) => page.evaluate(async (list) => {
    const rows = (await (await fetch("/api/collections/links")).json()).data;
    const byName = {};
    rows.forEach((r) => { byName[r.name] = r; });
    for (let i = 0; i < list.length; i++) {
      const row = byName[list[i]];
      if (row && Number(row.sort) !== i) {
        await fetch("/api/collections/links/" + row.id, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sort: i })
        });
      }
    }
  }, names);

  /* ---------------- 1. 区块与卡片 ---------------- */
  const cards = await page.locator(cardSel).count();
  check(cards === 12, "独立页面渲染 12 张卡片", "实际 " + cards);

  const statText = (await page.locator(".mini-stat").first().innerText()).replace(/\s/g, "");
  check(statText.includes("12") && statText.includes("网站总数"), "统计卡显示网站总数", statText);

  const firstMeta = (await page.locator(cardSel).first().locator(".sc-host").innerText()).trim();
  check(firstMeta.length > 0, "卡片展示备注（无备注时回退主机名）", firstMeta);

  const tabs = await page.locator(".site-tabs .site-tab").count();
  check(tabs === 5, "分组筛选含「全部 + 4 组」", "实际 " + tabs);

  /* 图标：<img> 必须真实加载出内容（站点图标或服务端首字母头像） */
  await page.waitForFunction((sel) => {
    const imgs = Array.from(document.querySelectorAll(sel + " .sc-ico img"));
    return imgs.length === 12 && imgs.every((i) => i.complete && i.naturalWidth > 0);
  }, cardSel, { timeout: 30000 }).catch(() => null);
  const iconStat = await page.evaluate((sel) => {
    const imgs = Array.from(document.querySelectorAll(sel + " .sc-ico img"));
    return {
      total: imgs.length,
      loaded: imgs.filter((i) => i.complete && i.naturalWidth > 0).length,
      visible: imgs.filter((i) => i.classList.contains("on")).length,
      sample: imgs.slice(0, 3).map((i) => i.currentSrc || i.src)
    };
  }, cardSel);
  check(iconStat.total === 12, "每张卡片都有图标位", "实际 " + iconStat.total);
  check(iconStat.loaded === 12, "全部图标成功加载（不会出现裂图）",
        iconStat.loaded + "/" + iconStat.total);
  check(iconStat.sample.every((s) => s.includes("/api/links/favicon?")), "图标走服务端抓取接口",
        iconStat.sample[0]);

  await shot("09-sites", true);

  /* ---------------- 2. 分组筛选 ---------------- */
  await page.locator(".site-tabs .site-tab", { hasText: "教学平台" }).first().click();
  await page.waitForTimeout(220);
  const teachCount = await page.locator(cardSel).count();
  check(teachCount === 2, "切到「教学平台」只剩 2 张卡片", "实际 " + teachCount);
  const allNames = await page.locator(cardSel + " .sc-name").allInnerTexts();
  check(allNames.every((n) => /MOOC|学堂/.test(n)), "筛选结果属于该分组", allNames.join("、"));

  await page.locator(".site-tabs .site-tab").first().click();   // 回到「全部」
  await page.waitForTimeout(200);
  check(await page.locator(cardSel).count() === 12, "切回「全部」恢复 12 张");

  /* 卡片点击应新标签打开对应站点（不离开工作台） */
  const firstHref = await page.locator(cardSel).first().locator("a.sc-link").getAttribute("href");
  const [popup] = await Promise.all([
    ctx.waitForEvent("page", { timeout: 10000 }).catch(() => null),
    page.locator(cardSel).first().locator("a.sc-link").click()
  ]);
  const popupUrl = popup ? popup.url().replace(/\/$/, "") : "";
  check(!!popup && popupUrl === firstHref.replace(/\/$/, ""), "点击卡片在新标签打开对应站点",
        popupUrl + " vs " + firstHref);
  if (popup) await popup.close();
  check((await page.locator(".mini-stats").count()) === 1, "打开站点后仍停留在工作台");

  /* ---------------- 3. 新增网站（自动抓取标题与图标） ---------------- */
  await page.locator(".toolbar .btn", { hasText: "管理网站" }).click();
  await page.waitForTimeout(200);
  check(await page.locator(".site-card.editing").count() === 12, "进入管理模式后卡片可编辑");
  check(await page.locator(".site-card.site-add").count() === 1, "管理模式露出「添加网站」卡片");
  check(await page.locator(".site-hint").count() === 1, "管理模式给出拖动提示");
  await shot("10-sites-edit", true);

  await page.locator(".site-card.site-add").click();
  await page.waitForSelector(".modal-mask.show .lk-form", { timeout: 8000 });
  check((await page.locator(".modal-mask.show .modal-head h2").innerText()).trim() === "添加网站",
        "打开「添加网站」弹窗");

  await page.fill(".modal-mask.show input[placeholder*='cnki']", TEST_SITE.url);
  // 先等图标抓取出结果，再等站点标题回来（两次探测是串行的）
  await page.waitForFunction(
    () => {
      const el = document.querySelector(".modal-mask.show .lk-ico-msg");
      return el && /站点图标|首字母头像/.test(el.textContent);
    },
    null,
    { timeout: 25000 }
  );
  await page.waitForFunction(
    () => {
      const hint = document.querySelector(".modal-mask.show .field .hint");
      return hint && hint.textContent.trim().length > 0;
    },
    null,
    { timeout: 25000 }
  );
  const icoMsg = (await page.locator(".modal-mask.show .lk-ico-msg").innerText()).trim();
  const nameVal = await page.locator(".modal-mask.show input[placeholder*='中国知网']").inputValue();
  const metaMsg = (await page.locator(".modal-mask.show .field .hint").innerText()).trim();
  check(/站点图标|首字母头像/.test(icoMsg), "弹窗自动抓取图标并给出状态", icoMsg);
  check(nameVal.includes(TEST_SITE.title), "按站点标题自动填充名称", nameVal + " / " + metaMsg);
  await shot("11-site-form");

  await page.locator(".modal-mask.show .modal-actions .btn.primary").click();
  await page.waitForTimeout(900);
  check((await page.locator(cardSel).count()) === 13, "新增后卡片数变为 13");

  /* 刷新页面：确认已落库 */
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });
  await goLinks();
  const afterReload = await page.locator(cardSel + " .sc-name").allInnerTexts();
  check(afterReload.some((n) => n.includes(TEST_SITE.title)), "新增网站刷新后仍在（已写入服务端）");

  /* ---------------- 4. 编辑 ---------------- */
  await page.locator(".toolbar .btn", { hasText: "管理网站" }).click();
  await page.waitForTimeout(200);
  const target = page.locator(cardSel).filter({ hasText: TEST_SITE.title }).first();
  await target.locator(".sc-op[title='编辑']").click();
  await page.waitForSelector(".modal-mask.show .lk-form", { timeout: 8000 });
  check((await page.locator(".modal-mask.show .modal-head h2").innerText()).trim() === "编辑网站",
        "打开「编辑网站」弹窗（表单已回填）");
  const filled = await page.locator(".modal-mask.show input[placeholder*='中国知网']").inputValue();
  check(filled.includes(TEST_SITE.title), "编辑弹窗回填原名称", filled);
  await page.fill(".modal-mask.show input[placeholder*='中国知网']", NEW_NAME);
  await page.fill(".modal-mask.show input[placeholder*='选填']", "学历学位在线验证");
  await page.locator(".modal-mask.show .modal-actions .btn.primary").click();
  await page.waitForTimeout(900);
  const renamed = await page.locator(cardSel + " .sc-name").allInnerTexts();
  check(renamed.includes(NEW_NAME), "改名立即生效", renamed.join("、"));
  const tip = await page.locator(cardSel).filter({ hasText: NEW_NAME }).first()
    .getAttribute("title");
  check((tip || "").includes("学历学位在线验证"), "备注写入悬停提示", tip);

  /* ---------------- 5. 拖动排序 ---------------- */
  const before = await page.locator(cardSel + " .sc-name").allInnerTexts();
  await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll(".site-grid .site-card:not(.site-add)"));
    const dt = new DataTransfer();
    const fire = (el, type) =>
      el.dispatchEvent(new DragEvent(type, { dataTransfer: dt, bubbles: true, cancelable: true }));
    fire(cards[0], "dragstart");
    fire(cards[3], "dragover");
    fire(cards[3], "drop");
    fire(cards[0], "dragend");
  });
  await page.waitForTimeout(1200);
  const after = await page.locator(cardSel + " .sc-name").allInnerTexts();
  check(after[3] === before[0], "拖动后第 1 张移到第 4 位", after.slice(0, 4).join(" → "));

  const persisted = await page.evaluate(async (expectFirst) => {
    const res = await fetch("/api/collections/links");
    const rows = (await res.json()).data.slice().sort((a, b) => (a.sort || 0) - (b.sort || 0));
    return { first: rows[0].name, second: rows[1].name, expectFirst };
  }, after[0]);
  check(persisted.first === persisted.expectFirst, "顺序已落库（刷新后保持）",
        persisted.first + " / " + persisted.second);

  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });
  await goLinks();
  const afterReload2 = await page.locator(cardSel + " .sc-name").allInnerTexts();
  check(afterReload2[0] === persisted.first, "刷新后仍保持新顺序", afterReload2[0]);

  /* ---------------- 6. 删除 ---------------- */
  await page.locator(".toolbar .btn", { hasText: "管理网站" }).click();
  await page.waitForTimeout(200);
  await page.locator(cardSel).filter({ hasText: NEW_NAME }).first()
    .locator(".sc-op[title='删除']").click();
  await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
  check((await page.locator(".modal-mask.show .modal-head h2").innerText()).includes("删除"),
        "删除前二次确认");
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  await page.waitForTimeout(900);
  const left = await page.locator(cardSel + " .sc-name").allInnerTexts();
  check(left.length === 12 && !left.some((n) => n.includes("学信网")), "删除后恢复 12 张",
        "实际 " + left.length);

  /* 管理模式点链接不应跳转 */
  await page.locator(cardSel).first().locator("a.sc-link").click();
  await page.waitForTimeout(400);
  check((await page.locator(".site-grid").count()) === 1, "管理模式下点击卡片不跳转");

  await page.locator(".toolbar .btn", { hasText: "完成" }).click();
  await page.waitForTimeout(250);
  check(await page.locator(".site-card.editing").count() === 0, "「完成」退出管理模式");

  /* ---------------- 7. 深色主题 ---------------- */
  await page.evaluate(() => window.FWB.theme.apply("graphite"));
  await page.waitForTimeout(300);
  const darkShot = await page.locator(".site-grid").screenshot();
  check(darkShot.length > 3000, "深色主题下区块正常渲染");
  await shot("12-sites-dark", true);
  await page.evaluate(() => window.FWB.theme.apply("mint"));
  await page.waitForTimeout(200);

  /* ---------------- 8. 窄窗口 / 小屏自适应 ---------------- */
  const colsAt = async (w) => {
    await page.setViewportSize({ width: w, height: 900 });
    await page.waitForTimeout(250);
    return page.evaluate(() => {
      const grid = document.querySelector(".site-grid");
      return {
        cols: getComputedStyle(grid).gridTemplateColumns.split(" ").length,
        overflow: grid.scrollWidth > document.querySelector(".content").clientWidth + 2,
        cards: document.querySelectorAll(".site-grid .site-card:not(.site-add)").length
      };
    });
  };
  const mid = await colsAt(1100);
  check(mid.cols >= 3, "窗口变窄后卡片自动递减列数", "1100px → " + mid.cols + " 列");
  check(mid.cards === 12, "换列后卡片数量不变");
  await shot("13-sites-narrow", true);

  const small = await colsAt(760);
  check(small.cols >= 2, "更窄时仍保持多列", "760px → " + small.cols + " 列");
  check(!small.overflow, "窄窗口下无横向溢出");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(200);

  /* ---------------- 9. 还原起始顺序 ---------------- */
  await setOrder(orderBefore);
  await page.waitForTimeout(500);
  const restored = await page.evaluate(async () => {
    const rows = (await (await fetch("/api/collections/links")).json()).data;
    return rows.slice().sort((a, b) => (a.sort || 0) - (b.sort || 0)).map((r) => r.name);
  });
  check(restored.length === 12 && restored.join("|") === orderBefore.join("|"),
        "用例结束后网站顺序已还原", restored.join("、"));

  /* ---------------- 10. 控制台 ---------------- */
  const realErrors = consoleErrors.filter((t) => !/status of 401\s*\(UNAUTHORIZED\)/.test(t));
  check(realErrors.length === 0, "浏览器控制台无报错", realErrors.slice(0, 4).join(" | "));

  await browser.close();

  const failed = checks.filter((c) => !c.ok);
  console.log("\n=== 常用网站 E2E 结果 ===");
  checks.forEach((c) => {
    console.log((c.ok ? "  ✓ " : "  ✗ ") + c.label + (!c.ok && c.detail ? "  [" + c.detail + "]" : ""));
  });
  console.log("\n通过 " + (checks.length - failed.length) + " / " + checks.length + " 项");
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
