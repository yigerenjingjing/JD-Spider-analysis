# -*- coding: utf-8 -*-
"""模块化京东爬虫入口 —— MySQL 版（数据直接存入数据库，不生成 Excel）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.jd_browser import create_product_tab, initialize_list_browser
from crawler.jd_comment_crawler import crawl_product_comments
from crawler.jd_product_extractor import extract_product_list
from mysql.store_to_mysql import store_to_database


def main():
    """运行完整爬取流程，数据直接存入 MySQL。"""
    sys.stdout.reconfigure(encoding="utf-8")

    dp = None
    try:
        dp, tab = initialize_list_browser()
        products = extract_product_list(tab)

        print("[系统] 商品总览预览：共 {} 条记录".format(len(products)), flush=True)

        product_tab = create_product_tab(dp)
        comments_data = []
        for index, product in enumerate(products, start=1):
            product_name = product["商品名称"]
            print(f"\n--- 开始处理第 {index}/{len(products)} 个商品: {product_name} ---", flush=True)
            comments = crawl_product_comments(dp, product_tab, product)
            comments_data.append({"product_name": product_name, "comments": comments})

        print("\n--- 所有商品评论爬取任务已尝试执行完毕 ---", flush=True)
        print("\n[系统] 开始将采集数据存入 MySQL 数据库...", flush=True)
        store_to_database(products, comments_data)

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
