#!/usr/bin/env python3
"""Compose a goods big-data report by orchestrating the goods MCP.

Calls the upstream goods-mcp-server tools and assembles a structured JSON
payload rendered into a professional HTML / Markdown report. Supports
``--dry-run`` which returns a well-formed skeleton from the bundled sample data
WITHOUT contacting the MCP.

The goods MCP uses newer-style tools with Literal ``source``/``view`` selectors
and type hints; there is no separate fuzzy search. The ``matchKeyword`` is the
enterprise name (or overseas shop id for the overseas product profile) and is
queried directly.

Workflow (real run, enterprise mode):
  1. Use the provided enterprise name directly (these MCP tools query by name).
  2. Call goods_profile (画像), goods_brand (品牌), goods_channel (渠道).
  3. Optionally call goods_search / goods_price / goods_trend when the user
     supplies the relevant selectors (source/view/stats-month/platform/shop).
  4. Build unified report JSON with domain sections.
  5. Optionally render HTML + Markdown.

This file never prints secrets; MCP credentials live in the server's own .env.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
from typing import Any, Dict, List, Mapping, Optional, Sequence

from common import REPORT_BANNER, REPORT_TYPE, attach_pagination, call_tool_once, collect_detail_pages, json_dumps, load_json_file, paid_call_scope, print_json
import mcp_client
from render_report import render_html, render_markdown, html_to_pdf

SAMPLE_PATH = pathlib.Path(__file__).resolve().parent.parent / "assets" / "report.example.json"

# Goods MCP tools.
T_SEARCH = "goods_search"
T_ENTERPRISE_PRODUCTS = "goods_enterprise_products"
T_OVERSEAS_PRODUCTS = "goods_overseas_store_products"
T_BRAND = "goods_brand"
T_CHANNEL = "goods_channel"

# Default Literal selectors.
DEFAULT_SEARCH_SOURCE = "retail"
DEFAULT_PROFILE_SOURCE = "domestic"
DEFAULT_BRAND_VIEW = "brand_detail"
DEFAULT_CHANNEL_SOURCE = "domestic_store"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _is_api_error(value: Any) -> bool:
    """Detect MCP API error responses (not empty data, but actual failures like 405)."""
    if value is None:
        return False
    if isinstance(value, str):
        return any(s in value for s in ("接口调用失败", "查询失败", "状态码：4", "状态码：5"))
    if isinstance(value, dict):
        if value.get("_mcp_error") or value.get("_error") or value.get("isError") is True or value.get("error"):
            return True
        for v in value.values():
            if isinstance(v, str) and any(s in v for s in ("接口调用失败", "查询失败", "状态码：4", "状态码：5")):
                return True
    return False

def _first_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if _is_api_error(value):
            return []
        # Treat upstream empty responses ({"text": "查询数据为空"}) and internal
        # skip markers ({"_error": "未指定..."}) as empty so tables don't render
        # a phantom all-"-" row.
        if set(value.keys()) <= {"text", "error", "code", "_error"} and not any(
            isinstance(value.get(k), list) for k in ("resultList", "list", "items", "data", "productList")
        ):
            return []
        for key in ("resultList", "list", "items", "data", "productList", "eshopList"):
            if isinstance(value.get(key), list):
                return value[key]
    if value in (None, "", {}):
        return []
    return [value]


def _first_record(value: Any) -> Dict[str, Any]:
    for record in _first_list(value):
        if isinstance(record, dict):
            return record
    if isinstance(value, dict) and not _is_api_error(value):
        return value
    return {}


def _text(value: Any, limit: int = 0) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        t = json.dumps(value, ensure_ascii=False)
    else:
        t = str(value)
    t = " ".join(t.split())
    if limit and len(t) > limit:
        return t[: limit - 1].rstrip() + "…"
    return t


def _int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_call(tool: str, arguments: Dict[str, Any]) -> Any:
    try:
        result = call_tool_once(mcp_client.call_tool, tool, arguments)
        if _is_api_error(result):
            return {"_error": "API错误"}
        return result
    except Exception as exc:
        return {"_error": str(exc)}


def _safe_total(payload: Any) -> Any:
    if isinstance(payload, dict):
        if payload.get("total") is not None:
            return payload.get("total")
        if payload.get("dataTotal") is not None:
            return payload.get("dataTotal")
    return None


def _channel_total(payload: Any) -> Any:
    """Channel total key differs by source: domestic uses resultList/total, global uses eshopList/eshopListCount."""
    if isinstance(payload, dict):
        for key in ("total", "dataTotal", "eshopListCount"):
            value = payload.get(key)
            if value is not None:
                return value
    return None


def _is_error(payload: Any) -> bool:
    return isinstance(payload, dict) and ("error" in payload or "_error" in payload)


def _payload_status(payload: Any) -> str:
    if _is_api_error(payload):
        return "error"
    if isinstance(payload, dict) and str(payload.get("text") or "").strip() == "查询数据为空":
        return "empty"
    if _first_list(payload) or (isinstance(payload, dict) and any(v not in (None, "", [], {}) for v in payload.values())):
        return "success"
    return "empty"


def _join_list(value: Any) -> str:
    items = _first_list(value)
    return "、".join(_text(t) for t in items if t) if items else ""


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #

def resolve_enterprise_name(raw: str) -> Dict[str, Any]:
    """Goods MCP tools query by enterprise name directly; treat input as full name.

    When the input clearly looks like a full name (contains common company
    suffixes) we use it verbatim; otherwise we still use it as-is because there
    is no fuzzy search tool, but flag it as not definitively resolved.
    """
    raw = (raw or "").strip()
    if not raw:
        return {"keyword": "", "enterprise": "", "resolved": False, "reason": "关键词为空"}
    if any(suffix in raw for suffix in ("公司", "集团", "有限", "院", "厂", "中心", "事务所", "合作社", "合伙")):
        return {"keyword": raw, "enterprise": raw, "resolved": True, "reason": "视为企业全称"}
    return {"keyword": raw, "enterprise": raw, "resolved": True, "reason": "按企业名称直查（无模糊查询工具）"}


# --------------------------------------------------------------------------- #
# Section builders
# --------------------------------------------------------------------------- #

def build_subject(raw: str, resolved: Mapping[str, Any], keyword_type: str) -> Dict[str, Any]:
    return {
        "enterprise": resolved.get("enterprise") or raw,
        "matchKeyword": resolved.get("enterprise") or raw,
        "keywordType": keyword_type,
        "match_raw": raw,
        "resolved": bool(resolved.get("resolved")),
        "resolve_reason": resolved.get("reason", ""),
    }


def build_metrics(search_total: Any, profile: Mapping[str, Any], channel_total: Any) -> List[Dict[str, Any]]:
    metrics: List[Dict[str, Any]] = []
    if search_total is not None:
        metrics.append({"label": "商品检索结果", "value": _text(search_total), "hint": "本次商品搜索命中数"})
    p = profile if isinstance(profile, dict) else {}
    if _is_error(p):
        p = {}
    profile_total = _safe_total(p)
    if profile_total is not None and not metrics:
        metrics.append({"label": "电商商品数", "value": _text(profile_total), "hint": "企业电商商品明细总数"})
    elif profile_total is not None:
        metrics.append({"label": "电商商品数", "value": _text(profile_total), "hint": "企业电商商品明细总数"})
    if channel_total is not None:
        metrics.append({"label": "店铺/渠道数", "value": _text(channel_total), "hint": "电商店铺或网店数量"})

    # Totals come from different products and universes. Do not divide search,
    # enterprise-product, and channel totals without a documented common set.
    return [m for m in metrics if m.get("value") not in ("", None, "-")]


def build_caliber(subject: Mapping[str, Any], selectors: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "match_target": subject.get("enterprise") or subject.get("match_raw"),
        "match_type": f"商品数据按企业主体匹配（keywordType={subject.get('keywordType', 'name')}）；商品明细/品牌/渠道通过当前 MCP 已注册工具查询",
        "data_scope": "企业商品明细、品牌分析、渠道本次采集样本",
        "products": ["企业商品明细", "商品品牌分析", "商品渠道分析"],
        "limit": "渠道为分页样本，不代表企业完整渠道；海外商品需网店 id。品牌结果缺少可核验主体绑定时仅保留为来源线索，不进入指标与肯定性洞察。当前 MCP 未注册历史价格与销售趋势工具，相关选择器仅作缺口披露。",
    }


def _goods_price_value(raw: Any) -> Optional[float]:
    """Parse '24.8元' / '24.8' / 24.8 → float; None if not parseable."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    import re as _re
    m = _re.search(r"(\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else None


def _goods_price_text(raw: Any) -> str:
    v = _goods_price_value(raw)
    return f"{v:g}元" if v is not None else _text(raw)


def build_core_analysis(
    search: Any,
    profile: Any,
    brand: Any,
    price: Any,
    channel: Any,
    trend: Any,
    selectors: Mapping[str, Any],
) -> Dict[str, Any]:
    # 商品明细：goods_enterprise_products 返回 {resultList:[{goodsName,
    # goodsPrice, goodsSource, goodsImageLink}], total}. goods_search 返回相同字段，
    # 但按企业名查询通常返回"产品不存在"，因此商品明细以 profile 为主、search 为辅。
    profile_total = _safe_total(profile) if isinstance(profile, dict) else None
    primary_list = profile if (profile and not _is_error(profile)) else search
    goods_rows: List[Dict[str, Any]] = []
    for item in _first_list(primary_list):
        if not isinstance(item, dict):
            continue
        # 兼容两种来源：profile(goodsName/goodsPrice/goodsSource) 与 search（同字段）。
        name = item.get("goodsName") or item.get("name") or item.get("productName")
        if not name:
            continue
        goods_rows.append({
            "商品名称": _text(name) or "-",
            "价格": _goods_price_text(item.get("goodsPrice") if item.get("goodsPrice") is not None else item.get("price")),
            "来源": _text(item.get("goodsSource") or item.get("source") or item.get("eshopSource")) or "-",
        })

    # 商品画像 KV（基于 profile 汇总：商品总数 + 价格带 + 来源平台）。
    profile_kv: Dict[str, Any] = {}
    if profile_total is not None:
        profile_kv["电商商品总数"] = _text(profile_total)
    if goods_rows:
        prices = [p for p in (_goods_price_value(r.get("价格")) for r in goods_rows) if p is not None]
        if prices:
            profile_kv["样本价格区间"] = f"{min(prices):g}~{max(prices):g}元"
            profile_kv["样本均价"] = f"{sum(prices) / len(prices):.1f}元"
        sources = [str(r.get("来源")) for r in goods_rows if r.get("来源") and r.get("来源") != "-"]
        if sources:
            uniq = []
            for s in sources:
                if s not in uniq:
                    uniq.append(s)
            profile_kv["样本来源"] = "、".join(uniq[:8])

    # 品牌分析：goods_brand view=brand_detail 返回 {brandsCount, brandsList:[{name,
    # productCount, logo, mainProducts}]}.
    brand_kv: Dict[str, Any] = {}
    brand_rows: List[Dict[str, Any]] = []
    b = brand if isinstance(brand, dict) and not _is_error(brand) else {}
    brand_subject = _text(b.get("enterpriseName") or b.get("companyName"))
    expected_subject = _text(selectors.get("enterprise"))
    brand_evidence_status = (
        "verified_subject_relation"
        if brand_subject and expected_subject and brand_subject.strip() == expected_subject.strip()
        else "unverified_subject_relation"
    )
    if b.get("brandsCount") is not None:
        brand_kv["品牌数量"] = _text(b.get("brandsCount"))
    brand_items = b.get("brandsList") or _first_list(brand)
    for bi in brand_items:
        if not isinstance(bi, dict):
            continue
        brand_rows.append({
            "品牌名称": _text(bi.get("name")) or "-",
            "商品数": _text(bi.get("productCount")) or "-",
            "主营产品": _join_list(bi.get("mainProducts")) or "-",
        })

    # 价格分析表（store_hot_items / enterprise_monthly_sales；字段未统一，保留兼容）。
    price_rows: List[Dict[str, Any]] = []
    for item in _first_list(price):
        if not isinstance(item, dict):
            continue
        price_rows.append({
            "商品名称": _text(item.get("goodsName") or item.get("productName") or item.get("name")) or "-",
            "价格": _goods_price_text(item.get("goodsPrice") if item.get("goodsPrice") is not None else (item.get("price") or item.get("salePrice") or item.get("avgPrice"))),
            "销量": _text(item.get("saleCount") or item.get("sales") or item.get("monthSales")) or "-",
            "统计月份": _text(selectors.get("stats_month")) or "-",
        })

    # 渠道分析：goods_channel domestic_store 返回 {resultList:[{ecShopName, ecSource,
    # ecShopUrl, ecShopFoundTime, ecShopProducts}], total}.
    channel_rows: List[Dict[str, Any]] = []
    channel_total = _safe_total(channel) if isinstance(channel, dict) else None
    if channel_total is None and isinstance(channel, dict):
        channel_total = channel.get("eshopListCount")
    for item in _first_list(channel):
        if not isinstance(item, dict):
            continue
        channel_rows.append({
            "店铺名称": _text(item.get("ecShopName") or item.get("eshopName") or item.get("shopName")) or "-",
            "平台": _text(item.get("ecSource") or item.get("eshopSource") or item.get("platform")) or "-",
            "开店时间": _text(item.get("ecShopFoundTime") or item.get("eshopFoundTime")) or "-",
            "店铺链接": _text(item.get("ecShopUrl") or item.get("eshopUrl")) or "-",
            "在售关键词数": str(len(item.get("ecShopProducts") or [])) if isinstance(item.get("ecShopProducts"), list) else "-",
        })

    # 销售趋势表（需 stats_month；字段兼容多种命名）。
    trend_rows: List[Dict[str, Any]] = []
    for item in _first_list(trend):
        if not isinstance(item, dict):
            continue
        trend_rows.append({
            "周期/月份": _text(item.get("month") or item.get("statsMonth") or item.get("date") or item.get("statsMonthStr")) or "-",
            "销售额": _text(item.get("salesAmount") or item.get("amount") or item.get("totalSaleAmount")) or "-",
            "销量": _text(item.get("saleCount") or item.get("sales") or item.get("totalSaleQty")) or "-",
        })

    sections: List[Dict[str, Any]] = []

    # 商品画像 KV
    if profile_kv:
        sections.append({"key": "product_profile", "title": "商品画像", "kind": "kv", "note": "企业电商商品画像概览"})

    # 品牌分析（bar 优先，无 list 时用 KV）
    if brand_rows:
        sections.append({"key": "brand_analysis", "title": "品牌来源线索", "kind": "bar", "note": "上游未返回可核验的企业绑定字段；仅保留来源线索，不作为确定企业品牌",
                         "chart": {"name": "品牌名称", "value": "商品数", "orient": "v"},
                         "columns": [("品牌名称", "品牌名称"), ("商品数", "商品数"), ("主营产品", "主营产品")]})
    elif brand_kv:
        sections.append({"key": "brand_analysis", "title": "品牌分析", "kind": "kv", "note": "企业品牌产品概况"})

    # 价格分析（仅当 --stats-month 提供时有数据）
    if price_rows:
        sections.append({"key": "price_analysis", "title": "价格分析", "kind": "bar",
                         "note": f"统计月份 {selectors.get('stats_month') or '-'}；数据源 {selectors.get('price_source') or '-'}",
                         "chart": {"name": "商品名称", "value": "价格", "orient": "h"},
                         "columns": [("商品名称", "商品名称"), ("价格", "价格"), ("销量", "销量"), ("统计月份", "统计月份")]})

    # 渠道分析
    if channel_rows:
        sections.append({"key": "channel_analysis", "title": "渠道分析", "kind": "table",
                         "note": f"数据源 {selectors.get('channel_source') or '-'}；上游总数 {channel_total if channel_total is not None else '未知'}，本次采集展示 {len(channel_rows)} 条样本，不代表企业完整渠道",
                         "columns": [("店铺名称", "店铺名称"), ("平台", "平台"), ("开店时间", "开店时间"), ("店铺链接", "店铺链接"), ("在售关键词数", "在售关键词数")]})

    # 销售趋势（仅当 --stats-month 提供时有数据）
    if trend_rows:
        sections.append({"key": "sales_trend", "title": "销售趋势", "kind": "line",
                         "note": f"统计月份 {selectors.get('stats_month') or '-'}；数据源 {selectors.get('trend_source') or '-'}",
                         "chart": {"x": "周期/月份", "y": "销售额", "area": True},
                         "columns": [("周期/月份", "周期/月份"), ("销售额", "销售额"), ("销量", "销量")]})

    # 商品明细（profile 主导）
    if goods_rows:
        sections.append({"key": "search_records", "title": "电商商品明细", "kind": "table",
                         "note": f"企业电商商品 {profile_total if profile_total is not None else '若干'} 条，本次采集展示 {len(goods_rows)} 条样本",
                         "columns": [("商品名称", "商品名称"), ("价格", "价格"), ("来源", "来源")]})

    return {
        "sections": sections,
        "product_profile": profile_kv,
        "brand_analysis": brand_rows if brand_rows else brand_kv,
        "brand_evidence_status": brand_evidence_status if (brand_rows or brand_kv) else "empty",
        "price_analysis": price_rows,
        "channel_analysis": channel_rows,
        "sales_trend": trend_rows,
        "search_records": goods_rows,
        "source_status": {
            "search": _payload_status(search) if selectors.get("search_source") == "overseas" else "not_requested",
            "enterprise_products": _payload_status(profile),
            "brand": _payload_status(brand), "channel": _payload_status(channel),
            "price": "unsupported" if selectors.get("price_source") or selectors.get("stats_month") else "not_requested",
            "trend": "unsupported" if selectors.get("trend_source") else "not_requested",
        },
    }


def build_records(core: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for item in core.get("search_records") or []:
        out.append({
            "商品名称": item.get("商品名称") or "-",
            "价格": item.get("价格") or "-",
            "来源": item.get("来源") or "-",
        })
    if not out:
        for item in core.get("channel_analysis") or []:
            out.append({
                "店铺名称": item.get("店铺名称") or "-",
                "平台": item.get("平台") or "-",
                "开店时间": item.get("开店时间") or "-",
            })
    return out[:20]


def _trend_analysis(rows: List[Mapping[str, Any]], value_key: str = "销售额") -> Dict[str, Any]:
    """Compute trend direction, peak, and YoY/MoM change from a {period,value} series."""
    nums = []
    for r in rows:
        try:
            nums.append(float(str(r.get(value_key, 0)).replace(",", "")))
        except (TypeError, ValueError):
            nums.append(0.0)
    if not nums:
        return {}
    peak_idx = max(range(len(nums)), key=lambda i: nums[i])
    direction = "持平"
    yoy = ""
    if len(nums) >= 2:
        last, prev = nums[-1], nums[-2]
        if prev > 0:
            pct = (last - prev) / prev * 100
            if pct > 5:
                direction = f"上升 {pct:.0f}%"
            elif pct < -5:
                direction = f"下降 {abs(pct):.0f}%"
            yoy = f"环比 {pct:+.0f}%"
    return {"peak_period": rows[peak_idx].get("周期/月份", "-"), "peak_value": nums[peak_idx], "direction": direction, "yoy": yoy, "last": nums[-1]}


def _concentration(rows: Sequence[Mapping[str, Any]], name_key: str, value_key: str, top_n: int = 3) -> Dict[str, Any]:
    """Compute top-N concentration (CRn) and dominant category."""
    items = []
    for r in rows:
        try:
            items.append((r.get(name_key, "-"), float(str(r.get(value_key, 0)).replace(",", ""))))
        except (TypeError, ValueError):
            items.append((r.get(name_key, "-"), 0.0))
    total = sum(v for _, v in items)
    if not total:
        return {}
    items.sort(key=lambda x: x[1], reverse=True)
    cr = sum(v for _, v in items[:top_n]) / total * 100
    return {"top": items[0][0], "top_share": items[0][1] / total * 100, "cr": cr, "total": total}


def _price_stats(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Min/max/avg/median of price across rows."""
    prices = []
    for r in rows:
        try:
            prices.append(float(str(r.get("价格", 0)).replace(",", "")))
        except (TypeError, ValueError):
            continue
    if not prices:
        return {}
    prices.sort()
    n = len(prices)
    median = prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) / 2
    return {"min": prices[0], "max": prices[-1], "avg": sum(prices) / n, "median": median, "count": n}


def build_insights(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    insights: List[Dict[str, Any]] = []
    metric_map = {m["label"]: str(m["value"]) for m in metrics}
    search_rows = core.get("search_records") or []
    channel_rows = [r for r in (core.get("channel_analysis") or []) if isinstance(r, dict)]
    brand_rows = [r for r in (core.get("brand_analysis") or []) if isinstance(r, dict)]
    price_rows = [r for r in (core.get("price_analysis") or []) if isinstance(r, dict)]
    trend_rows = core.get("sales_trend") or []

    # 1. 商品规模
    if metric_map.get("商品检索结果") or metric_map.get("电商商品数") or metric_map.get("电商商品总数"):
        val = metric_map.get("商品检索结果") or metric_map.get("电商商品数") or metric_map.get("电商商品总数")
        insights.append({
            "feature": "商品规模",
            "evidence": f"商品数据命中 {val} 条。",
            "interpretation": "商品规模反映企业电商业务覆盖广度，是选品与竞品分析的基础。",
        })

    # 2. 品牌集中度（CR3 / top share）
    if brand_rows and core.get("brand_evidence_status") == "verified_subject_relation":
        conc = _concentration(brand_rows, "品牌名称", "商品数", 3)
        if conc:
            insights.append({
                "feature": "品牌矩阵与集中度",
                "evidence": f"识别品牌 {len(brand_rows)} 个，“{conc['top']}”商品数占比约 {conc['top_share']:.0f}%，前 3 品牌合计 {conc['cr']:.0f}%（CR3）。",
                "interpretation": "品牌集中度高说明资源聚焦主力品牌，多品牌且分布均衡则覆盖更细分的人群与价格带。",
            })

    # 3. 价格带分布（min/max/median）— 优先用价格分析表，回退到商品明细样本。
    price_sample = price_rows if price_rows else [
        {"价格": r.get("价格")} for r in search_rows if r.get("价格") and r.get("价格") != "-"
    ]
    if price_sample:
        ps = _price_stats(price_sample)
        if ps:
            spread = ps["max"] - ps["min"]
            band = "窄" if spread and spread / max(ps["max"], 1) < 0.5 else "宽"
            insights.append({
                "feature": "价格带结构",
                "evidence": f"采样 {ps['count']} 个商品，价格区间 {ps['min']:.0f}~{ps['max']:.0f}元，中位价 {ps['median']:.0f}元，均价 {ps['avg']:.0f}元。",
                "interpretation": f"价格带{band}（极差 {spread:.0f}元）；中位价偏高通常意味定位中高端，均价与中位价偏离则反映长尾高低价商品并存。",
            })

    # 4. 渠道布局（domestic_store 无销量字段，改为覆盖广度）
    if channel_rows:
        platforms = [str(r.get("平台")) for r in channel_rows if r.get("平台") and r.get("平台") != "-"]
        uniq_plat = []
        for p in platforms:
            if p not in uniq_plat:
                uniq_plat.append(p)
        insights.append({
            "feature": "渠道布局",
            "evidence": f"覆盖店铺 {len(channel_rows)} 家，分布平台 {len(uniq_plat)} 个" + (f"（{ '、'.join(uniq_plat[:5]) }）" if uniq_plat else "") + "。",
            "interpretation": "渠道覆盖面反映电商触达能力；多平台布局可扩大触达与分散依赖，单一平台占比过高存在渠道集中风险。",
        })

    # 5. 销售趋势（环比/峰值）— 仅当 --stats-month 提供时有数据。
    if trend_rows:
        ta = _trend_analysis(trend_rows, "销售额")
        if ta:
            insights.append({
                "feature": "销售趋势研判",
                "evidence": f"销售额峰值出现在“{ta['peak_period']}”（{ta['peak_value']:.0f}），近月{ta['direction']}，{ta.get('yoy', '')}。",
                "interpretation": "环比上升通常反映需求走强或营销活动见效；下降需结合季节性与促销节点排查，并关注库存与备货节奏。",
            })

    # 6. 来源分布（聚合商品明细来源）
    if search_rows:
        plat: Dict[str, int] = {}
        for r in search_rows:
            p = r.get("来源") or r.get("平台/来源")
            if p and p != "-":
                plat[p] = plat.get(p, 0) + 1
        if plat:
            top_plat = sorted(plat.items(), key=lambda kv: kv[1], reverse=True)[0]
            insights.append({
                "feature": "来源分布",
                "evidence": f"商品样本覆盖来源 {len(plat)} 个，“{top_plat[0]}”商品数 {top_plat[1]}，占比约 {top_plat[1] / len(search_rows) * 100:.0f}%。",
                "interpretation": "来源分布反映企业电商商品的数据采集渠道；多来源覆盖说明数据较全面。",
            })

    if not insights:
        insights.append({
            "feature": "数据完整性",
            "evidence": "部分维度未返回有效数据。",
            "interpretation": "建议核对匹配关键词是否为企业全称，或检查 MCP 连接与上游数据产品覆盖范围。",
        })
    return insights


def build_abstract(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: Sequence[Mapping[str, Any]]) -> str:
    name = subject.get("enterprise") or subject.get("match_raw") or "目标企业"
    parts = [f"本报告以“{name}”为分析对象，基于当前 MCP 可用的企业商品、品牌与渠道数据，呈现分页样本和证据边界。"]
    if metrics:
        kv = "、".join(f"{m['label']} {m['value']}" for m in metrics[:5])
        parts.append(f"关键指标包括：{kv}。")
    parts.append("报告同时给出商品规模、品牌矩阵与渠道布局的结构化解读，便于选品、竞品、品牌与电商运营决策参考。")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Dry-run sample
# --------------------------------------------------------------------------- #

def build_dry_run_payload(raw: str, keyword_type: str) -> Dict[str, Any]:
    try:
        sample = load_json_file(SAMPLE_PATH)
    except Exception:
        sample = {}
    sample = sample if isinstance(sample, dict) else {}
    subject = sample.get("subject") or {"enterprise": raw, "matchKeyword": raw, "keywordType": keyword_type, "match_raw": raw}
    subject = {**subject, "match_raw": raw, "keywordType": keyword_type}
    core = sample.get("core_analysis") or {}
    metrics = sample.get("metrics") or []
    return _assemble(subject, core, metrics, dry_run=True, selectors={})


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def _assemble(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: Sequence[Mapping[str, Any]], *, dry_run: bool, selectors: Mapping[str, Any]) -> Dict[str, Any]:
    abstract = build_abstract(subject, core, metrics)
    records = build_records(core)
    insights = build_insights(subject, core, metrics)
    # Quality gate uses independent evidence dimensions, not only sections that
    # happened to be appended (which would inflate a one-section report to 100%).
    ca = core if isinstance(core, dict) else {}
    requested_unsupported = int(bool(selectors.get("price_source") or selectors.get("stats_month"))) + int(bool(selectors.get("trend_source")))
    total_secs = 3 + requested_unsupported
    populated = sum((
        bool(ca.get("product_profile") or ca.get("search_records")),
        bool(ca.get("brand_analysis")) and ca.get("brand_evidence_status") == "verified_subject_relation",
        bool(ca.get("channel_analysis")),
    ))
    quality_report = {
        "total_sections": total_secs,
        "populated_sections": populated,
        "empty_sections": total_secs - populated,
        "coverage_pct": round(populated / max(1, total_secs) * 100),
    }
    if populated == 0:
        import sys
        print("⚠️ 质量门禁警告: 所有核心分析维度均无数据", file=sys.stderr)
    title = f"{subject.get('enterprise') or '目标企业'} 商品大数据报告"
    return {
        "report_type": REPORT_TYPE,
        "title": title,
        "banner": REPORT_BANNER,
        "subject": dict(subject),
        "abstract": abstract,
        "summary": abstract,
        "executive_summary": [item["interpretation"] for item in insights][:5] or [abstract[:120]],
        "metrics": list(metrics),
        "caliber": build_caliber(subject, selectors),
        "core_analysis": dict(core),
        "representative_records": records,
        "insights": insights,
        "data_source": {
            "mcp_server": "goods-mcp-server",
            "products": _selected_products(selectors),
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "dry_run": dry_run,
            "unsupported_dimensions": [
                item for item, requested in (
                    ("历史价格分析（当前 MCP 未注册对应工具）", selectors.get("price_source") or selectors.get("stats_month")),
                    ("销售趋势分析（当前 MCP 未注册对应工具）", selectors.get("trend_source")),
                ) if requested
            ],
            "source_status": core.get("source_status", {}),
            "evidence_status": {"brand_subject_relation": core.get("brand_evidence_status", "empty")},
            "quality_report": quality_report,
        },
    }


def _selected_products(selectors: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Return the product list actually used given the selectors."""
    products: List[Dict[str, str]] = []
    search_source = selectors.get("search_source", DEFAULT_SEARCH_SOURCE)
    if search_source == "overseas":
        products.append({"name": "海外网店搜索", "product_id": "66c9a954268e9d7292c1a9ab"})
    else:
        products.append({"name": "企业零售商品", "product_id": "66c33eff3c0917a9a02feb9d"})

    profile_source = selectors.get("profile_source", DEFAULT_PROFILE_SOURCE)
    if profile_source == "overseas":
        products.append({"name": "海外网店商品画像", "product_id": "66d5b7e0537c3f61d646c496"})
    else:
        products.append({"name": "企业商品明细", "product_id": "66c33eff3c0917a9a02feb9d"})

    brand_view = selectors.get("brand_view", DEFAULT_BRAND_VIEW)
    if brand_view == "product_overview":
        products.append({"name": "品牌产品概况", "product_id": "66d5b7e1537c3f61d646c573"})
    else:
        products.append({"name": "品牌明细", "product_id": "66c702b725f04ab44cd24d5e"})

    channel_source = selectors.get("channel_source", DEFAULT_CHANNEL_SOURCE)
    if channel_source == "global_store":
        products.append({"name": "国内外网店渠道", "product_id": "672b3125338beb3ec2f5dc43"})
    else:
        products.append({"name": "国内电商店铺渠道", "product_id": "66c702b725f04ab44cd24c83"})

    return products


@paid_call_scope
def build_payload(raw: str, keyword_type: str, opts: Mapping[str, Any]) -> Dict[str, Any]:
    """Build a report using only tools registered by the current goods MCP.

    Historical price/trend selectors are retained for CLI compatibility, but the
    current server exposes no price/trend tool. They are disclosed as unsupported
    instead of issuing an unknown-tool call or fabricating a section.

    Paginated detail interfaces (goods_search / goods_overseas_store_products /
    goods_enterprise_products / goods_channel) are collected within an explicit
    --max-pages budget (default 1); totals, fetched rows and completeness land in
    data_source.pagination, and identical paid requests within this run are
    deduplicated via call_tool_once.
    """
    max_pages = opts.get("max_pages", 1)
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError("max_pages 必须为正整数")
    resolved = resolve_enterprise_name(raw)
    enterprise = resolved["enterprise"]
    selectors: Dict[str, Any] = {
        "search_source": opts.get("source") or DEFAULT_SEARCH_SOURCE,
        "profile_source": opts.get("profile_source") or DEFAULT_PROFILE_SOURCE,
        "brand_view": opts.get("view") or DEFAULT_BRAND_VIEW,
        "channel_source": opts.get("channel_source") or DEFAULT_CHANNEL_SOURCE,
        "price_source": opts.get("price_source"),
        "trend_source": opts.get("trend_source"),
        "stats_month": opts.get("stats_month"),
        "enterprise": enterprise,
    }
    page_size = opts.get("page_size") or 50

    search: Any = {}
    if selectors["search_source"] == "overseas":
        search = collect_detail_pages(_safe_call, T_SEARCH, {
            "matchKeyword": enterprise, "source": "overseas", "pageSize": page_size,
        }, get_rows=_first_list, get_total=_safe_total, is_error=_is_api_error, max_pages=max_pages)

    # Enterprise-scoped products replace the removed goods_profile tool.
    profile: Any = {}
    if selectors["profile_source"] == "overseas":
        # Overseas product lookup requires a store id; the caller's keyword is
        # passed verbatim and the report labels this limitation.
        profile = collect_detail_pages(_safe_call, T_OVERSEAS_PRODUCTS, {
            "storeId": enterprise, "pageSize": page_size,
        }, get_rows=_first_list, get_total=_safe_total, is_error=_is_api_error, max_pages=max_pages)
    else:
        product_type = "retail" if selectors["search_source"] == "retail" else "ecommerce"
        profile = collect_detail_pages(_safe_call, T_ENTERPRISE_PRODUCTS, {
            "matchKeyword": enterprise, "productType": product_type,
            "keywordType": keyword_type, "pageSize": page_size,
        }, get_rows=_first_list, get_total=_safe_total, is_error=_is_api_error, max_pages=max_pages)

    brand = _safe_call(T_BRAND, {
        "matchKeyword": enterprise, "view": selectors["brand_view"],
        "keywordType": keyword_type,
    })
    channel = collect_detail_pages(_safe_call, T_CHANNEL, {
        "matchKeyword": enterprise, "source": selectors["channel_source"],
        "keywordType": keyword_type, "pageSize": page_size,
    }, get_rows=_first_list, get_total=_channel_total, is_error=_is_api_error, max_pages=max_pages)

    subject = build_subject(raw, resolved, keyword_type)
    core = build_core_analysis(search, profile, brand, None, channel, None, selectors)
    search_total = _safe_total(search) if isinstance(search, dict) else None
    channel_total = _channel_total(channel) if isinstance(channel, dict) else None
    metrics = build_metrics(search_total, profile if isinstance(profile, dict) else {}, channel_total)
    _derive_core_metrics(metrics, core)
    pagination_sources: Dict[str, Any] = {}
    if selectors["search_source"] == "overseas":
        pagination_sources["海外商品检索"] = search
    if selectors["profile_source"] == "overseas":
        pagination_sources["海外网店商品"] = profile
    else:
        pagination_sources["企业商品明细"] = profile
    pagination_sources["渠道明细"] = channel
    return attach_pagination(_assemble(subject, core, metrics, dry_run=False, selectors=selectors), pagination_sources)

def _derive_core_metrics(metrics: List[Dict[str, Any]], core: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Derive additional metrics from core analysis sections."""
    brand = core.get("brand_analysis", []) if isinstance(core, dict) else []
    channel = core.get("channel_analysis", []) if isinstance(core, dict) else []
    records = core.get("search_records", []) if isinstance(core, dict) else []
    if isinstance(brand, list) and brand and core.get("brand_evidence_status") == "verified_subject_relation":
        metrics.append({"label": "品牌数量", "value": str(len(brand)), "hint": "涉及品牌总数"})
        try:
            def _cnt(r):
                v = str(r.get("商品数", "0")).replace(",", "")
                return int(v) if v.isdigit() else 0
            top_brand = max(brand, key=_cnt)
            if top_brand.get("品牌名称"):
                metrics.append({"label": "核心品牌", "value": str(top_brand["品牌名称"]), "hint": "商品数最多的品牌"})
        except (ValueError, TypeError):
            pass
    if isinstance(channel, list) and channel:
        platforms = set(str(r.get("平台", "")) for r in channel if r.get("平台"))
        if platforms:
            metrics.append({"label": "覆盖平台", "value": str(len(platforms)), "hint": "不同电商平台数"})
    if isinstance(records, list) and records:
        import re as _re
        prices = []
        for r in records:
            try:
                p = str(r.get("价格", ""))
                m = _re.search(r"(\d+\.?\d*)", p)
                if m:
                    prices.append(float(m.group(1)))
            except (ValueError, TypeError):
                pass
        if prices:
            metrics.append({"label": "价格区间", "value": f"¥{min(prices):.0f}–{max(prices):.0f}", "hint": "商品最低至最高价格"})
            metrics.append({"label": "均价", "value": f"¥{sum(prices)/len(prices):.0f}", "hint": "商品平均价格"})
    return metrics


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="Compose a goods big-data report via the goods MCP.")
    parser.add_argument("--enterprise", required=True, help="企业全称或关键词（goods MCP 按企业名称直查）")
    parser.add_argument("--keyword-type", default="name", help="主体类型：name/nameId/regNumber/socialCreditCode")
    parser.add_argument("--source", default=None, choices=["retail", "overseas"], help="商品搜索数据源：retail=零售商品（默认）/ overseas=海外网店")
    parser.add_argument("--profile-source", default=None, choices=["domestic", "overseas"], help="商品画像数据源：domestic=企业电商商品（默认）/ overseas=海外网店（matchKeyword 为网店 id）")
    parser.add_argument("--view", default=None, choices=["brand_detail", "product_overview"], help="品牌分析视图：brand_detail=品牌明细（默认）/ product_overview=品牌产品概况")
    parser.add_argument("--channel-source", default=None, choices=["domestic_store", "global_store"], help="渠道分析数据源：domestic_store=国内电商店铺（默认）/ global_store=国内外网店")
    parser.add_argument("--price-source", default=None, choices=["store_hot_items", "enterprise_monthly_sales"], help="价格分析数据源（需 --stats-month）：store_hot_items（需 --platform/--shop-id）/ enterprise_monthly_sales")
    parser.add_argument("--trend-source", default=None, choices=["store_monthly", "enterprise_monthly", "enterprise_cumulative"], help="销售趋势数据源（需 --stats-month）")
    parser.add_argument("--stats-month", default=None, help="价格/趋势统计月份，格式 yyyyMM，例如 202505")
    parser.add_argument("--platform", default=None, help="店铺维度数据源的平台标识（store_hot_items / store_monthly 必填）")
    parser.add_argument("--shop-id", default=None, help="店铺维度数据源的店铺 id（store_hot_items / store_monthly 必填）")
    parser.add_argument("--page-size", type=int, default=None, help="分页大小（最多 50）")
    parser.add_argument("--max-pages", type=int, default=1, help="明细接口付费分页预算上限（每接口），默认1；先按 total 估算，只有必要且已授权时提高")
    parser.add_argument("--dry-run", action="store_true", help="不调用真实 MCP，使用样例数据组装报告骨架")
    parser.add_argument("--output", help="输出 JSON 路径；省略则打印到 stdout")
    parser.add_argument("--report-output", help="同时输出 HTML 报告（.html）与 Markdown 报告（.md）")
    parser.add_argument("--pdf-output", help="额外输出 PDF 报告（.pdf）；需要 Playwright + Chromium")
    args = parser.parse_args()

    if args.max_pages < 1:
        raise SystemExit("--max-pages 必须为正整数")

    opts = {
        "source": args.source,
        "profile_source": args.profile_source,
        "view": args.view,
        "channel_source": args.channel_source,
        "price_source": args.price_source,
        "trend_source": args.trend_source,
        "stats_month": args.stats_month,
        "platform": args.platform,
        "shop_id": args.shop_id,
        "page_size": args.page_size,
        "max_pages": args.max_pages,
    }

    if args.dry_run:
        payload = build_dry_run_payload(args.enterprise, args.keyword_type)
    else:
        payload = build_payload(args.enterprise, args.keyword_type, opts)

    if args.output:
        out = pathlib.Path(args.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_dumps(payload, pretty=True), encoding="utf-8")
        print_json({"ok": True, "json": str(out), "dry_run": args.dry_run})
    else:
        print_json(payload)

    if args.report_output:
        base_out = pathlib.Path(args.report_output).expanduser()
        base_out.parent.mkdir(parents=True, exist_ok=True)
        html_path = base_out.with_suffix(".html") if base_out.suffix.lower() not in (".html", ".htm") else base_out
        md_path = html_path.with_suffix(".md")
        html_path.write_text(render_html(payload), encoding="utf-8")
        md_path.write_text(render_markdown(payload), encoding="utf-8")
        if args.pdf_output:
            pdf_path = pathlib.Path(args.pdf_output).expanduser()
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            html_to_pdf(render_html(payload), str(pdf_path))
        print_json({"ok": True, "html": str(html_path), "markdown": str(md_path), "pdf": str(pdf_path) if args.pdf_output else None, "dry_run": args.dry_run})


if __name__ == "__main__":
    main()
