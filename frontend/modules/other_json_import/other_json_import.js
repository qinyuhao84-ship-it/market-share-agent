(function (root) {
  const MODAL_ID = "otherJsonImportModal";
  const TEXTAREA_ID = "otherJsonImportTextarea";
  const ERROR_ID = "otherJsonImportError";
  const PREVIEW_ID = "otherJsonImportPreview";

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

  function isHttpUrl(value) {
    try {
      const parsed = new URL(String(value || "").trim());
      return parsed.protocol === "http:" || parsed.protocol === "https:";
    } catch (_error) {
      return false;
    }
  }

  function requireHttpUrl(value, label) {
    const text = requireString(value, label);
    if (!isHttpUrl(text)) {
      throw new Error(`${label} 必须是纯 URL`);
    }
    return text;
  }

  function normalizeDate(value, label) {
    const text = requireString(value, label);
    const match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) {
      throw new Error(`${label} 必须是 YYYY-MM-DD`);
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
      throw new Error(`${label} 不是有效日期`);
    }
    return text;
  }

  function normalizeCompanyName(value) {
    return trimText(value).replace(/\s+/g, "").replace(/（/g, "(").replace(/）/g, ")");
  }

  function getOtherTargets() {
    const api = getApi();
    const targets = api.getOtherCompanyProfileImportTargets();
    if (!Array.isArray(targets)) {
      return [];
    }
    return targets
      .map((target, index) => {
        if (!isPlainObject(target)) {
          return null;
        }
        const requestedName = trimText(target.requested_name);
        if (!requestedName) {
          return null;
        }
        return {
          requested_name: requestedName,
          is_self: index === 0 || !!target.is_self,
        };
      })
      .filter(Boolean);
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
    if (templateType !== "other") {
      setError("请先切换到他证模板再导入 JSON");
      setPreview("当前模板不是他证，导入已阻止", "error");
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
    if (!getOtherTargets().length) {
      setError("请先填写企业名称和竞争对手");
      setPreview("当前没有可导入的第三章企业名单", "error");
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

  function normalizeCompanyProfile(item, index, expectedTarget, currentCompanyName, currentProductName) {
    const profile = requireObject(item, `companies[${index}]`);
    const requestedName = requireString(profile.requested_name, `companies[${index}].requested_name`);
    const expectedName = requireString(expectedTarget.requested_name, `targets[${index}].requested_name`);
    if (requestedName !== expectedName) {
      throw new Error(`companies[${index}].requested_name 必须与网站当前顺序一致：应为“${expectedName}”，实际是“${requestedName}”`);
    }

    const companyName = requireString(profile.company_name, `companies[${index}].company_name`);
    const companyUrl = requireHttpUrl(profile.company_url, `companies[${index}].company_url`);
    const registeredCapital = requireString(profile.registered_capital, `companies[${index}].registered_capital`);
    const establishedDate = normalizeDate(profile.established_date, `companies[${index}].established_date`);
    const legalRepresentative = requireString(profile.legal_representative, `companies[${index}].legal_representative`);
    const companyAddress = requireString(profile.company_address, `companies[${index}].company_address`);
    const mainBusiness = requireString(profile.main_business, `companies[${index}].main_business`);

    return {
      requested_name: expectedName,
      company_name: companyName,
      company_url: companyUrl,
      registered_capital: registeredCapital,
      established_date: establishedDate,
      legal_representative: legalRepresentative,
      company_address: companyAddress,
      main_business: mainBusiness,
      matched_exactly: normalizeCompanyName(companyName) === normalizeCompanyName(expectedName),
    };
  }

  function normalizeOtherPayload(payload) {
    if (!isPlainObject(payload)) {
      throw new Error("JSON 顶层必须是对象");
    }
    if (trimText(payload.schema_version) !== "other_company_profiles_import_v1") {
      throw new Error("schema_version 必须是 other_company_profiles_import_v1");
    }
    if (trimText(payload.payload_type) !== "other_company_profiles") {
      throw new Error("payload_type 必须是 other_company_profiles");
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
    const companyName = requireString(data.company_name, "data.company_name");
    const productName = requireString(data.product_name, "data.product_name");
    const currentTarget = getApi().getSelectedVersionTarget();
    if (!currentTarget) {
      throw new Error("请先选择企业和版本，再导入 JSON");
    }
    if (trimText(currentTarget.companyName) !== companyName) {
      throw new Error("JSON 企业名称与当前版本企业不一致，请先切换到正确版本");
    }
    const currentCompanyName = requireString(document.getElementById("company_name")?.value || "", "页面企业名称");
    if (currentCompanyName !== companyName) {
      throw new Error("JSON 企业名称与当前页面企业名称不一致，请先切换到正确版本");
    }
    const currentProductName = requireString(document.getElementById("product_name")?.value || "", "页面主导产品名称");
    if (currentProductName !== productName) {
      throw new Error("JSON 主导产品名称与当前页面不一致，请先切换到正确版本");
    }

    const targets = getOtherTargets();
    if (!targets.length) {
      throw new Error("请先填写企业名称和竞争对手");
    }

    const companies = requireArray(data.companies, "data.companies");
    if (!companies.length) {
      throw new Error("data.companies 至少需要 1 家企业");
    }
    if (companies.length !== targets.length) {
      throw new Error(`data.companies 数量必须与网站当前企业名单一致：当前需要 ${targets.length} 家，实际是 ${companies.length} 家`);
    }

    const normalizedCompanies = companies.map((item, index) => normalizeCompanyProfile(
      item,
      index,
      targets[index],
      companyName,
      productName
    ));

    return {
      company_name: companyName,
      product_name: productName,
      companies: normalizedCompanies,
    };
  }

  function describePayload(payload) {
    if (!isPlainObject(payload)) {
      return { text: "JSON 顶层必须是对象", tone: "warn" };
    }
    const schema = trimText(payload.schema_version);
    const type = trimText(payload.payload_type);
    const status = trimText(payload.status);
    if (schema === "other_company_profiles_import_v1" && type === "other_company_profiles") {
      return {
        text: `已识别：他证第三章 JSON / ${status || "unknown"}`,
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
    } catch (_error) {
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
      const normalized = normalizeOtherPayload(payload);
      api.applyOtherCompanyProfilesImport(normalized.companies);
      const saved = await api.saveDraft(false);
      if (!saved) {
        throw new Error("内容已填入，但保存当前版本失败，请检查当前企业和版本是否一致");
      }
      api.setStatus("他证第三章企业基本信息 JSON 已导入并保存，请核对字段");
      closeImportModal();
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
    window.ReportOtherJsonImport = {
      openImportModal,
      closeImportModal,
      importFromTextarea,
    };
    root.ReportOtherJsonImport = window.ReportOtherJsonImport;
  } else {
    root.ReportOtherJsonImport = {
      openImportModal,
      closeImportModal,
      importFromTextarea,
    };
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
