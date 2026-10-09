/* =====================================================================
   e2e_cv.cjs —— 个人简历端到端验收（Playwright + Chromium）

   前置：先启动服务（另开终端）
       python run.py --port 5173 --prod

   运行：
       node tests/e2e_cv.cjs [baseUrl]

   校验点：工作台发布卡（公开开关 / 固定链接 / 复制 / 更换确认）、
           头像上传与移除、区块开关往返、教育经历 CRUD、
           公开页数据实时同步（改简介立即生效）、
           隐私白名单（学生邮箱 / 业绩分不下发）、
           未公开与无效令牌的锁定态、深色 / 移动端 / 打印视图、控制台无报错
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
let pass = 0, fail = 0;
const failures = [];
function check(ok, label, detail) {
  checks.push({ ok, label, detail });
  if (ok) { pass++; console.log("  ✓ " + label); }
  else { fail++; failures.push(label + (detail ? " —— " + detail : "")); console.log("  ✗ " + label + (detail ? " —— " + detail : "")); }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* 真实可解码的 1×1 PNG（损坏图片会触发 img @error 回落首字母，无法通过用例） */
const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64");

const ORIGINAL_TAGLINE = "面向真实场景的智能感知与多模态理解";
const TEST_TAGLINE = "E2E测试定位语" + Date.now().toString(36);
const TEST_SCHOOL = "E2E测试大学";

async function main() {
  fs.mkdirSync(SHOT_DIR, { recursive: true });
  const browser = await chromium.launch(CHROME_PATH ? { executablePath: CHROME_PATH } : {});
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE });
  const page = await ctx.newPage();

  const consoleErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
  page.on("pageerror", (e) => consoleErrors.push("pageerror: " + e.message));
  const realErrors = () => consoleErrors.filter((t) => !t.includes("401"));

  const shot = (name, full) => page.screenshot({ path: path.join(SHOT_DIR, name + ".png"), fullPage: !!full });

  /* 访客页（独立上下文，不带教师会话；公开接口本身 credentials: omit） */
  const openVisitor = async (path_, opts) => {
    const vctx = opts && opts.ctx ? opts.ctx : await browser.newContext();
    const p2 = await vctx.newPage();
    const errs2 = [];
    p2.on("pageerror", (e) => errs2.push(e.message));
    if (opts && opts.printStub) {
      await p2.addInitScript(() => {
        window.__printCalls = 0;
        window.print = () => { window.__printCalls++; };
      });
    }
    await p2.goto(BASE + path_, { waitUntil: "networkidle" });
    await p2.waitForTimeout(500);
    return { p2, vctx, errs2 };
  };

  /* ===================================================================== */
  console.log("\n== 1. 登录与用例自愈 ==");
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForSelector(".lc-form", { timeout: 15000 });
  await page.locator(".lc-form input").nth(0).fill("jiangxl");
  await page.locator(".lc-form input").nth(1).fill("123456");
  await page.locator(".lc-submit").click();
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });
  check(true, "教师登录成功");

  /* 自愈：公开 + 全部区块打开 + 无头像 + 定位语还原（消除上次中断遗留状态） */
  await page.evaluate(async (tagline) => {
    await fetch("/api/cv/visibility", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ published: true }) });
    const cur = await (await fetch("/api/cv")).json();
    const sections = {};
    Object.keys(cur.data.sections).forEach((k) => { sections[k] = true; });
    await fetch("/api/cv/sections", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sections) });
    await fetch("/api/cv/avatar", { method: "DELETE" });
    const prof = await (await fetch("/api/profile")).json();
    await fetch("/api/profile", { method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({}, prof.data, { tagline: tagline })) });
  }, ORIGINAL_TAGLINE);
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });

  /* ===================================================================== */
  console.log("\n== 2. 工作台「个人简历」页 ==");

  await page.locator(".sidebar .nav-item", { hasText: "个人简历" }).first().click();
  await page.waitForSelector(".cvs-avatar-row", { timeout: 10000 });
  check(true, "侧栏导航进入个人简历页");

  const pageTitle = (await page.locator(".page-title").innerText()).trim();
  check(pageTitle === "个人简历", "页面标题", pageTitle);

  const statVals = await page.locator(".stat-card .stat-val").allInnerTexts();
  check(statVals.length === 4 && /已公开|未公开/.test(statVals[0]), "顶部 4 张数字卡", statVals.join("|"));

  const linkText = (await page.locator(".cs-link code").innerText()).trim();
  check(/^http:\/\/127\.0\.0\.1:5173\/cv\/[0-9a-f]{16}$/.test(linkText), "固定链接格式", linkText);
  check((await page.locator(".cs-link .btn").count()) === 4, "链接操作 4 个（复制/打开/打印/更换）");

  const toggleOn = await page.locator(".cs-switch.on").count();
  check(toggleOn === 1, "公开开关处于打开态");

  const toggles = await page.locator(".cvs-toggle").count();
  check(toggles === 11, "展示区块 11 个开关", "实际 " + toggles);

  const srcRows = await page.locator(".cvs-src-row").allInnerTexts();
  check(srcRows.length === 4 && srcRows[0].indexOf("科研项目") >= 0, "内容来源 4 条", srcRows.join("|"));
  await shot("42-cv-settings");

  /* ---------------- 区块开关往返 ---------------- */
  console.log("\n== 3. 区块开关 ==");
  const svcToggle = page.locator(".cvs-toggle", { hasText: "社会服务" });
  await svcToggle.click();
  await sleep(600);
  const svcNowOff = await svcToggle.evaluate((el) => !el.classList.contains("on"));
  check(svcNowOff, "点击后「社会服务」关闭");

  const token = await page.evaluate(() => window.FWB.store.state.cv.token);
  const pubState = await page.evaluate(async (tk) => {
    const res = await fetch("/api/public/cv/" + tk, { credentials: "omit" });
    const body = await res.json();
    return body.ok ? body.data.sections.services : "locked";
  }, token);
  check(pubState === false, "公开接口同步：services 区块已隐藏", String(pubState));

  await svcToggle.click();
  await sleep(600);
  check(await svcToggle.evaluate((el) => el.classList.contains("on")), "再点一次恢复显示");

  /* ---------------- 固定链接复制 ---------------- */
  console.log("\n== 4. 固定链接复制 ==");
  await page.locator(".cs-link .btn", { hasText: "复制" }).click();
  await sleep(400);
  let clip = "";
  try { clip = await page.evaluate(() => navigator.clipboard.readText()); } catch (e) { clip = "读取失败"; }
  check(clip === linkText, "剪贴板与页面链接一致", clip);

  /* 更换链接有确认弹窗，点取消不换 */
  await page.locator(".cs-link .btn", { hasText: "更换链接" }).click();
  await page.waitForSelector(".modal-mask.show", { timeout: 6000 });
  check((await page.locator(".modal-mask.show .modal-head h2").innerText()).indexOf("更换固定链接") >= 0, "更换链接弹出确认");
  await page.locator(".modal-mask.show [data-cfm='no']").click();
  await sleep(400);
  const linkAfterCancel = (await page.locator(".cs-link code").innerText()).trim();
  check(linkAfterCancel === linkText, "取消后链接不变");

  /* ===================================================================== */
  console.log("\n== 5. 头像上传与移除 ==");
  await page.setInputFiles(".cvs-avatar-row input[type=file]", {
    name: "avatar.png", mimeType: "image/png", buffer: PNG_BYTES,
  });
  await page.waitForSelector(".cvs-avatar img", { timeout: 10000 });
  check(true, "上传后头像立即显示");
  await shot("43-cv-settings-avatar");

  const avatarApi = await page.evaluate(async (tk) => {
    const r = await fetch("/api/public/cv/" + tk + "/avatar", { credentials: "omit" });
    return { status: r.status, type: r.headers.get("content-type") || "" };
  }, token);
  check(avatarApi.status === 200 && avatarApi.type.indexOf("image/") === 0, "公开侧头像可访问", JSON.stringify(avatarApi));

  await page.locator(".cvs-avatar-side .btn", { hasText: "移除" }).click();
  await page.waitForSelector(".cvs-avatar img", { state: "detached", timeout: 10000 });
  const fb = (await page.locator(".cvs-avatar").innerText()).trim();
  check(fb === "江", "移除后回落姓名首字", fb);

  /* ===================================================================== */
  console.log("\n== 6. 简历基本信息编辑（实时同步验证） ==");
  await page.locator(".card-head .more", { hasText: "编辑" }).first().click();
  await page.waitForSelector(".modal-mask.show .form-row.two", { timeout: 6000 });
  const fieldCount = await page.locator(".modal-mask.show .field").count();
  check(fieldCount === 14, "基本信息表单 14 个字段", "实际 " + fieldCount);
  await shot("44-cv-profile-modal");

  const tagInput = page.locator(".modal-mask.show .field", { hasText: "一句话定位" }).locator("input");
  await tagInput.fill(TEST_TAGLINE);
  await page.locator(".modal-mask.show .modal-foot .btn.primary").click();
  await page.waitForSelector(".modal-mask.show", { state: "detached", timeout: 6000 });
  await sleep(400);
  check((await page.locator(".cvs-tagline").innerText()).trim() === TEST_TAGLINE,
        "工作台立即显示新定位语");

  /* 公开页（访客视角）读到的也是新值 —— 数据实时聚合，无副本 */
  {
    const { p2, vctx, errs2 } = await openVisitor("/cv/" + token);
    await p2.waitForSelector(".cv-hero", { timeout: 10000 });
    const tagline = (await p2.locator(".cv-tagline").innerText()).trim();
    check(tagline === TEST_TAGLINE, "访客看到最新定位语（实时同步）", tagline);

    /* ---------------- 公开页结构 ---------------- */
    console.log("\n== 7. 公开简历页 ==");
    const heroName = (await p2.locator(".cv-hero h1").innerText()).trim();
    check(heroName.indexOf("江老师") === 0, "姓名开头正确", heroName);
    check((await p2.locator(".cv-role-title").count()) === 1, "职称徽标");
    const navLinks = await p2.locator(".cv-nav-link").count();
    check(navLinks === 10, "锚点导航 10 项", "实际 " + navLinks);
    const secs = await p2.locator(".cv-sec").count();
    check(secs >= 9, "正文区块齐全（≥9 段）", "实际 " + secs);
    check((await p2.locator("#publications .cv-pub").count()) === 4, "论文 4 条");
    check((await p2.locator("#students .cv-student").count()) === 4, "学生 4 条");
    check((await p2.locator("#education .cv-tl-item").count()) === 3, "教育经历 3 段");
    check((await p2.locator("#services .cv-svc").count()) === 6, "社会服务 6 条");
    await p2.screenshot({ path: path.join(SHOT_DIR, "45-cv-public-full.png"), fullPage: true });

    /* 隐私：页面与公开接口都不含私有字段 */
    const pubJson = await p2.evaluate(async (tk) => {
      const res = await fetch("/api/public/cv/" + tk, { credentials: "omit" });
      return (await res.json()).data;
    }, token);
    const blob = JSON.stringify(pubJson);
    check(blob.indexOf("auditStatus") < 0 && blob.indexOf('"score"') < 0,
          "公开数据不含审核状态 / 业绩分");
    check((pubJson.students || []).every((s) => !("email" in s)), "学生邮箱不下发");
    check(!("events" in pubJson) && !("todos" in pubJson) && !("tools" in pubJson),
          "日程 / 待办 / 工具不出现在公开数据");
    check(errs2.length === 0, "公开页无脚本错误", errs2.join("; ") || "");
    await p2.close();
    await vctx.close();
  }

  /* 定位语还原 */
  await page.locator(".card-head .more", { hasText: "编辑" }).first().click();
  await page.waitForSelector(".modal-mask.show .form-row.two", { timeout: 6000 });
  await page.locator(".modal-mask.show .field", { hasText: "一句话定位" }).locator("input").fill(ORIGINAL_TAGLINE);
  await page.locator(".modal-mask.show .modal-foot .btn.primary").click();
  await page.waitForSelector(".modal-mask.show", { state: "detached", timeout: 6000 });

  /* ===================================================================== */
  console.log("\n== 8. 教育经历 CRUD ==");
  const eduBefore = await page.locator(".cvs-row").count();
  await page.locator(".card", { hasText: "教育经历" }).locator(".btn", { hasText: "新增" }).click();
  await page.waitForSelector(".modal-mask.show .form-row.two", { timeout: 6000 });
  await page.locator(".modal-mask.show .field", { hasText: "学校 / 单位" }).locator("input").fill(TEST_SCHOOL);
  await page.locator(".modal-mask.show .field", { hasText: "专业 / 院系" }).locator("input").fill("测试专业");
  await page.locator(".modal-mask.show .field", { hasText: "起始时间" }).locator("input").fill("2020-09");
  await page.locator(".modal-mask.show .modal-foot .btn.primary").click();
  await page.waitForSelector(".modal-mask.show", { state: "detached", timeout: 6000 });
  await sleep(400);
  const eduAfter = await page.locator(".cvs-row").count();
  check(eduAfter === eduBefore + 1, "新增教育经历后列表 +1", eduBefore + " -> " + eduAfter);
  check((await page.locator(".cvs-row", { hasText: TEST_SCHOOL }).count()) === 1, "新条目出现在列表首位附近");

  /* 删除（确认弹窗） */
  await page.locator(".cvs-row", { hasText: TEST_SCHOOL }).locator(".btn", { hasText: "删除" }).click();
  await page.waitForSelector(".modal-mask.show", { timeout: 6000 });
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  await sleep(500);
  check((await page.locator(".cvs-row", { hasText: TEST_SCHOOL }).count()) === 0, "删除后条目消失");

  /* ===================================================================== */
  console.log("\n== 9. 未公开与无效令牌 ==");
  await page.evaluate(async () => {
    await fetch("/api/cv/visibility", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ published: false }) });
  });
  {
    const { p2, vctx } = await openVisitor("/cv/" + token);
    await p2.waitForSelector(".cv-lock-card", { timeout: 10000 });
    check((await p2.locator(".cv-lock-card h1").innerText()).indexOf("暂未公开") >= 0, "未公开时显示锁定提示");
    await p2.screenshot({ path: path.join(SHOT_DIR, "48-cv-public-private.png") });
    await p2.close();
    await vctx.close();
  }
  await page.evaluate(async () => {
    await fetch("/api/cv/visibility", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ published: true }) });
  });

  {
    const { p2, vctx } = await openVisitor("/cv/deadbeefdeadbeef");
    await p2.waitForSelector(".cv-lock-card", { timeout: 10000 });
    check((await p2.locator(".cv-lock-card h1").innerText()).indexOf("无效") >= 0, "无效令牌提示");
    await p2.screenshot({ path: path.join(SHOT_DIR, "49-cv-public-invalid.png") });
    await p2.close();
    await vctx.close();
  }

  /* ===================================================================== */
  console.log("\n== 10. 深色 / 移动端 / 打印 ==");
  {
    const darkCtx = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: "dark" });
    const { p2, vctx } = await openVisitor("/cv/" + token, { ctx: darkCtx });
    await p2.waitForSelector(".cv-hero", { timeout: 10000 });
    const bg = await p2.evaluate(() => getComputedStyle(document.body).backgroundColor);
    check(bg !== "rgb(245, 247, 246)", "深色主题生效", bg);
    await p2.screenshot({ path: path.join(SHOT_DIR, "46-cv-public-dark.png") });
    await p2.close();
    await vctx.close();
  }
  {
    const mobCtx = await browser.newContext({ viewport: { width: 414, height: 860 }, isMobile: true });
    const { p2, vctx } = await openVisitor("/cv/" + token, { ctx: mobCtx });
    await p2.waitForSelector(".cv-hero", { timeout: 10000 });
    const over = await p2.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    check(!over, "移动端 414px 无横向溢出");
    await p2.close();
    await vctx.close();
  }
  {
    const printCtx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const { p2, vctx } = await openVisitor("/cv/" + token + "?print=1", { ctx: printCtx, printStub: true });
    await p2.waitForSelector(".cv-hero", { timeout: 10000 });
    await sleep(900);
    const calls = await p2.evaluate(() => window.__printCalls || 0);
    check(calls === 1, "工作台「打印 / PDF」触发一次打印", "调用 " + calls + " 次");
    await p2.close();
    await vctx.close();
  }

  /* ===================================================================== */
  check(realErrors().length === 0, "工作台控制台无真实报错", realErrors().join(" | ") || "");
  await shot("47-cv-settings-final");

  console.log("\n----------------------------------------");
  console.log(`通过 ${pass} / ${pass + fail} 项`);
  if (failures.length) {
    console.log("失败项：");
    failures.forEach((f) => console.log("  - " + f));
    process.exitCode = 1;
  }
  await browser.close();
}

main().catch((e) => { console.error("FATAL:", e); process.exit(1); });
