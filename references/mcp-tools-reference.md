# MCP 工具参考 — goods-mcp-server

本 skill 连接的 MCP server：`handaas-mcp-server/goods-mcp-server`（“商品大数据”）。

> **重要**：goods MCP 采用 newer-style 工具，通过 `source` / `view` 等 Literal 选择器路由到不同上游数据源，**单次工具调用不会默认触发多个计费接口**。无独立的 fuzzy_search 工具；`matchKeyword` 一般为企业名称（domestic 系列）或海外网店 id（overseas 系列），按企业名称直查。

## 通用约定

- `keywordType` 枚举（企业主体工具）：`name`（企业名称）/ `nameId`（企业 id）/ `regNumber`（注册号）/ `socialCreditCode`（统一社会信用代码）。
- 分页：`pageIndex` 从 1 开始；`pageSize` 单页最多 50。
- 价格/趋势类工具的 `statsMonth` 必须为 `yyyyMM`（如 `202505`）。
- 店铺维度数据源（store_hot_items / store_monthly）需提供 `platform` + `shopId`。

---

## 工具清单

### 1. `goods_search` — 商品搜索

用途：搜索零售商品或海外网店，用于选品、竞品发现和跨境渠道筛选。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 否 | 商品名、网店名或商品关键词 |
| `source` | Literal | 否 | `retail`（零售商品，默认）/ `overseas`（海外网店） |
| `pageIndex` | int | 否 | 从 1 开始（默认 1） |
| `pageSize` | int | 否 | retail 默认 10，overseas 默认 50；最大 50 |
| `eshopSource` | string | 否 | 海外网店平台，仅 source=overseas |
| `eshopCategories` | string | 否 | 海外商品类目，逗号分隔 |
| `eshopSalesLevel` | string | 否 | 海外网店销量等级 |
| `operationStatus` | string | 否 | 海外网店状态（默认“全部”） |
| `hasAssociateEnterprise` | string | 否 | 是否有关联企业（默认“全部”） |

返回（`total` + `resultList`）：商品/网店信息（含 name、price、saleCount、platform、eshopSource、eshopCategories 等）。

product_id：`retail`→`6a609f509d30d4fcc00ccff5`；`overseas`→`66c9a954268e9d7292c1a9ab`。

---

### 2. `goods_profile` — 商品画像

用途：查询企业国内电商商品明细或指定海外网店的商品画像。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 是 | domestic 时为企业标识；overseas 时为海外网店 id |
| `source` | Literal | 否 | `domestic`（默认）/ `overseas` |
| `keywordType` | Literal | 否 | domestic 企业标识类型（默认 name） |
| `pageIndex` | int | 否 | 从 1 开始（默认 1） |
| `pageSize` | int | 否 | 最大 50（默认 50） |

返回（`total` + `resultList`）：商品明细（productName、price、saleCount、shopName、productCategory 等）。

product_id：`domestic`→`66c33eff3c0917a9a02feb9d`；`overseas`→`66d5b7e0537c3f61d646c496`。

---

### 3. `goods_brand` — 商品品牌分析

用途：查询美业企业品牌明细或品牌产品功效概况。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 是 | 企业名称/企业 id/注册号/统一社会信用代码 |
| `view` | Literal | 否 | `brand_detail`（品牌明细，默认）/ `product_overview`（品牌产品概况） |
| `keywordType` | Literal | 否 | 主体类型（默认 name） |

返回：brand_detail 为品牌列表（brandName、productCount、saleCount 等）；product_overview 为品牌产品概况（brandCount、productCount 等）。

product_id：`brand_detail`→`66c702b725f04ab44cd24d5e`；`product_overview`→`66d5b7e1537c3f61d646c573`。

---

### 4. `goods_price` — 商品价格分析

用途：查询店铺热销商品价格表现或企业月度销售表现。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `statsMonth` | string | 是 | 统计月份 yyyyMM（如 202505） |
| `source` | Literal | 否 | `store_hot_items`（默认）/ `enterprise_monthly_sales` |
| `platform` | string | 否 | store_hot_items 必填 |
| `shopId` | string | 否 | store_hot_items 必填 |
| `matchKeyword` | string | 否 | enterprise_monthly_sales 必填（企业标识） |
| `keywordType` | Literal | 否 | 主体类型（默认 name） |

返回：商品/销售价格表现列表（productName、price/salePrice、saleCount、avgPrice 等）。

product_id：`store_hot_items`→`684ad781d4819127431f9fe1`；`enterprise_monthly_sales`→`684ad781d4819127431fa026`。

---

### 5. `goods_channel` — 商品渠道分析

用途：查询企业国内电商店铺列表或国内外网店全局明细。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 是 | 企业名称/企业 id/注册号/统一社会信用代码 |
| `source` | Literal | 否 | `domestic_store`（默认）/ `global_store` |
| `keywordType` | Literal | 否 | 主体类型（默认 name） |
| `pageIndex` | int | 否 | domestic_store 分页（默认 1） |
| `pageSize` | int | 否 | domestic_store 最大 50（默认 50） |

返回（`total` + `resultList`）：店铺/网店（shopName/eshopName、platform/eshopSource、productCount、saleCount 等）。

product_id：`domestic_store`→`66c702b725f04ab44cd24c83`；`global_store`→`672b3125338beb3ec2f5dc43`。

---

### 6. `goods_trend` — 商品销售趋势

用途：查询店铺或企业的月度、累计销售趋势。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `statsMonth` | string | 是 | 统计月份 yyyyMM |
| `source` | Literal | 否 | `store_monthly`（默认）/ `enterprise_monthly` / `enterprise_cumulative` |
| `platform` | string | 否 | store_monthly 必填 |
| `shopId` | string | 否 | store_monthly 必填 |
| `matchKeyword` | string | 否 | enterprise_monthly / enterprise_cumulative 必填 |
| `keywordType` | Literal | 否 | 主体类型（默认 name） |

返回：销售趋势列表（month/statsMonth、salesAmount、saleCount 等）。

product_id：`store_monthly`→`684ad781d4819127431f9ff8`；`enterprise_monthly`→`684ad781d4819127431fa026`；`enterprise_cumulative`→`684ad781d4819127431fa016`。

---

## 推荐调用顺序（报告编排）

1. `goods_profile`（source=domestic，企业主体）→ 商品画像概览。
2. `goods_brand`（view=brand_detail）→ 品牌明细。
3. `goods_channel`（source=domestic_store）→ 国内店铺渠道。
4. `goods_search`（source=retail）→ 商品搜索明细（可选）。
5. （当用户提供 statsMonth）`goods_price` / `goods_trend` → 价格与销售趋势。

> 单次报告通常调用 3-6 个工具；每个工具的 Literal 选择器决定具体上游数据源与计费 product_id。
