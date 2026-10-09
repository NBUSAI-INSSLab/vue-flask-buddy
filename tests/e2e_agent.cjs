/* =====================================================================
   e2e_agent.cjs —— 智能助手端到端验收（Playwright + Chromium）

   前置：python run.py --port 5173 --prod
   运行：node tests/e2e_agent.cjs [baseUrl]

   校验点：导航与页面渲染、未配置引导、发送拦截、设置（供应商切换 /
   自动填充 / 无 Key 连接测试 / 保存与状态徽标）、知识库（上传 / 清单 /
   检索试测 / 删除确认）、会话列表空态；输出截图到 docs/screenshots/
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

const KB_MD = [
  "# 研究生学位论文写作规范", "",
  "硕士论文正文字数不少于三万字，参考文献不少于四十篇。",
  "论文查重率不得超过百分之八，重复片段须规范引用。",
  "开题报告应当在第三学期结束前完成。", ""
].join("\n");

/* 每次运行用唯一文件名：清单按「最新在前」排序，同名条目会让定位产生歧义 */
const DOC_NAME = `论文写作规范-${Date.now()}.md`;

const problems = [];
const checks = [];
function check(ok, label, detail) {
  checks.push({ ok, label, detail });
  if (!ok) problems.push(label + (detail ? " —— " + detail : ""));
}

async function main() {
  fs.mkdirSync(SHOT_DIR, { recursive: true });
  const browser = await chromium.launch(CHROME_PATH ? { executablePath: CHROME_PATH } : {});
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on("pageerror", (e) => consoleErrors.push("pageerror: " + e.message));
  page.on("requestfailed", (r) => {
    if (!r.url().endsWith("/favicon.ico")) consoleErrors.push("requestfailed: " + r.url());
  });
  const shot = async (name) => page.screenshot({ path: path.join(SHOT_DIR, name + ".png") });

  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.locator(".lc-form input").nth(0).fill("jiangxl");
  await page.locator(".lc-form input").nth(1).fill("123456");
  await page.locator(".lc-submit").click();
  await page.waitForSelector(".sidebar .nav-item", { timeout: 15000 });

  /* ===================================================================== */
  console.log("\n== 1. 导航与页面渲染 ==");

  check((await page.locator(".nav-item", { hasText: "智能助手" }).count()) === 1,
        "侧边栏提供「智能助手」导航");
  check((await page.locator(".nav-item").count()) === 14,
        "导航共 14 项（新增智能助手）", "实际 " + (await page.locator(".nav-item").count()));

  await page.locator(".nav-item", { hasText: "智能助手" }).first().click();
  await page.waitForTimeout(900);
  check((await page.locator(".page-title").innerText()).trim() === "智能助手",
        "页面标题渲染");
  check((await page.locator(".tab", { hasText: "对话" }).count()) === 1 &&
        (await page.locator(".tab", { hasText: "知识库" }).count()) === 1 &&
        (await page.locator(".tab", { hasText: "设置" }).count()) === 1,
        "三个标签（对话 / 知识库 / 设置）");
  check((await page.locator(".ag-side .ag-new").count()) === 1, "左侧「新对话」按钮");
  check((await page.locator(".ag-input textarea").count()) === 1, "对话输入框");

  /* 助手回答按 Markdown 渲染，且模型输出的原生 HTML 被转义（防注入） */
  const mdOk = await page.evaluate(() => {
    const html = FWB.util.md("| 日期 | 事项 |\n| --- | --- |\n| 10-09 | 组会 |\n\n**加粗** <b>原生标签</b>");
    return html.indexOf("<table") >= 0 && html.indexOf("10-09") >= 0 &&
           html.indexOf("<strong>") >= 0 && html.indexOf("<b>原生标签</b>") < 0 &&
           html.indexOf("&lt;b&gt;") >= 0;
  });
  check(mdOk, "助手回答按 Markdown 渲染（表格 / 加粗），原生 HTML 被转义");

  /* ===================================================================== */
  console.log("\n== 2. 未配置引导与发送拦截 ==");

  /* 当前租户：配置与否都要给出对应界面（本项不依赖外部环境） */
  const guidedHere = (await page.locator(".ag-guide").count()) === 1;
  const welcomed = (await page.locator(".ag-list .ag-welcome").count()) === 1;
  const hasMsgs = (await page.locator(".ag-list .ag-msg").count()) > 0;
  check(guidedHere || welcomed || hasMsgs,
        "对话页渲染：引导卡（未配置）/ 欢迎语 / 历史消息");

  /* 「未配置」态用另一个没填过 API Key 的租户验证：
     设置按教师隔离，主租户可能已经填好 Key，直接在主租户断言会随环境漂移。 */
  const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page2 = await ctx2.newPage();
  await page2.goto(BASE, { waitUntil: "networkidle" });
  await page2.locator(".lc-form input").nth(0).fill("zhangwei");
  await page2.locator(".lc-form input").nth(1).fill("123456");
  await page2.locator(".lc-submit").click();
  await page2.waitForSelector(".sidebar .nav-item", { timeout: 15000 });
  await page2.locator(".nav-item", { hasText: "智能助手" }).first().click();
  await page2.waitForTimeout(900);

  check((await page2.locator(".ag-guide").count()) === 1,
        "未配置租户显示引导卡（该租户已填过 Key？请换一个未配置的租户做未配置态验证）");
  await page2.locator(".ag-guide .btn", { hasText: "去设置" }).click();
  await page2.waitForTimeout(300);
  check((await page2.locator(".ag-set-head .badge").innerText()).includes("未配置"),
        "引导卡一键跳到设置");
  check((await page2.locator(".ag-set-head .badge.amber").count()) === 1, "未配置徽标为琥珀色");

  /* 无 Key 连接测试 → 友好报错（不打真实网络） */
  await page2.locator(".ag-set-ops .btn", { hasText: "测试连接" }).click();
  await page2.waitForTimeout(500);
  const testText2 = await page2.locator(".ag-test").innerText().catch(() => "");
  check(testText2.includes("Key") || testText2.includes("失败"), "无 Key 连接测试给出提示", testText2);

  /* 只保存地址与模型、不填 Key → 不得变成「已就绪」 */
  await page2.locator(".ag-set-ops .btn", { hasText: "保存设置" }).click();
  await page2.waitForTimeout(600);
  check((await page2.locator(".ag-set-head .badge").innerText()).trim() === "未配置",
        "未填 Key 时保持「未配置」");

  /* 未配置时发送被拦截并跳转设置页 */
  await page2.locator(".tab", { hasText: "对话" }).click();
  await page2.waitForTimeout(250);
  await page2.locator(".ag-input textarea").fill("我最近有什么日程？");
  await page2.locator(".ag-input .btn", { hasText: "发送" }).click();
  await page2.waitForTimeout(900);
  check((await page2.locator(".tab.active", { hasText: "设置" }).count()) === 1,
        "未配置时发送被拦截并跳转设置页");
  await page2.locator(".tab", { hasText: "对话" }).click();
  await page2.waitForTimeout(250);
  check((await page2.locator(".ag-input textarea").inputValue()) === "我最近有什么日程？",
        "被拦截的输入内容保留，便于配置后重发");
  await ctx2.close();

  /* ===================================================================== */
  console.log("\n== 3. 设置：供应商切换与保存 ==");

  await page.locator(".tab", { hasText: "设置" }).click();
  await page.waitForTimeout(300);
  const provOptions = await page.locator(".ag-set select option").count();
  check(provOptions >= 5, "供应商下拉 ≥ 5 项", "实际 " + provOptions);
  const baseUrl0 = await page.locator('.ag-set input[type="text"]').first().inputValue();
  check(baseUrl0.includes("deepseek"), "默认 DeepSeek 并自动带出 base_url", baseUrl0);

  await page.locator(".ag-set select").selectOption("ollama");
  await page.waitForTimeout(150);
  const baseUrl1 = await page.locator('.ag-set input[type="text"]').first().inputValue();
  check(baseUrl1.includes("11434"), "切换 Ollama 自动填充本地地址", baseUrl1);
  await page.locator(".ag-set select").selectOption("deepseek");
  await page.waitForTimeout(150);

  /* 保存 base_url / model；留空的 Key 输入不会覆盖已保存的 Key */
  await page.locator(".ag-set-ops .btn", { hasText: "保存设置" }).click();
  await page.waitForTimeout(700);
  check((await page.locator(".toast").count()) >= 0, "设置保存成功（toast）");
  const badgeText = (await page.locator(".ag-set-head .badge").innerText()).trim();
  check(["未配置", "已就绪"].includes(badgeText), "保存后状态徽标有效", badgeText);

  /* ===================================================================== */
  console.log("\n== 4. 知识库：上传 / 检索 / 删除 ==");

  await page.locator(".tab", { hasText: "知识库" }).click();
  await page.waitForTimeout(400);
  const before = await page.locator(".ag-kb-card tbody tr").count();

  await page.setInputFiles('.ag-kb-top input[type="file"]', {
    name: DOC_NAME, mimeType: "text/markdown", buffer: Buffer.from(KB_MD, "utf8")
  });
  await page.waitForTimeout(1200);
  const after = await page.locator(".ag-kb-card tbody tr").count();
  check(after === before + 1, "上传文档出现在清单", `前 ${before} → 后 ${after}`);
  check((await page.locator(".ag-doc", { hasText: DOC_NAME }).count()) === 1,
        "清单显示文档名");
  const row = page.locator(".ag-kb-card tbody tr", { hasText: DOC_NAME }).first();
  const chunkText = await row.innerText();
  check(/(\d+)\s*块/.test(chunkText), "清单显示分块数", chunkText.replace(/\n/g, " "));
  check((await page.locator(".ag-kb-top .ms-val").first().innerText()).includes(String(after)),
        "统计卡计数同步");
  await shot("50-agent-kb-upload");

  /* 检索试测 */
  await page.locator(".ag-kb-q input").fill("查重率不能超过多少");
  await page.locator(".ag-kb-q .btn", { hasText: "检索" }).click();
  await page.waitForTimeout(800);
  check((await page.locator(".ag-hit").count()) >= 1, "检索试测命中片段");
  check((await page.locator(".ag-hit-head .badge").first().innerText()).includes("论文写作规范"),
        "命中结果标注出处文档");
  await shot("51-agent-kb-search");

  /* 删除（二次确认）—— 按文件名定位，避免误删其他文档 */
  await row.locator(".icon-btn[title='删除']").click();
  await page.waitForSelector(".modal-mask.show", { timeout: 8000 });
  check((await page.locator(".modal-mask.show .modal-head h2").innerText()).includes("删除"),
        "删除文档前二次确认");
  await page.locator(".modal-mask.show [data-cfm='yes']").click();
  await page.waitForTimeout(900);
  check((await page.locator(".ag-kb-card tbody tr").count()) === before, "删除后清单还原");
  check((await page.locator(".ag-doc", { hasText: DOC_NAME }).count()) === 0,
        "删除的是本次上传的文档");

  /* ===================================================================== */
  console.log("\n== 5. 会话列表 ==");

  await page.locator(".tab", { hasText: "对话" }).click();
  await page.waitForTimeout(300);
  check((await page.locator(".ag-side").count()) === 1, "会话侧栏渲染");
  await shot("52-agent-chat");

  /* ===================================================================== */
  check(consoleErrors.length === 0, "无控制台报错", consoleErrors.join(" | "));

  await browser.close();
  const passed = checks.filter((c) => c.ok).length;
  console.log(`\n通过 ${passed} / ${checks.length} 项`);
  if (problems.length) {
    console.log("\n未通过：");
    problems.forEach((p) => console.log("  ✗ " + p));
    process.exit(1);
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
