import requests
from DrissionPage import Chromium,ChromiumOptions
from DrissionPage.errors import PageDisconnectedError, ElementNotFoundError
from bs4 import BeautifulSoup
import time
import json
import pandas as pd
import os
import builtins
import re


def print(*args, **kwargs):
    """让运行日志立即输出，便于定位卡住位置。"""
    kwargs.setdefault("flush", True)
    return builtins.print(*args, **kwargs)

# 目标网址（京东宠物玩具搜索结果页）
url = "https://search.jd.com/Search?keyword=%E5%AE%A0%E7%89%A9%E7%8E%A9%E5%85%B7&enc=utf-8&wq=%E5%AE%A0%E7%89%A9wan%27jv&pvid=a31833d4f6ba4a038b51e97e9aa91ab7"

headers = {
    # 模拟浏览器头部，防止被反爬
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
}

#保存文件地址
output_path = r"D:\jd_result.xlsx"

# 浏览器管理函数
def initialize_browser():
    """初始化浏览器、打开页面、点击排序，并返回实例和主标签页。"""
    print("\n[系统] 正在初始化新的浏览器实例...")
    dp = Chromium()
    tab = dp.new_tab()
    tab.get(url)
    tab.wait.load_start()
    print("[系统] 正在等待并点击销量排序...")
    tab.wait.ele_displayed('text:销量', timeout=15)
    tab.ele('text:销量').click()
    time.sleep(2)
    print("[系统] 浏览器初始化完成，已进入商品列表页。")
    return dp, tab

# 主程序
# 1. 初始化浏览器并获取商品列表
dp, tab = initialize_browser()
# 等待商品名称元素加载完成，确保页面已渲染
tab.wait.ele_displayed('css:._text_1x4i2_30', timeout=15)

def extract_text(ele):
    """尽量从元素中提取可见文字，兼容部分页面 .text 为空的情况。"""
    candidates = []
    for attr_name in ('text', 'raw_text'):
        try:
            candidates.append(getattr(ele, attr_name, ''))
        except Exception:
            pass
    for attr_name in ('title', 'aria-label'):
        try:
            candidates.append(ele.attr(attr_name))
        except Exception:
            pass
    try:
        candidates.append(ele.run_js('return this.innerText || this.textContent || "";'))
    except Exception:
        pass

    for text in candidates:
        text = (text or '').strip()
        if text:
            return text
    return ''

def get_elements(page, selectors, limit=4, wait_selector=None):
    """按顺序尝试多个选择器，返回第一组非空元素。"""
    if isinstance(selectors, str):
        selectors = [selectors]
    if wait_selector:
        try:
            page.wait.ele_displayed(wait_selector, timeout=15)
        except Exception:
            print(f"[调试] 等待选择器 {wait_selector} 超时，继续尝试备用选择器。")
    for selector in selectors:
        try:
            eles = page.eles(selector)
            if eles:
                print(f"[调试] 选择器 {selector} 匹配到 {len(eles)} 个元素。")
                return eles[:limit]
        except Exception as e:
            print(f"[调试] 选择器 {selector} 获取失败: {e}")
    return []

def normalize_url(link):
    """只保留京东商品详情页链接，避免误打开客服/店铺等入口。"""
    link = (link or '').strip()
    if not link:
        return ''
    if link.startswith('//'):
        return 'https:' + link
    if link.startswith('/'):
        return 'https://item.jd.com' + link
    match = re.search(r'https?://item\.jd\.com/(\d+)\.html', link)
    if match:
        return f"https://item.jd.com/{match.group(1)}.html"
    return ''

def sku_link(root):
    """优先从商品卡片 data-sku 拼出详情页链接。"""
    try:
        sku = root.attr('data-sku')
        if sku and sku.isdigit():
            return f"https://item.jd.com/{sku}.html"
    except Exception:
        pass

    try:
        sku_ele = root.ele('css:[data-sku]', timeout=0.5)
        if sku_ele:
            sku = sku_ele.attr('data-sku')
            if sku and sku.isdigit():
                return f"https://item.jd.com/{sku}.html"
    except Exception:
        pass

    return ''

def first_link(root):
    """在商品卡片内提取详情页链接。"""
    link = sku_link(root)
    if link:
        return link

    link_selectors = [
        'css:a[href*="item.jd.com"]',
        'css:a[href*="//item.jd.com"]',
    ]
    for selector in link_selectors:
        try:
            for ele in root.eles(selector):
                link = normalize_url(ele.attr('href'))
                if link:
                    return link
        except Exception:
            pass
    return ''

def close_other_tabs(dp, keep_tab):
    """按 tab_id 保留列表页，关闭其它详情/评论标签页。"""
    keep_tab_id = keep_tab.tab_id
    print(f"[调试] 准备关闭额外标签页，保留列表页 tab_id={keep_tab_id}")
    for current_tab in list(dp.get_tabs()):
        try:
            if current_tab.tab_id != keep_tab_id:
                print(f"[调试] 关闭标签页 tab_id={current_tab.tab_id}")
                current_tab.close()
        except Exception as e:
            print(f"[调试] 关闭标签页失败: {e}")
    time.sleep(1)
    try:
        return dp.get_tab(keep_tab_id)
    except Exception as e:
        print(f"[调试] 列表页已不可用，将重新初始化浏览器: {e}")
        raise PageDisconnectedError

name_selectors = ['css:._text_1x4i2_30', 'css:.p-name em', 'css:.p-name a', 'css:[class*="_text_"]']
price_selectors = ['css:._price_1tn4o_13', 'css:.p-price i', 'css:.p-price', 'css:[class*="_price_"]']
promotion_selectors = ['css:._tags_hzhkm_2', 'css:.p-icons', 'css:[class*="_tags_"]']
store_selectors = ['css:._name_d19t5_35', 'css:.p-shop a', 'css:.p-shop', 'css:[class*="_name_"]']
sales_selectors = ['css:._goods_volume_1xkku_1', 'css:.p-commit', 'css:[class*="_goods_volume_"]']

def first_text(root, selectors):
    """在某个商品卡片内按顺序尝试选择器，返回第一段非空文本。"""
    if isinstance(selectors, str):
        selectors = [selectors]
    for selector in selectors:
        try:
            ele = root.ele(selector, timeout=0.5)
            if not ele:
                continue
            text = extract_text(ele).replace('\n', '/').strip()
            if text:
                return text
        except Exception:
            pass
    return ''

def extract_products_by_cards(page, limit=4):
    """优先按商品卡片逐行提取，避免不同字段列表错位。"""
    card_selectors = [
        'css:li.gl-item',
        'css:.gl-item',
        'css:[data-sku]',
        'css:[class*="_goods_item_"]',
    ]
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
                '商品名称': name.replace('/', ''),
                '价格': price_text.replace('/', ''),
                '活动': first_text(card, promotion_selectors),
                '店铺名称': first_text(card, store_selectors).replace('/', ''),
                '销量': first_text(card, sales_selectors).replace('/', ''),
                '详情链接': first_link(card),
            })
            if len(products) >= limit:
                break
        if products:
            print(f"[调试] 已通过商品卡片选择器 {selector} 提取到 {len(products)} 个商品。")
            return products
    return []

print("\n[系统] 正在获取商品列表...")
products = extract_products_by_cards(tab)
if products:
    content = [p['商品名称'] for p in products]
    price = [p['价格'] for p in products]
    huodong = [p['活动'] for p in products]
    store_name = [p['店铺名称'] for p in products]
    goods_volume = [p['销量'] for p in products]
    product_links = [p.get('详情链接', '') for p in products]
else:
    name_eles = get_elements(tab, name_selectors, wait_selector=name_selectors[0])
    content = [extract_text(e).replace('\n', '') for e in name_eles]
    content = [text for text in content if text]
    product_links = []

    price_eles = get_elements(tab, price_selectors)
    price = [extract_text(e).replace('\n', '') for e in price_eles]

    promotion_eles = get_elements(tab, promotion_selectors)
    huodong = [extract_text(e).replace('\n', '/') for e in promotion_eles]

    store_eles = get_elements(tab, store_selectors)
    store_name = [extract_text(e).replace('\n', '') for e in store_eles]

    sales_eles = get_elements(tab, sales_selectors)
    goods_volume = [extract_text(e).replace('\n', '') for e in sales_eles]

if not content:
    raise RuntimeError("没有提取到商品名称，请检查页面是否登录/验证，或京东页面选择器是否已变化。")

def normalize_column(values, target_length, fill_value=''):
    """把商品字段列表统一成相同长度，避免某些字段缺失导致 DataFrame 创建失败。"""
    values = list(values)[:target_length]
    if len(values) < target_length:
        values.extend([fill_value] * (target_length - len(values)))
    return values

product_count = len(content)
price = normalize_column(price, product_count)
huodong = normalize_column(huodong, product_count)
store_name = normalize_column(store_name, product_count)
goods_volume = normalize_column(goods_volume, product_count)
product_links = normalize_column(product_links, product_count)
print(
    "[系统] 字段数量："
    f"商品名称={len(content)}, 价格={len(price)}, 活动={len(huodong)}, "
    f"店铺名称={len(store_name)}, 销量={len(goods_volume)}"
)
print("[系统] 商品列表获取完成 (仅获取前4个)。")

# 2. 创建总览DataFrame和用于存储评论的字典
all_products_data = {
    '商品名称': content, '价格': price, '活动': huodong,
    '店铺名称': store_name, '销量': goods_volume
}
all_products_df = pd.DataFrame(all_products_data)
print("[系统] 商品总览预览：共 {} 条记录".format(len(all_products_df)))
# 简化预览输出，避免 Unicode 编码问题
all_comments_data = {} # 用于在内存中存储所有评论

# 商品列表和详情链接已提取完，后续每个商品独立打开浏览器，避免多标签返回列表页时卡死。
try:
    dp.quit()
except Exception:
    pass

def open_product_browser(product_link):
    """为单个商品启动独立浏览器实例并打开详情页。"""
    product_dp = Chromium()
    product_tab = product_dp.new_tab(product_link)
    product_tab.wait.load_start()
    return product_dp, product_tab

# 3. 使用while循环爬取每个商品的评论
i = 0
while i < len(content):
    product_name = content[i]
    product_link = product_links[i] if i < len(product_links) else ''
    product_dp = None
    try:
        print(f"\n--- 开始处理第 {i + 1}/{len(content)} 个商品: {product_name} ---")
    except UnicodeEncodeError:
        # 若控制台编码不支持某些字符，使用 utf-8 编码后再打印（忽略错误）
        safe_name = product_name.encode('utf-8', errors='ignore').decode('utf-8')
        print(f"\n--- 开始处理第 {i + 1}/{len(content)} 个商品: {safe_name} ---")
    
    try:
        if not product_link:
            print("[警告] 未提取到合法商品详情链接，跳过该商品，避免误打开客服/店铺页。")
            i += 1
            continue

        print(f"[调试] 使用详情链接打开商品页: {product_link}")
        product_dp, new_tab = open_product_browser(product_link)
        print("已进入商品详情页...")
        time.sleep(2)

        # 等待并点击“全部评价”
        new_tab.wait.ele_displayed('css:.all-btn', timeout=15)
        new_tab.ele('css:.all-btn').click()
        time.sleep(2)
        comments_page = product_dp.latest_tab
        comments_page.wait.load_start()

        # 等待并爬取评论
        comments_page.wait.ele_displayed('.jdc-pc-rate-card-main-desc', timeout=15)
        all_comments_texts = set()
        retries = 5
        last_comment_count = 0
        while retries > 0:
            current_comments_eles = comments_page.eles('css:.jdc-pc-rate-card-main-desc')
            for comment in current_comments_eles:
                comment_text = extract_text(comment)
                if comment_text:
                    all_comments_texts.add(comment_text)

            if len(all_comments_texts) > last_comment_count:
                last_comment_count = len(all_comments_texts)
                retries = 5
            else:
                retries -= 1
            
            if len(all_comments_texts) >= 20:
                break

            if current_comments_eles:
                current_comments_eles[-1].scroll.to_see()
            else:
                break
            time.sleep(1.5)

        # 数据清洗并存入内存字典
        if all_comments_texts:
            cleaned_texts = [
                text.strip() for text in all_comments_texts 
                if text.strip() != "此用户未填写评价内容" and len(text.strip()) >= 5
            ]
            if cleaned_texts:
                all_comments_data[product_name] = cleaned_texts
                print(f"成功采集 {len(cleaned_texts)} 条评论到内存。")

        print("正在关闭当前商品浏览器，准备下一个商品...")
        product_dp.quit()
        time.sleep(1)
        i += 1

    except PageDisconnectedError as e:
        print(f"[严重错误] 与浏览器连接已断开: {e}")
        print("[恢复流程] 正在关闭当前商品浏览器并跳过当前商品...")
        try:
            product_dp.quit()
        except:
            pass
        i += 1

    except Exception as e:
        print(f"[未知错误] 处理 '{product_name}' 时发生错误: {e}")
        print("[恢复流程] 正在关闭当前商品浏览器并跳过当前商品...")
        try:
            product_dp.quit()
        except:
            pass
        i += 1

print("\n--- 所有商品评论爬取任务已尝试执行完毕 ---")

# 4. 所有爬取任务结束后，一次性写入Excel文件
print("\n[系统] 开始将所有采集数据一次性写入Excel文件...")
try:
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        all_products_df.to_excel(writer, sheet_name='商品总览', index=False)
        print("已写入 '商品总览' 工作表。")
        
        for product_name, comments in all_comments_data.items():
            df_comments = pd.DataFrame(comments, columns=['评论'])
            sheet_name = product_name.replace('/', '-').replace('\\', '-').replace('?', '').replace('*', '').replace('[', '').replace(']', '')[:31]
            df_comments.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"已写入 '{sheet_name}' 工作表。")
    print(f"[成功] 数据已全部保存至 '{output_path}'")
except Exception as e:
    print(f"[失败] 写入Excel文件时发生错误: {e}")
