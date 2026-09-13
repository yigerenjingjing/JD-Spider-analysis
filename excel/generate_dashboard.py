# -*- coding: utf-8 -*-
"""读取爬虫 Excel 并生成数据可视化 HTML 看板。

使用 jieba + TF-IDF 提取关键词，包含统计分析（Pearson 相关、t 检验）和词云。
"""

import json
import os
import re
import sys

import jieba
import jieba.analyse
import numpy as np
import pandas as pd
from scipy import stats as sp_stats


# ═══════════════════════════════════════════════════════════
# 1. 读取数据
# ═══════════════════════════════════════════════════════════

def load_data(excel_path):
    xls = pd.ExcelFile(excel_path)
    overview = pd.read_excel(xls, sheet_name="商品总览")
    comments_data = []
    for sheet in xls.sheet_names[1:]:
        df = pd.read_excel(xls, sheet_name=sheet)
        comments_data.append({
            "product": sheet,
            "comments": df.iloc[:, 0].dropna().tolist(),
        })
    return overview, comments_data


# ═══════════════════════════════════════════════════════════
# 2. 情感分析（基于词典）
# ═══════════════════════════════════════════════════════════

POSITIVE_WORDS = {
    "好", "棒", "满意", "喜欢", "推荐", "不错", "赞", "超赞", "完美", "优秀",
    "给力", "好评", "耐用", "结实", "厚实", "稳固", "方便", "舒服", "舒适",
    "安全", "开心", "迅速", "很快", "靠谱", "信赖", "回购", "划算", "超值",
    "惊喜", "漂亮", "可爱", "精细", "放心", "贴心", "爱不释手", "一流",
    "高品质", "省心", "物美价廉", "性价比高", "值得", "必备", "神器",
    "不占地", "良心", "到位", "周到", "及时", "好看", "整洁", "干净",
    "温和", "柔软", "有弹性", "尽情", "挺好", "非常好", "很棒", "便宜",
    "物超所值", "棒棒哒", "不贵", "给力",
}

NEGATIVE_WORDS = {
    "差", "不好", "失望", "垃圾", "坑", "差劲", "烂", "糟糕", "坏",
    "异味", "气味", "味道大", "臭", "难闻", "刺鼻",
    "掉屑", "飞渣", "掉渣", "坏了", "破损", "损坏", "烂了",
    "不值", "贵", "稍贵", "不太", "不推荐", "后悔", "退", "换货",
    "问题", "缺陷", "缺点", "瑕疵", "不足", "有点大", "太小",
    "不喜欢", "不爱", "没兴趣", "不玩", "不怎么", "不怎么样",
    "差评", "不好用", "不耐用", "容易坏", "很快坏", "质量差",
    "失望", "闹心", "糟心", "差很多",
}

STOPWORDS = {
    "的", "了", "是", "我", "很", "也", "都", "不", "就", "和", "还", "一个",
    "这个", "已经", "可以", "没有", "比较", "觉得", "知道", "因为", "所以",
    "但是", "如果", "虽然", "而且", "或者", "不过", "然后", "之后", "还是",
    "非常", "真的", "挺", "有点", "蛮", "太", "比较", "特别", "会", "要",
    "在", "有", "买", "用", "给", "让", "把", "被", "对", "从", "到",
    "出", "过", "着", "之", "中", "上", "下", "大", "小", "多", "少",
    "好", "等", "该", "这", "那", "其", "它", "他", "她", "们",
    "款式", "型号", "颜色", "规格", "京东", "物流", "快递", "配送",
    "包装", "客服", "售后", "购物", "宝贝", "卖家", "店铺", "东西",
    "收到", "打开", "拿到", "送来", "到货", "下单", "购买", "发货",
}


def analyze_sentiment(text):
    pos = sum(text.count(w) for w in POSITIVE_WORDS)
    neg = sum(text.count(w) for w in NEGATIVE_WORDS)
    return pos, neg


def classify_sentiment(pos, neg):
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def sentiment_analysis(comments_data):
    results = []
    for item in comments_data:
        sentiments = {"positive": 0, "neutral": 0, "negative": 0}
        detail = []
        for c in item["comments"]:
            pos, neg = analyze_sentiment(c)
            label = classify_sentiment(pos, neg)
            sentiments[label] += 1
            detail.append({"text": c[:60], "pos": pos, "neg": neg, "label": label})
        results.append({
            "product": item["product"],
            "sentiments": sentiments,
            "detail": detail,
            "total": len(item["comments"]),
        })
    return results


# ═══════════════════════════════════════════════════════════
# 3. jieba + TF-IDF 关键词提取
# ═══════════════════════════════════════════════════════════

def keyword_analysis(comments_data):
    results = []
    for item in comments_data:
        all_text = " ".join(item["comments"])
        tfidf_kw = jieba.analyse.extract_tags(
            all_text, topK=15, withWeight=True,
        )
        filtered = [(w, round(s, 1)) for w, s in tfidf_kw if w not in STOPWORDS and len(w) >= 2]
        results.append({
            "product": item["product"],
            "keywords": dict(filtered[:12]),
        })
    return results


def global_keywords_tfidf(comments_data):
    all_text = " ".join(c for item in comments_data for c in item["comments"])
    tfidf_kw = jieba.analyse.extract_tags(
        all_text, topK=30, withWeight=True,
    )
    filtered = [(w, round(s, 1)) for w, s in tfidf_kw if w not in STOPWORDS and len(w) >= 2]
    return dict(filtered[:20])


# ═══════════════════════════════════════════════════════════
# 4. 词云数据生成
# ═══════════════════════════════════════════════════════════

def wordcloud_data(comments_data):
    all_text = " ".join(c for item in comments_data for c in item["comments"])
    tfidf_kw = jieba.analyse.extract_tags(
        all_text, topK=100, withWeight=True,
    )
    max_weight = tfidf_kw[0][1] if tfidf_kw else 1
    return [
        {"name": w, "value": int(s / max_weight * 80 + 10)}
        for w, s in tfidf_kw if w not in STOPWORDS and len(w) >= 2
    ][:80]


# ═══════════════════════════════════════════════════════════
# 5. 统计分析
# ═══════════════════════════════════════════════════════════

def pearson_price_sales(products, comments_data):
    """价格与销量的 Pearson 相关系数。返回 (r, p_value, 价格列表, 销量列表)。"""
    prices = []
    sales = []
    for p in products:
        try:
            price = float(str(p.get("price", p.get("价格", "0"))).replace("¥", ""))
            sales_num = int(p.get("sales_num", 0))
            if price > 0 and sales_num > 0:
                prices.append(price)
                sales.append(sales_num)
        except (ValueError, TypeError):
            pass
    if len(prices) < 3:
        return None, None, prices, sales
    r, p_val = sp_stats.pearsonr(prices, sales)
    return round(r, 4), round(p_val, 4), prices, sales


def ttest_review_length(comments_data, sentiments):
    """正面 vs 负面评论长度的独立样本 t 检验。"""
    pos_lengths = []
    neg_lengths = []
    for item, sent in zip(comments_data, sentiments):
        for c, d in zip(item["comments"], sent["detail"]):
            if d["label"] == "positive":
                pos_lengths.append(len(c))
            elif d["label"] == "negative":
                neg_lengths.append(len(c))
    if len(pos_lengths) < 2 or len(neg_lengths) < 2:
        return None, None, pos_lengths, neg_lengths
    t_stat, p_val = sp_stats.ttest_ind(pos_lengths, neg_lengths, equal_var=False)
    return round(t_stat, 4), round(p_val, 4), pos_lengths, neg_lengths


# ═══════════════════════════════════════════════════════════
# 6. 评论长度统计
# ═══════════════════════════════════════════════════════════

def comment_length_stats(comments_data):
    results = []
    for item in comments_data:
        lengths = [len(c) for c in item["comments"]]
        results.append({
            "product": item["product"],
            "avg": round(sum(lengths) / max(len(lengths), 1), 1),
            "max": max(lengths) if lengths else 0,
            "min": min(lengths) if lengths else 0,
            "lengths": lengths,
        })
    return results


# ═══════════════════════════════════════════════════════════
# 7. 解析销量与好评率
# ═══════════════════════════════════════════════════════════

def parse_sales_and_rate(overview):
    products = []
    for _, row in overview.iterrows():
        sales_text = str(row.get("销量", ""))
        sales_num = 0
        rate = 0
        m = re.search(r"已售(\d+)万", sales_text)
        if m:
            sales_num = int(m.group(1)) * 10000
        else:
            m = re.search(r"已售(\d+)\+", sales_text)
            if m:
                sales_num = int(m.group(1))
            else:
                m = re.search(r"(\d+)万\+", sales_text)
                if m:
                    sales_num = int(m.group(1)) * 10000

        m2 = re.search(r"(\d+)%好评", sales_text)
        if m2:
            rate = int(m2.group(1))

        products.append({
            "name": str(row.get("商品名称", "")),
            "price": str(row.get("价格", "")),
            "promotion": str(row.get("活动", "")),
            "store": str(row.get("店铺名称", "")),
            "sales_text": sales_text,
            "sales_num": sales_num,
            "good_rate": rate,
        })
    return products


# ═══════════════════════════════════════════════════════════
# 8. 生成 HTML
# ═══════════════════════════════════════════════════════════

def generate_html(overview, comments_data, output_path):
    products = parse_sales_and_rate(overview)
    sentiments = sentiment_analysis(comments_data)
    keywords = keyword_analysis(comments_data)
    global_kw = global_keywords_tfidf(comments_data)
    length_stats = comment_length_stats(comments_data)
    wordcloud = wordcloud_data(comments_data)

    # 统计分析
    pearson_r, pearson_p, prices_list, sales_list = pearson_price_sales(products, comments_data)
    t_stat, t_pval, pos_lens, neg_lens = ttest_review_length(comments_data, sentiments)

    total_comments = sum(len(c["comments"]) for c in comments_data)
    avg_len = round(sum(s["avg"] for s in length_stats) / max(len(length_stats), 1))

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>京东宠物玩具数据分析看板</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; background: #f0f2f5; color: #333; }}
.header {{ background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: #fff; padding: 28px 40px; text-align: center; }}
.header h1 {{ font-size: 28px; letter-spacing: 2px; }}
.header p {{ font-size: 14px; opacity: 0.85; margin-top: 6px; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
.stats-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }}
.stat-card {{ background: #fff; border-radius: 10px; padding: 20px 24px; box-shadow: 0 2px 10px rgba(0,0,0,.06); display: flex; align-items: center; gap: 16px; }}
.stat-icon {{ width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; }}
.stat-icon.blue {{ background: #e8f4fd; color: #1890ff; }}
.stat-icon.green {{ background: #e6f7e6; color: #52c41a; }}
.stat-icon.orange {{ background: #fff3e0; color: #fa8c16; }}
.stat-icon.purple {{ background: #f3e8ff; color: #722ed1; }}
.stat-value {{ font-size: 28px; font-weight: 700; }}
.stat-label {{ font-size: 13px; color: #888; margin-top: 2px; }}
.charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
.charts-grid.triple {{ grid-template-columns: 1fr 1fr 1fr; }}
.chart-card {{ background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,.06); }}
.chart-card.full {{ grid-column: 1 / -1; }}
.chart-card h3 {{ font-size: 16px; margin-bottom: 12px; color: #444; padding-bottom: 10px; border-bottom: 1px solid #f0f0f0; }}
.chart {{ width: 100%; height: 380px; }}
.chart.tall {{ height: 500px; }}
.table-card {{ background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,.06); margin-bottom: 20px; }}
.table-card h3 {{ font-size: 16px; margin-bottom: 12px; color: #444; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th {{ background: #fafafa; padding: 12px 14px; text-align: left; border-bottom: 2px solid #e8e8e8; font-weight: 600; }}
td {{ padding: 10px 14px; border-bottom: 1px solid #f0f0f0; }}
tr:hover td {{ background: #fafafa; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-right: 4px; }}
.tag.pos {{ background: #f6ffed; color: #52c41a; }}
.tag.neg {{ background: #fff2f0; color: #e74c3c; }}
.tag.neu {{ background: #fffbe6; color: #d48806; }}
.footer {{ text-align: center; padding: 20px; color: #999; font-size: 13px; }}
.stats-note {{ background: #fff; border-radius: 10px; padding: 16px 20px; box-shadow: 0 2px 10px rgba(0,0,0,.06); margin-bottom: 20px; font-size: 14px; line-height: 2; }}
.stats-note strong {{ color: #722ed1; }}
</style>
</head>
<body>

<div class="header">
  <h1>🐾 京东宠物玩具数据分析看板</h1>
  <p>基于用户评论的多维度数据可视化分析 · jieba + TF-IDF 关键词提取 · 数据来源：JD.com</p>
</div>

<div class="container">

  <!-- 统计卡片 -->
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-icon blue">📦</div>
      <div><div class="stat-value">{len(products)}</div><div class="stat-label">爬取商品数</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon green">💬</div>
      <div><div class="stat-value">{total_comments}</div><div class="stat-label">总评论数</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon orange">⭐</div>
      <div><div class="stat-value">{round(sum(p['good_rate'] for p in products)/max(len(products),1), 1)}%</div><div class="stat-label">平均好评率</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon purple">📝</div>
      <div><div class="stat-value">{avg_len}</div><div class="stat-label">平均评论长度（字）</div></div>
    </div>
  </div>

  <!-- 统计分析卡片 -->
  <div class="stats-note">
    🔬 <strong>统计分析：</strong>
    价格与销量 Pearson 相关系数 <strong>r = {pearson_r}</strong>（p = {pearson_p}）{"，呈显著负相关，低价商品销量更高" if pearson_r is not None and pearson_r < -0.3 and pearson_p is not None and pearson_p < 0.05 else ""}{"，呈显著正相关，高价商品反而销量更好" if pearson_r is not None and pearson_r > 0.3 and pearson_p is not None and pearson_p < 0.05 else ""}{"，价格与销量无显著线性相关" if pearson_r is not None and abs(pearson_r) <= 0.3 or (pearson_p is not None and pearson_p >= 0.05) else ""}{"，样本不足无法计算" if pearson_r is None else ""}
    &nbsp;|&nbsp;
    正面 vs 负面评论长度 t 检验 <strong>t = {t_stat}</strong>（p = {t_pval}）{"，正面评论显著更长" if t_stat is not None and t_stat > 0 and t_pval is not None and t_pval < 0.05 else ""}{"，负面评论显著更长" if t_stat is not None and t_stat < 0 and t_pval is not None and t_pval < 0.05 else ""}{"，两类评论长度无显著差异" if t_stat is not None and t_pval is not None and t_pval >= 0.05 else ""}{"，样本不足无法计算" if t_stat is None else ""}
    &nbsp;|&nbsp;
    正面评论均长 <strong>{round(np.mean(pos_lens), 1) if pos_lens else 'N/A'}</strong> 字，负面评论均长 <strong>{round(np.mean(neg_lens), 1) if neg_lens else 'N/A'}</strong> 字
  </div>

  <!-- 第一行：价格 + 销量好评率 -->
  <div class="charts-grid">
    <div class="chart-card"><h3>💰 商品价格对比</h3><div class="chart" id="chart-price"></div></div>
    <div class="chart-card"><h3>📊 销量与好评率对比</h3><div class="chart" id="chart-sales-rate"></div></div>
  </div>

  <!-- 第二行：情感分析 -->
  <div class="charts-grid">
    <div class="chart-card"><h3>😊 评论情感分布（按商品）</h3><div class="chart tall" id="chart-sentiment-bar"></div></div>
    <div class="chart-card"><h3>🎯 整体情感占比</h3><div class="chart tall" id="chart-sentiment-pie"></div></div>
  </div>

  <!-- 第三行：词云 + TF-IDF 关键词 -->
  <div class="charts-grid">
    <div class="chart-card"><h3>☁️ 评论词云（TF-IDF 加权）</h3><div class="chart tall" id="chart-wordcloud"></div></div>
    <div class="chart-card"><h3>🔑 TF-IDF 关键词（全局 Top 20）</h3><div class="chart tall" id="chart-keywords"></div></div>
  </div>

  <!-- 第四行：评论长度 + 价格-销量散点 -->
  <div class="charts-grid">
    <div class="chart-card"><h3>📏 评论长度分布（箱线图）</h3><div class="chart" id="chart-length"></div></div>
    <div class="chart-card"><h3>📈 价格-销量散点图（含回归趋势）</h3><div class="chart" id="chart-scatter"></div></div>
  </div>

  <!-- 各商品关键词 -->
  <div class="charts-grid">
    {''.join(f'''<div class="chart-card"><h3>🏷️ 「{kw['product'][:18]}」TF-IDF 关键词</h3><div class="chart" id="chart-kw-{i}"></div></div>''' for i, kw in enumerate(keywords))}
  </div>

  <!-- 数据表格 -->
  <div class="table-card">
    <h3>📋 商品数据明细</h3>
    <div style="overflow-x:auto;">
      <table>
        <thead><tr><th>序号</th><th>商品名称</th><th>价格</th><th>店铺</th><th>销量</th><th>好评率</th><th>评论数</th><th>正面</th><th>中性</th><th>负面</th><th>均长(字)</th></tr></thead>
        <tbody>
          {''.join(f'''<tr>
            <td>{i+1}</td><td>{p['name'][:30]}</td><td>{p['price']}</td><td>{p['store'][:18]}</td>
            <td>{p['sales_text']}</td><td>{p['good_rate']}%</td>
            <td>{s['total']}</td>
            <td><span class="tag pos">{s['sentiments']['positive']}</span></td>
            <td><span class="tag neu">{s['sentiments']['neutral']}</span></td>
            <td><span class="tag neg">{s['sentiments']['negative']}</span></td>
            <td>{l['avg']}</td>
          </tr>''' for i, (p, s, l) in enumerate(zip(products, sentiments, length_stats)))}
        </tbody>
      </table>
    </div>
  </div>

</div>

<div class="footer">京东宠物玩具数据可视化看板 · jieba + TF-IDF · ECharts · 自动生成于 {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</div>

<script>
const PRODUCTS = {json.dumps(products, ensure_ascii=False)};
const SENTIMENTS = {json.dumps(sentiments, ensure_ascii=False)};
const KEYWORDS = {json.dumps(keywords, ensure_ascii=False)};
const LENGTH_STATS = {json.dumps(length_stats, ensure_ascii=False)};
const GLOBAL_KW = {json.dumps(global_kw, ensure_ascii=False)};
const WORDCLOUD_DATA = {json.dumps(wordcloud, ensure_ascii=False)};
const SCATTER_DATA = {json.dumps([{"price": p, "sales": s} for p, s in zip(prices_list, sales_list)], ensure_ascii=False)};
const PEARSON_R = {json.dumps(pearson_r)};
const T_STAT = {json.dumps(t_stat)};

const prodNames = PRODUCTS.map((p, i) => '#' + (i+1) + ' ' + p.name.slice(0,10));
const priceData = PRODUCTS.map(p => parseFloat(p.price.replace('¥','')) || 0);

// ── 价格柱状图 ──
(function() {{
  const c = echarts.init(document.getElementById('chart-price'));
  c.setOption({{
    tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }} }},
    grid: {{ left: '3%', right: '10%', bottom: '10%', top: '10%', containLabel: true }},
    xAxis: {{ type: 'category', data: prodNames, axisLabel: {{ rotate: 20, fontSize: 11 }} }},
    yAxis: {{ type: 'value', name: '价格 (¥)' }},
    series: [{{
      type: 'bar', data: priceData,
      itemStyle: {{ color: new echarts.graphic.LinearGradient(0,0,0,1,[
        {{offset:0, color:'#e74c3c'}}, {{offset:1, color:'#f1948a'}}
      ]) }},
      label: {{ show: true, position: 'top', formatter: '¥{{c}}', fontSize: 12 }},
      barMaxWidth: 50,
    }}]
  }});
  window.addEventListener('resize', () => c.resize());
}})();

// ── 销量 + 好评率双轴 ──
(function() {{
  const c = echarts.init(document.getElementById('chart-sales-rate'));
  c.setOption({{
    tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'cross' }} }},
    legend: {{ data: ['销量', '好评率'], bottom: 0 }},
    grid: {{ left: '3%', right: '10%', bottom: '15%', top: '10%', containLabel: true }},
    xAxis: {{ type: 'category', data: prodNames, axisLabel: {{ rotate: 20, fontSize: 11 }} }},
    yAxis: [
      {{ type: 'value', name: '销量', axisLabel: {{ formatter: '{{value}}' }} }},
      {{ type: 'value', name: '好评率 (%)', min: 90, axisLabel: {{ formatter: '{{value}}%' }} }}
    ],
    series: [
      {{ name: '销量', type: 'bar', data: PRODUCTS.map(p => p.sales_num),
         itemStyle: {{ color: '#1890ff' }}, barMaxWidth: 40,
         label: {{ show: true, position: 'top', formatter: p => {{ const v = p.value; return v >= 10000 ? (v/10000).toFixed(0) + '万' : v; }}, fontSize: 11 }} }},
      {{ name: '好评率', type: 'line', yAxisIndex: 1, data: PRODUCTS.map(p => p.good_rate),
         lineStyle: {{ color: '#52c41a', width: 3 }}, itemStyle: {{ color: '#52c41a' }},
         symbol: 'circle', symbolSize: 10,
         label: {{ show: true, formatter: '{{c}}%', fontSize: 12, color: '#52c41a' }} }}
    ]
  }});
  window.addEventListener('resize', () => c.resize());
}})();

// ── 情感分布柱状图 ──
(function() {{
  const c = echarts.init(document.getElementById('chart-sentiment-bar'));
  c.setOption({{
    tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }} }},
    legend: {{ data: ['正面', '中性', '负面'], bottom: 0 }},
    grid: {{ left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true }},
    xAxis: {{ type: 'category', data: prodNames, axisLabel: {{ rotate: 20, fontSize: 11 }} }},
    yAxis: {{ type: 'value', name: '评论数' }},
    series: [
      {{ name: '正面', type: 'bar', stack: 'total', data: SENTIMENTS.map(s => s.sentiments.positive), itemStyle: {{ color: '#52c41a' }}, barMaxWidth: 50 }},
      {{ name: '中性', type: 'bar', stack: 'total', data: SENTIMENTS.map(s => s.sentiments.neutral), itemStyle: {{ color: '#faad14' }}, barMaxWidth: 50 }},
      {{ name: '负面', type: 'bar', stack: 'total', data: SENTIMENTS.map(s => s.sentiments.negative), itemStyle: {{ color: '#e74c3c' }}, barMaxWidth: 50 }},
    ]
  }});
  window.addEventListener('resize', () => c.resize());
}})();

// ── 整体情感饼图 ──
(function() {{
  const tP = SENTIMENTS.reduce((a,s) => a + s.sentiments.positive, 0);
  const tN = SENTIMENTS.reduce((a,s) => a + s.sentiments.neutral, 0);
  const tNg = SENTIMENTS.reduce((a,s) => a + s.sentiments.negative, 0);
  const c = echarts.init(document.getElementById('chart-sentiment-pie'));
  c.setOption({{
    tooltip: {{ trigger: 'item', formatter: '{{b}}: {{c}} 条 ({{d}}%)' }},
    legend: {{ orient: 'vertical', left: 'left', top: 'center' }},
    series: [{{
      type: 'pie', radius: ['45%', '72%'], center: ['55%', '50%'],
      emphasis: {{ label: {{ fontSize: 18, fontWeight: 'bold' }} }},
      label: {{ formatter: '{{b}}\\n{{c}} 条 ({{d}}%)' }},
      data: [
        {{ value: tP, name: '正面评价', itemStyle: {{ color: '#52c41a' }} }},
        {{ value: tN, name: '中性评价', itemStyle: {{ color: '#faad14' }} }},
        {{ value: tNg, name: '负面评价', itemStyle: {{ color: '#e74c3c' }} }},
      ]
    }}]
  }});
  window.addEventListener('resize', () => c.resize());
}})();

// ── 词云 ──
(function() {{
  const c = echarts.init(document.getElementById('chart-wordcloud'));
  c.setOption({{
    tooltip: {{ formatter: '{{b}}: TF-IDF={{c}}' }},
    series: [{{
      type: 'wordCloud',
      shape: 'circle',
      left: 'center', top: 'center', width: '90%', height: '90%',
      sizeRange: [14, 60],
      rotationRange: [-45, 45],
      rotationStep: 45,
      gridSize: 8,
      drawOutOfBound: false,
      layoutAnimation: true,
      textStyle: {{
        fontFamily: '"Microsoft YaHei", sans-serif',
        fontWeight: 'normal',
        color: function() {{
          const colors = ['#e74c3c','#1890ff','#52c41a','#fa8c16','#722ed1','#eb2f96','#13c2c2','#f5222d','#2f54eb','#faad14'];
          return colors[Math.floor(Math.random() * colors.length)];
        }}
      }},
      emphasis: {{ textStyle: {{ fontSize: 28, fontWeight: 'bold' }} }},
      data: WORDCLOUD_DATA
    }}]
  }});
  window.addEventListener('resize', () => c.resize());
}})();

// ── TF-IDF 全局关键词 ──
(function() {{
  const c = echarts.init(document.getElementById('chart-keywords'));
  const entries = Object.entries(GLOBAL_KW);
  c.setOption({{
    tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }} }},
    grid: {{ left: '2%', right: '15%', bottom: '3%', top: '3%', containLabel: true }},
    xAxis: {{ type: 'value', name: 'TF-IDF 权重' }},
    yAxis: {{ type: 'category', data: entries.map(e=>e[0]).reverse(), axisLabel: {{ fontSize: 12 }}, inverse: true }},
    series: [{{
      type: 'bar', data: entries.map(e=>e[1]).reverse(),
      itemStyle: {{ color: new echarts.graphic.LinearGradient(0,0,1,0,[
        {{offset:0, color:'#722ed1'}}, {{offset:1, color:'#b37feb'}}
      ]) }},
      label: {{ show: true, position: 'right', fontSize: 11 }},
      barMaxWidth: 24,
    }}]
  }});
  window.addEventListener('resize', () => c.resize());
}})();

// ── 评论长度箱线图 ──
(function() {{
  const c = echarts.init(document.getElementById('chart-length'));
  const bd = LENGTH_STATS.map((s, i) => {{
    const so = [...s.lengths].sort((a,b)=>a-b);
    return [s.min, so[Math.floor(so.length*0.25)], so[Math.floor(so.length*0.5)], so[Math.floor(so.length*0.75)], s.max];
  }});
  c.setOption({{
    tooltip: {{ trigger: 'axis' }},
    grid: {{ left: '8%', right: '5%', bottom: '10%', top: '10%' }},
    xAxis: {{ type: 'category', data: prodNames, axisLabel: {{ rotate: 20, fontSize: 11 }} }},
    yAxis: {{ type: 'value', name: '字数' }},
    series: [
      {{ type: 'boxplot', data: bd, itemStyle: {{ color: '#722ed1', borderColor: '#531dab' }} }},
      {{ type: 'scatter', data: LENGTH_STATS.map((s,i) => [i, s.avg]),
         symbolSize: 12, itemStyle: {{ color: '#e74c3c' }},
         label: {{ show: true, formatter: p => '均' + p.value, position: 'top', fontSize: 11 }} }}
    ]
  }});
  window.addEventListener('resize', () => c.resize());
}})();

// ── 价格-销量散点图 ──
(function() {{
  const c = echarts.init(document.getElementById('chart-scatter'));
  c.setOption({{
    title: {{ text: PEARSON_R !== null ? 'r = ' + PEARSON_R : '', left: 'center', top: 5, textStyle: {{ fontSize: 14, color: '#722ed1' }} }},
    tooltip: {{ trigger: 'item', formatter: '价格: ¥{{c[0]}}<br/>销量: {{c[1]}}' }},
    grid: {{ left: '12%', right: '5%', bottom: '10%', top: '15%' }},
    xAxis: {{ type: 'value', name: '价格 (¥)', nameLocation: 'center', nameGap: 30 }},
    yAxis: {{ type: 'value', name: '销量', nameLocation: 'center', nameGap: 40,
      axisLabel: {{ formatter: v => v >= 10000 ? (v/10000).toFixed(0) + '万' : v }} }},
    series: [{{
      type: 'scatter', data: SCATTER_DATA.map(d => [d.price, d.sales]),
      symbolSize: 16, itemStyle: {{ color: '#1890ff' }},
    }}]
  }});
  window.addEventListener('resize', () => c.resize());
}})();

// ── 各商品 TF-IDF 关键词 ──
KEYWORDS.forEach((item, i) => {{
  const c = echarts.init(document.getElementById('chart-kw-' + i));
  const entries = Object.entries(item.keywords);
  c.setOption({{
    tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }} }},
    grid: {{ left: '2%', right: '15%', bottom: '3%', top: '3%', containLabel: true }},
    xAxis: {{ type: 'value', name: 'TF-IDF' }},
    yAxis: {{ type: 'category', data: entries.map(e=>e[0]).reverse(), axisLabel: {{ fontSize: 11 }}, inverse: true }},
    series: [{{
      type: 'bar', data: entries.map(e=>e[1]).reverse(),
      itemStyle: {{ color: new echarts.graphic.LinearGradient(0,0,1,0,[
        {{offset:0, color:'#1890ff'}}, {{offset:1, color:'#69c0ff'}}
      ]) }},
      label: {{ show: true, position: 'right', fontSize: 10 }},
      barMaxWidth: 20,
    }}]
  }});
  window.addEventListener('resize', () => c.resize());
}});
</script>

</body>
</html>"""

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[成功] 数据看板已生成: {output_path}", flush=True)


# ═══════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    excel_path = sys.argv[1] if len(sys.argv) > 1 else r"D:\jd_result.xlsx"
    output_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    overview, comments_data = load_data(excel_path)
    generate_html(overview, comments_data, output_path)


if __name__ == "__main__":
    main()
