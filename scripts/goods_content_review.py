#!/usr/bin/env python3
"""Offline content review for an existing goods report.

Pure ``apply_content_review(report)`` reconciles channel platform labels with
store URLs, separates search hits from enterprise product totals, translates
upstream source codes, and removes empty price columns. It never calls the MCP.
"""
from __future__ import annotations

import argparse
import copy
import json
import pathlib
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from typing import Any, Dict, List, Mapping, Optional

_PLATFORM_ALIASES = {
    "天猫": "天猫", "tmall": "天猫", "tmall.com": "天猫",
    "淘宝": "淘宝", "taobao": "淘宝", "taobao.com": "淘宝",
    "京东": "京东", "jd": "京东", "jd.com": "京东",
    "苏宁": "苏宁", "suning": "苏宁",
    "1688": "1688",
    "抖音": "抖音", "douyin": "抖音", "jinritemai": "抖音",
    "拼多多": "拼多多", "pinduoduo": "拼多多",
    "唯品会": "唯品会", "vip.com": "唯品会",
    "国美": "国美", "gome": "国美",
    "cn.made-in-china": "中国制造网（Made-in-China）",
    "made-in-china": "中国制造网（Made-in-China）",
    "tradekey": "TradeKey",
    "alibaba": "阿里巴巴国际站", "alibaba.com": "阿里巴巴国际站",
    "amazon": "亚马逊", "amazon.com": "亚马逊",
    "ebay": "eBay", "shopee": "Shopee", "lazada": "Lazada",
}
_HOST_PLATFORM = [
    (("jd.com", "jd.hk"), "京东"),
    (("tmall.com", "tmall.hk"), "天猫"),
    (("taobao.com",), "淘宝"),
    (("suning.com",), "苏宁"),
    (("1688.com",), "1688"),
    (("jinritemai.com", "douyin.com"), "抖音"),
    (("pinduoduo.com", "yangkeduo.com"), "拼多多"),
    (("vip.com",), "唯品会"),
    (("gome.com.cn",), "国美"),
    (("made-in-china.com",), "中国制造网（Made-in-China）"),
    (("tradekey.com",), "TradeKey"),
    (("alibaba.com",), "阿里巴巴国际站"),
    (("amazon.com",), "亚马逊"),
    (("ebay.com",), "eBay"),
    (("shopee.com",), "Shopee"),
    (("lazada.com",), "Lazada"),
]
_SOURCE_LABELS = {
    "commodity": "商品明细",
    "domestic_store": "国内渠道明细",
    "global_store": "海外渠道明细",
    "enterprise_products": "企业商品明细",
    "goods_search": "商品检索",
}
_UNKNOWN_PLATFORMS = {"", "-", "—", "待核实", "未知", "未知平台"}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _platform_label(raw: str) -> str:
    key = _text(raw).casefold()
    if not key:
        return "-"
    for k, v in _PLATFORM_ALIASES.items():
        if key == k.casefold():
            return v
    return _text(raw)


def _platform_from_url(url: str) -> str:
    text = _text(url)
    if not text or text == "-":
        return "待核实"
    parsed = urlsplit(text if "://" in text or text.startswith("//") else "//" + text)
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return "待核实"
    for domains, name in _HOST_PLATFORM:
        for domain in domains:
            base = domain.lower().rstrip(".")
            if host == base or host.endswith("." + base):
                return name
    return "待核实"


def _source_label(raw: Any) -> str:
    text = _text(raw)
    if not text or text == "-":
        return "-"
    return _SOURCE_LABELS.get(text.casefold(), text)


def _known_platform(raw: Any) -> bool:
    return _text(raw) not in _UNKNOWN_PLATFORMS


def _price_text(raw: Any) -> str:
    text = _text(raw)
    if not text or text in {"-", "—"}:
        return "-"
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return text
    try:
        number = Decimal(match.group(1))
    except InvalidOperation:
        return text
    return f"{number.normalize():f} 元"


def _fix_caliber(report: Dict[str, Any], search_hits: Optional[str]) -> None:
    caliber = report.get("caliber")
    if not isinstance(caliber, dict):
        return
    caliber["match_type"] = "商品数据按企业名称匹配；商品明细、品牌与渠道通过当前可用工具查询"
    limit = _text(caliber.get("limit"))
    sentences = [
        "网站渠道为分页样本，不代表企业完整渠道",
        "不同产品返回的商品数、店铺数和平台数属于不同总体，不相互补齐或相除",
    ]
    if search_hits:
        sentences.append(f"关键词检索命中 {search_hits} 条仅为搜索反馈，不代表企业商品总量")
    for sentence in sentences:
        if sentence not in limit and not (sentence == "网站渠道为分页样本，不代表企业完整渠道" and "分页样本" in limit):
            limit = (limit.rstrip("。") + "。" + sentence).lstrip("。")
    caliber["limit"] = limit


def _fix_product_profile(core: Dict[str, Any]) -> None:
    profile = core.get("product_profile")
    if not isinstance(profile, dict):
        return
    if "样本来源" in profile:
        raw = _text(profile["样本来源"])
        profile["样本来源"] = _source_label(raw)
        if profile["样本来源"] != raw:
            profile["来源原始值"] = raw
    if "商品检索结果" in profile:
        profile.pop("商品检索结果", None)


def _fix_channel(core: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = core.get("channel_analysis")
    if not isinstance(rows, list):
        return []
    out: List[Dict[str, Any]] = []
    has_keyword = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        reviewed = dict(row)
        raw_platform = _text(reviewed.get("平台"))
        canonical = _platform_label(raw_platform)
        inferred = _platform_from_url(_text(reviewed.get("店铺链接")))
        reviewed["平台"] = canonical
        reviewed["链接推断平台"] = inferred
        if not _known_platform(canonical):
            source = raw_platform if raw_platform not in ("", "—") else "空"
            if inferred != "待核实":
                reviewed["平台核验"] = f"上游平台未明确（{source}）；链接推断为{inferred}，待核实"
            else:
                reviewed["平台核验"] = f"上游平台未明确（{source}），链接无法确认"
        elif inferred != "待核实" and canonical != "待核实" and canonical != inferred:
            # Common upstream case: a taobao.com shop is labelled 天猫.
            if not (canonical == "天猫" and inferred == "淘宝"):
                reviewed["平台核验"] = "上游平台与链接域名不一致，待核实"
            else:
                reviewed["平台核验"] = "上游标为天猫、链接为淘宝域名，待核实"
        else:
            reviewed["平台核验"] = "一致" if inferred == canonical else "待核实"
        if _text(reviewed.get("在售关键词数")) not in ("", "-", "—"):
            has_keyword = True
        out.append(reviewed)
    core["channel_analysis"] = out
    sections = core.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, dict) and section.get("key") == "channel_analysis":
                section["note"] = _text(section.get("note")).replace("数据源 domestic_store；", "上游渠道明细；").replace("数据源 global_store；", "上游海外渠道明细；")
                section["note"] = section["note"].replace("，不代表企业完整渠道", "；平台已按链接域名交叉核对，待核实表示无法从域名确认；不代表企业完整渠道")
                columns = [("店铺名称", "店铺名称"), ("平台", "平台"), ("链接推断平台", "链接推断平台"),
                           ("平台核验", "平台核验"), ("开店时间", "开店时间"), ("店铺链接", "店铺链接")]
                if has_keyword:
                    columns.append(("在售关键词数", "在售关键词数"))
                section["columns"] = columns
    return out


def _fix_search(core: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = core.get("search_records")
    if not isinstance(rows, list):
        return []
    out: List[Dict[str, Any]] = []
    has_price = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        reviewed = dict(row)
        if "来源" in reviewed:
            raw = _text(reviewed["来源"])
            reviewed["来源"] = _source_label(raw)
            if reviewed["来源"] != raw:
                reviewed["来源原始值"] = raw
        if _text(reviewed.get("价格")) not in ("", "-", "—"):
            reviewed["价格"] = _price_text(reviewed.get("价格"))
            has_price = True
        else:
            reviewed["价格"] = "-"
        out.append(reviewed)
    core["search_records"] = out
    sections = core.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, dict) and section.get("key") == "search_records":
                columns = [("商品名称", "商品名称")]
                if has_price:
                    columns.append(("价格", "价格"))
                columns.append(("来源", "来源"))
                section["columns"] = columns
                if not has_price:
                    note = _text(section.get("note"))
                    extra = "上游未返回价格，价格列已隐藏"
                    if extra not in note:
                        section["note"] = note.rstrip("。") + "；" + extra
                else:
                    note = _text(section.get("note"))
                    extra = "价格为上游原值口径"
                    if extra not in note:
                        section["note"] = note.rstrip("。") + "；" + extra
    return out


def _fix_records(report: Dict[str, Any], search_rows: List[Dict[str, Any]]) -> None:
    records = report.get("representative_records")
    if not isinstance(records, list) or not records:
        return
    has_price = any(_text(r.get("价格")) not in ("", "-", "—") for r in records if isinstance(r, dict))
    for record in records:
        if not isinstance(record, dict):
            continue
        if "来源" in record:
            record["来源"] = _source_label(record.get("来源"))
        if "价格" in record:
            if has_price:
                record["价格"] = _price_text(record.get("价格"))
            else:
                record.pop("价格", None)


def _fix_metrics(report: Dict[str, Any], core: Dict[str, Any]) -> Optional[str]:
    metrics = [m for m in (report.get("metrics") or []) if isinstance(m, dict)]
    out: List[Dict[str, Any]] = []
    search_hits = None
    channel_rows = [r for r in (core.get("channel_analysis") or []) if isinstance(r, dict)]
    platforms = []
    for row in channel_rows:
        name = _text(row.get("平台"))
        if _known_platform(name) and name not in platforms:
            platforms.append(name)
    for metric in metrics:
        label = _text(metric.get("label"))
        if label == "商品检索结果":
            search_hits = _text(metric.get("value"))
            continue
        if label == "店铺/渠道数":
            metric["hint"] = "上游渠道总数；当前样本以渠道明细行为准，样本不等于全量"
        if label == "覆盖平台":
            metric["label"] = "覆盖平台（样本）"
            metric["value"] = str(len(platforms))
            metric["hint"] = "当前渠道样本中上游平台字段可识别的平台数；链接推断仅作待核实线索，不代表企业完整平台覆盖"
        out.append(metric)
    report["metrics"] = out
    return search_hits


def _fix_sections(core: Dict[str, Any]) -> None:
    sections = core.get("sections")
    if not isinstance(sections, list):
        return
    for section in sections:
        if not isinstance(section, dict):
            continue
        if section.get("key") == "brand_analysis":
            if core.get("brand_evidence_status") == "verified_subject_relation":
                section["note"] = "上游返回的企业名称字段与查询主体一致；仅表示品牌记录归属该主体，不代表市场份额、授权关系或渠道覆盖"
            else:
                section["note"] = "上游未返回可核验的企业绑定字段；仅保留来源线索，不作为确定企业品牌"

def _build_insights(report: Dict[str, Any], core: Dict[str, Any], search_rows: List[Dict[str, Any]],
                    channel_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    metrics = {m.get("label"): _text(m.get("value")) for m in (report.get("metrics") or []) if isinstance(m, dict)}
    insights: List[Dict[str, Any]] = []
    product_total = metrics.get("电商商品数") or metrics.get("电商商品总数") or (core.get("product_profile") or {}).get("电商商品总数")
    if product_total:
        insights.append({
            "feature": "企业商品规模",
            "evidence": f"企业商品明细总数 {product_total} 条。",
            "interpretation": "该值是企业商品明细产品的总量，不等同于在售 SKU、可售库存或渠道销量。",
        })
    if channel_rows:
        platforms = []
        for row in channel_rows:
            raw_platform = _text(row.get("平台"))
            if not _known_platform(raw_platform):
                continue
            name = raw_platform
            if "待核实" in _text(row.get("平台核验")):
                name = f"{name}（链接为{_text(row.get('链接推断平台'))}，待核实）"
            if name and name not in platforms:
                platforms.append(name)
        total = metrics.get("店铺/渠道数")
        scope = f"当前样本 {len(channel_rows)} 家"
        if total:
            scope += f"（上游总数 {total} 家）"
        insights.append({
            "feature": "渠道布局（样本）",
            "evidence": scope + f"，样本平台 {len(platforms)} 个：" + ("、".join(platforms) if platforms else "无上游可识别平台") + "。",
            "interpretation": "渠道样本只用于核验线索；上游总数与样本平台数不能推出平台份额或集中度，单一平台也不自动构成风险。",
        })
        missing = [r for r in channel_rows if not _known_platform(r.get("平台"))]
        if missing:
            inferred = []
            for row in missing:
                name = _text(row.get("链接推断平台"))
                if name and name != "待核实" and name not in inferred:
                    inferred.append(name)
            evidence = f"当前样本中 {len(missing)} 条记录的上游平台字段缺失或不可识别"
            if inferred:
                evidence += "；店铺链接域名分别指向：" + "、".join(inferred)
            insights.append({
                "feature": "平台字段缺失",
                "evidence": evidence + "。",
                "interpretation": "链接域名只能作为待核实线索，不能据此认定企业平台覆盖、店铺归属或渠道份额。",
            })
        mismatches = [r for r in channel_rows if "不一致" in _text(r.get("平台核验"))]
        if mismatches:
            insights.append({
                "feature": "平台标签与链接核验",
                "evidence": f"当前样本中 {len(mismatches)} 条记录的上游平台与店铺链接域名不一致：" +
                            "、".join(f"{r.get('店铺名称')}（{r.get('平台')} / {r.get('链接推断平台')}）" for r in mismatches) + "。",
                "interpretation": "平台字段以链接域名可复核部分为准；不一致记录保留原值并标为待核实，不静默改写。",
            })
    sources: Dict[str, int] = {}
    for row in search_rows:
        source = _text(row.get("来源"))
        if source and source != "-":
            sources[source] = sources.get(source, 0) + 1
    if sources:
        insights.append({
            "feature": "商品样本来源",
            "evidence": f"当前商品样本 {len(search_rows)} 条，来源 {len(sources)} 个：" +
                        "、".join(f"{k} {v} 条" for k, v in sorted(sources.items(), key=lambda kv: -kv[1])) + "。",
            "interpretation": "来源只描述本次样本的采集入口；样本数量和来源数不能说明数据完整性或多渠道铺货。",
        })
    return insights or [{
        "feature": "数据完整性",
        "evidence": "部分维度未返回有效数据。",
        "interpretation": "不得将缺失解释为商品为零或无渠道；建议核对关键词与上游产品覆盖范围。",
    }]


def _build_abstract(report: Dict[str, Any]) -> str:
    subject = report.get("subject") if isinstance(report.get("subject"), dict) else {}
    core = report.get("core_analysis") if isinstance(report.get("core_analysis"), dict) else {}
    metrics = [m for m in (report.get("metrics") or []) if isinstance(m, dict)]
    parts = [f"本报告以“{_text(subject.get('enterprise')) or _text(subject.get('match_raw')) or '目标企业'}”为分析对象，基于当前可用企业商品、品牌与渠道数据，呈现商品总量、渠道样本与证据边界。"]
    statuses = core.get("source_status") if isinstance(core.get("source_status"), Mapping) else {}
    failed = [label for key, label in (
        ("search", "商品检索"), ("enterprise_products", "企业商品明细"),
        ("brand", "品牌分析"), ("channel", "渠道明细"),
    ) if statuses.get(key) == "error"]
    if failed:
        parts.append("以下接口受阻，相关字段缺失：" + "、".join(failed) + "；不据此推断商品为零或无渠道。")
    if metrics:
        parts.append("关键指标包括：" + "、".join(f"{m.get('label')} {m.get('value')}" for m in metrics[:5]) + "。")
    parts.append("报告仅对返回字段作结构化展示，不构成选品、竞品、渠道份额或经营结论；样本不等于全量。")
    return "".join(parts)


def _dedupe(items: List[Any]) -> List[Any]:
    out: List[Any] = []
    seen = set()
    for item in items:
        key = _text(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _has_review_body(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict, tuple)) and len(value) == 0:
        return False
    return True


def _refresh_quality_report(report: Dict[str, Any]) -> None:
    """Recompute section-fill stats from the final sections and bodies.

    0 counts as populated; only None and empty containers/strings are empty.
    coverage_pct is section fill rate, never an accuracy claim.
    """
    core = report.get("core_analysis") if isinstance(report.get("core_analysis"), dict) else {}
    sections = core.get("sections") if isinstance(core.get("sections"), list) else []
    total = len([s for s in sections if isinstance(s, dict)])
    populated = 0
    for section in sections:
        if not isinstance(section, dict):
            continue
        key = section.get("key")
        if key and _has_review_body(core.get(key)):
            populated += 1
    data_source = report.get("data_source")
    if not isinstance(data_source, dict):
        data_source = {}
        report["data_source"] = data_source
    quality = data_source.get("quality_report")
    if not isinstance(quality, dict):
        quality = {}
        data_source["quality_report"] = quality
    quality.update({
        "total_sections": total,
        "populated_sections": populated,
        "empty_sections": total - populated,
        "coverage_pct": round(populated / total * 100) if total else 0,
    })


def apply_content_review(report: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a reviewed deep copy of a frozen goods report."""
    reviewed = copy.deepcopy(dict(report))
    core = reviewed.get("core_analysis") if isinstance(reviewed.get("core_analysis"), dict) else {}
    _fix_product_profile(core)
    channel_rows = _fix_channel(core)
    search_rows = _fix_search(core)
    _fix_sections(core)
    search_hits = _fix_metrics(reviewed, core)
    _fix_caliber(reviewed, search_hits)
    _fix_records(reviewed, search_rows)
    insights = _build_insights(reviewed, core, search_rows, channel_rows)
    reviewed["insights"] = insights
    reviewed["executive_summary"] = _dedupe([i.get("interpretation") for i in insights])[:5]
    reviewed["abstract"] = _build_abstract(reviewed)
    reviewed["summary"] = reviewed["abstract"]
    _refresh_quality_report(reviewed)
    return reviewed


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply offline content review to a goods report.json")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    input_path = pathlib.Path(args.input).expanduser().resolve()
    output_path = pathlib.Path(args.out_dir).expanduser()
    target = (output_path / "report.json").resolve()
    same = target == input_path
    if not same and target.exists():
        try:
            same = target.samefile(input_path)
        except OSError:
            same = False
    if same:
        raise SystemExit("拒绝写入：--out-dir 的 report.json 指向 --input，冻结源报告不可覆盖")
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from render_report import render_html, render_markdown

    source = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
    reviewed = apply_content_review(source)
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(reviewed, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.md").write_text(render_markdown(reviewed), encoding="utf-8")
    (out / "report.html").write_text(render_html(reviewed), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
