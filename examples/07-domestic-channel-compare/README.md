# 国内电商渠道结构分析

- 用户需求：分析小米科技有限责任公司的国内电商店铺渠道结构，供渠道团队检查平台集中度。
- 决策用途：发现平台和店铺分布的集中风险。
- 本轮结果：**本轮检查通过**
- 实际工具调用：3；失败 0
- 章节覆盖率：67%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 国内店铺和商品画像口径一致
- 渠道集中度有记录数量支撑
- 同名店铺不被无依据合并
- 报告不把检索样本外推为全渠道份额

## 本轮自动检查发现


## 使用局限

- 仅覆盖数据源可见店铺
- 无法仅凭名称确认全部店铺授权关系

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 goods-skill/scripts/compose_report.py --enterprise '小米科技有限责任公司' --channel-source domestic_store --profile-source domestic --page-size 10 --output goods-skill/output/07-domestic-channel-compare/report.json --report-output goods-skill/output/07-domestic-channel-compare/report.html
```

## 逐场景业务复核

本轮真实产物的全部清单检查均有当前字段证据，且报告保留样本/缺失/关系边界。

- **pass** 国内店铺和商品画像口径一致：该项由当前调用参数、报告同名字段、样本与局限说明共同核对。 当前冻结快照：{"technical_status":"passed","successful_data_calls":3,"calls":[{"tool":"goods_enterprise_products","status":"data","rows":10,"total":1836,"args":{"matchKeyword":"小米科技有限责任公司","productType":"retail","keywordType":"name","pageIndex":1,"pageSize":10}},{"tool":"goods_brand","status":"data","rows":null,"total":null,"args":{"matchKeyword":"小米科技有限责任公司","view":"brand_detail","keywordType":"name"}},{"tool":"goods_channel","status":"data","rows":1,"total":1,"args":{"matchKeyword":"小米科技有限责任公司","source":"domestic_store","keywordType":"name","pageIndex":1,"pageSize":10}}],"subject":{"enterprise":"小米科技有限责任公司","matchKeyword":"小米科技有限责任公司","keywordType":"name","match_raw":"小米科技有限责任公司","resolved":true,"resolve_reason":"视为企业全称"},"metrics":[{"label":"电商商品数","value":"1836","hint":"企业电商商品明细总数"},{"label":"店铺/渠道数","value":"1","hint":"电商店铺或网店数量"},{"label":"覆盖平台","value":"1","hint":"不同电商平台数"}],"core_counts":{"sections":3,"brand_analysis":5,"price_analysis":0,"channel_analysis":1,"sales_trend":0,"search_records":0},"core_samples":{"channel_analysis":[{"店铺名称":"小米移动旗舰店","平台":"天猫","开店时间":"-","店铺链接":"https://shop240603011.taobao.com","在售关键词数":"-"}]},"quality":{"total_sections":3,"populated_sections":2,"empty_sections":1,"coverage_pct":67},"limit":"渠道为分页样本，不代表企业完整渠道；海外商品需网店 id。品牌结果缺少可核验主体绑定时仅保留为来源线索，不进入指标与肯定性洞察。当前 MCP 未注册历史价格与销售趋势工具，相关选择器仅作缺口披露。","html_bytes":1059599,"markdown_bytes":2414}
- **pass** 渠道集中度有记录数量支撑：该项由当前调用参数、报告同名字段、样本与局限说明共同核对。 当前冻结快照：{"technical_status":"passed","successful_data_calls":3,"calls":[{"tool":"goods_enterprise_products","status":"data","rows":10,"total":1836,"args":{"matchKeyword":"小米科技有限责任公司","productType":"retail","keywordType":"name","pageIndex":1,"pageSize":10}},{"tool":"goods_brand","status":"data","rows":null,"total":null,"args":{"matchKeyword":"小米科技有限责任公司","view":"brand_detail","keywordType":"name"}},{"tool":"goods_channel","status":"data","rows":1,"total":1,"args":{"matchKeyword":"小米科技有限责任公司","source":"domestic_store","keywordType":"name","pageIndex":1,"pageSize":10}}],"subject":{"enterprise":"小米科技有限责任公司","matchKeyword":"小米科技有限责任公司","keywordType":"name","match_raw":"小米科技有限责任公司","resolved":true,"resolve_reason":"视为企业全称"},"metrics":[{"label":"电商商品数","value":"1836","hint":"企业电商商品明细总数"},{"label":"店铺/渠道数","value":"1","hint":"电商店铺或网店数量"},{"label":"覆盖平台","value":"1","hint":"不同电商平台数"}],"core_counts":{"sections":3,"brand_analysis":5,"price_analysis":0,"channel_analysis":1,"sales_trend":0,"search_records":0},"core_samples":{"channel_analysis":[{"店铺名称":"小米移动旗舰店","平台":"天猫","开店时间":"-","店铺链接":"https://shop240603011.taobao.com","在售关键词数":"-"}]},"quality":{"total_sections":3,"populated_sections":2,"empty_sections":1,"coverage_pct":67},"limit":"渠道为分页样本，不代表企业完整渠道；海外商品需网店 id。品牌结果缺少可核验主体绑定时仅保留为来源线索，不进入指标与肯定性洞察。当前 MCP 未注册历史价格与销售趋势工具，相关选择器仅作缺口披露。","html_bytes":1059599,"markdown_bytes":2414}
- **pass** 同名店铺不被无依据合并：该项由当前调用参数、报告同名字段、样本与局限说明共同核对。 当前冻结快照：{"technical_status":"passed","successful_data_calls":3,"calls":[{"tool":"goods_enterprise_products","status":"data","rows":10,"total":1836,"args":{"matchKeyword":"小米科技有限责任公司","productType":"retail","keywordType":"name","pageIndex":1,"pageSize":10}},{"tool":"goods_brand","status":"data","rows":null,"total":null,"args":{"matchKeyword":"小米科技有限责任公司","view":"brand_detail","keywordType":"name"}},{"tool":"goods_channel","status":"data","rows":1,"total":1,"args":{"matchKeyword":"小米科技有限责任公司","source":"domestic_store","keywordType":"name","pageIndex":1,"pageSize":10}}],"subject":{"enterprise":"小米科技有限责任公司","matchKeyword":"小米科技有限责任公司","keywordType":"name","match_raw":"小米科技有限责任公司","resolved":true,"resolve_reason":"视为企业全称"},"metrics":[{"label":"电商商品数","value":"1836","hint":"企业电商商品明细总数"},{"label":"店铺/渠道数","value":"1","hint":"电商店铺或网店数量"},{"label":"覆盖平台","value":"1","hint":"不同电商平台数"}],"core_counts":{"sections":3,"brand_analysis":5,"price_analysis":0,"channel_analysis":1,"sales_trend":0,"search_records":0},"core_samples":{"channel_analysis":[{"店铺名称":"小米移动旗舰店","平台":"天猫","开店时间":"-","店铺链接":"https://shop240603011.taobao.com","在售关键词数":"-"}]},"quality":{"total_sections":3,"populated_sections":2,"empty_sections":1,"coverage_pct":67},"limit":"渠道为分页样本，不代表企业完整渠道；海外商品需网店 id。品牌结果缺少可核验主体绑定时仅保留为来源线索，不进入指标与肯定性洞察。当前 MCP 未注册历史价格与销售趋势工具，相关选择器仅作缺口披露。","html_bytes":1059599,"markdown_bytes":2414}
- **pass** 报告不把检索样本外推为全渠道份额：该项由当前调用参数、报告同名字段、样本与局限说明共同核对。 当前冻结快照：{"technical_status":"passed","successful_data_calls":3,"calls":[{"tool":"goods_enterprise_products","status":"data","rows":10,"total":1836,"args":{"matchKeyword":"小米科技有限责任公司","productType":"retail","keywordType":"name","pageIndex":1,"pageSize":10}},{"tool":"goods_brand","status":"data","rows":null,"total":null,"args":{"matchKeyword":"小米科技有限责任公司","view":"brand_detail","keywordType":"name"}},{"tool":"goods_channel","status":"data","rows":1,"total":1,"args":{"matchKeyword":"小米科技有限责任公司","source":"domestic_store","keywordType":"name","pageIndex":1,"pageSize":10}}],"subject":{"enterprise":"小米科技有限责任公司","matchKeyword":"小米科技有限责任公司","keywordType":"name","match_raw":"小米科技有限责任公司","resolved":true,"resolve_reason":"视为企业全称"},"metrics":[{"label":"电商商品数","value":"1836","hint":"企业电商商品明细总数"},{"label":"店铺/渠道数","value":"1","hint":"电商店铺或网店数量"},{"label":"覆盖平台","value":"1","hint":"不同电商平台数"}],"core_counts":{"sections":3,"brand_analysis":5,"price_analysis":0,"channel_analysis":1,"sales_trend":0,"search_records":0},"core_samples":{"channel_analysis":[{"店铺名称":"小米移动旗舰店","平台":"天猫","开店时间":"-","店铺链接":"https://shop240603011.taobao.com","在售关键词数":"-"}]},"quality":{"total_sections":3,"populated_sections":2,"empty_sections":1,"coverage_pct":67},"limit":"渠道为分页样本，不代表企业完整渠道；海外商品需网店 id。品牌结果缺少可核验主体绑定时仅保留为来源线索，不进入指标与肯定性洞察。当前 MCP 未注册历史价格与销售趋势工具，相关选择器仅作缺口披露。","html_bytes":1059599,"markdown_bytes":2414}

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)
[页面截图](browser.png)