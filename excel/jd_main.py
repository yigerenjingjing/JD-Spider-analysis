# -*- coding: utf-8 -*-
"""模块化京东爬虫入口。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.jd_browser import create_product_tab, initialize_list_browser
from crawler.jd_comment_crawler import crawl_product_comments
from excel.jd_excel_writer import write_result
from crawler.jd_product_extractor import extract_product_list


def main():
    """运行完整爬取流程。"""
    sys.stdout.reconfigure(encoding="utf-8")

    dp = None
    try:
        dp, tab = initialize_list_browser()
        products = extract_product_list(tab)

        print("[系统] 商品总览预览：共 {} 条记录".format(len(products)), flush=True)

        product_tab = create_product_tab(dp)
        comments_data = []  # 改用列表避免同名商品覆盖
        for index, product in enumerate(products, start=1):
            product_name = product["商品名称"]
            print(f"\n--- 开始处理第 {index}/{len(products)} 个商品: {product_name} ---", flush=True)
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
