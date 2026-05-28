# 他证 JSON 导入模块

这套模块只用于他证第三章企业基本信息导入。

## 他证第三章 Prompt

```text
基于我们上文已经确定的申报企业、主导产品、竞争对手名单、竞争对手 2025 年市占率排序，继续整理“他证报告第三章企业基本信息”。

你现在不要重新解释市占率推算路径，不要重新输出表格，不要总结。你的唯一任务是：查找这些企业的公司全称、公司地址、法人、注册资本、成立日期、主营业务，并输出一个可以直接复制到网站“导入他证 JSON”弹窗里的 JSON 对象。

重要背景：
1. 这是“他证报告”的第三章企业基本信息导入数据。
2. 企业输出顺序必须和上文已确定的名单完全一致：第 1 个是我的企业；第 2 个开始是竞争对手，竞争对手按上文 2025 年市占率从高到低排列。
3. 不允许新增、删除、合并或重排企业。
4. requested_name 必须原样照抄上文企业名称，用于网站匹配；不要改简称、不要补括号、不要换成别名。
5. company_name 填你查到的公司全称。
6. company_url 填你实际使用的来源网址，只能是企查查、爱企查或公司官网的网址。
7. 必须真实，只能从企查查、爱企查或公司官网查找。如果任一必填信息查不到，或者上文缺少申报企业/主导产品/竞争对手名单，不要编造，status 填 "blocked"，blocking_reasons 写清楚缺少哪家公司、哪个字段。
8. 只输出一个合法 JSON 对象，不要 Markdown，不要代码块，不要解释，不要表格，不要 JSON 之外的任何文字。
9. 输出前自己检查一遍：JSON 必须能被 JSON.parse 解析；companies 数量必须等于“我司 + 上文竞争对手数量”；companies 顺序必须是“我司第一，竞品按 2025 年市占率降序”。

输出格式必须严格如下：

{
  "schema_version": "other_company_profiles_import_v1",
  "payload_type": "other_company_profiles",
  "status": "ready",
  "blocking_reasons": [],
  "data": {
    "company_name": "【上文申报企业名称】",
    "product_name": "【上文主导产品名称】",
    "companies": [
      {
        "requested_name": "【必须原样照抄上文企业名称】",
        "company_name": "【查到的公司全称】",
        "company_url": "【企查查、爱企查或公司官网的纯网址】",
        "registered_capital": "【注册资本】",
        "established_date": "【成立日期，YYYY-MM-DD】",
        "legal_representative": "【法人】",
        "company_address": "【公司地址】",
        "main_business": "【主营业务】"
      }
    ]
  }
}
```

## 导入边界

- `schema_version` 必须是 `other_company_profiles_import_v1`
- `payload_type` 必须是 `other_company_profiles`
- `status` 必须是 `ready`
- `blocking_reasons` 在 `ready` 时必须为空
- 企业顺序必须和当前网站第三章名单完全一致
- 只输出 JSON，不要额外文字
