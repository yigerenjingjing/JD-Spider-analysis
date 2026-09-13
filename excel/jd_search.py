# -*- coding: utf-8 -*-
"""JD商品搜索爬虫，可通过用户输入关键字进行爬取，复用已有模块化代码。"""

import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jd_config import URL as DEFAULT_URL
from crawler.jd_browser import initialize_list_browser, create_product_tab
from crawler.jd_product_extractor import extract_product_list
from crawler.jd_comment_crawler import crawl_product_comments
from excel.jd_excel_writer import write_result
import jd_config

def main():
    sys.stdout.reconfigure(encoding="utf-8")

    keyword = input("请输入想要搜索的商品关键字: ").strip()
    if not keyword:
        print("未输入关键字，程序退出。")
        return
    encoded = urllib.parse.quote(keyword)
    search_url = f"https://search.jd.com/Search?keyword={encoded}&enc=utf-8&wq={encoded}"
    jd_config.URL = search_url
    dp = None
    try:
        dp, list_tab = initialize_list_browser()
        products = extract_product_list(list_tab)
        print(f"[系统] 商品总览预览：共 {len(products)} 条记录", flush=True)
        product_tab = create_product_tab(dp)
        comments_data = []  # 改用列表避免同名商品覆盖
        for idx, product in enumerate(products, start=1):
            name = product.get("商品名称", "")
            print(f"\n--- 开始处理第 {idx}/{len(products)} 个商品: {name} ---", flush=True)
            comments = crawl_product_comments(dp, product_tab, product)
            comments_data.append((product, comments))
        print("\n--- 所有商品评论爬取任务已尝试执行完毕 ---", flush=True)
        print("\n[系统] 开始将所有采集数据一次性写入Excel文件...", flush=True)
        write_result(products, comments_data)
    except KeyboardInterrupt:
        print("\n[系统] 用户中断，正在清理资源...", flush=True)
    finally:
        if dp:
            try:
                dp.quit()
            except Exception:
                pass

if __name__ == "__main__":
    main()
