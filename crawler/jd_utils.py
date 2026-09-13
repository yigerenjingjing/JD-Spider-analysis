# -*- coding: utf-8 -*-
"""通用工具函数。"""

import re


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
    """从京东商品详情链接中提取 SKU。"""
    match = re.search(r"item\.jd\.com/(\d+)\.html", link or "")
    return match.group(1) if match else ""


def normalize_column(values, target_length, fill_value=""):
    """把字段列表统一成相同长度，避免 DataFrame 创建失败。"""
    values = list(values)[:target_length]
    if len(values) < target_length:
        values.extend([fill_value] * (target_length - len(values)))
    return values


def sanitize_sheet_name(name, max_length=31):
    """清理 Excel 工作表名称。"""
    for char in r"[]:*?/\\":
        name = name.replace(char, "-")
    name = name.strip()[:max_length]
    return name or "Sheet"
