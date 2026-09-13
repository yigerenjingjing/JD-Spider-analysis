# -*- coding: utf-8 -*-
"""京东数据爬虫优化版。

基于 `爬取京东数据.py` 重写，主要优化爬取速度：
1. 只启动一次浏览器，避免每个商品重复启动浏览器。
2. 复用一个商品工作标签页，避免每个商品后频繁关闭标签页造成卡住。
3. 尽量使用元素等待替代固定 sleep，减少无效等待。
"""

import builtins
import os
import re
import time

import pandas as pd
from DrissionPage import Chromium
from DrissionPage.errors import PageDisconnectedError


def print(*args, **kwargs):
    """让运行日志立即输出，便于定位卡住位置。"""
    kwargs.setdefault("flush", True)
    return builtins.print(*args, **kwargs)


# 目标网址（京东宠物玩具搜索结果页）
url = "https://search.jd.com/Search?keyword=%E5%AE%A0%E7%89%A9%E7%8E%A9%E5%85%B7&enc=utf-8&wq=%E5%AE%A0%E7%89%A9wan%27jv&pvid=a31833d4f6ba4a038b51e97e9aa91ab7"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
}

output_path = r"D:\jd_result.xlsx"

MAX_PRODUCTS = 4
MAX_COMMENTS_PER_PRODUCT = 20
TIMEOUT = 15
SHORT_TIMEOUT = 5

name_selectors = ["css:._text_1x4i2_30", "css:.p-name em", "css:.p-name a", "css:[class*=\"_text_\"]"]
price_selectors = ["css:._price_1tn4o_13", "css:.p-price i", "css:.p-price", "css:[class*=\"_price_\"]"]
promotion_selectors = ["css:._tags_hzhkm_2", "css:.p-icons", "css:[class*=\"_tags_\"]"]
store_selectors = ["css:._name_d19t5_35", "css:.p-shop a", "css:.p-shop", "css:[class*=\"_name_\"]"]
sales_selectors = ["css:._goods_volume_1xkku_1", "css:.p-commit", "css:[class*=\"_goods_volume_\"]"]
card_selectors = ["css:li.gl-item", "css:.gl-item", "css:[data-sku]", "css:[class*=\"_goods_item_\"]"]
comment_selectors = ["css:.jdc-pc-rate-card-main-desc", "css:.comment-con", "css:[class*=\"rate-card-main-desc\"]"]
all_comment_button_selectors = ["css:.all-btn", "text:全部评价", "css:#comment"]


def initialize_browser():
    """初始化浏览器、打开列表页并点击销量排序。"""
    print("\n[系统] 正在初始化浏览器...")
    dp = Chromium()
    list_tab = dp.new_tab()
    list_tab.get(url)
    list_tab.wait.load_start()

    print("[系统] 正在等待并点击销量排序...")
    list_tab.wait.ele_displayed("text:销量", timeout=TIMEOUT)
    list_tab.ele("text:销量").click()
    list_tab.wait.ele_displayed(name_selectors[0], timeout=TIMEOUT)
    print("[系统] 浏览器初始化完成，已进入商品列表页。")
    return dp, list_tab


def extract_text(ele):
    """尽量从元素中提取可见文字，兼容部分页面 .text 为空的情况。"""
    candidates = []
    for attr_name in ("text", "raw_text"):
        try:
            candidates.append(getattr(ele, attr_name, ""))
        except Exception:
            pass

    for attr_name in ("title", "aria-label"):
        try:
            candidates.append(ele.attr(attr_name))
        except Exception:
            pass

    try:
        candidates.append(ele.run_js('return this.innerText || this.textContent || "";'))
    except Exception:
        pass

    for text in candidates:
        text = (text or "").strip()
        if text:
            return text
    return ""


def normalize_url(link):
    """只保留京东商品详情页链接，避免误打开客服/店铺等入口。"""
    link = (link or "").strip()
    if not link:
        return ""
    if link.startswith("//"):
        link = "https:" + link
    elif link.startswith("/"):
        link = "https://item.jd.com" + link

    match = re.search(r"https?://item\.jd\.com/(\d+)\.html", link)
    if match:
        return f"https://item.jd.com/{match.group(1)}.html"
    return ""


def get_sku_from_link(link):
    """从商品详情链接中提取 SKU。"""
    match = re.search(r"item\.jd\.com/(\d+)\.html", link or "")
    return match.group(1) if match else ""


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
    """在商品卡片内提取详情页链接。"""
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


def get_elements(page, selectors, limit=MAX_PRODUCTS, wait_selector=None):
    """按顺序尝试多个选择器，返回第一组非空元素。"""
    if isinstance(selectors, str):
        selectors = [selectors]

    if wait_selector:
        try:
            page.wait.ele_displayed(wait_selector, timeout=TIMEOUT)
        except Exception:
            print(f"[调试] 等待选择器 {wait_selector} 超时，继续尝试备用选择器。")

    for selector in selectors:
        try:
            elements = page.eles(selector)
            if elements:
                print(f"[调试] 选择器 {selector} 匹配到 {len(elements)} 个元素。")
                return elements[:limit]
        except Exception as e:
            print(f"[调试] 选择器 {selector} 获取失败: {e}")
    return []


def normalize_column(values, target_length, fill_value=""):
    """把商品字段列表统一成相同长度。"""
    values = list(values)[:target_length]
    if len(values) < target_length:
        values.extend([fill_value] * (target_length - len(values)))
    return values


def extract_products_by_cards(page, limit=MAX_PRODUCTS):
    """优先按商品卡片逐行提取，避免不同字段列表错位。"""
    for selector in card_selectors:
        try:
            cards = page.eles(selector)
        except Exception:
            cards = []

        products = []
        for card in cards:
            name = first_text(card, name_selectors)
            price_text = first_text(card, price_selectors)
            if not name or not price_text:
                continue

            products.append({
                "商品名称": name.replace("/", ""),
                "价格": price_text.replace("/", ""),
                "活动": first_text(card, promotion_selectors),
                "店铺名称": first_text(card, store_selectors).replace("/", ""),
                "销量": first_text(card, sales_selectors).replace("/", ""),
                "详情链接": first_link(card),
            })
            if len(products) >= limit:
                break

        if products:
            print(f"[调试] 已通过商品卡片选择器 {selector} 提取到 {len(products)} 个商品。")
            return products
    return []


def extract_products(page):
    """提取商品列表。"""
    print("\n[系统] 正在获取商品列表...")
    products = extract_products_by_cards(page)
    if products:
        print(f"[系统] 商品列表获取完成，共 {len(products)} 条。")
        return products

    name_eles = get_elements(page, name_selectors, wait_selector=name_selectors[0])
    content = [extract_text(e).replace("\n", "") for e in name_eles]
    content = [text for text in content if text]
    if not content:
        raise RuntimeError("没有提取到商品名称，请检查页面是否登录/验证，或京东页面选择器是否已变化。")

    price = [extract_text(e).replace("\n", "") for e in get_elements(page, price_selectors)]
    huodong = [extract_text(e).replace("\n", "/") for e in get_elements(page, promotion_selectors)]
    store_name = [extract_text(e).replace("\n", "") for e in get_elements(page, store_selectors)]
    goods_volume = [extract_text(e).replace("\n", "") for e in get_elements(page, sales_selectors)]

    product_count = len(content)
    price = normalize_column(price, product_count)
    huodong = normalize_column(huodong, product_count)
    store_name = normalize_column(store_name, product_count)
    goods_volume = normalize_column(goods_volume, product_count)

    products = []
    for index, name in enumerate(content):
        products.append({
            "商品名称": name,
            "价格": price[index],
            "活动": huodong[index],
            "店铺名称": store_name[index],
            "销量": goods_volume[index],
            "详情链接": "",
        })
    print(f"[系统] 商品列表获取完成，共 {len(products)} 条。")
    return products


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
    for selector in comment_selectors:
        try:
            page.wait.ele_displayed(selector, timeout=SHORT_TIMEOUT)
            return selector
        except Exception:
            pass
    return comment_selectors[0]


def open_comment_page(dp, product_tab, product_link):
    """打开评论页。优先点击页面按钮，失败时用 SKU 构造评论页地址。"""
    button = first_displayed(product_tab, all_comment_button_selectors)
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
    print(f"[调试] 未找到全部评价按钮，改用评论页 URL: {comment_url}")
    product_tab.get(comment_url)
    product_tab.wait.load_start()
    return product_tab


def collect_comments(comments_page):
    """滚动评论页并收集评论。"""
    selector = visible_comment_selector(comments_page)
    all_comments_texts = set()
    retries = 5
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
            retries = 5
        else:
            retries -= 1

        if current_count >= MAX_COMMENTS_PER_PRODUCT:
            break

        if current_comments_eles:
            current_comments_eles[-1].scroll.to_see()
            time.sleep(0.5)
        else:
            break

    return [
        text.strip()
        for text in all_comments_texts
        if text.strip() != "此用户未填写评价内容" and len(text.strip()) >= 5
    ]


def crawl_comments(dp, product_tab, product):
    """复用商品工作标签页爬取单个商品评论。"""
    product_name = product["商品名称"]
    product_link = product.get("详情链接", "")
    if not product_link:
        print("[警告] 未提取到合法商品详情链接，跳过该商品，避免误打开客服/店铺页。")
        return []

    try:
        print(f"[调试] 使用详情链接打开商品页: {product_link}")
        product_tab.get(product_link)
        product_tab.wait.load_start()
        print("已进入商品详情页。")

        comments_page = open_comment_page(dp, product_tab, product_link)
        comments_page.wait.load_start()
        comments = collect_comments(comments_page)
        print(f"成功采集 {len(comments)} 条评论到内存。")
        return comments

    except PageDisconnectedError as e:
        print(f"[严重错误] 与浏览器连接已断开: {e}")
        return []
    except Exception as e:
        print(f"[未知错误] 处理 '{product_name}' 时发生错误: {e}")
        return []


def sanitize_sheet_name(name, max_length=31):
    """清理 Excel 工作表名称。"""
    for char in r"[]:*?/\\":
        name = name.replace(char, "-")
    name = name.strip()[:max_length]
    return name or "Sheet"


def write_excel(products, comments_data):
    """写入 Excel 文件。"""
    dir_path = os.path.dirname(output_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    overview = [{
        "商品名称": product.get("商品名称", ""),
        "价格": product.get("价格", ""),
        "活动": product.get("活动", ""),
        "店铺名称": product.get("店铺名称", ""),
        "销量": product.get("销量", ""),
    } for product in products]

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(overview).to_excel(writer, sheet_name="商品总览", index=False)
        print("已写入 '商品总览' 工作表。")

        used_sheet_names = {"商品总览"}
        for product_name, comments in comments_data.items():
            if not comments:
                continue

            sheet_name = sanitize_sheet_name(product_name)
            base_name = sheet_name
            suffix = 1
            while sheet_name in used_sheet_names:
                tail = f"_{suffix}"
                sheet_name = f"{base_name[:31 - len(tail)]}{tail}"
                suffix += 1
            used_sheet_names.add(sheet_name)

            pd.DataFrame(comments, columns=["评论"]).to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"已写入 '{sheet_name}' 工作表。")

    print(f"[成功] 数据已全部保存至 '{output_path}'")


def main():
    """主程序。"""
    dp = None
    try:
        dp, list_tab = initialize_browser()
        products = extract_products(list_tab)
        print("[系统] 商品总览预览：共 {} 条记录".format(len(products)))

        # 只创建一个商品工作标签页，后续所有商品都复用它跳转。
        product_tab = dp.new_tab()
        comments_data = {}
        for index, product in enumerate(products, start=1):
            product_name = product["商品名称"]
            print(f"\n--- 开始处理第 {index}/{len(products)} 个商品: {product_name} ---")
            comments_data[product_name] = crawl_comments(dp, product_tab, product)

        print("\n--- 所有商品评论爬取任务已尝试执行完毕 ---")
        print("\n[系统] 开始将所有采集数据一次性写入Excel文件...")
        write_excel(products, comments_data)

    finally:
        if dp:
            try:
                dp.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
