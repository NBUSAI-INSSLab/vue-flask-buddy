/* =====================================================================
   e2e_courses.cjs —— 课程开放（学生公开页）+ 课程资料上传下载 浏览器验收
   运行：node tests/e2e_courses.cjs [baseUrl]
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
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext({ viewport: { width: 1560, height: 1000 } });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on("console", m => { if (m.type() === "error") consoleErrors.push(m.text()); });
  page.on("pageerror", e => consoleErrors.push("pageerror: " + e.message));
  /* 登录前的 /api/auth/me 探测必然 401，属预期 */
  const realErrors = () => consoleErrors.filter(t => !t.includes("401"));

  const shot = (name, full) => page.screenshot({ path: path.join(SHOT_DIR, name + ".png"), fullPage: !!full });
  const stripState = async () =>
    (await page.locator(".share-strip .ss-head").innerText()).replace(/\s+/g, " ").trim();

  /* 学生公开页加载，返回页面主文本 */
  const openStudentPage = async (token) => {
    const p2 = await ctx.newPage();
    const errs2 = [];
    p2.on("pageerror", e => errs2.push(e.message));
    await p2.goto(BASE + "/c/" + token, { waitUntil: "networkidle" });
    await p2.waitForTimeout(400);
    return { p2, errs2 };
  };
  const setVisibility = async (payload) => {
    await page.locator(".share-strip .ss-ops .btn").click();
    await page.waitForSelector(".cs-form", { timeout: 8000 });
    const on = await page.locator(".cs-switch").evaluate(el => el.classList.contains("on"));
    if (payload.published !== on) await page.locator(".cs-switch").click();
    await page.locator(".cs-range-row input").nth(0).fill(payload.openFrom || "");
    await page.locator(".cs-range-row input").nth(1).fill(payload.openUntil || "");
    await page.locator(".modal-actions .btn.primary").click();
    await page.waitForSelector(".cs-form", { state: "detached", timeout: 8000 });
    await sleep(500);
  };

  /* ===================================================================== */
  console.log("\n== 1. 教师端：课程列表与详情 ==");

  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForSelector(".login-page", { timeout: 15000 });
  await page.locator(".lc-form input").nth(0).fill("jiangxl");
  await page.locator(".lc-form input").nth(1).fill("123456");
  await page.locator(".lc-submit").click();
  await page.waitForSelector(".sidebar", { timeout: 15000 });
  await page.waitForTimeout(900);
  check(true, "教师登录成功");

  /* 用例自愈：把三门课归位到「出厂演示态」——
     c1 长期开放 / c2 处于时间窗口内 / c3 手动关闭。
     · c3 的关闭态是种子有意设计的演示样例（见 tests/test_api_courses.py：
       「C3 = "c3"  # Python 程序设计：种子中默认关闭」），所以徽标断言必须按课程
       分别校验，不能要求三门课都开放；
     · c2 的窗口滚动刷新，否则窗口过期后徽标会变成「已结束」，用例随时间失真；
     · 同时消除上次运行中断遗留状态带来的不确定性（原本只自愈 c1）。 */
  const dayShift = (n) => {
    const d = new Date();
    d.setDate(d.getDate() + n);
    const p = (x) => String(x).padStart(2, "0");
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate());
  };
  await page.evaluate(async (win) => {
    const setVis = (id, body) => fetch("/api/courses/" + id + "/visibility", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    await setVis("c1", { published: true, openFrom: "", openUntil: "" });
    await setVis("c2", { published: true, openFrom: win.from, openUntil: win.until });
    await setVis("c3", { published: false, openFrom: "", openUntil: "" });
  }, { from: dayShift(-40), until: dayShift(90) });
  /* 自愈走的是裸 fetch，前端 store 仍是登录时拉到的旧状态；
     刷新一次再校验徽标，避免上一次运行遗留状态导致本用例失真 */
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });

  await page.locator(".sidebar .nav-item", { hasText: "课程资源" }).click();
  await page.waitForSelector(".course-grid .course-card", { timeout: 15000 });
  check((await page.locator(".course-card").count()) === 3, "课程列表 3 门课");
  /* 逐个课程卡校验徽标：c1 长期开放、c2 在时间窗口内、c3 手动关闭，三种态都要正确。
     注意 c2 与 c3 的差别——同是「种子演示课」，c2 可见、c3 不可见，缺一不可。 */
  const visRows = await page.$$eval(".course-card", (cards) => cards.map((c) => {
    const n = c.querySelector(".cb-name"), v = c.querySelector(".cb-vis");
    return { name: n ? n.innerText.trim() : "", vis: v ? v.innerText.trim() : "" };
  }));
  const badgeOf = (nm) => (visRows.find((x) => x.name.indexOf(nm) >= 0) || {}).vis || "";
  const wantVis = { "计算机网络": "已开放", "机器学习导论": "已开放", "Python 程序设计": "已关闭" };
  check(visRows.length === 3 && Object.keys(wantVis).every((k) => badgeOf(k) === wantVis[k]),
        "课程卡显示可见性徽标（开放 / 窗口内 / 关闭）",
        visRows.map((x) => x.name + "=" + x.vis).join("|"));
  check((await page.locator(".mini-stat", { hasText: "学生可见" }).count()) === 1,
        "列表统计含「学生可见」");
  await shot("35-course-list");

  await page.locator(".course-card", { hasText: "计算机网络" }).click();
  await page.waitForSelector(".share-strip", { timeout: 15000 });
  await page.waitForFunction(() => document.querySelector(".ss-link code") && document.querySelector(".ss-link code").innerText.indexOf("http") === 0,
    { timeout: 12000 });
  check((await stripState()).indexOf("已开放") >= 0, "详情页学生访问状态条", await stripState());
  const courseLink = (await page.locator(".ss-link code").innerText()).trim();
  check(/^http.+\/c\/[0-9a-f]{16}$/.test(courseLink), "访问链接格式正确", courseLink);
  check((await page.locator(".ss-link .btn", { hasText: "复制" }).count()) === 1, "提供复制链接按钮");
  check((await page.locator(".ss-link .btn", { hasText: "预览" }).count()) === 1, "提供预览按钮");
  check((await page.locator(".ss-hint").innerText()).indexOf("长期开放") >= 0,
        "开放说明文案", (await page.locator(".ss-hint").innerText()).trim());

  /* ===================================================================== */
  console.log("\n== 1.5 教学日历与联系方式 ==");

  check((await page.locator(".detail-head .btn", { hasText: "助教与联系" }).count()) === 1,
        "详情页提供「助教与联系」入口");
  await page.locator(".tabs .tab", { hasText: "教学日历" }).click();
  await page.waitForSelector(".cal-toolbar", { timeout: 8000 });
  check((await page.locator(".tbl tbody tr").count()) === 14, "教学日历 14 周",
        String(await page.locator(".tbl tbody tr").count()));
  const calFoot = (await page.locator(".tbl tfoot").innerText()).replace(/\s/g, "");
  check(calFoot.includes("14周") && calFoot.includes("56学时"), "日历合计学时", calFoot);
  await shot("36-course-calendar");

  await page.locator(".cal-toolbar .btn", { hasText: "编辑日历与联系方式" }).click();
  await page.waitForSelector(".modal-mask.show .ct-form", { timeout: 8000 });
  await page.waitForTimeout(600);
  check((await page.locator(".modal-mask.show .modal-head h2").innerText()).trim() === "助教与联系方式",
        "打开「助教与联系方式」弹窗");
  check((await page.locator(".modal-mask.show input[maxlength='64']").inputValue()) === "736285914",
        "QQ 群号已回填");
  check((await page.locator(".modal-mask.show .ct-qr img").count()) === 1, "群二维码预览已加载");
  check((await page.locator(".modal-mask.show .ct-cal-row:not(.ct-cal-head)").count()) === 14,
        "日历编辑器回填 14 行");
  const saveLabel = (await page.locator(".modal-mask.show .modal-actions .btn.primary").innerText()).trim();
  check(saveLabel === "已是最新", "未修改时保存按钮显示已是最新", saveLabel);

  /* 从大纲生成（两步确认，点亮后立即再点一次）→ 8 章覆盖 14 行；随后取消不保存 */
  const genBtn = page.locator(".modal-mask.show .ct-sec-head .btn", { hasText: "从大纲生成" });
  await genBtn.click();
  await page.waitForTimeout(250);
  check((await page.locator(".modal-mask.show .btn", { hasText: "再点一次覆盖" }).count()) === 1,
        "覆盖生成走两步确认");
  await page.locator(".modal-mask.show .ct-sec-head .btn.danger").click();   // 确认态按钮已变 danger
  await page.waitForTimeout(500);
  check((await page.locator(".modal-mask.show .ct-cal-row:not(.ct-cal-head)").count()) === 8,
        "按大纲生成 8 行日历");
  const genFirst = await page.locator(".modal-mask.show .ct-cal-row:not(.ct-cal-head) input.ct-wide")
    .first().inputValue();
  check(genFirst.indexOf("第 1 章") === 0, "生成内容取自大纲章节", genFirst);
  await shot("37-course-contact-modal");
  await page.locator(".modal-mask.show .modal-actions .btn", { hasText: "取消" }).click();
  await page.waitForTimeout(300);
  check((await page.locator(".ct-form").count()) === 0, "取消后弹窗关闭且不保存");

  /* ===================================================================== */
  console.log("\n== 1.6 课程助教（姓名 + 联系方式，可编辑）==");

  await page.locator(".tabs .tab", { hasText: "课程助教" }).click();
  await page.waitForSelector(".ta-link", { timeout: 8000 });
  check((await page.locator(".tbl tbody tr").count()) === 2, "课程助教 2 位",
        String(await page.locator(".tbl tbody tr").count()));
  const taRow0 = (await page.locator(".tbl tbody tr").first().innerText()).replace(/\s+/g, " ");
  check(taRow0.indexOf("李明") >= 0 && taRow0.indexOf("博士生助教") >= 0, "助教姓名与身份/分工", taRow0);
  check((await page.locator(".tbl tbody tr a[href^='tel:']").count()) === 2, "助教电话可一键拨打");
  check((await page.locator(".tbl tbody tr a[href^='mailto:']").count()) === 2, "助教邮箱可一键发信");
  await shot("42-course-ta");

  /* 打开编辑弹窗：回填 + 未修改时的按钮文案 */
  await page.locator(".cal-toolbar .btn", { hasText: "编辑助教信息" }).click();
  await page.waitForSelector(".modal-mask.show .ct-form", { timeout: 8000 });
  await page.waitForTimeout(400);
  check((await page.locator(".modal-mask.show .modal-head h2").innerText()).trim() === "助教与联系方式",
        "助教标签页可打开编辑弹窗");
  check((await page.locator(".modal-mask.show .ct-ta-item").count()) === 2, "助教编辑器回填 2 条");
  const taName0 = await page.locator(".modal-mask.show .ct-ta-item").first()
    .locator(".ct-f input").first().inputValue();
  check(taName0 === "李明", "助教姓名回填", taName0);
  check((await page.locator(".modal-mask.show .modal-actions .btn.primary").innerText()).trim() === "已是最新",
        "未修改助教时保存按钮显示已是最新");

  /* 新增一位助教（填满六项）并保存 */
  await page.locator(".modal-mask.show .ct-sec-head .btn", { hasText: "添加助教" }).click();
  await page.waitForTimeout(200);
  check((await page.locator(".modal-mask.show .ct-ta-item").count()) === 3, "添加助教后编辑器 3 条");
  const taFields = page.locator(".modal-mask.show .ct-ta-item").last().locator(".ct-f input");
  await taFields.nth(0).fill("e2e助教");
  await taFields.nth(1).fill("实验助教");
  await taFields.nth(2).fill("137 0000 9999");
  await taFields.nth(3).fill("e2e-ta@university.edu.cn");
  await taFields.nth(4).fill("999888777");
  await taFields.nth(5).fill("自动化验收创建");
  await shot("43-course-ta-edit");
  await page.locator(".modal-mask.show .modal-actions .btn.primary").click();
  await page.waitForSelector(".ct-form", { state: "detached", timeout: 8000 });
  await page.waitForTimeout(700);
  check((await page.locator(".tbl tbody tr").count()) === 3, "保存后详情页助教 3 位");
  check((await page.locator(".tbl tbody tr", { hasText: "e2e助教" }).count()) === 1, "新助教显示在详情页");

  /* 学生公开页同步（电话 / 邮箱链接、首页信息条计数） */
  {
    const token = courseLink.split("/c/")[1];
    const { p2 } = await openStudentPage(token);
    await p2.waitForSelector(".pub-tas", { timeout: 10000 });
    check((await p2.locator(".pub-ta").count()) === 3, "学生页同步展示 3 位助教");
    check((await p2.locator(".pub-ta", { hasText: "e2e助教" }).count()) === 1, "学生页出现新增助教");
    const telHref = await p2.locator(".pub-ta", { hasText: "e2e助教" })
      .locator("a[href^='tel:']").getAttribute("href");
    check(telHref === "tel:13700009999", "学生页电话链接去掉空格", telHref);
    check((await p2.locator(".pub-hero-chips").innerText()).indexOf("3 位助教") >= 0,
          "首页信息条显示助教人数");
    await p2.screenshot({ path: path.join(SHOT_DIR, "44-student-page-ta.png"), fullPage: true });
    await p2.close();
  }

  /* 删除刚新增的助教，还原演示数据 */
  await page.locator(".cal-toolbar .btn", { hasText: "编辑助教信息" }).click();
  await page.waitForSelector(".modal-mask.show .ct-form", { timeout: 8000 });
  await page.waitForTimeout(400);
  await page.locator(".modal-mask.show .ct-ta-item").last().locator(".ct-ta-top .icon-btn").click();
  await page.waitForTimeout(200);
  check((await page.locator(".modal-mask.show .ct-ta-item").count()) === 2, "删除助教后编辑器 2 条");
  await page.locator(".modal-mask.show .modal-actions .btn.primary").click();
  await page.waitForSelector(".ct-form", { state: "detached", timeout: 8000 });
  await page.waitForTimeout(500);
  check((await page.locator(".tbl tbody tr").count()) === 2, "还原：助教回到 2 位");

  /* ===================================================================== */
  console.log("\n== 2. 课程资料上传 / 下载 / 删除 ==");

  await page.locator(".tabs .tab", { hasText: "课程资料" }).click();
  await page.waitForSelector(".mat-head", { timeout: 10000 });
  const before = await page.locator(".file-item").count();
  check(before === 7, "种子资料 7 条", String(before));
  check((await page.locator(".file-item .badge", { hasText: "未上传文件" }).count()) === 5,
        "未上传文件标记 5 条");
  check((await page.locator(".mh-hint").innerText()).indexOf("已上传 2 份") >= 0,
        "头部统计已上传份数");

  const buf1 = Buffer.from("计算机网络 · 第 05 次作业\n1. RFC 5681\n2. cwnd 曲线\n", "utf8");
  const buf2 = Buffer.from("%PDF-1.4\n% e2e upload\n" + "x".repeat(2048), "utf8");
  await page.setInputFiles(".mat-head input[type=file]", [
    { name: "e2e-作业说明.txt", mimeType: "text/plain", buffer: buf1 },
    { name: "e2e-实验手册.pdf", mimeType: "application/pdf", buffer: buf2 },
  ]);
  await page.waitForFunction((n) => document.querySelectorAll(".file-item").length === n + 2,
    before, { timeout: 12000 });
  check(true, "上传 2 份资料后列表 +2");
  check((await page.locator(".file-item .badge.teal").count()) === 4, "新资料标记为可下载");
  check((await page.locator(".file-item", { hasText: "e2e-作业说明.txt" }).count()) === 1,
        "上传文件名正确显示");
  check((await page.locator(".mh-hint").innerText()).indexOf("已上传 4 份") >= 0,
        "头部统计更新为 4 份");
  const href = await page.locator(".file-item", { hasText: "e2e-实验手册.pdf" }).locator("a.icon-btn").getAttribute("href");
  check(/^\/api\/courses\/c1\/materials\/[^/]+\/download$/.test(href || ""), "下载链接指向教师接口", href);
  const dl = await page.request.get(BASE + href);
  check(dl.status() === 200 && (await dl.body()).length === buf2.length, "教师端下载内容一致");
  await shot("36-course-materials");

  /* 删除刚上传的一份 */
  await page.locator(".file-item", { hasText: "e2e-作业说明.txt" }).locator("button.icon-btn").click();
  await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
  check((await page.locator(".modal-mask.show").innerText()).indexOf("服务器上的文件将同时删除") >= 0,
        "删除弹窗说明文件同步删除");
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  await page.waitForFunction((n) => document.querySelectorAll(".file-item").length === n - 1,
    before + 2, { timeout: 10000 });
  check(true, "删除后列表 -1");
  await page.locator(".file-item", { hasText: "e2e-实验手册.pdf" }).locator("button.icon-btn").click();
  await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  await page.waitForFunction((n) => document.querySelectorAll(".file-item").length === n,
    before, { timeout: 10000 });
  check(true, "还原：资料回到 7 条");

  /* ===================================================================== */
  console.log("\n== 3. 开放设置弹窗 ==");

  await page.locator(".share-strip .ss-ops .btn").click();
  await page.waitForSelector(".cs-form", { timeout: 8000 });
  check((await page.locator(".cs-switch .css-text b").innerText()).indexOf("允许学生访问") >= 0,
        "开关显示当前为开放");
  check((await page.locator(".cs-preview").innerText()).indexOf("已开放") >= 0,
        "实时预览开放状态");
  check((await page.locator(".cs-link code").innerText()).trim() === courseLink,
        "弹窗内链接与状态条一致");
  check((await page.locator(".modal-actions .btn.primary").innerText()).indexOf("已是最新") >= 0,
        "未修改时按钮提示已是最新");
  await shot("37-course-share-modal");

  await page.locator(".cs-range-row input").nth(0).fill("2026-12-01");
  await page.waitForTimeout(150);
  check((await page.locator(".cs-preview").innerText()).indexOf("定时开放") >= 0,
        "设置未来起始日后预览变为定时开放");
  await page.locator(".cs-range-row input").nth(0).fill("2026-01-01");
  await page.locator(".cs-range-row input").nth(1).fill("2025-12-31");
  await page.locator(".modal-actions .btn.primary").click();
  /* 页面上可能残留上一条 toast，必须等「内容匹配」的那条出现 */
  const toastOk = await page.waitForFunction(() => {
    const t = document.querySelector(".toast");
    return !!t && t.innerText.indexOf("不能晚于") >= 0;
  }, { timeout: 6000 }).then(() => true).catch(() => false);
  check(toastOk && (await page.locator(".cs-form").count()) === 1, "日期倒置在弹窗内被拦截");
  await page.locator(".modal-actions .btn.ghost").click();
  await page.waitForSelector(".cs-form", { state: "detached", timeout: 8000 });
  check(true, "取消关闭弹窗");

  /* ===================================================================== */
  console.log("\n== 4. 关闭课程 → 学生不可见 ==");

  await setVisibility({ published: false, openFrom: "", openUntil: "" });
  check((await stripState()).indexOf("已关闭") >= 0, "教师端状态条变为已关闭", await stripState());
  check((await page.locator(".ss-hint").innerText()).indexOf("暂未开放") >= 0, "说明文案提示学生不可见");

  {
    const token = courseLink.split("/c/")[1];
    const { p2 } = await openStudentPage(token);
    await p2.waitForSelector(".pub-locked", { timeout: 10000 });
    check((await p2.locator(".pub-locked h1").innerText()).indexOf("暂未开放") >= 0,
          "学生页显示「课程暂未开放」");
    check((await p2.locator(".pub-lock-msg").innerText()).indexOf("请联系任课教师") >= 0,
          "学生页展示提示文案");
    check((await p2.locator(".pub-lock-course b").innerText()) === "计算机网络",
          "学生页仅回显课程名便于确认");
    check((await p2.locator(".pub-hero").count()) === 0, "关闭态不下发课程正文");
    await p2.screenshot({ path: path.join(SHOT_DIR, "38-student-page-closed.png") });
    await p2.close();
  }

  /* ===================================================================== */
  console.log("\n== 5. 定时开放 / 已过期 ==");

  await setVisibility({ published: true, openFrom: "2099-01-01", openUntil: "" });
  check((await stripState()).indexOf("定时开放") >= 0, "教师端状态条变为定时开放");
  {
    const token = courseLink.split("/c/")[1];
    const { p2 } = await openStudentPage(token);
    await p2.waitForSelector(".pub-locked", { timeout: 10000 });
    check((await p2.locator(".pub-locked h1").innerText()).indexOf("尚未开放") >= 0, "学生页显示未到开放时间");
    check((await p2.locator(".pub-lock-msg").innerText()).indexOf("2099-01-01") >= 0, "提示开放起始日期");
    await p2.close();
  }

  await setVisibility({ published: true, openFrom: "", openUntil: "2020-01-01" });
  check((await stripState()).indexOf("已结束") >= 0, "教师端状态条变为已结束");
  {
    const token = courseLink.split("/c/")[1];
    const { p2 } = await openStudentPage(token);
    await p2.waitForSelector(".pub-locked", { timeout: 10000 });
    check((await p2.locator(".pub-locked h1").innerText()).indexOf("已结束") >= 0, "学生页显示已结束开放");
    check((await p2.locator(".pub-lock-msg").innerText()).indexOf("2020-01-01") >= 0, "提示结束日期");
    await p2.close();
  }

  /* ===================================================================== */
  console.log("\n== 6. 恢复开放 → 学生页完整呈现 ==");

  await setVisibility({ published: true, openFrom: "", openUntil: "" });
  check((await stripState()).indexOf("已开放") >= 0, "还原为长期开放");

  {
    const token = courseLink.split("/c/")[1];
    const { p2, errs2 } = await openStudentPage(token);
    await p2.waitForSelector(".pub-hero", { timeout: 10000 });
    check((await p2.locator(".pub-hero h1").innerText()).trim() === "计算机网络", "学生页课程名正确");
    check((await p2.locator(".pub-hero-meta").innerText()).indexOf("江老师") >= 0, "学生页展示任课教师");
    check((await p2.locator(".pub-table:not(.cal-table) tbody tr").count()) === 8, "教学大纲 8 章");
    check((await p2.locator(".pub-file").count()) === 2, "学生页只列出可下载的 2 份资料");
    /* 教学日历与联系方式 */
    check((await p2.locator(".cal-table tbody tr").count()) === 14, "教学日历 14 周",
          String(await p2.locator(".cal-table tbody tr").count()));
    check((await p2.locator(".pub-h2-note", { hasText: "56 学时" }).count()) >= 1, "日历标题带学时合计");
    check((await p2.locator(".cal-flag", { hasText: "本周" }).count()) === 1, "高亮当前周");
    check((await p2.locator(".pub-qq").innerText()).indexOf("736285914") >= 0, "展示 QQ 群号");
    check((await p2.locator(".pub-qr img").count()) === 1, "展示群二维码");
    const qrResp = await ctx.request.get(BASE + "/api/public/courses/" + token + "/qr");
    check(qrResp.status() === 200 && (await qrResp.body()).length > 0, "群二维码公开接口可访问");
    /* 教师手机号（来自工作台资料）——助教卡也复用 .pub-contact，故按卡片精确定位 */
    check((await p2.locator(".pub-card:has(.pub-teacher) a[href^='tel:']").count()) === 1,
          "手机号可一键拨打");
    /* 课程助教：姓名 + 联系方式 */
    check((await p2.locator(".pub-ta").count()) === 2, "学生页展示 2 位助教");
    check((await p2.locator(".pub-ta", { hasText: "李明" }).count()) === 1, "学生页助教姓名");
    check((await p2.locator(".pub-ta .ta-head .pub-tag").count()) === 2, "学生页助教身份徽标");
    check((await p2.locator(".pub-ta a[href^='tel:']").count()) === 2, "学生页助教电话可拨打");
    check((await p2.locator(".pub-ta a[href^='mailto:']").count()) === 2, "学生页助教邮箱可发信");
    check((await p2.locator(".pub-ta .ta-note").count()) === 2, "学生页展示助教值班备注");
    check((await p2.locator(".ta-tip").count()) === 1, "学生页提示联系助教的场景");
    /* 二维码放大查看 */
    await p2.locator(".pub-qr").click();
    await p2.waitForTimeout(300);
    check((await p2.locator(".pub-zoom").count()) === 1, "二维码可放大查看");
    await p2.locator(".pub-zoom").click();
    await p2.waitForTimeout(200);
    check((await p2.locator(".pub-zoom").count()) === 0, "点击任意处关闭放大");
    check((await p2.locator(".pub-open-row b").innerText()).indexOf("已开放") >= 0, "侧栏开放状态卡");
    check((await p2.locator(".pub-teacher b").innerText()).indexOf("江老师") >= 0, "侧栏教师信息");

    /* 学生匿名下载 */
    const href2 = await p2.locator(".pub-file a.btn").first().getAttribute("href");
    check(href2.indexOf("/api/public/courses/") === 0, "下载链接走公开接口", href2);
    const dl2 = await ctx.request.get(BASE + href2);
    check(dl2.status() === 200 && (await dl2.body()).length > 0, "学生匿名下载成功");
    const resp2 = await ctx.request.get(BASE + "/api/public/courses/" + token);
    const body2 = await resp2.json();
    check(resp2.status() === 200 && !("published" in body2.data) && !("shareToken" in body2.data),
          "公开接口不泄漏教师私有字段");
    await p2.screenshot({ path: path.join(SHOT_DIR, "39-student-page-open.png"), fullPage: true });

    /* 学生页深色主题 */
    await p2.evaluate(() => localStorage.setItem("fwb-theme", "graphite"));
    await p2.reload({ waitUntil: "networkidle" });
    await p2.waitForSelector(".pub-hero", { timeout: 10000 });
    const bg = await p2.evaluate(() => getComputedStyle(document.body).backgroundColor);
    check(bg !== "rgb(241, 246, 242)", "学生页支持深色主题", bg);
    await p2.screenshot({ path: path.join(SHOT_DIR, "40-student-page-dark.png") });

    check(errs2.length === 0, "学生页无脚本错误", errs2.join("; ") || "");
    await p2.close();
  }

  /* ===================================================================== */
  console.log("\n== 7. 无效链接 ==");

  {
    const { p2 } = await openStudentPage("deadbeefdeadbeef");
    await p2.waitForSelector(".pub-locked", { timeout: 10000 });
    check((await p2.locator(".pub-locked h1").innerText()).indexOf("无效") >= 0, "无效令牌提示");
    await p2.close();
    const { p2: p3 } = await openStudentPage("zzz");
    await p3.waitForSelector(".pub-locked", { timeout: 10000 });
    check((await p3.locator(".pub-locked h1").innerText()).indexOf("无效") >= 0, "格式错误令牌提示");
    await p3.close();
  }

  check(realErrors().length === 0, "工作台控制台无真实报错", realErrors().join(" | ") || "");
  await shot("41-course-detail-final");

  /* ===================================================================== */
  console.log("\n----------------------------------------");
  console.log(`通过 ${pass} / ${pass + fail} 项`);
  if (failures.length) {
    console.log("失败项：");
    failures.forEach(f => console.log("  - " + f));
    process.exitCode = 1;
  }
  await browser.close();
})().catch(e => { console.error("FATAL:", e); process.exit(1); });
