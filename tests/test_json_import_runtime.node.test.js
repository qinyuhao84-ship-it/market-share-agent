const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const selfSource = fs.readFileSync(path.join(__dirname, "../frontend/modules/self_json_import/self_json_import.js"), "utf8");
const otherSource = fs.readFileSync(path.join(__dirname, "../frontend/modules/other_json_import/other_json_import.js"), "utf8");

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

function runImporter(source, payload, api, elements) {
  const document = {
    getElementById(id) {
      return elements.get(id) || null;
    },
    addEventListener() {},
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

  return context;
}

function loadSelfImporter(payload) {
  const elements = new Map([
    ["selfJsonImportModal", createElement()],
    ["selfJsonImportTextarea", createElement(JSON.stringify(payload))],
    ["selfJsonImportError", createElement()],
    ["selfJsonImportPreview", createElement()],
    ["company_name", createElement(payload.data.company_name)],
    ["product_name", createElement(payload.data.product_name)],
    ["product_code", createElement(payload.data.product_code)],
    ["template_type", createElement("self")],
    ["province", createElement("")],
  ]);

  const captured = {};
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

  const context = runImporter(selfSource, payload, api, elements);
  return {
    importer: context.window.ReportSelfJsonImport,
    captured,
    elements,
  };
}

function loadOtherImporter(payload, targets) {
  const elements = new Map([
    ["otherJsonImportModal", createElement()],
    ["otherJsonImportTextarea", createElement(JSON.stringify(payload))],
    ["otherJsonImportError", createElement()],
    ["otherJsonImportPreview", createElement()],
    ["company_name", createElement(payload.data.company_name)],
    ["product_name", createElement(payload.data.product_name)],
    ["template_type", createElement("other")],
  ]);

  const captured = {};
  const api = {
    getSelectedVersionTarget() {
      return { companyName: payload.data.company_name, versionNo: 1 };
    },
    getOtherCompanyProfileImportTargets() {
      return targets;
    },
    applyOtherCompanyProfilesImport(profiles) {
      captured.appliedProfiles = profiles;
    },
    saveDraft() {
      captured.saveDraftCalled = true;
      return Promise.resolve(true);
    },
    setStatus(message) {
      captured.status = message;
    },
  };

  const context = runImporter(otherSource, payload, api, elements);
  return {
    importer: context.window.ReportOtherJsonImport,
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

  const { importer, captured } = loadSelfImporter(payload);
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

test("他证 JSON 导入会按网站顺序填入第三章企业信息并保存", async () => {
  const payload = {
    schema_version: "other_company_profiles_import_v1",
    payload_type: "other_company_profiles",
    status: "ready",
    blocking_reasons: [],
    data: {
      company_name: "浙江达航数据技术有限公司",
      product_name: "高安全性自锁紧型电源连接系统",
      companies: [
        {
          requested_name: "浙江达航数据技术有限公司",
          company_name: "浙江达航数据技术有限公司",
          company_url: "https://www.qcc.com/firm/example-self",
          registered_capital: "5188万元",
          established_date: "2021-10-19",
          legal_representative: "沈某",
          company_address: "浙江省宁波市慈溪市观海卫镇师东村",
          main_business: "电源连接系统研发制造",
        },
        {
          requested_name: "北京鼎汉技术集团股份有限公司",
          company_name: "北京鼎汉技术集团股份有限公司",
          company_url: "https://www.qcc.com/firm/example-a",
          registered_capital: "6.56亿元",
          established_date: "2002-01-18",
          legal_representative: "王某",
          company_address: "北京市丰台区",
          main_business: "轨道交通信号和供电设备研发制造",
        },
        {
          requested_name: "杭州高特电子设备股份有限公司",
          company_name: "杭州高特电子设备股份有限公司",
          company_url: "https://www.aqicha.baidu.com/company_detail_example-b",
          registered_capital: "5000万元",
          established_date: "2004-05-06",
          legal_representative: "李某",
          company_address: "浙江省杭州市",
          main_business: "电子设备研发制造",
        },
      ],
    },
  };

  const targets = [
    { requested_name: "浙江达航数据技术有限公司", is_self: true },
    { requested_name: "北京鼎汉技术集团股份有限公司", is_self: false },
    { requested_name: "杭州高特电子设备股份有限公司", is_self: false },
  ];

  const { importer, captured } = loadOtherImporter(payload, targets);
  await importer.importFromTextarea();

  assert.equal(captured.saveDraftCalled, true);
  assert.equal(captured.status, "他证第三章企业基本信息 JSON 已导入并保存，请核对字段");
  assert.equal(captured.appliedProfiles.length, 3);
  assert.equal(captured.appliedProfiles[0].requested_name, "浙江达航数据技术有限公司");
  assert.equal(captured.appliedProfiles[1].requested_name, "北京鼎汉技术集团股份有限公司");
  assert.equal(captured.appliedProfiles[2].requested_name, "杭州高特电子设备股份有限公司");
  assert.equal(captured.appliedProfiles[0].company_url, "");
});

test("他证 JSON 顺序错误时会失败且不保存", async () => {
  const payload = {
    schema_version: "other_company_profiles_import_v1",
    payload_type: "other_company_profiles",
    status: "ready",
    blocking_reasons: [],
    data: {
      company_name: "浙江达航数据技术有限公司",
      product_name: "高安全性自锁紧型电源连接系统",
      companies: [
        {
          requested_name: "浙江达航数据技术有限公司",
          company_name: "浙江达航数据技术有限公司",
          company_url: "https://www.qcc.com/firm/example-self",
          registered_capital: "5188万元",
          established_date: "2021-10-19",
          legal_representative: "沈某",
          company_address: "浙江省宁波市慈溪市观海卫镇师东村",
          main_business: "电源连接系统研发制造",
        },
        {
          requested_name: "杭州高特电子设备股份有限公司",
          company_name: "杭州高特电子设备股份有限公司",
          company_url: "https://www.aqicha.baidu.com/company_detail_example-b",
          registered_capital: "5000万元",
          established_date: "2004-05-06",
          legal_representative: "李某",
          company_address: "浙江省杭州市",
          main_business: "电子设备研发制造",
        },
        {
          requested_name: "北京鼎汉技术集团股份有限公司",
          company_name: "北京鼎汉技术集团股份有限公司",
          company_url: "https://www.qcc.com/firm/example-a",
          registered_capital: "6.56亿元",
          established_date: "2002-01-18",
          legal_representative: "王某",
          company_address: "北京市丰台区",
          main_business: "轨道交通信号和供电设备研发制造",
        },
      ],
    },
  };

  const targets = [
    { requested_name: "浙江达航数据技术有限公司", is_self: true },
    { requested_name: "北京鼎汉技术集团股份有限公司", is_self: false },
    { requested_name: "杭州高特电子设备股份有限公司", is_self: false },
  ];

  const { importer, captured, elements } = loadOtherImporter(payload, targets);
  await importer.importFromTextarea();

  assert.equal(captured.saveDraftCalled, undefined);
  assert.equal(captured.appliedProfiles, undefined);
  assert.match(elements.get("otherJsonImportError").textContent, /requested_name 必须与网站当前顺序一致/);
});

test("他证 JSON 缺失字段时会失败且不保存", async () => {
  const payload = {
    schema_version: "other_company_profiles_import_v1",
    payload_type: "other_company_profiles",
    status: "ready",
    blocking_reasons: [],
    data: {
      company_name: "浙江达航数据技术有限公司",
      product_name: "高安全性自锁紧型电源连接系统",
      companies: [
        {
          requested_name: "浙江达航数据技术有限公司",
          company_name: "浙江达航数据技术有限公司",
          company_url: "https://www.qcc.com/firm/example-self",
          registered_capital: "5188万元",
          established_date: "2021-10-19",
          legal_representative: "沈某",
          company_address: "浙江省宁波市慈溪市观海卫镇师东村",
          main_business: "电源连接系统研发制造",
        },
        {
          requested_name: "北京鼎汉技术集团股份有限公司",
          company_name: "北京鼎汉技术集团股份有限公司",
          company_url: "https://www.qcc.com/firm/example-a",
          registered_capital: "6.56亿元",
          established_date: "2002-01-18",
          legal_representative: "王某",
          company_address: "北京市丰台区",
          main_business: "",
        },
        {
          requested_name: "杭州高特电子设备股份有限公司",
          company_name: "杭州高特电子设备股份有限公司",
          company_url: "https://www.aqicha.baidu.com/company_detail_example-b",
          registered_capital: "5000万元",
          established_date: "2004-05-06",
          legal_representative: "李某",
          company_address: "浙江省杭州市",
          main_business: "电子设备研发制造",
        },
      ],
    },
  };

  const targets = [
    { requested_name: "浙江达航数据技术有限公司", is_self: true },
    { requested_name: "北京鼎汉技术集团股份有限公司", is_self: false },
    { requested_name: "杭州高特电子设备股份有限公司", is_self: false },
  ];

  const { importer, captured, elements } = loadOtherImporter(payload, targets);
  await importer.importFromTextarea();

  assert.equal(captured.saveDraftCalled, undefined);
  assert.equal(captured.appliedProfiles, undefined);
  assert.match(elements.get("otherJsonImportError").textContent, /main_business 不能为空/);
});
