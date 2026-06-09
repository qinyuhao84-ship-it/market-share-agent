const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '../frontend/index.html'), 'utf8');
const appJs = fs.readFileSync(path.join(__dirname, '../frontend/app.js'), 'utf8');
const chapter1ConfigJs = fs.readFileSync(path.join(__dirname, '../frontend/modules/other_chapter1_config.js'), 'utf8');
const selfJsonImportJs = fs.readFileSync(path.join(__dirname, '../frontend/modules/self_json_import/self_json_import.js'), 'utf8');
const selfJsonImportReadme = fs.readFileSync(path.join(__dirname, '../frontend/modules/self_json_import/README.md'), 'utf8');
const otherJsonImportJs = fs.readFileSync(path.join(__dirname, '../frontend/modules/other_json_import/other_json_import.js'), 'utf8');
const otherJsonImportReadme = fs.readFileSync(path.join(__dirname, '../frontend/modules/other_json_import/README.md'), 'utf8');
const source = [html, appJs, chapter1ConfigJs].join('\n');
const selfImportSource = [selfJsonImportJs, selfJsonImportReadme].join('\n');
const otherImportSource = [otherJsonImportJs, otherJsonImportReadme].join('\n');

test('顶部版本中心操作入口存在', () => {
  assert.match(source, /id="createCompanyBtnTop"[^>]*onclick="onCreateCompanyClick\(\)"/);
  assert.match(source, /id="createVersionBtnTop"[^>]*onclick="onCreateVersionClick\(\)"/);
  assert.match(source, /id="saveDraftBtnTop"[^>]*onclick="onSaveDraftClick\(\)"/);
  assert.match(source, /id="importSelfJsonBtnTop"[^>]*onclick="ReportSelfJsonImport\.openImportModal\(\)"/);
  assert.match(source, /id="importOtherJsonBtnTop"[^>]*onclick="ReportOtherJsonImport\.openImportModal\(\)"/);
  assert.match(source, /id="deleteVersionBtnTop"[^>]*onclick="onDeleteVersionClick\(\)"/);
  assert.match(source, /id="deleteCompanyBtnTop"[^>]*onclick="onDeleteCompanyClick\(\)"/);
});

test('JSON 导入入口和资源已接入页面', () => {
  assert.match(source, /href="\/frontend\/modules\/self_json_import\/self_json_import\.css"/);
  assert.match(source, /href="\/frontend\/modules\/other_json_import\/other_json_import\.css"/);
  assert.match(source, /id="selfJsonImportModal"/);
  assert.match(source, /id="selfJsonImportTextarea"/);
  assert.match(source, /id="selfJsonImportPreview"/);
  assert.match(source, /id="selfJsonImportError"/);
  assert.match(source, /id="otherJsonImportModal"/);
  assert.match(source, /id="otherJsonImportTextarea"/);
  assert.match(source, /id="otherJsonImportPreview"/);
  assert.match(source, /id="otherJsonImportError"/);
  assert.match(source, /src="\/frontend\/modules\/self_json_import\/self_json_import\.js"/);
  assert.match(source, /src="\/frontend\/modules\/other_json_import\/other_json_import\.js"/);
});

test('旧入口已移除：恢复、清空、手选目标版本号', () => {
  assert.doesNotMatch(source, /恢复所选/);
  assert.doesNotMatch(source, /清空草稿/);
  assert.doesNotMatch(source, /draftTargetVersionNo/);
  assert.doesNotMatch(source, /saveDraftVersion\(/);
  assert.doesNotMatch(source, /clearDraft\(/);
  assert.doesNotMatch(source, /createFinalVersionBtnTop/);
  assert.doesNotMatch(source, /finalVersionModal/);
  assert.doesNotMatch(source, /selectedFinalDocxFile/);
  assert.doesNotMatch(source, /saveAsFinalVersion/);
  assert.doesNotMatch(source, /extract-final-docx/);
  assert.doesNotMatch(source, /is_final/);
  assert.doesNotMatch(source, /final-badge/);
});

test('版本下拉切换即加载当前版本', () => {
  assert.match(source, /id="draftVersionSelect" onchange="onDraftVersionChange\(\)"/);
  assert.match(source, /async function onDraftVersionChange\(\) \{/);
  assert.match(source, /await loadDraft\(true\);/);
});

test('按钮交互增强：状态机、防连点、快捷键', () => {
  assert.match(source, /function updateTopActionState\(\) \{/);
  assert.match(source, /async function runTopAction\(buttonId, busyText, action\) \{/);
  assert.match(source, /function bindDraftHotkeys\(\) \{/);
  assert.match(source, /if \(\(event\.ctrlKey \|\| event\.metaKey\).*key === "s"\)/);
  assert.match(source, /buttons\.importSelfJson/);
  assert.match(source, /buttons\.importOtherJson/);
  assert.match(source, /buttons\.importSelfJson\.disabled = !hasCompany \|\| !hasVersion \|\| !isSelfTemplate \|\| busyKeys\.has\("importSelfJson"\);/);
  assert.match(source, /buttons\.importOtherJson\.disabled = !hasCompany \|\| !hasVersion \|\| isSelfTemplate \|\| busyKeys\.has\("importOtherJson"\);/);
  assert.match(source, /导入自证基础资料或竞争对手 JSON/);
  assert.match(source, /导入他证第三章企业基本信息 JSON/);
  assert.match(source, /请先切换到自证模板/);
  assert.match(source, /请先切换到他证模板/);
});

test('第一章按企业缓存：版本草稿会保存并恢复第一章', () => {
  assert.match(source, /cacheKey: "report_other_chapter1_by_company_v3_deepseek_v4_pro"/);
  assert.match(source, /schemaVersion: "chapter1_semantic_v1"/);
  assert.match(source, /modelName: "deepseek-v4-pro"/);
  assert.match(source, /modelMode: "thinking"/);
  assert.match(source, /directGenerationOnly: true/);
  assert.match(source, /const OTHER_CHAPTER1_CACHE_KEY = ReportAutomationChapter1Config\.cacheKey/);
  assert.match(source, /function chapter1SectionsContainPlaceholder\(sections\) \{/);
  assert.doesNotMatch(source, /if \(paragraphs\.length < spec\.slot_count\) return true;/);
  assert.match(source, /text\.includes\("【待补充："\)/);
  assert.match(source, /function isReusableOtherChapter1CacheEntry\(entry, productName = ""\) \{/);
  assert.match(source, /function getOtherChapter1Cache\(companyName, productName = ""\) \{/);
  assert.match(source, /if \(!isReusableOtherChapter1CacheEntry\(entry, productName\)\) \{/);
  assert.match(source, /delete otherProofChapter1CacheByCompany\[key\];/);
  assert.match(source, /function setOtherChapter1Cache\(companyName, sections, productName = ""\) \{/);
  assert.match(source, /semantic_draft:\s*otherProofChapter1SemanticDraft \|\| null,/);
  assert.match(source, /replay_file_path:\s*otherProofChapter1ReplayFilePath \|\| "",/);
  assert.match(source, /if \(!force\) \{[\s\S]*getOtherChapter1Cache\(companyName,\s*product\)/);
  assert.match(source, /otherProofChapter1SemanticDraft = cached\.semantic_draft \|\| null;/);
  assert.match(source, /otherProofChapter1TaskId = "";[\s\S]*otherProofChapter1TaskSnapshot = null;/);
  assert.match(source, /setOtherChapter1Cache\(companyName, legacySections, product\);/);
  assert.match(source, /chapter1_sections:\s*chapter1Sections,/);
  assert.match(source, /chapter1_semantic_draft:\s*templateType === "other" \? otherProofChapter1SemanticDraft : null,/);
  assert.match(source, /chapter1_replay_file_path:\s*chapter1ReplayFilePath,/);
  assert.match(
    source,
    /const hasChapter1Snapshot =[\s\S]*Object\.prototype\.hasOwnProperty\.call\(snapshot, "chapter1_sections"\);/
  );
  assert.match(source, /otherProofChapter1Sections = Array\.isArray\(snapshot\.chapter1_sections\) \? snapshot\.chapter1_sections : \[\];/);
  assert.match(source, /otherProofChapter1ReplayFilePath = typeof snapshot\.chapter1_replay_file_path === "string"/);
  assert.match(source, /otherProofChapter1SemanticDraft = snapshot\.chapter1_semantic_draft \|\| null;/);
  assert.match(source, /otherProofChapter1TaskId = "";[\s\S]*otherProofChapter1TaskSnapshot = null;/);
  assert.match(source, /if \(!hasChapter1Snapshot\) \{[\s\S]*applyCompanyChapter1Cache\(target\.companyName\);/);
});

test('第一章重新生成只能显式触发', () => {
  assert.match(source, /onclick="regenerateOtherChapter1\(\)"/);
  assert.match(source, /async function regenerateOtherChapter1\(\) \{/);
  assert.match(source, /ensureOtherChapter1\(true,\s*false\)/);
  assert.match(source, /ensureOtherChapter1\(false,\s*true\)/);
  assert.doesNotMatch(source, /ensureOtherChapter1\(false,\s*false\)/);
});

test('图表标题前缀自动生成，用户只填写后半句', () => {
  assert.match(source, /class="chart-prefix">图表1：<\/span>/);
  assert.match(source, /class="s-chart-suffix"/);
  assert.match(source, /class="s-c23"/);
  assert.match(source, /class="s-c24"/);
  assert.match(source, /class="s-c25"/);
  assert.match(source, /function addSourceMultiInput\(button, type, value = ""\) \{/);
  assert.match(source, /function collectSourceMultiValues\(card, type\) \{/);
  assert.match(source, /function extractChartTitleSuffix\(rawTitle\) \{/);
  assert.match(source, /function validateSourceChartData\(sources, contextLabel = "数据来源"\) \{/);
  assert.match(source, /chart_title: `图表\$\{idx \+ 1\}：\$\{suffix\}`/);
  assert.match(source, /names,\s*url: urls\[0\] \|\| "",\s*urls,/);
  assert.match(source, /if \(block\.names\.length \|\| block\.urls\.length \|\| suffix \|\| block\.analysis \|\| block\.chart_2023 \|\| block\.chart_2024 \|\| block\.chart_2025\) list\.push\(block\);/);
});

test('经营数据市场规模支持手填且来源优先', () => {
  assert.match(source, /<input id="total_mkt_23" oninput="onMarketInputChange\('23'\)" \/>/);
  assert.match(source, /<input id="total_mkt_24" oninput="onMarketInputChange\('24'\)" \/>/);
  assert.match(source, /<input id="total_mkt_25" oninput="onMarketInputChange\('25'\)" \/>/);
  assert.match(source, /function onMarketInputChange\(year\) \{/);
  assert.match(source, /function syncBusinessMarketScaleFromSources\(\) \{/);
  assert.match(source, /const bottom = sources\.length \? sources\[sources\.length - 1\] : null;/);
  assert.match(source, /if \(nextValue && input\.value !== nextValue\) \{/);
  assert.match(source, /function resolveEffectiveMarketScale\(year, sources\) \{/);
  assert.match(source, /function convertMarketScaleYiToWan\(rawValue\) \{/);
  assert.match(source, /const wanValue = yiValue \* 10000;/);
  assert.match(source, /syncBusinessMarketScaleFromSources\(\);\s*const company = document\.getElementById\("company_name"\)\.value\.trim\(\);/);
});

test('竞争对手输入不自动跳格，也不自动重排行', () => {
  assert.match(
    source,
    /function competitorInputChanged\(input, year, mode\) \{[\s\S]*refreshCompetitorBoard\(\{ sortRows: false \}\);/
  );
  assert.doesNotMatch(
    source,
    /function competitorInputChanged\(input, year, mode\) \{[\s\S]*\.focus\(/,
  );
});

test('他证第一章部分失败时继续导出并显示回放路径', () => {
  assert.doesNotMatch(source, /id="skipChapter1OnFailure"/);
  assert.match(source, /id="stopChapter1Btn"/);
  assert.match(source, /async function abortOtherChapter1Generation\(\) \{/);
  assert.match(source, /fetch\(`\/other-proof\/chapter1\/tasks\/\$\{encodeURIComponent\(taskId\)\}\/cancel`/);
  assert.match(source, /signal: otherChapter1AbortController\.signal/);
  assert.match(source, /allow_incomplete_export:\s*allowPartial/);
  assert.match(source, /enable_web_retrieval:\s*false/);
  assert.match(source, /formatApiErrorDetail\(err, chapter1RetryTip\)/);
  assert.match(source, /调试回放文件/);
  assert.match(source, /const chapter1Ready = await ensureOtherChapter1\(false,\s*true\);/);
  assert.match(source, /if \(!chapter1Ready\) \{[\s\S]*已继续导出 Word/);
  assert.doesNotMatch(source, /const chapter1WasRunning = !!otherChapter1AbortController;/);
  assert.doesNotMatch(source, /if \(!chapter1Ready && chapter1WasRunning\) \{\s*return;/);
  assert.match(source, /data\.chapter1_replay_file_path = otherProofChapter1ReplayFilePath;/);
  assert.match(source, /data\.skip_chapter1 = false;/);
  assert.match(source, /X-Chapter1-Replay-File-Path/);
  assert.doesNotMatch(source, /skipChapter1ForExport/);
  assert.doesNotMatch(source, /最终 Word 不写入第一章正文/);
});

test('导出文件名：自证按公司名，他证按产品名', () => {
  assert.match(source, /function buildOutputFileName\(data\) \{/);
  assert.match(source, /const namePart = data\.template_type === "other"/);
  assert.match(source, /\? sanitizeFileNamePart\(data\.product_name \|\| "产品名称"\)/);
  assert.match(source, /: sanitizeFileNamePart\(data\.company_name \|\| "企业名称"\)/);
  assert.match(source, /return `\$\{mm\}\$\{dd\}-\$\{namePart\}-\$\{versionNo\}版\.docx`;/);
});

test('JSON 导入模块暴露固定 API 和严格校验', () => {
  assert.match(source, /window\.ReportAutomationFormApi = \{/);
  assert.match(source, /clearSourcesForImport/);
  assert.match(source, /clearCompetitorsForImport/);
  assert.match(source, /getOtherCompanyProfileImportTargets/);
  assert.match(source, /applyOtherCompanyProfilesImport/);
  assert.match(source, /fillFormFromExtractedData\(data, options = \{\}\)/);
  assert.match(source, /keepBlankCompetitorRow = options\.keepBlankCompetitorRow !== false/);
  assert.match(selfImportSource, /window\.ReportSelfJsonImport = \{/);
  assert.match(selfImportSource, /function importFromTextarea\(\) \{/);
  assert.match(selfImportSource, /schema_version\) !== "self_proof_import_v1"/);
  assert.match(selfImportSource, /schema_version\) !== "competitors_import_v1"/);
  assert.match(selfImportSource, /company_name 不能等于申报企业名称/);
  assert.match(selfImportSource, /不要包含图表编号/);
  assert.match(selfImportSource, /saveDraft\(false\)/);
  assert.match(otherImportSource, /window\.ReportOtherJsonImport = \{/);
  assert.match(otherImportSource, /function importFromTextarea\(\) \{/);
  assert.match(otherImportSource, /schema_version\) !== "other_company_profiles_import_v1"/);
  assert.match(otherImportSource, /payload_type\) !== "other_company_profiles"/);
  assert.match(otherImportSource, /请先切换到他证模板再导入 JSON/);
  assert.match(otherImportSource, /JSON 企业名称与当前版本企业不一致，请先切换到正确版本/);
  assert.match(otherImportSource, /他证第三章企业基本信息 JSON 已导入并保存，请核对字段/);
  assert.match(otherImportSource, /saveDraft\(false\)/);
});
