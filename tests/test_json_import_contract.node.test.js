const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const selfReadme = fs.readFileSync(path.join(__dirname, '../frontend/modules/self_json_import/README.md'), 'utf8');
const selfModuleSource = fs.readFileSync(path.join(__dirname, '../frontend/modules/self_json_import/self_json_import.js'), 'utf8');
const otherReadme = fs.readFileSync(path.join(__dirname, '../frontend/modules/other_json_import/README.md'), 'utf8');
const otherModuleSource = fs.readFileSync(path.join(__dirname, '../frontend/modules/other_json_import/other_json_import.js'), 'utf8');

test('README 固定了两个自证提示词和字段边界', () => {
  assert.match(selfReadme, /self_proof_import_v1/);
  assert.match(selfReadme, /competitors_import_v1/);
  assert.match(selfReadme, /不要输出竞争对手销售额/);
  assert.match(selfReadme, /chart_title_suffix/);
  assert.match(selfReadme, /source_names/);
  assert.match(selfReadme, /source_urls/);
  assert.match(selfReadme, /source_urls 只写纯来源网址/);
  assert.match(selfReadme, /不要 Markdown 链接格式/);
  assert.match(selfReadme, /market_share/);
});

test('README 固定了他证第三章提示词和 JSON 格式', () => {
  assert.match(otherReadme, /other_company_profiles_import_v1/);
  assert.match(otherReadme, /other_company_profiles/);
  assert.match(otherReadme, /基于我们上文已经确定的申报企业、主导产品、竞争对手名单/);
  assert.match(otherReadme, /企业输出顺序必须和上文已确定的名单完全一致/);
  assert.match(otherReadme, /requested_name/);
  assert.doesNotMatch(otherReadme, /company_url/);
  assert.match(otherReadme, /只输出一个合法 JSON 对象/);
  assert.match(otherReadme, /blocking_reasons/);
});

test('自证 JSON 导入模块只接受固定 schema 并按当前版本导入', () => {
  assert.match(selfModuleSource, /function normalizeSelfPayload\(payload\)/);
  assert.match(selfModuleSource, /function normalizeCompetitorPayload\(payload\)/);
  assert.match(selfModuleSource, /function ensureSelectedVersionMatches\(expectedCompanyName\)/);
  assert.match(selfModuleSource, /function normalizeSourceUrl\(rawValue, label\)/);
  assert.match(selfModuleSource, /modal\.classList\.add\("open"\);/);
  assert.match(selfModuleSource, /请先切换到自证模板再导入 JSON/);
  assert.match(selfModuleSource, /请先选择企业和版本，再导入 JSON/);
  assert.match(selfModuleSource, /当前模板不是自证，导入已阻止/);
  assert.match(selfModuleSource, /先选企业和版本，再导入/);
  assert.match(selfModuleSource, /JSON 企业名称与当前版本企业不一致，请先切换到正确版本/);
  assert.match(selfModuleSource, /竞争对手 JSON 已导入并保存，请核对销售额和排名/);
  assert.match(selfModuleSource, /自证 JSON 已导入并保存，请核对字段/);
  assert.match(selfModuleSource, /month: String\(month\)/);
  assert.match(selfModuleSource, /day: String\(day\)/);
  assert.match(selfModuleSource, /normalizeSourceUrl\(value, `sources\[\$\{index\}\]\.source_urls\[\$\{innerIndex\}\]`\)/);
  assert.match(selfModuleSource, /window\.ReportSelfJsonImport = \{/);
});

test('他证 JSON 导入模块只接受固定 schema 并按当前版本导入', () => {
  assert.match(otherModuleSource, /function normalizeOtherPayload\(payload\)/);
  assert.match(otherModuleSource, /function normalizeCompanyProfile\(item, index, expectedTarget, currentCompanyName, currentProductName\)/);
  assert.match(otherModuleSource, /function getOtherTargets\(\)/);
  assert.match(otherModuleSource, /schema_version\) !== "other_company_profiles_import_v1"/);
  assert.match(otherModuleSource, /payload_type\) !== "other_company_profiles"/);
  assert.match(otherModuleSource, /请先切换到他证模板再导入 JSON/);
  assert.match(otherModuleSource, /请先填写企业名称和竞争对手/);
  assert.match(otherModuleSource, /JSON 企业名称与当前版本企业不一致，请先切换到正确版本/);
  assert.match(otherModuleSource, /JSON 主导产品名称与当前页面不一致，请先切换到正确版本/);
  assert.match(otherModuleSource, /data\.companies 数量必须与网站当前企业名单一致/);
  assert.match(otherModuleSource, /companies\[\$\{index\}\]\.requested_name 必须与网站当前顺序一致/);
  assert.match(otherModuleSource, /他证第三章企业基本信息 JSON 已导入并保存，请核对字段/);
  assert.match(otherModuleSource, /window\.ReportOtherJsonImport = \{/);
  assert.match(otherModuleSource, /saveDraft\(false\)/);
});
