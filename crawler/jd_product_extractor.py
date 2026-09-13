# -*- coding: utf-8 -*-
"""商品列表提取。"""

from jd_config import (
    CARD_SELECTORS,
    MAX_PRODUCTS,
    NAME_SELECTORS,
    PRICE_SELECTORS,
    PROMOTION_SELECTORS,
    SALES_SELECTORS,
    STORE_SELECTORS,
    TIMEOUT,
)
from crawler.jd_utils import extract_text, normalize_column, normalize_url


def get_elements(page, selectors, limit=MAX_PRODUCTS, wait_selector=None):
    """按顺序尝试多个选择器，返回第一组非空元素。"""
    if isinstance(selectors, str):
        selectors = [selectors]

    if wait_selector:
        try:
            page.wait.ele_displayed(wait_selector, timeout=TIMEOUT)
        except Exception:
            print(f"[调试] 等待选择器 {wait_selector} 超时，继续尝试备用选择器。", flush=True)

    for selector in selectors:
        try:
            eles = page.eles(selector)
            if eles:
                print(f"[调试] 选择器 {selector} 匹配到 {len(eles)} 个元素。", flush=True)
                return eles[:limit]
        except Exception as e:
            print(f"[调试] 选择器 {selector} 获取失败: {e}", flush=True)
    return []


def first_text(root, selectors):
    """在某个商品卡片内按顺序尝试选择器，返回第一段非空文本。"""
    if isinstance(selectors, str):
        selectors = [selectors]

    for selector in selectors:
        try:
            ele = root.ele(selector, timeout=0.5)
            if not ele:
                continue
            text = extract_text(ele).replace("\n", "/").strip()
            if text:
                return text
        except Exception:
            pass
    return ""


def sku_link(root):
    """优先从商品卡片 data-sku 拼出详情页链接。"""
    try:
        sku = root.attr("data-sku")
        if sku and sku.isdigit():
            return f"https://item.jd.com/{sku}.html"
    except Exception:
        pass

    try:
        sku_ele = root.ele("css:[data-sku]", timeout=0.5)
        if sku_ele:
            sku = sku_ele.attr("data-sku")
            if sku and sku.isdigit():
                return f"https://item.jd.com/{sku}.html"
    except Exception:
        pass
    return ""


def first_link(root):
    """在商品卡片内提取合法详情页链接。"""
    link = sku_link(root)
    if link:
        return link

    for selector in ("css:a[href*=\"item.jd.com\"]", "css:a[href*=\"//item.jd.com\"]"):
        try:
            for ele in root.eles(selector):
                link = normalize_url(ele.attr("href"))
                if link:
                    return link
        except Exception:
            pass
    return ""


def extract_products_by_cards(page, limit=MAX_PRODUCTS):
    """优先按商品卡片逐行提取，避免不同字段列表错位。"""
    for selector in CARD_SELECTORS:
        try:
            cards = page.eles(selector)
        except Exception:
            cards = []

        products = []
        for card in cards:
            name = first_text(card, NAME_SELECTORS)
            price_text = first_text(card, PRICE_SELECTORS)
            if not name or not price_text:
                continue

            products.append({
                "商品名称": name.replace("/", ""),
                "价格": price_text.replace("/", ""),
                "活动": first_text(card, PROMOTION_SELECTORS),
                "店铺名称": first_text(card, STORE_SELECTORS).replace("/", ""),
                "销量": first_text(card, SALES_SELECTORS).replace("/", ""),
                "详情链接": first_link(card),
            })
            if len(products) >= limit:
                break

        if products:
            print(f"[调试] 已通过商品卡片选择器 {selector} 提取到 {len(products)} 个商品。", flush=True)
            return products
    return []


def extract_product_list(page):
    """提取商品总览数据。"""
    print("\n[系统] 正在获取商品列表...", flush=True)
    products = extract_products_by_cards(page)

    if not products:
        name_eles = get_elements(page, NAME_SELECTORS, wait_selector=NAME_SELECTORS[0])
        names = [extract_text(e).replace("\n", "") for e in name_eles]
        names = [text for text in names if text]
        products = [{"商品名称": name, "详情链接": ""} for name in names]

        prices = [extract_text(e).replace("\n", "") for e in get_elements(page, PRICE_SELECTORS)]
        promotions = [extract_text(e).replace("\n", "/") for e in get_elements(page, PROMOTION_SELECTORS)]
        stores = [extract_text(e).replace("\n", "") for e in get_elements(page, STORE_SELECTORS)]
        sales = [extract_text(e).replace("\n", "") for e in get_elements(page, SALES_SELECTORS)]

        count = len(products)
        prices = normalize_column(prices, count)
        promotions = normalize_column(promotions, count)
        stores = normalize_column(stores, count)
        sales = normalize_column(sales, count)
        for i, product in enumerate(products):
            product.update({"价格": prices[i], "活动": promotions[i], "店铺名称": stores[i], "销量": sales[i]})

    if not products:
        raise RuntimeError("没有提取到商品名称，请检查页面是否登录/验证，或京东页面选择器是否已变化。")

    print(f"[系统] 商品列表获取完成，共 {len(products)} 个商品。", flush=True)
    return products
