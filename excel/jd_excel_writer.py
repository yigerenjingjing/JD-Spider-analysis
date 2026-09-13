# -*- coding: utf-8 -*-
"""Excel 写入，支持增量去重：已有商品合并新评论，新商品追加。"""

import os

import pandas as pd

from jd_config import OUTPUT_PATH
from crawler.jd_utils import sanitize_sheet_name


def _normalize_name(name):
    """标准化商品名用于匹配。"""
    return str(name).strip().replace(" ", "")


def _make_product_key(product):
    """生成去重匹配 key：商品名称 + 价格 + 店铺。"""
    name = _normalize_name(product.get("商品名称", ""))
    price = str(product.get("价格", "")).strip()
    store = str(product.get("店铺名称", "")).strip()
    return f"{name}|{price}|{store}"


def write_result(products, comments_data, output_path=OUTPUT_PATH):
    """增量写入：已有 Excel 则合并去重，否则新建。

    comments_data: [(product_dict, [comment_text, ...]), ...]
    """
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    dir_path = os.path.dirname(output_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    # ── 1. 加载已有数据（如果文件存在）──
    existing_products = {}   # key -> {产品行数据, comments: [str]}
    existing_sheet_order = []  # sheet 顺序

    if os.path.exists(output_path):
        print(f"[去重] 检测到已有数据文件，正在加载比对...", flush=True)
        xls = pd.ExcelFile(output_path)
        old_overview = pd.read_excel(xls, sheet_name="商品总览")
        for _, row in old_overview.iterrows():
            p = {
                "商品名称": str(row.get("商品名称", "")),
                "价格": str(row.get("价格", "")),
                "活动": str(row.get("活动", "")),
                "店铺名称": str(row.get("店铺名称", "")),
                "销量": str(row.get("销量", "")),
            }
            key = _make_product_key(p)
            existing_products[key] = {"product": p, "comments": []}
            existing_sheet_order.append(key)

        for sheet in xls.sheet_names[1:]:
            df = pd.read_excel(xls, sheet_name=sheet)
            comments = df.iloc[:, 0].dropna().tolist()
            # 找到对应 key（sheet 名可能被截断过，遍历匹配）
            for i, key in enumerate(existing_sheet_order):
                if key not in existing_products:
                    continue
                if not existing_products[key]["comments"]:
                    existing_products[key]["comments"] = comments
                    break
            else:
                # 没匹配上就用 sheet 名新建
                if sheet not in existing_products:
                    existing_products[sheet] = {"product": {"商品名称": sheet}, "comments": comments}
                    existing_sheet_order.append(sheet)

    # ── 2. 合并新数据 ──
    new_product_count = 0
    new_comment_count = 0

    for product, comments in comments_data:
        if not comments:
            continue
        key = _make_product_key(product)

        if key in existing_products:
            # 已有商品：合并新评论（去重）
            old_comments_set = set(existing_products[key]["comments"])
            added = [c for c in comments if c not in old_comments_set]
            if added:
                existing_products[key]["comments"].extend(added)
                new_comment_count += len(added)
                print(f"[去重] 「{product.get('商品名称', '')[:20]}」已有，合并 {len(added)} 条新评论", flush=True)
            else:
                print(f"[去重] 「{product.get('商品名称', '')[:20]}」已有，无新评论，跳过", flush=True)
            # 更新销量信息（可能已变化）
            existing_products[key]["product"]["销量"] = str(product.get("销量", ""))
        else:
            # 新商品：追加
            new_product_count += 1
            new_comment_count += len(comments)
            existing_products[key] = {
                "product": {
                    "商品名称": product.get("商品名称", ""),
                    "价格": product.get("价格", ""),
                    "活动": product.get("活动", ""),
                    "店铺名称": product.get("店铺名称", ""),
                    "销量": product.get("销量", ""),
                },
                "comments": list(comments),
            }
            existing_sheet_order.append(key)
            print(f"[去重] 「{product.get('商品名称', '')[:20]}」为新商品，追加", flush=True)

    # ── 3. 写入 ──
    overview_rows = []
    for key in existing_sheet_order:
        if key in existing_products:
            overview_rows.append(existing_products[key]["product"])

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(overview_rows).to_excel(writer, sheet_name="商品总览", index=False)
        print("已写入 '商品总览' 工作表。", flush=True)

        used_sheet_names = {"商品总览"}
        for key in existing_sheet_order:
            if key not in existing_products:
                continue
            entry = existing_products[key]
            comments = entry["comments"]
            if not comments:
                continue

            product_name = entry["product"]["商品名称"]
            sheet_name = sanitize_sheet_name(product_name)
            base_name = sheet_name
            suffix = 1
            while sheet_name in used_sheet_names:
                tail = f"_{suffix}"
                sheet_name = f"{base_name[:31 - len(tail)]}{tail}"
                suffix += 1
            used_sheet_names.add(sheet_name)

            pd.DataFrame(comments, columns=["评论"]).to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"已写入 '{sheet_name}' 工作表 ({len(comments)} 条评论)。", flush=True)

    print(f"[成功] 新增 {new_product_count} 个商品、{new_comment_count} 条评论，总计 {len(overview_rows)} 个商品。已保存至 '{output_path}'", flush=True)
