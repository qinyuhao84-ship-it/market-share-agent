const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const readme = fs.readFileSync(path.join(__dirname, '../frontend/modules/json_import/README.md'), 'utf8');
const moduleSource = fs.readFileSync(path.join(__dirname, '../frontend/modules/json_import/json_import.js'), 'utf8');

test('README 固定了两个提示词和字段边界', () => {
  assert.match(readme, /self_proof_import_v1/);
  assert.match(readme, /competitors_import_v1/);
  assert.match(readme, /不要输出竞争对手销售额/);
  assert.match(readme, /chart_title_suffix/);
  assert.match(readme, /source_names/);
  assert.match(readme, /source_urls/);
  assert.match(readme, /source_urls 只写纯来源网址/);
  assert.match(readme, /不要 Markdown 链接格式/);
  assert.match(readme, /market_share/);
});

test('JSON 导入模块只接受固定 schema 并按当前版本导入', () => {
  assert.match(moduleSource, /function normalizeSelfPayload\(payload\)/);
  assert.match(moduleSource, /function normalizeCompetitorPayload\(payload\)/);
  assert.match(moduleSource, /function ensureSelectedVersionMatches\(expectedCompanyName\)/);
  assert.match(moduleSource, /function normalizeSourceUrl\(rawValue, label\)/);
  assert.match(moduleSource, /modal\.classList\.add\("open"\);/);
  assert.match(moduleSource, /请先切换到自证模板再导入 JSON/);
  assert.match(moduleSource, /请先选择企业和版本，再导入 JSON/);
  assert.match(moduleSource, /当前模板不是自证，导入已阻止/);
  assert.match(moduleSource, /先选企业和版本，再导入/);
  assert.match(moduleSource, /JSON 企业名称与当前版本企业不一致，请先切换到正确版本/);
  assert.match(moduleSource, /竞争对手 JSON 已导入并保存，请核对销售额和排名/);
  assert.match(moduleSource, /自证 JSON 已导入并保存，请核对字段/);
  assert.match(moduleSource, /month: String\(month\)/);
  assert.match(moduleSource, /day: String\(day\)/);
  assert.match(moduleSource, /normalizeSourceUrl\(value, `sources\[\$\{index\}\]\.source_urls\[\$\{innerIndex\}\]`\)/);
});
