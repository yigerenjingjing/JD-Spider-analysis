# -*- coding: utf-8 -*-
"""京东爬虫 MySQL 数据库存储与读取。

用法:
    # 从爬虫脚本直接调用
    from store_to_mysql import store_to_database, load_all_data
    store_to_database(products, comments_data)

    # 从 Excel 导入历史数据
    python store_to_mysql.py D:\jd_result.xlsx
    python store_to_mysql.py D:\jd_result.xlsx --host 192.168.1.100 --password xxx
"""

import argparse
import os
import re
import sys
from datetime import datetime

import pymysql

# ═══════════════════════════════════════════════════════════
# 默认数据库配置
# ═══════════════════════════════════════════════════════════

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",  # 不要在这里写明文密码，请用 --password 参数传入
    "database": "jd_spider",
    "charset": "utf8mb4",
}

# ═══════════════════════════════════════════════════════════
# 简易情感词典
# ═══════════════════════════════════════════════════════════

POSITIVE_WORDS = {
    "好", "棒", "满意", "喜欢", "推荐", "不错", "赞", "超赞", "完美", "优秀",
    "给力", "好评", "耐用", "结实", "厚实", "稳固", "方便", "舒服", "舒适",
    "安全", "开心", "迅速", "很快", "靠谱", "信赖", "回购", "划算", "超值",
    "惊喜", "漂亮", "可爱", "精细", "放心", "贴心", "爱不释手", "一流",
    "高品质", "省心", "物美价廉", "性价比高", "值得", "必备", "神器",
    "不占地", "良心", "到位", "周到", "及时", "好看", "整洁", "干净",
    "温和", "柔软", "有弹性", "尽情", "挺好", "非常好", "很棒", "便宜",
    "物超所值", "棒棒哒", "不贵", "给力",
}

NEGATIVE_WORDS = {
    "差", "不好", "失望", "垃圾", "坑", "差劲", "烂", "糟糕", "坏",
    "异味", "气味", "味道大", "臭", "难闻", "刺鼻",
    "掉屑", "飞渣", "掉渣", "坏了", "破损", "损坏", "烂了",
    "不值", "贵", "稍贵", "不太", "不推荐", "后悔", "退", "换货",
    "问题", "缺陷", "缺点", "瑕疵", "不足", "有点大", "太小",
    "不喜欢", "不爱", "没兴趣", "不玩", "不怎么", "不怎么样",
    "差评", "不好用", "不耐用", "容易坏", "很快坏", "质量差",
    "失望", "闹心", "糟心", "差很多",
}


def analyze_sentiment(text):
    pos = sum(text.count(w) for w in POSITIVE_WORDS)
    neg = sum(text.count(w) for w in NEGATIVE_WORDS)
    if pos > neg:
        return "positive", pos, neg
    if neg > pos:
        return "negative", pos, neg
    return "neutral", pos, neg


# ═══════════════════════════════════════════════════════════
# SQL 建表语句
# ═══════════════════════════════════════════════════════════

CREATE_DATABASE_SQL = (
    "CREATE DATABASE IF NOT EXISTS {db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
)

CREATE_PRODUCTS_TABLE = """
CREATE TABLE IF NOT EXISTS products (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    product_name    VARCHAR(255)    NOT NULL COMMENT '商品名称',
    price           VARCHAR(50)     DEFAULT '' COMMENT '价格',
    promotion       VARCHAR(500)    DEFAULT '' COMMENT '促销信息',
    store_name      VARCHAR(255)    DEFAULT '' COMMENT '店铺名称',
    sales_text      VARCHAR(100)    DEFAULT '' COMMENT '销量原文',
    sales_num       INT             DEFAULT 0 COMMENT '销量数值',
    good_rate       INT             DEFAULT 0 COMMENT '好评率(%)',
    detail_link     VARCHAR(500)    DEFAULT '' COMMENT '详情链接',
    crawl_time      DATETIME        NOT NULL COMMENT '爬取时间',
    INDEX idx_product_name (product_name),
    INDEX idx_crawl_time (crawl_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商品总览表';
"""

CREATE_COMMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS comments (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    product_id      INT             NOT NULL COMMENT '关联 products.id',
    product_name    VARCHAR(255)    DEFAULT '' COMMENT '商品名称(冗余)',
    comment_text    TEXT            NOT NULL COMMENT '评论原文',
    sentiment       ENUM('positive','neutral','negative') DEFAULT 'neutral' COMMENT '情感标签',
    pos_score       INT             DEFAULT 0 COMMENT '正面词命中数',
    neg_score       INT             DEFAULT 0 COMMENT '负面词命中数',
    comment_length  INT             DEFAULT 0 COMMENT '评论字数',
    crawl_time      DATETIME        NOT NULL COMMENT '爬取时间',
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    INDEX idx_product_id (product_id),
    INDEX idx_sentiment (sentiment),
    INDEX idx_crawl_time (crawl_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商品评论表';
"""


# ═══════════════════════════════════════════════════════════
# 数据库操作类
# ═══════════════════════════════════════════════════════════

class JDSpiderDB:
    """京东爬虫数据库管理。"""

    def __init__(self, config=None):
        self.config = {**DB_CONFIG, **(config or {})}
        self.conn = None

    def connect(self):
        self.conn = pymysql.connect(
            host=self.config["host"],
            port=self.config["port"],
            user=self.config["user"],
            password=self.config["password"],
            charset=self.config["charset"],
        )
        db = self.config["database"]
        with self.conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cur.execute(f"USE `{db}`")
        self.conn.commit()
        print(f"[数据库] 已连接到 {self.config['host']}:{self.config['port']}/{db}", flush=True)
        return self

    def init_schema(self):
        with self.conn.cursor() as cur:
            cur.execute(CREATE_PRODUCTS_TABLE)
            cur.execute(CREATE_COMMENTS_TABLE)
        self.conn.commit()
        print(f"[数据库] 表结构已就绪", flush=True)

    def insert_products(self, products, crawl_time):
        """批量插入商品，返回按插入顺序排列的 product_id 列表。"""
        sql = """INSERT INTO products (product_name, price, promotion, store_name, sales_text, sales_num, good_rate, detail_link, crawl_time)
                 VALUES (%(product_name)s, %(price)s, %(promotion)s, %(store_name)s, %(sales_text)s, %(sales_num)s, %(good_rate)s, %(detail_link)s, %(crawl_time)s)"""
        ids = []
        with self.conn.cursor() as cur:
            for p in products:
                p["crawl_time"] = crawl_time
                cur.execute(sql, p)
                ids.append(cur.lastrowid)
        self.conn.commit()
        print(f"[数据库] 已插入 {len(ids)} 条商品记录", flush=True)
        return ids

    def insert_comments(self, comments_data, product_ids, crawl_time):
        """批量插入评论（含情感分析）。按索引位置匹配商品与评论组。"""
        sql = """INSERT INTO comments (product_id, product_name, comment_text, sentiment, pos_score, neg_score, comment_length, crawl_time)
                 VALUES (%(product_id)s, %(product_name)s, %(comment_text)s, %(sentiment)s, %(pos_score)s, %(neg_score)s, %(comment_length)s, %(crawl_time)s)"""
        total = 0
        with self.conn.cursor() as cur:
            for idx, item in enumerate(comments_data):
                if idx >= len(product_ids):
                    print(f"[警告] 评论组 #{idx} 超出商品数，跳过", flush=True)
                    break
                product_id = product_ids[idx]
                product_name = item.get("product_name", item.get("product", ""))
                comments = item.get("comments", item.get("comment_list", []))
                for text in comments:
                    sentiment, pos, neg = analyze_sentiment(text)
                    cur.execute(sql, {
                        "product_id": product_id,
                        "product_name": product_name,
                        "comment_text": text,
                        "sentiment": sentiment,
                        "pos_score": pos,
                        "neg_score": neg,
                        "comment_length": len(text),
                        "crawl_time": crawl_time,
                    })
                    total += 1
        self.conn.commit()
        print(f"[数据库] 已插入 {total} 条评论记录", flush=True)
        return total

    def load_products(self, limit=None):
        """从数据库读取商品列表。"""
        sql = "SELECT * FROM products ORDER BY id DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql)
            return cur.fetchall()

    def load_comments(self, product_id=None):
        """从数据库读取评论。"""
        if product_id:
            sql = "SELECT * FROM comments WHERE product_id = %s ORDER BY id"
            with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql, (product_id,))
                return cur.fetchall()
        sql = "SELECT * FROM comments ORDER BY id"
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql)
            return cur.fetchall()

    def load_latest_crawl_time(self):
        """获取最近一次爬取的时间。"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT MAX(crawl_time) FROM products")
            row = cur.fetchone()
            return row[0] if row else None

    def stats(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM products")
            p_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM comments")
            c_count = cur.fetchone()[0]
            cur.execute("SELECT sentiment, COUNT(*) FROM comments GROUP BY sentiment ORDER BY sentiment")
            sent = dict(cur.fetchall())
            print(f"\n{'='*50}")
            print(f"  数据库 `{self.config['database']}` 统计")
            print(f"  {'='*50}")
            print(f"  商品总数:  {p_count}")
            print(f"  评论总数:  {c_count}")
            print(f"  正面评论:  {sent.get('positive', 0)}")
            print(f"  中性评论:  {sent.get('neutral', 0)}")
            print(f"  负面评论:  {sent.get('negative', 0)}")
            print(f"  {'='*50}\n", flush=True)

    def close(self):
        if self.conn:
            self.conn.close()
            print("[数据库] 连接已关闭", flush=True)


# ═══════════════════════════════════════════════════════════
# 高层 API：爬虫直接调用
# ═══════════════════════════════════════════════════════════

def store_to_database(products, comments_data, config=None):
    """爬虫脚本直接调用：将商品和评论存入 MySQL。

    Args:
        products: 商品列表，每个元素为 dict，字段:
            product_name, price, promotion, store_name, sales_text, detail_link
        comments_data: 评论数据，每个元素为 dict，字段:
            product (商品名), comments (评论文本列表)
        config: 数据库配置覆盖项
    """
    # 解析销量并统一字段名
    for p in products:
        sales_text = str(p.get("sales_text", p.get("销量", "")))
        p.setdefault("product_name", p.get("product_name", p.get("商品名称", "")))
        p.setdefault("sales_text", sales_text)
        p.setdefault("sales_num", _parse_sales_num(sales_text))
        p.setdefault("good_rate", _parse_good_rate(sales_text))
        p.setdefault("price", p.get("price", p.get("价格", "")))
        p.setdefault("promotion", p.get("promotion", p.get("活动", "")))
        p.setdefault("store_name", p.get("store_name", p.get("店铺名称", "")))
        p.setdefault("detail_link", p.get("detail_link", p.get("详情链接", "")))

    # 规范化 comments_data
    normalized_comments = []
    for item in comments_data:
        if isinstance(item, tuple):
            product_dict, comment_list = item
            normalized_comments.append({
                "product_name": product_dict.get("product_name", product_dict.get("商品名称", "")),
                "comments": comment_list,
            })
        elif isinstance(item, dict):
            name = item.get("product_name", item.get("商品名称", item.get("product", "")))
            comments = item.get("comments", item.get("comment_list", []))
            normalized_comments.append({"product_name": name, "comments": comments})
        else:
            normalized_comments.append(item)

    crawl_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db = JDSpiderDB(config)
    try:
        db.connect()
        db.init_schema()
        ids = db.insert_products(products, crawl_time)
        db.insert_comments(normalized_comments, ids, crawl_time)
        db.stats()
    finally:
        db.close()


def load_all_data(config=None):
    """从数据库读取最新一批爬取数据，返回 (products, comments_data)。"""
    db = JDSpiderDB(config)
    try:
        db.connect()
        products = db.load_products()
        if not products:
            return [], []

        comments_data = []
        for p in products:
            comments = db.load_comments(p["id"])
            comments_data.append({
                "product_name": p["product_name"],
                "product_id": p["id"],
                "comments": [c["comment_text"] for c in comments],
                "sentiments": [c["sentiment"] for c in comments],
            })
        return products, comments_data
    finally:
        db.close()


def _parse_sales_num(text):
    m = re.search(r"已售(\d+)万", str(text))
    if m:
        return int(m.group(1)) * 10000
    m = re.search(r"已售(\d+)\+", str(text))
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)万\+", str(text))
    return int(m.group(1)) * 10000 if m else 0


def _parse_good_rate(text):
    m = re.search(r"(\d+)%好评", str(text))
    return int(m.group(1)) if m else 0


# ═══════════════════════════════════════════════════════════
# CLI：从 Excel 导入历史数据
# ═══════════════════════════════════════════════════════════

def _load_excel(excel_path):
    import pandas as pd
    xls = pd.ExcelFile(excel_path)
    overview = pd.read_excel(xls, sheet_name="商品总览")

    products = []
    for _, row in overview.iterrows():
        products.append({
            "product_name": str(row.get("商品名称", "")),
            "price": str(row.get("价格", "")),
            "promotion": str(row.get("活动", "")),
            "store_name": str(row.get("店铺名称", "")),
            "sales_text": str(row.get("销量", "")),
            "detail_link": "",
        })

    comments_data = []
    for sheet in xls.sheet_names[1:]:
        df = pd.read_excel(xls, sheet_name=sheet)
        comments_data.append({
            "product_name": sheet,
            "comments": df.iloc[:, 0].dropna().tolist(),
        })

    return products, comments_data


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="将京东爬虫 Excel 导入 MySQL")
    parser.add_argument("excel", nargs="?", default=r"D:\jd_result.xlsx", help="Excel 文件路径")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--database", default=None)
    args = parser.parse_args()

    config = {}
    for key in ("host", "port", "user", "password", "database"):
        if getattr(args, key) is not None:
            config[key] = getattr(args, key)

    if not os.path.exists(args.excel):
        print(f"[错误] 找不到 Excel 文件: {args.excel}", flush=True)
        sys.exit(1)

    print(f"[系统] 读取 Excel: {args.excel}", flush=True)
    products, comments_data = _load_excel(args.excel)
    print(f"[系统] 解析到 {len(products)} 个商品, {len(comments_data)} 组评论", flush=True)

    store_to_database(products, comments_data, config)


if __name__ == "__main__":
    main()
