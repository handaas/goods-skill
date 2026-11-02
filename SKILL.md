---
name: goods-report
description: Use for generating a professional goods big-data report (商品大数据报告) from the HandaaS goods MCP — covering 企业商品明细、品牌分析、渠道分页样本，并明确披露当前不支持的历史价格/趋势维度. Trigger when users ask for “商品大数据报告”, “商品分析报告”, “查一家公司的商品”, “商品画像”, “品牌分析”, “商品价格分析”, “商品渠道分析”, “商品销售趋势”, “选品报告”, or “企业电商画像”. Infer the canonical enterprise name and the right Literal data-source selectors (source/view/stats-month), pick the right MCP tools, and produce HTML + Markdown + JSON reports automatically. MCP 服务名称触发词：零售商品动态。
---

# 商品大数据报告

## 用户契约

把“商品大数据报告”作为面向用户的调用短语。`goods-report` 仅为内部包名。

当本 skill 处于激活状态：

1. 不要向用户索要 product_id、MCP 工具名、API 字段、内部参数或凭证信息；只接受企业名称、统一社会信用代码、注册号、企业 ID（以及可选的数据源选择器与统计月份/店铺信息）。
2. 接受自然目标，例如“查一下某某公司的商品”“给我一份电商商品画像报告”“分析这家企业的品牌与渠道”“看下店铺热销商品价格”。
3. goods MCP 工具按企业名称直查（无模糊查询工具）；当用户只给关键词时，按企业名称直接查询。
4. 优先使用 MCP 连接（`GOODS_MCP_URL` Remote MCP 或本地 `handaas-mcp-server/goods-mcp-server`）；不要让用户处理签名或凭证。
5. 同时产出 HTML（可分享交付）、Markdown（知识库 / wiki）、JSON（系统集成）三类产物。
6. 报告正文必须是专业研究报告风格：只见商品事实与结构化数据，绝不出现工具名、入参、product_id、内部字段或空表。
7. 绝不打印 `secret_id`、`secret_key`、签名、token 或原始签名请求。
8. 默认 dry-run；真实付费 / 凭证调用需用户明确要求且 MCP 连接配置完整。
9. 数据为空时明确说明数据范围 / 口径，不渲染空表、不臆造事实。


- MCP 返回的嵌套 JSON 字符串（如金额 `{"coinType":"人民币","value":430000000.0}`、地址 `{"city":"杭州市",...}`）必须解析为可读文本（如"4.30 亿 人民币"、"浙江省杭州市"），绝不在报告正文、表格或指标中输出原始 JSON 字符串。
- 报告所有章节标题、指标卡标签必须用中文；`core_analysis.sections` 的 `title` 字段必须中文，不可显示英文 key（如 `holders`、`investments`）。
- 指标值必须可读化：金额格式为"X 亿/万 + 币种"，地址拼接省市区，比率显示百分号。详见 `references/report-output.md` 的「数据格式约束」。

## 付费调用纪律（先规划后查询）

每次真实调用均按接口/页计费，必须先规划再查询，不得默认全量拉取：

1. 每一次业务/工具调用、每一页都可能收费。想算 total / 页数不是无限制取全量的授权。
2. 调用前先推导：需要哪些结论、需要哪些数据维度、工具与参数计划、必要页数与最大调用预算。total 未知时，第一个必要的明细页同时完成 total 发现并直接作为报告数据，绝不为此多付一次（首屏响应必须复用，不重复拉取）。
3. 优先用一次返回的品牌明细（goods_brand）与各明细接口的 total 回答能回答的问题；分页明细接口（商品检索、海外网店商品、企业商品明细、渠道明细）仅取结论、图表、代表性记录或用户明确的全量/计数需求所需的行数。只有用户明确要全面报告时才加大分页预算，绝不因为工具存在就全部调用。
4. 在 schema 允许范围内用合理的大 pageSize（≤50），取得所需证据 / 样本即停，且不超出显式预算。更多调用必须有"缺失结论"的正当理由，不能只为填满章节。不得用样本分布冒充全量结论。
5. 复用当前任务 / 报告内的相同请求（含首屏规划数据）；不要为渲染重跑 compose/MCP，用已保存 JSON 本地重渲染。不自动重试、不重复拉取同一统计或明细、不并行独立拉取相同数据。任何补充查询必须先列缺口并复用已返回记录。
6. `total_pages` / `remaining_pages` 是按请求 pageSize 的估算；短而非空页面仍有剩余记录时在预算内继续。只有稳定有效的 total 等于实际扫描条数才算完整采集；错误、提前空页、重复页、total 变化/缺失、数量溢出均视为不完整。显式预算 / 样本停止即部分采集，绝不宣称全量。
7. 预算不足以支撑用户要求的关键结论时：先说明证据缺口与预计需要追加的调用数，再请求扩大授权（提高 `--max-pages`）；不静默降级结论，也不擅自扩大计费范围。

分页收集默认一次明细调用预算 `--max-pages 1`（每明细接口）；明细接口的 total、实际取数、完整性披露写入报告 `data_source.pagination`，报告级去重统计写入 `data_source.call_usage`。

## MCP 服务入口

- MCP 服务当前名称：零售商品动态（连接仍使用原服务目录标识）。

- 上游 MCP 项目：`handaas-mcp-server/goods-mcp-server`（位于 `HANDAAS_MCP_SERVER_ROOT` 或本仓库同级目录）。
- Remote MCP：设置环境变量 `GOODS_MCP_URL`（streamable-http），可选 `GOODS_MCP_TOKEN`。
- 本地 MCP：设置 `HANDAAS_MCP_SERVER_ROOT` 指向 `handaas-mcp-server` 仓库根目录；该 server 自己的 `.env` 提供 `INTEGRATOR_ID` / `SECRET_ID` / `SECRET_KEY`。
- 首次真实查询前，运行 `scripts/mcp_client.py ping` 与 `scripts/mcp_client.py list-tools` 验证连通。

## 按需加载 references

- 不清楚该 MCP 有哪些工具、参数、返回字段、何时调用：`references/mcp-tools-reference.md`。
- 报告结构、章节、质量底线、渲染工作流：`references/report-output.md`。

## 意图路由

| 用户意图 | 内部工作流 |
| --- | --- |
| 查一家公司的全维度商品报告 | 调商品画像 + 品牌 + 渠道 + 搜索组装全量报告；`compose_report.py --enterprise ...` |
| 指定零售/海外商品搜索 | `compose_report.py --enterprise ... --source retail\|overseas` |
| 海外网店商品画像 | `compose_report.py --enterprise <网店id> --profile-source overseas` |
| 品牌明细 vs 品牌产品概况 | `--view brand_detail\|product_overview` |
| 历史价格诉求 | 当前 MCP 不支持；保留选择器并在 `unsupported_dimensions` 披露，不发起调用 |
| 价格月份口径 | `--stats-month` 仅记录用户口径，不触发额外工具 |
| 国内店铺渠道 vs 国内外网店渠道 | `--channel-source domestic_store\|global_store` |
| 历史销售趋势诉求 | 当前 MCP 不支持；明确披露，不生成占位趋势 |
| 只要 JSON / 只要 HTML / 只要 Markdown | 用 `--output`（JSON）或 `--report-output`（HTML+MD），或 `render_report.py` 重渲染 |
| 连接 / 工具不存在 / 传参错误 | `mcp_client.py ping` / `list-tools` 排查；报脱敏后的缺失项 |

## Golden path for 商品大数据报告

1. **解析企业主体**：goods MCP 按企业名称直查；将输入视为企业全称（含“公司/集团/有限/院/厂/中心/事务所/合作社/合伙”后缀时直接确认）。
2. **确定数据源选择器**：根据用户意图选择 `source`（搜索）、`--profile-source`、`--view`（品牌）、`--channel-source`；价格/趋势选择器只用于记录当前不支持的诉求。
3. **调用已注册工具**：企业商品用 `goods_enterprise_products`，海外店铺商品用 `goods_overseas_store_products`，并调用 `goods_brand` / `goods_channel`；仅海外关键词搜索使用 `goods_search`。不得调用未注册的 profile/price/trend 工具。
4. **组装统一报告**：核心分析含企业商品样本、品牌来源线索、渠道样本行；分页明细接口在 `--max-pages` 预算内收集（默认 1 页），total / 实际取数 / 完整性写入 `data_source.pagination`，报告级去重统计写入 `data_source.call_usage`；品牌响应没有可核验主体绑定字段时标 unverified，不进入肯定指标/洞察；价格/趋势选择器如出现，写入 unsupported_dimensions。
5. **渲染三件套**：`compose_report.py --enterprise ... --output ... --report-output ...` 直接产出 JSON + HTML + Markdown；或 `render_report.py --input ... --output ...` 重渲染。
6. **返回路径**：返回 JSON、HTML、Markdown 文件路径，以及企业全称映射与数据口径（含所选数据源）。

## 脚本速查

```bash
# 校验连接配置（脱敏）
python scripts/validate_config.py --allow-placeholders

# 连通性自测
python scripts/mcp_client.py ping
python scripts/mcp_client.py list-tools

# 干跑（不调真实 API，用样例数据组装报告骨架）
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --dry-run \
  --output output/goods.json \
  --report-output output/goods.html

# 真实查询 + 渲染（默认：零售搜索 + 国内画像 + 品牌明细 + 国内店铺渠道）
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --output output/goods.json \
  --report-output output/goods.html

# 明细接口需要更多页时显式扩大预算（默认 --max-pages 1；先按 total 列缺口再请求授权）
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --max-pages 3 \
  --output output/goods.json \
  --report-output output/goods.html

# 历史价格/趋势诉求：仅生成不支持披露，不会调用未知工具
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --price-source enterprise_monthly_sales \
  --trend-source enterprise_monthly \
  --stats-month 202505 \
  --report-output output/goods_202505.html

# 海外网店画像 + 全球网店渠道
python scripts/compose_report.py \
  --enterprise "<海外网店id>" \
  --profile-source overseas \
  --channel-source global_store \
  --report-output output/goods_overseas.html

# 手动调单个工具
python scripts/mcp_client.py call-tool \
  --tool goods_enterprise_products \
  --arguments-json '{"matchKeyword": "示例科技有限公司", "productType": "retail", "keywordType": "name"}'

# 重渲染已有 JSON
python scripts/render_report.py --input output/goods.json --output output/goods.html
python scripts/render_report.py --input output/goods.json --output output/goods.md
```

## 输出字段

- `subject`：企业全称、匹配关键词、主体类型、解析说明。
- `abstract` / `summary`：封面摘要与详细摘要。
- `metrics`：商品检索结果、电商商品数、店铺/渠道数等指标卡。
- `caliber`：匹配对象、匹配方式（含所选数据源）、数据范围、产品、局限。
- `core_analysis`：企业商品样本、品牌分析、渠道样本行（受 `--max-pages` 预算约束，默认 1 页，非全量枚举）；空/错误不生成占位行。
- `data_source.unsupported_dimensions`：当前 MCP 不支持的历史价格/趋势诉求。
- `data_source.pagination`：各分页明细接口的上游 total、预计页数、实际请求页数、取得行数、完整性判定与停止原因。
- `data_source.call_usage`：本次报告的实付请求数与复用请求数（相同工具+参数只付一次）。
- `representative_records`：代表性商品/店铺记录（名称 / 价格 / 销量 / 平台）。
- `insights`：结构化解读；未验证主体关系的品牌线索不得进入品牌矩阵洞察。
- `data_source`：MCP server、所选数据产品（随选择器动态变化）、生成时间、是否 dry-run，以及 `pagination`、`call_usage`。

若 API 调用失败，明确报出缺失的配置 / 缺失的工具 / MCP 错误 / 参数校验错误 / 上游网络错误，给出 dry-run 命令或配置步骤，绝不暴露密钥。
