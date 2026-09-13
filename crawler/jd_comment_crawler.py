# -*- coding: utf-8 -*-
"""商品评论爬取。

优化版策略：复用同一个浏览器实例和一个商品工作标签页，避免每个商品重复启动浏览器。
"""

import random
import time

from DrissionPage.errors import PageDisconnectedError

from jd_config import (
    ALL_COMMENT_BUTTON_SELECTORS,
    COMMENT_SCROLL_DELAY,
    COMMENT_TEXT_SELECTORS,
    CRAWL_DELAY_MAX,
    CRAWL_DELAY_MIN,
    INVALID_COMMENT,
    MAX_COMMENTS_PER_PRODUCT,
    MIN_COMMENT_LENGTH,
    PAGE_LOAD_DELAY,
    SCROLL_RETRIES,
    SHORT_TIMEOUT,
)
from crawler.jd_utils import extract_text, get_sku_from_link


def clean_comments(comments):
    """过滤无效评论。"""
    cleaned = []
    for text in comments:
        stripped = text.strip()
        if stripped == INVALID_COMMENT:
            continue
        if len(stripped) < MIN_COMMENT_LENGTH:
            continue
        cleaned.append(stripped)
    return cleaned


def first_displayed(page, selectors, timeout=SHORT_TIMEOUT):
    """返回第一个显示出来的元素。"""
    for selector in selectors:
        try:
            page.wait.ele_displayed(selector, timeout=timeout)
            element = page.ele(selector)
            if element:
                return element
        except Exception:
            pass
    return None


def visible_comment_selector(page):
    """返回当前页面可用的评论选择器。"""
    for selector in COMMENT_TEXT_SELECTORS:
        try:
            page.wait.ele_displayed(selector, timeout=SHORT_TIMEOUT)
            return selector
        except Exception:
            pass
    return COMMENT_TEXT_SELECTORS[0]


def open_comment_page(dp, product_tab, product_link):
    """打开评论页。优先点击页面按钮，失败时用 SKU 构造评论页地址。"""
    button = first_displayed(product_tab, ALL_COMMENT_BUTTON_SELECTORS)
    if button:
        before_tab_ids = set(dp.tab_ids)
        button.click()
        try:
            new_tab_id = dp.wait.new_tab(timeout=3, curr_tab=product_tab.tab_id, raise_err=False)
        except Exception:
            new_tab_id = None

        if new_tab_id and new_tab_id not in before_tab_ids:
            return dp.get_tab(new_tab_id)
        return product_tab

    sku = get_sku_from_link(product_link)
    if not sku:
        raise RuntimeError("无法找到全部评价按钮，也无法从商品链接解析 SKU。")

    comment_url = f"https://club.jd.com/comment/sku/{sku}/page/1.html"
    print(f"[调试] 未找到全部评价按钮，改用评论页 URL: {comment_url}", flush=True)
    product_tab.get(comment_url)
    product_tab.wait.load_start()
    return product_tab


def collect_comments(comments_page):
    """滚动评论页并收集评论。"""
    selector = visible_comment_selector(comments_page)
    all_comments_texts = set()
    retries = SCROLL_RETRIES
    last_comment_count = 0

    while retries > 0:
        current_comments_eles = comments_page.eles(selector)
        for comment in current_comments_eles:
            comment_text = extract_text(comment)
            if comment_text:
                all_comments_texts.add(comment_text)

        current_count = len(all_comments_texts)
        if current_count > last_comment_count:
            last_comment_count = current_count
            retries = SCROLL_RETRIES
        else:
            retries -= 1

        if current_count >= MAX_COMMENTS_PER_PRODUCT:
            break

        if current_comments_eles:
            current_comments_eles[-1].scroll.to_see()
            time.sleep(COMMENT_SCROLL_DELAY)
        else:
            break

    comments = clean_comments(all_comments_texts)
    return comments[:MAX_COMMENTS_PER_PRODUCT]


def crawl_product_comments(dp, product_tab, product):
    """复用商品工作标签页爬取单个商品评论。"""
    product_name = product["商品名称"]
    product_link = product.get("详情链接", "")

    if not product_link:
        print("[警告] 未提取到合法商品详情链接，跳过该商品，避免误打开客服/店铺页。", flush=True)
        return []

    try:
        print(f"[调试] 使用详情链接打开商品页: {product_link}", flush=True)
        product_tab.get(product_link)
        product_tab.wait.load_start()
        time.sleep(PAGE_LOAD_DELAY)
        print("已进入商品详情页。", flush=True)

        comments_page = open_comment_page(dp, product_tab, product_link)
        comments_page.wait.load_start()
        time.sleep(PAGE_LOAD_DELAY)
        comments = collect_comments(comments_page)
        print(f"成功采集 {len(comments)} 条评论到内存。", flush=True)

        delay = random.uniform(CRAWL_DELAY_MIN, CRAWL_DELAY_MAX)
        print(f"[限速] 等待 {delay:.1f} 秒后处理下一个商品...", flush=True)
        time.sleep(delay)
        return comments

    except PageDisconnectedError as e:
        print(f"[严重错误] 与浏览器连接已断开: {e}", flush=True)
        return []
    except Exception as e:
        print(f"[未知错误] 处理 '{product_name}' 时发生错误: {e}", flush=True)
        return []
