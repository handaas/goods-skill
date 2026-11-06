# 报告输出 — 商品大数据报告

本文件规定 `goods-report` skill 产出的报告结构、质量底线与渲染工作流。所有产物遵循 `AGENTS.md` 的统一 JSON 骨架与本 skill 的领域裁剪。

## 默认展示模式

- HTML：可分享 / 可交付的可视化报告；独立本地文件，内嵌 CSS，无调试 / 内部段落。
- Markdown：知识库 / wiki / PRD / 后续手工编辑。
- JSON：系统集成或二次处理。

`compose_report.py` 通过 `--report-output <path>` 同时产出 HTML + Markdown；`--output <path>` 产出 JSON。`render_report.py` 可基于已有 JSON 重渲染。

## 数据源选择器

goods MCP 通过 Literal 选择器路由到不同上游数据源（单次调用不触发多个计费接口）：

- `--source retail|overseas`：商品搜索（零售商品 / 海外网店）。
- `--profile-source domestic|overseas`：商品画像（企业电商商品 / 海外网店商品；overseas 时 matchKeyword 为网店 id）。
- `--view brand_detail|product_overview`：品牌分析（品牌明细 / 品牌产品概况）。
- `--channel-source domestic_store|global_store`：渠道分析（国内电商店铺 / 国内外网店）。
- `--price-source store_hot_items|enterprise_monthly_sales`：价格分析（需 `--stats-month`；前者需 `--platform`+`--shop-id`）。
- `--trend-source store_monthly|enterprise_monthly|enterprise_cumulative`：销售趋势（需 `--stats-month`；store_monthly 需 `--platform`+`--shop-id`）。

## 报告结构（7 章）

1. **报告摘要**：分析对象、数据覆盖范围、核心发现、关键指标卡。
2. **查询对象与口径**：企业全称、匹配方式（含所选数据源）、数据范围、产品、局限。
3. **数据总览**：商品检索结果、电商商品数、店铺/渠道数等指标卡。
4. **核心分析**（商品专属子章节，由 `core_analysis.sections` 驱动渲染）：
   - 商品画像（KV：商品总数 / 商品名称 / 价格 / 销量 / 店铺名称 / 商品类目）。
   - 品牌分析（表：品牌名称 / 商品数 / 销量；或 KV：品牌数量 / 商品数）。
   - 价格分析（表：商品名称 / 价格 / 销量 / 统计月份）。
   - 渠道分析（表：店铺/网店名称 / 平台 / 商品数 / 销量）。
   - 销售趋势（表：周期/月份 / 销售额 / 销量）。
   - 商品搜索明细（表：商品/网店名称 / 价格 / 销量 / 平台/来源 / 类目）。
5. **代表性记录**：关键商品/店铺记录 Top N（名称 / 价格 / 销量 / 平台）。
6. **特征与洞察**：结构化解读（商品规模 / 品牌矩阵 / 渠道布局），每条含 `feature` / `evidence` / `interpretation`。
7. **数据口径与来源**：MCP server、所选数据产品（随选择器动态变化）、生成时间、是否 dry-run。

## 质量底线

- 报告脱离 Skill 上下文也可独立阅读；正文只见商品事实与结构化数据。
- 绝不出现工具名、入参（如 `matchKeyword=...`、`source=...`）、product_id、内部字段名、空表、调试信息。
- HTML 采用研究报告视觉风格：A4 风、灰色顶部条纹、蓝色报告横幅、左侧目录 / 范围侧栏、深蓝章节标题、深蓝表头、浅蓝斑马行、打印友好分页。
- 数据为空时明确说明数据范围 / 口径，不渲染空表、不臆造事实。
- 绝不打印 `secret_id` / `secret_key` / 签名 / token / 原始签名请求。
- 报告口径中应说明本次所用的数据源选择器（如 source/view/stats-month）。

### 数据格式约束（铁律）

以下约束适用于 compose_report.py 组装数据与 render_report.py 渲染输出的全过程：

1. **嵌套 JSON 字符串必须解析**：MCP 返回的某些字段（如 `regCapital`、`addressValue`、`subscriptionDetail`）可能是 JSON 字符串（例：`{"coinType":"人民币","value":430000000.0}`）。compose 层必须调用 `_unwrap_json_str()` / `_parse_reg_capital()` / `_flatten_addr()` 解析为可读文本（如"4.30 亿 人民币"、"浙江省杭州市滨江区..."）。绝不在报告正文、表格单元格或指标值中输出原始 JSON 字符串。

2. **section 标题必须用中文**：`core_analysis.sections` 数组中每个 section 的 `title` 字段必须使用中文（如"企业基本信息"、"对外投资"、"股东信息"）。`key` 字段用英文 snake_case 供程序索引，但 `title` 绝不可显示英文 key。即使缺少 sections 数组，渲染器回退逻辑也内置了 `_TITLE_MAP` 映射。

3. **指标值可读化**：所有 `metrics` 的 `value` 字段必须格式化为人类可读形式：
   - 金额：`10995210218.0` → `109.95 亿 人民币`（≥1 亿用亿，≥1 万用万）
   - 地址：嵌套 dict → 省+市+区拼接 或取 `value` 字段
   - 比率：`0.8858` → `88.58%`
   - 日期：保持 `yyyy-MM-dd` 格式
   - "-" 表示字段缺失（MCP 未返回）；`0` 表示真实为零

4. **企业画像指标提取**：有 fuzzy_search 的 skill 必须从返回的 record 中提取 `regCapitalValue` / `foundTime` / `operStatus` / `enterpriseType` / `legalRepresentative`，通过 `_enrich_metrics_with_profile()` 追加为指标卡。

5. **分布派生指标**：`_derive_core_metrics()` 从 core_analysis 各 section 计算分布指标（CR3 集中度、覆盖城市/平台/类目数、价格区间、正面占比等），确保指标总数 M ≥ 6。

## 工作流

```bash
# 1. 干跑（不调真实 API，用样例数据组装报告骨架）
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --dry-run \
  --output output/goods.json \
  --report-output output/goods.html

# 2. 真实查询 + 渲染（默认数据源）
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --output output/goods.json \
  --report-output output/goods.html

# 3. 企业月度销售价格分析 + 企业月度销售趋势
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --price-source enterprise_monthly_sales \
  --trend-source enterprise_monthly \
  --stats-month 202505 \
  --report-output output/goods_202505.html

# 4. 重渲染已有 JSON
python scripts/render_report.py --input output/goods.json --output output/goods.html
python scripts/render_report.py --input output/goods.json --output output/goods.md
```

返回：JSON 路径、HTML 路径、Markdown 路径，以及企业全称映射与数据口径摘要。

## 内容审校（离线）

对已有 `report.json` 复核而不调用 MCP：`python scripts/goods_content_review.py --input <report.json> --out-dir <dir>`；纯函数 `goods_content_review.apply_content_review(report)`。审校顺序：

1. 搜索命中与商品总量分开：`商品检索结果` 不进业务规模指标；规模用企业商品明细总数。
2. 渠道平台与链接域名交叉核对；不一致保留原值并标“待核实”，不静默改写；上游未返回可识别平台时，链接推断仅作待核实线索，不计入平台数。
3. 样本边界：`店铺/渠道数` 是上游总数，`覆盖平台（样本）` 只统计上游平台字段可识别的平台；不推平台份额或数据完整性。
4. 空列：价格全部为空时隐藏价格列并注明“上游未返回价格”；`commodity` 等来源码转可读名称。
5. 措辞：删除“选品基础”“多来源说明数据全面”等营销式结论；正文不出现 `keywordType`、`domestic_store`。

交付前按最终 `sections` 与实际 body 刷新 `data_source.quality_report`（`0` 计为已填充；`coverage_pct` 仅为章节填充率）；保留原 `generated_at`。平台域名用 `urlsplit().hostname` 做精确/后缀匹配，不接受 credentials、query 或外来域名中的片段。

CLI 会拒绝 `--out-dir` 的 `report.json` 解析为 `--input` 的调用；输出目标应位于本 skill 的 `output/content-quality-review/`，不得覆盖 `examples/` 或 `test-records/`。
