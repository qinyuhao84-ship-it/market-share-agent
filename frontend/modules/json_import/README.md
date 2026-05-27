# JSON 导入模块

这套模块用于把 ChatGPT 输出的固定 JSON 导入到当前表单，减少人工复制粘贴。

## 约束

- 只支持自证与竞争对手两种 JSON。
- 自证 JSON 只填自证页面基础资料、经营数据和来源。
- 竞争对手 JSON 只填竞争对手表。
- 导入前必须选好企业和版本。
- 当前页面必须处于自证模板。
- 任何字段缺失、类型不对、当前版本不匹配，直接停止。
- 不做兼容性补丁，不做自动补值，不做静默降级。

## 自证 JSON 提示词

```text
你是一个公开信息检索与结构化整理助手。请围绕【企业名称】和【主导产品名称】公开检索并整理“市场占有率自证”所需信息。

强制要求：
1. 只输出一个 JSON 对象，不要 Markdown，不要解释。
2. 如果任一必填信息无法公开确认，仍输出同一 JSON 结构，但 status 填 "blocked"，blocking_reasons 写清缺少什么；不要编造。
3. report_date 使用你回答当天日期，格式 YYYY-MM-DD。
4. 销售额单位是“万元”；市场规模单位是“亿元”。
5. chart_title_suffix 只写标题后半句，不要写“图表1/图表2”。
6. sources 至少 1 层；最后一层代表最终用于计算市占率的细分市场规模。
7. source_names 写来源名称，source_urls 写来源网址，二者顺序要对应。
8. analysis_text 写成可以直接粘贴进报告的数据说明正文。

输出格式：
{
  "schema_version": "self_proof_import_v1",
  "payload_type": "self_proof",
  "status": "ready",
  "blocking_reasons": [],
  "data": {
    "company_name": "",
    "product_name": "",
    "product_code": "",
    "report_date": "YYYY-MM-DD",
    "target_scope": "CN",
    "company_intro": "",
    "product_intro": "",
    "business": {
      "sales_wan": {
        "2023": "",
        "2024": "",
        "2025": ""
      }
    },
    "sources": [
      {
        "source_names": [""],
        "source_urls": [""],
        "chart_title_suffix": "2023-2025年……市场规模（亿元）",
        "market_size_yi": {
          "2023": "",
          "2024": "",
          "2025": ""
        },
        "analysis_text": ""
      }
    ]
  }
}
```

## 竞争对手 JSON 提示词

```text
你是一个公开信息检索与结构化整理助手。请围绕【企业名称】、【主导产品名称】和已确定的细分市场，整理主要竞争对手 2023-2025 年市占率。

强制要求：
1. 只输出一个 JSON 对象，不要 Markdown，不要解释。
2. 不要输出竞争对手销售额，网站会根据市占率和市场规模自动计算。
3. competitors 不要包含申报企业自己。
4. 市占率统一写成百分比字符串，例如 "12.34%"。
5. 如果无法公开确认竞争对手或市占率，status 填 "blocked"，blocking_reasons 写清缺口；不要编造。

输出格式：
{
  "schema_version": "competitors_import_v1",
  "payload_type": "competitors",
  "status": "ready",
  "blocking_reasons": [],
  "data": {
    "company_name": "",
    "product_name": "",
    "competitors": [
      {
        "company_name": "",
        "market_share": {
          "2023": "",
          "2024": "",
          "2025": ""
        }
      }
    ]
  }
}
```

## 字段说明

- `report_date`：`YYYY-MM-DD`
- `sales_wan`：万元
- `market_size_yi`：亿元
- `source_names` / `source_urls`：数组，顺序必须对应
- `chart_title_suffix`：只写图表后半句，不要写图表编号
- `market_share`：百分比字符串，导入后会转成统一格式

## 常见失败原因

- JSON 不是对象
- `schema_version` 不对
- `payload_type` 不对
- `status` 不是 `ready`
- `blocking_reasons` 为空但 `status` 是 `blocked`
- 当前不是自证模板
- 当前没有选企业或版本
- JSON 企业名称和当前版本不一致
- 竞争对手 JSON 里出现销售额字段
- 来源数组为空
- 来源名称和来源网址数量不一致

