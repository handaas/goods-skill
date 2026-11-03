# goods-skill：已验收示例

本目录只展示 **4 个完全通过的真实正向场景**（最低要求4例）。

每例均为真实、非空、非缓存调用；技术检查、独立业务检查和离线浏览器检查全部通过。不把空数据、报错处理或仅生成页面计作通过。历史验收记录保留在本地 test-records/；本目录的 HTML/Markdown 由原 JSON 重渲染，不代表重新查询或重新验收。

| 场景 | 真实使用需求 | 报告 |
|---|---|---|
| [国内电商渠道结构分析](07-domestic-channel-compare/README.md) | 分析小米科技有限责任公司的国内电商店铺渠道结构，供渠道团队检查平台集中度。 | [HTML](07-domestic-channel-compare/report.html) / [MD](07-domestic-channel-compare/report.md) / [JSON](07-domestic-channel-compare/report.json) |
| [三只松鼠国内店铺样本追溯](09-domestic-store-trace/README.md) | 请列出三只松鼠股份有限公司当前可查的国内电商店铺样本、平台和原始链接，供渠道人员逐条复核；不要判断品牌归属。 | [HTML](09-domestic-store-trace/report.html) / [MD](09-domestic-store-trace/report.md) / [JSON](09-domestic-store-trace/report.json) |
| [华为全球平台记录核查](10-global-marketplace-trace/README.md) | 请核查华为技术有限公司当前返回的全球网店记录，逐条列出原始店铺名称、平台和链接；不要推断国家覆盖或官方授权。 | [HTML](10-global-marketplace-trace/report.html) / [MD](10-global-marketplace-trace/report.md) / [JSON](10-global-marketplace-trace/report.json) |
| [华为网络设备商品命名样本](11-network-product-sample/README.md) | 请抽取华为技术有限公司海外商品检索当前页的具体商品名称，用于建立网络设备命名词表；不分析价格、销量、趋势或渠道覆盖。 | [HTML](11-network-product-sample/report.html) / [MD](11-network-product-sample/report.md) / [JSON](11-network-product-sample/report.json) |

- [逐例验收结果](results.json) · [业务复核](review.json) · [证据摘要](evidence-index.json)
- 完整测试记录仅存于本地 test-records/live-replaced-20261027/（仅本地审计用，不随本目录发布），不属于可展示示例。
- 当前数据与结论限于原查询时点及公开样本；覆盖率不代表准确率或低风险。
