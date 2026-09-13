# -*- coding: utf-8 -*-
"""京东爬虫配置。"""

URL = "https://search.jd.com/Search?keyword=%E5%AE%A0%E7%89%A9%E7%8E%A9%E5%85%B7&enc=utf-8&wq=%E5%AE%A0%E7%89%A9wan%27jv&pvid=a31833d4f6ba4a038b51e97e9aa91ab7"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
}

OUTPUT_PATH = r"D:\jd_result.xlsx"

MAX_PRODUCTS = 4
MAX_COMMENTS_PER_PRODUCT = 20
TIMEOUT = 15
SHORT_TIMEOUT = 5
SCROLL_RETRIES = 5
MIN_COMMENT_LENGTH = 5

# ── 浏览器持久化 & 登录态 ──
USER_DATA_PATH = "./jd_user_data"
SESSION_CHECK_URL = "https://order.jd.com/center/list.action"

# ── 无头模式（服务器部署时启用） ──
HEADLESS = False

CARD_SELECTORS = [
    "css:li.gl-item",
    "css:.gl-item",
    "css:[data-sku]",
    "css:[class*=\"_goods_item_\"]",
]

NAME_SELECTORS = [
    "css:._text_1x4i2_30",
    "css:.p-name em",
    "css:.p-name a",
    "css:[class*=\"_text_\"]",
]

PRICE_SELECTORS = [
    "css:._price_1tn4o_13",
    "css:.p-price i",
    "css:.p-price",
    "css:[class*=\"_price_\"]",
]

PROMOTION_SELECTORS = [
    "css:._tags_hzhkm_2",
    "css:.p-icons",
    "css:[class*=\"_tags_\"]",
]

STORE_SELECTORS = [
    "css:._name_d19t5_35",
    "css:.p-shop a",
    "css:.p-shop",
    "css:[class*=\"_name_\"]",
]

SALES_SELECTORS = [
    "css:._goods_volume_1xkku_1",
    "css:.p-commit",
    "css:[class*=\"_goods_volume_\"]",
]

ALL_COMMENT_BUTTON_SELECTORS = [
    "css:.all-btn",
    "text:全部评价",
    "css:#comment",
]

COMMENT_TEXT_SELECTORS = [
    "css:.jdc-pc-rate-card-main-desc",
    "css:.comment-con",
    "css:[class*=\"rate-card-main-desc\"]",
]

INVALID_COMMENT = "此用户未填写评价内容"

# ── 限速配置（防止 IP 被封） ──
CRAWL_DELAY_MIN = 2.0       # 每个商品之间最小等待秒数
CRAWL_DELAY_MAX = 5.0       # 每个商品之间最大等待秒数
COMMENT_SCROLL_DELAY = 1.0  # 评论滚动加载等待秒数（原 0.5s）
PAGE_LOAD_DELAY = 1.0       # 页面加载后额外等待秒数
