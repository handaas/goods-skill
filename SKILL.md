---
name: goods-report
description: Use for generating a professional goods big-data report (商品大数据报告) from the HandaaS goods MCP — covering 商品搜索明细、商品画像、品牌分析、价格分析、渠道分析、销售趋势. Trigger when users ask for “商品大数据报告”, “商品分析报告”, “查一家公司的商品”, “商品画像”, “品牌分析”, “商品价格分析”, “商品渠道分析”, “商品销售趋势”, “选品报告”, or “企业电商画像”. Infer the canonical enterprise name and the right Literal data-source selectors (source/view/stats-month), pick the right MCP tools, and produce HTML + Markdown + JSON reports automatically.
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

## MCP 服务入口

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
| 价格分析（店铺热销商品） | `--price-source store_hot_items --stats-month 202505 --platform ... --shop-id ...` |
| 价格分析（企业月销售） | `--price-source enterprise_monthly_sales --stats-month 202505` |
| 国内店铺渠道 vs 国内外网店渠道 | `--channel-source domestic_store\|global_store` |
| 销售趋势（店铺月度/企业月度/企业累计） | `--trend-source store_monthly\|enterprise_monthly\|enterprise_cumulative --stats-month 202505` |
| 只要 JSON / 只要 HTML / 只要 Markdown | 用 `--output`（JSON）或 `--report-output`（HTML+MD），或 `render_report.py` 重渲染 |
| 连接 / 工具不存在 / 传参错误 | `mcp_client.py ping` / `list-tools` 排查；报脱敏后的缺失项 |

## Golden path for 商品大数据报告

1. **解析企业主体**：goods MCP 按企业名称直查；将输入视为企业全称（含“公司/集团/有限/院/厂/中心/事务所/合作社/合伙”后缀时直接确认）。
2. **确定数据源选择器**：根据用户意图选择 `source`（搜索）、`--profile-source`、`--view`（品牌）、`--channel-source`、`--price-source`、`--trend-source`；价格/趋势需 `--stats-month`（yyyyMM）。
3. **调用商品工具**：`goods_profile`（画像）、`goods_brand`（品牌）、`goods_channel`（渠道）、`goods_search`（搜索）；按需 `goods_price` / `goods_trend`（需 statsMonth）。
4. **组装统一报告**：核心分析含商品画像（KV）、品牌分析（表/KV）、价格分析（表）、渠道分析（表）、销售趋势（表）、商品搜索明细（表）。
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

# 企业月度销售价格分析 + 企业月度销售趋势
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
  --tool goods_profile \
  --arguments-json '{"matchKeyword": "示例科技有限公司", "source": "domestic", "keywordType": "name"}'

# 重渲染已有 JSON
python scripts/render_report.py --input output/goods.json --output output/goods.html
python scripts/render_report.py --input output/goods.json --output output/goods.md
```

## 输出字段

- `subject`：企业全称、匹配关键词、主体类型、解析说明。
- `abstract` / `summary`：封面摘要与详细摘要。
- `metrics`：商品检索结果、电商商品数、店铺/渠道数等指标卡。
- `caliber`：匹配对象、匹配方式（含所选数据源）、数据范围、产品、局限。
- `core_analysis`：商品画像（KV）、品牌分析（表/KV）、价格分析（表）、渠道分析（表）、销售趋势（表）、商品搜索明细（表）。
- `representative_records`：代表性商品/店铺记录（名称 / 价格 / 销量 / 平台）。
- `insights`：结构化解读（商品规模 / 品牌矩阵 / 渠道布局）。
- `data_source`：MCP server、所选数据产品（随选择器动态变化）、生成时间、是否 dry-run。

若 API 调用失败，明确报出缺失的配置 / 缺失的工具 / MCP 错误 / 参数校验错误 / 上游网络错误，给出 dry-run 命令或配置步骤，绝不暴露密钥。
