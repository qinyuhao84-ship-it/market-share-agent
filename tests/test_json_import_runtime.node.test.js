const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../frontend/modules/json_import/json_import.js"), "utf8");

function createClassList() {
  const classes = new Set();
  return {
    add(...items) {
      items.forEach((item) => classes.add(item));
    },
    remove(...items) {
      items.forEach((item) => classes.delete(item));
    },
    contains(item) {
      return classes.has(item);
    },
    toArray() {
      return Array.from(classes);
    },
  };
}

function createElement(initialValue = "") {
  return {
    value: initialValue,
    textContent: "",
    className: "",
    innerHTML: "",
    classList: createClassList(),
    addEventListener() {},
    focus() {},
  };
}

function loadImporter(payload) {
  const elements = new Map([
    ["jsonImportModal", createElement()],
    ["jsonImportTextarea", createElement(JSON.stringify(payload))],
    ["jsonImportError", createElement()],
    ["jsonImportPreview", createElement()],
    ["company_name", createElement(payload.data.company_name)],
    ["product_name", createElement(payload.data.product_name)],
    ["product_code", createElement(payload.data.product_code)],
    ["template_type", createElement("self")],
    ["province", createElement("")],
  ]);

  const captured = {};
  const document = {
    getElementById(id) {
      return elements.get(id) || null;
    },
    addEventListener() {},
  };

  const api = {
    getSelectedVersionTarget() {
      return { companyName: payload.data.company_name, versionNo: 1 };
    },
    fillFormFromExtractedData(data, options = {}) {
      captured.data = data;
      captured.options = options;
    },
    resetOtherCompanyLookupState() {},
    saveDraft() {
      captured.saveDraftCalled = true;
      return Promise.resolve(true);
    },
    setStatus(message) {
      captured.status = message;
    },
    clearCompetitorsForImport() {},
    addCompetitorRow() {},
    refreshCompetitorBoard() {},
  };

  const context = {
    window: null,
    globalThis: null,
    document,
    console,
    URL,
    setTimeout(fn) {
      fn();
      return 0;
    },
    clearTimeout() {},
    ReportAutomationFormApi: api,
  };
  context.window = context;
  context.globalThis = context;

  vm.runInNewContext(source, context, { filename: "json_import.js" });

  return {
    importer: context.window.ReportJsonImport,
    captured,
    elements,
  };
}

test("JSON 导入会把日期月份去前导 0，并把 Markdown 来源网址还原成纯 URL", async () => {
  const payload = {
    schema_version: "self_proof_import_v1",
    payload_type: "self_proof",
    status: "ready",
    blocking_reasons: [],
    data: {
      company_name: "南京金星宇节能技术有限公司",
      product_name: "环境自适应智能动态调控遮阳一体化装置",
      product_code: "3699010000",
      report_date: "2026-05-08",
      target_scope: "CN",
      company_intro: "企业介绍",
      product_intro: "产品介绍",
      business: {
        sales_wan: {
          "2023": "7577.15",
          "2024": "9395.94",
          "2025": "10124.23",
        },
      },
      sources: [
        {
          source_names: ["全球自动遮阳系统行业总体规模、主要厂商及IPO上市调研报告，2025-2031"],
          source_urls: [
            "[https://www.globalinforesearch.com.cn/reports/2227607/automated-shading-system](https://www.globalinforesearch.com.cn/reports/2227607/automated-shading-system)",
          ],
          chart_title_suffix: "2023-2025年全球自动遮阳系统市场规模（亿元）",
          market_size_yi: {
            "2023": "22.91",
            "2024": "24.01",
            "2025": "25.19",
          },
          analysis_text: "根据公开报告整理的说明文本。",
        },
      ],
    },
  };

  const { importer, captured } = loadImporter(payload);
  await importer.importFromTextarea();

  assert.equal(captured.data.year, "2026");
  assert.equal(captured.data.month, "5");
  assert.equal(captured.data.day, "8");
  assert.equal(
    captured.data.sources[0].url,
    "https://www.globalinforesearch.com.cn/reports/2227607/automated-shading-system"
  );
  assert.equal(
    captured.data.sources[0].urls[0],
    "https://www.globalinforesearch.com.cn/reports/2227607/automated-shading-system"
  );
  assert.equal(captured.options.keepBlankCompetitorRow, false);
  assert.equal(captured.saveDraftCalled, true);
  assert.equal(captured.status, "自证 JSON 已导入并保存，请核对字段");
});
