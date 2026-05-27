(function (root) {
  const MODAL_ID = "jsonImportModal";
  const TEXTAREA_ID = "jsonImportTextarea";
  const ERROR_ID = "jsonImportError";
  const PREVIEW_ID = "jsonImportPreview";

  function getApi() {
    const api = root.ReportAutomationFormApi;
    if (!api) {
      throw new Error("页面表单能力未初始化，请刷新页面");
    }
    return api;
  }

  function getElement(id) {
    const el = document.getElementById(id);
    if (!el) {
      throw new Error(`页面缺少必要元素：${id}`);
    }
    return el;
  }

  function trimText(value) {
    return String(value ?? "").trim();
  }

  function isPlainObject(value) {
    return !!value && typeof value === "object" && !Array.isArray(value);
  }

  function setError(message) {
    const el = getElement(ERROR_ID);
    const text = trimText(message);
    el.textContent = text;
    el.className = text ? "json-import-error active" : "json-import-error";
  }

  function setPreview(message, tone = "muted") {
    const el = getElement(PREVIEW_ID);
    const text = trimText(message);
    if (!text) {
      el.textContent = "";
      el.className = "json-import-preview";
      return;
    }
    el.textContent = text;
    el.className = tone && tone !== "muted" ? `json-import-preview json-import-${tone}` : "json-import-preview";
  }

  function clearFeedback() {
    setError("");
    setPreview("等待粘贴 JSON");
  }

  function openImportModal() {
    const api = getApi();
    const templateType = trimText(document.getElementById("template_type")?.value || "self");
    const modal = getElement(MODAL_ID);
    const textarea = getElement(TEXTAREA_ID);
    textarea.value = "";
    modal.classList.add("open");
    clearFeedback();

    const target = api.getSelectedVersionTarget();
    if (templateType === "other") {
      setError("请先切换到自证模板再导入 JSON");
      setPreview("当前模板不是自证，导入已阻止", "error");
      window.setTimeout(() => {
        textarea.focus();
      }, 0);
      return;
    }
    if (!target) {
      setError("请先选择企业和版本，再导入 JSON");
      setPreview("先选企业和版本，再导入", "error");
      window.setTimeout(() => {
        textarea.focus();
      }, 0);
      return;
    }

    window.setTimeout(() => {
      textarea.focus();
    }, 0);
  }

  function closeImportModal() {
    const modal = getElement(MODAL_ID);
    modal.classList.remove("open");
    const textarea = getElement(TEXTAREA_ID);
    textarea.value = "";
    clearFeedback();
  }

  function parseJsonInput(rawText) {
    const text = trimText(rawText);
    if (!text) {
      throw new Error("请先粘贴 JSON");
    }
    return JSON.parse(text);
  }

  function requireObject(value, label) {
    if (!isPlainObject(value)) {
      throw new Error(`${label} 必须是对象`);
    }
    return value;
  }

  function requireArray(value, label) {
    if (!Array.isArray(value)) {
      throw new Error(`${label} 必须是数组`);
    }
    return value;
  }

  function requireString(value, label) {
    const text = trimText(value);
    if (!text) {
      throw new Error(`${label} 不能为空`);
    }
    return text;
  }

  function requireNumericText(value, label) {
    const text = trimText(value).replace(/,/g, "");
    if (!text) {
      throw new Error(`${label} 不能为空`);
    }
    if (!Number.isFinite(Number(text))) {
      throw new Error(`${label} 必须是数字`);
    }
    if (text.includes("%")) {
      throw new Error(`${label} 不能带百分号`);
    }
    return text;
  }

  function parseReportDate(rawDate) {
    const text = requireString(rawDate, "report_date");
    const match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) {
      throw new Error("report_date 必须是 YYYY-MM-DD");
    }
    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    const date = new Date(Date.UTC(year, month - 1, day));
    if (
      date.getUTCFullYear() !== year ||
      date.getUTCMonth() + 1 !== month ||
      date.getUTCDate() !== day
    ) {
      throw new Error("report_date 不是有效日期");
    }
    return { year: match[1], month: match[2], day: match[3], text };
  }

  function normalizePercent(rawValue, label) {
    const text = requireString(rawValue, label).replace(/,/g, "");
    const numeric = Number(text.replace(/%/g, ""));
    if (!Number.isFinite(numeric)) {
      throw new Error(`${label} 必须是数字或百分比`);
    }
    const percent = text.includes("%") ? numeric : numeric <= 1 ? numeric * 100 : numeric;
    return `${(Math.round(percent * 100) / 100).toFixed(2)}%`;
  }

  function normalizeSourceBlock(source, index) {
    const item = requireObject(source, `sources[${index}]`);
    const sourceNames = requireArray(item.source_names, `sources[${index}].source_names`)
      .map((value, innerIndex) => requireString(value, `sources[${index}].source_names[${innerIndex}]`));
    const sourceUrls = requireArray(item.source_urls, `sources[${index}].source_urls`)
      .map((value, innerIndex) => requireString(value, `sources[${index}].source_urls[${innerIndex}]`));
    if (!sourceNames.length) {
      throw new Error(`sources[${index}].source_names 不能为空`);
    }
    if (!sourceUrls.length) {
      throw new Error(`sources[${index}].source_urls 不能为空`);
    }
    if (sourceNames.length !== sourceUrls.length) {
      throw new Error(`sources[${index}] 的来源名称和来源网址数量必须一致`);
    }

    const chartTitleSuffix = requireString(item.chart_title_suffix, `sources[${index}].chart_title_suffix`);
    if (/^图表\s*\d+/.test(chartTitleSuffix)) {
      throw new Error(`sources[${index}].chart_title_suffix 不要包含图表编号`);
    }

    const marketSize = requireObject(item.market_size_yi, `sources[${index}].market_size_yi`);
    const chart2023 = requireNumericText(marketSize["2023"], `sources[${index}].market_size_yi.2023`);
    const chart2024 = requireNumericText(marketSize["2024"], `sources[${index}].market_size_yi.2024`);
    const chart2025 = requireNumericText(marketSize["2025"], `sources[${index}].market_size_yi.2025`);
    const analysisText = requireString(item.analysis_text, `sources[${index}].analysis_text`);

    return {
      name: sourceNames[0],
      names: sourceNames,
      url: sourceUrls[0],
      urls: sourceUrls,
      chart_title: `图表${index + 1}：${chartTitleSuffix}`,
      chart_2023: chart2023,
      chart_2024: chart2024,
      chart_2025: chart2025,
      analysis: analysisText,
    };
  }

  function normalizeSelfPayload(payload) {
    if (!isPlainObject(payload)) {
      throw new Error("JSON 顶层必须是对象");
    }
    if (trimText(payload.schema_version) !== "self_proof_import_v1") {
      throw new Error("schema_version 必须是 self_proof_import_v1");
    }
    if (trimText(payload.payload_type) !== "self_proof") {
      throw new Error("payload_type 必须是 self_proof");
    }

    const status = trimText(payload.status);
    const blockingReasons = requireArray(payload.blocking_reasons, "blocking_reasons")
      .map((item) => trimText(item))
      .filter(Boolean);
    if (status !== "ready") {
      if (status === "blocked") {
        throw new Error(`ChatGPT 返回 blocked，不能导入。\n${blockingReasons.length ? blockingReasons.join("\n") : "blocking_reasons 为空"}`);
      }
      throw new Error(`status 必须是 ready，当前是 ${status || "空"}`);
    }
    if (blockingReasons.length) {
      throw new Error("status 为 ready 时 blocking_reasons 必须为空");
    }

    const data = requireObject(payload.data, "data");
    const companyName = requireString(data.company_name, "企业名称");
    const productName = requireString(data.product_name, "主导产品名称");
    const productCode = requireString(data.product_code, "产品代码");
    const reportDate = parseReportDate(data.report_date);
    const targetScope = requireString(data.target_scope, "市场范围");
    if (targetScope !== "CN" && targetScope !== "GLOBAL") {
      throw new Error("市场范围只能是 CN 或 GLOBAL");
    }
    const companyIntro = requireString(data.company_intro, "企业介绍");
    const productIntro = requireString(data.product_intro, "产品介绍");

    const business = requireObject(data.business, "data.business");
    const salesWan = requireObject(business.sales_wan, "data.business.sales_wan");
    const sale23 = requireNumericText(salesWan["2023"], "data.business.sales_wan.2023");
    const sale24 = requireNumericText(salesWan["2024"], "data.business.sales_wan.2024");
    const sale25 = requireNumericText(salesWan["2025"], "data.business.sales_wan.2025");

    const sources = requireArray(data.sources, "sources");
    if (!sources.length) {
      throw new Error("sources 至少需要 1 层");
    }
    const normalizedSources = sources.map((source, index) => normalizeSourceBlock(source, index));

    return {
      company_name: companyName,
      product_name: productName,
      product_code: productCode,
      report_date: reportDate.text,
      target_scope: targetScope,
      company_intro: companyIntro,
      product_intro: productIntro,
      sale_23: sale23,
      sale_24: sale24,
      sale_25: sale25,
      sources: normalizedSources,
    };
  }

  function normalizeCompetitorPayload(payload) {
    if (!isPlainObject(payload)) {
      throw new Error("JSON 顶层必须是对象");
    }
    if (trimText(payload.schema_version) !== "competitors_import_v1") {
      throw new Error("schema_version 必须是 competitors_import_v1");
    }
    if (trimText(payload.payload_type) !== "competitors") {
      throw new Error("payload_type 必须是 competitors");
    }

    const status = trimText(payload.status);
    const blockingReasons = requireArray(payload.blocking_reasons, "blocking_reasons")
      .map((item) => trimText(item))
      .filter(Boolean);
    if (status !== "ready") {
      if (status === "blocked") {
        throw new Error(`ChatGPT 返回 blocked，不能导入。\n${blockingReasons.length ? blockingReasons.join("\n") : "blocking_reasons 为空"}`);
      }
      throw new Error(`status 必须是 ready，当前是 ${status || "空"}`);
    }
    if (blockingReasons.length) {
      throw new Error("status 为 ready 时 blocking_reasons 必须为空");
    }

    const data = requireObject(payload.data, "data");
    const companyName = requireString(data.company_name, "企业名称");
    const productName = requireString(data.product_name, "主导产品名称");
    const competitors = requireArray(data.competitors, "competitors");
    if (!competitors.length) {
      throw new Error("competitors 至少需要 1 家企业");
    }

    const normalizedCompetitors = competitors.map((item, index) => {
      const competitor = requireObject(item, `competitors[${index}]`);
      const competitorName = requireString(competitor.company_name, `competitors[${index}].company_name`);
      if (competitorName === companyName) {
        throw new Error(`competitors[${index}].company_name 不能等于申报企业名称`);
      }
      const marketShare = requireObject(competitor.market_share, `competitors[${index}].market_share`);
      return {
        company_name: competitorName,
        market_share: {
          "2023": normalizePercent(marketShare["2023"], `competitors[${index}].market_share.2023`),
          "2024": normalizePercent(marketShare["2024"], `competitors[${index}].market_share.2024`),
          "2025": normalizePercent(marketShare["2025"], `competitors[${index}].market_share.2025`),
        },
      };
    });

    return {
      company_name: companyName,
      product_name: productName,
      competitors: normalizedCompetitors,
    };
  }

  function ensureSelectedVersionMatches(expectedCompanyName) {
    const api = getApi();
    const target = api.getSelectedVersionTarget();
    if (!target) {
      throw new Error("请先选择企业和版本，再导入 JSON");
    }
    if (target.companyName !== expectedCompanyName) {
      throw new Error("JSON 企业名称与当前版本企业不一致，请先切换到正确版本");
    }
    return target;
  }

  function ensureCurrentValueMatches(fieldId, expectedValue, label) {
    const current = trimText(document.getElementById(fieldId)?.value || "");
    if (current && current !== expectedValue) {
      throw new Error(`${label} 与当前页面不一致，请先切换到正确版本`);
    }
  }

  function applySelfProofImport(normalized) {
    const api = getApi();
    ensureSelectedVersionMatches(normalized.company_name);
    ensureCurrentValueMatches("company_name", normalized.company_name, "企业名称");
    ensureCurrentValueMatches("product_name", normalized.product_name, "主导产品名称");
    ensureCurrentValueMatches("product_code", normalized.product_code, "产品代码");

    const province = trimText(document.getElementById("province")?.value || "");
    api.fillFormFromExtractedData(
      {
        template_type: "self",
        province,
        company_name: normalized.company_name,
        product_name: normalized.product_name,
        product_code: normalized.product_code,
        year: normalized.report_date.slice(0, 4),
        month: normalized.report_date.slice(5, 7),
        day: normalized.report_date.slice(8, 10),
        company_intro: normalized.company_intro,
        product_intro: normalized.product_intro,
        target_scope: normalized.target_scope,
        sale_23: normalized.sale_23,
        total_mkt_23: "",
        pct_23: "",
        rank_23: "",
        sale_24: normalized.sale_24,
        total_mkt_24: "",
        pct_24: "",
        rank_24: "",
        sale_25: normalized.sale_25,
        total_mkt_25: "",
        pct_25: "",
        rank_25: "",
        sources: normalized.sources,
        competitors: [],
      },
      { keepBlankCompetitorRow: false }
    );
    api.resetOtherCompanyLookupState();
  }

  function applyCompetitorsImport(normalized) {
    const api = getApi();
    ensureSelectedVersionMatches(normalized.company_name);
    ensureCurrentValueMatches("company_name", normalized.company_name, "企业名称");
    ensureCurrentValueMatches("product_name", normalized.product_name, "主导产品名称");

    api.clearCompetitorsForImport();
    normalized.competitors.forEach((competitor) => {
      api.addCompetitorRow(
        {
          name: competitor.company_name,
          p23: competitor.market_share["2023"],
          p24: competitor.market_share["2024"],
          p25: competitor.market_share["2025"],
        },
        { syncRows: false }
      );
    });
    api.refreshCompetitorBoard();
    api.resetOtherCompanyLookupState();
  }

  function describePayload(payload) {
    if (!isPlainObject(payload)) {
      return { text: "JSON 顶层必须是对象", tone: "warn" };
    }
    const schema = trimText(payload.schema_version);
    const type = trimText(payload.payload_type);
    const status = trimText(payload.status);
    if (schema === "self_proof_import_v1" && type === "self_proof") {
      return {
        text: `已识别：自证 JSON / ${status || "unknown"}`,
        tone: status === "ready" ? "ready" : status === "blocked" ? "warn" : "muted",
      };
    }
    if (schema === "competitors_import_v1" && type === "competitors") {
      return {
        text: `已识别：竞争对手 JSON / ${status || "unknown"}`,
        tone: status === "ready" ? "ready" : status === "blocked" ? "warn" : "muted",
      };
    }
    return {
      text: "已识别 JSON，但 schema_version 或 payload_type 不符合要求",
      tone: "warn",
    };
  }

  function updatePreviewFromRawText(rawText) {
    const text = trimText(rawText);
    if (!text) {
      setPreview("等待粘贴 JSON");
      return;
    }
    try {
      const payload = parseJsonInput(text);
      const summary = describePayload(payload);
      setPreview(summary.text, summary.tone);
    } catch (_err) {
      setPreview("JSON 尚未完整，继续粘贴即可");
    }
  }

  async function importFromTextarea() {
    const api = getApi();
    const textarea = getElement(TEXTAREA_ID);
    const rawText = textarea.value;
    setError("");

    try {
      const payload = parseJsonInput(rawText);
      const schema = trimText(payload.schema_version);
      const type = trimText(payload.payload_type);
      if (schema === "self_proof_import_v1" && type === "self_proof") {
        const normalized = normalizeSelfPayload(payload);
        applySelfProofImport(normalized);
        const saved = await api.saveDraft(false);
        if (!saved) {
          throw new Error("内容已填入，但保存当前版本失败，请检查当前企业和版本是否一致");
        }
        api.setStatus("自证 JSON 已导入并保存，请核对字段");
        closeImportModal();
        return;
      }
      if (schema === "competitors_import_v1" && type === "competitors") {
        const normalized = normalizeCompetitorPayload(payload);
        applyCompetitorsImport(normalized);
        const saved = await api.saveDraft(false);
        if (!saved) {
          throw new Error("内容已填入，但保存当前版本失败，请检查当前企业和版本是否一致");
        }
        api.setStatus("竞争对手 JSON 已导入并保存，请核对销售额和排名");
        closeImportModal();
        return;
      }
      throw new Error("schema_version 或 payload_type 不匹配，无法识别 JSON 类型");
    } catch (error) {
      const message = error && error.name === "SyntaxError"
        ? "JSON 解析失败，请检查是否粘贴完整"
        : error && error.message
          ? error.message
          : "导入失败";
      setError(message);
      setPreview("导入失败，请修正 JSON 后重试", "warn");
    }
  }

  function bindEvents() {
    const modal = getElement(MODAL_ID);
    const textarea = getElement(TEXTAREA_ID);

    textarea.addEventListener("input", () => {
      updatePreviewFromRawText(textarea.value);
      setError("");
    });

    textarea.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        importFromTextarea();
      }
    });

    modal.addEventListener("click", (event) => {
      if (event.target === modal) {
        closeImportModal();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && modal.classList.contains("open")) {
        closeImportModal();
      }
    });
  }

  bindEvents();

  if (typeof window !== "undefined") {
    window.ReportJsonImport = {
      openImportModal,
      closeImportModal,
      importFromTextarea,
    };
    root.ReportJsonImport = window.ReportJsonImport;
  } else {
    root.ReportJsonImport = {
      openImportModal,
      closeImportModal,
      importFromTextarea,
    };
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
