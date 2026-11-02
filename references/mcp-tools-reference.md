# Goods MCP 实际工具参考

> 依据同仓上游 `goods-mcp-server/server/mcp_server.py` 的当前注册签名。不得调用未注册的 `goods_profile`、`goods_price` 或 `goods_trend`。

## 已注册工具

### `goods_enterprise_search`
企业检索。参数：`matchKeyword`、`keywordType`、`pageIndex`、`pageSize`。

### `goods_search`
商品关键词搜索。参数：`matchKeyword`、`source=retail|overseas`、`pageIndex`、`pageSize`。它不是企业归属关系证明；企业报告优先使用 `goods_enterprise_products`。

### `goods_enterprise_products`
企业商品明细。参数：`matchKeyword`、`productType=retail|ecommerce`、`keywordType`、`pageIndex`、`pageSize`。

### `goods_overseas_store_products`
海外网店商品明细。参数：`storeId`、`pageIndex`、`pageSize`。`storeId` 不是企业名称。

### `goods_brand`
品牌分析。参数：`matchKeyword`、`view=brand_detail|product_overview`、`keywordType`。

### `goods_channel`
渠道分析。参数：`matchKeyword`、`source=domestic_store|global_store`、`keywordType`、`pageIndex`、`pageSize`。

全球渠道可能返回 `eshopList` / `eshopListCount`，国内渠道通常返回 `resultList` / `total`。两者均为分页样本，实际收集页数遵循 `--max-pages` 预算（默认 1）；不得把单页、单个字典或全 `-` 占位行描述成企业完整渠道。

## 当前不支持的维度

当前 MCP 未注册历史价格或销售趋势工具。CLI 为兼容既有调用保留 `--price-source`、`--trend-source`、`--stats-month`，但报告只会明确披露“不支持”，不会发起 Unknown tool 调用，也不会生成伪造数据。
