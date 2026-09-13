# 京东商品数据爬虫

基于 Python + DrissionPage 的京东商品数据采集项目。当前默认搜索关键词为“宠物玩具”，支持抓取京东搜索结果页的商品信息和商品评论，并提供 Excel 与 MySQL 两套存储流程，以及基于 ECharts 的 HTML 数据看板。

> 本项目仅供学习与数据分析练习使用。请合理控制访问频率，并遵守目标网站规则。

## 功能概览

- 自动打开京东搜索结果页，并点击“销量”排序。
- 首次扫码登录后保存浏览器用户数据，后续运行自动复用登录态。
- 启动时检测登录态，失效时提示重新扫码。
- 支持服务器无头模式运行。
- 抓取商品名称、价格、活动、店铺名称、销量和详情页链接。
- 从商品详情页进入评论区，按配置数量采集评论。
- 自动过滤空评论、“此用户未填写评价内容”等无效评论。
- 支持 Excel 文件输出和 MySQL 入库。
- 支持从历史 Excel 导入 MySQL。
- 可生成商品价格、销量、好评率、评论情感、关键词和评论长度等可视化看板。

## 项目结构

```text
JD_Spider/
├── README.md
├── jd_config.py                    # 全局配置
├── dashboard.html                  # 从 Excel 数据生成的历史看板（excel/generate_dashboard.py）
├── dashboard_new.html              # 从 Excel 数据生成的新版看板（dashboard.html 的更新版本）
├── dashboard_mysql.html            # 从 MySQL 数据库生成的历史看板（mysql/generate_dashboard_mysql.py）
├── crawler/                        # 爬虫核心模块
│   ├── __init__.py
│   ├── jd_browser.py               # 浏览器初始化、登录态检测、页面导航
│   ├── jd_product_extractor.py     # 搜索结果页商品信息提取
│   ├── jd_comment_crawler.py       # 商品详情页评论采集
│   └── jd_utils.py                 # URL、文本、SKU、工作表名等工具函数
├── excel/                          # Excel 存储方案
│   ├── __init__.py
│   ├── jd_main.py                  # 固定关键词入口
│   ├── jd_search.py                # 交互式关键词入口
│   ├── jd_excel_writer.py          # Excel 写入
│   ├── generate_dashboard.py       # 从 Excel 生成看板
│   └── dashboard.html              # Excel 看板默认输出
├── mysql/                          # MySQL 存储方案
│   ├── __init__.py
│   ├── jd_main_mysql.py            # 固定关键词入口
│   ├── jd_search_mysql.py          # 交互式关键词入口
│   ├── store_to_mysql.py           # 建库建表、入库、查询、Excel 导入
│   └── generate_dashboard_mysql.py # 从 MySQL 生成看板
├── legacy/                         # 原始脚本备份
│   ├── __init__.py
│   ├── 爬取京东数据.py
│   └── 爬取京东数据优化版.py
└── 样例图片/
    ├── 商品总览.png
    └── 商品评论.png
```

运行后还会生成 `jd_user_data/` 浏览器用户数据目录，以及 Python 的 `__pycache__/` 缓存目录。这些都属于运行产物。

## 环境要求

- Python 3.10 或更高版本。
- 本地需要安装 Chrome 或 Chromium。
- 使用 MySQL 方案时，需要可用的 MySQL 服务。

安装依赖：

```bash
pip install DrissionPage pandas openpyxl pymysql
```

| 依赖 | 用途 |
| --- | --- |
| DrissionPage | 浏览器自动化、页面元素定位和操作 |
| pandas | 数据处理、Excel 读取 |
| openpyxl | Excel 写入引擎 |
| pymysql | MySQL 数据库连接 |

## 配置说明

主要配置集中在 `jd_config.py`：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `URL` | 京东“宠物玩具”搜索结果页 | 固定关键词入口使用的搜索 URL |
| `OUTPUT_PATH` | `D:\jd_result.xlsx` | Excel 输出路径 |
| `MAX_PRODUCTS` | `4` | 每次抓取的商品数量 |
| `MAX_COMMENTS_PER_PRODUCT` | `20` | 每个商品最多抓取的评论数 |
| `MIN_COMMENT_LENGTH` | `5` | 评论最小有效长度 |
| `TIMEOUT` | `15` | 常规等待超时时间，单位秒 |
| `SHORT_TIMEOUT` | `5` | 短等待超时时间，单位秒 |
| `SCROLL_RETRIES` | `5` | 评论滚动加载重试次数 |
| `USER_DATA_PATH` | `./jd_user_data` | 浏览器登录态保存目录 |
| `HEADLESS` | `False` | 是否启用无头浏览器 |

京东页面结构变化时，优先检查 `jd_config.py` 中的 `*_SELECTORS` 选择器列表。代码会按列表顺序尝试，匹配到可用元素后继续执行。

## 快速开始

所有命令建议在项目根目录执行：

```bash
cd E:\JD_Spider
```

### 首次登录

首次运行任意爬虫入口时，程序会打开浏览器并检测京东登录态。如果未登录，会提示在浏览器中扫码登录。

```bash
python excel/jd_main.py
```

扫码完成后回到终端按回车。登录成功后，Cookie 和 Session 会保存在 `jd_user_data/`，后续运行会自动复用。

### 方案一：输出 Excel

固定使用 `jd_config.py` 中的默认搜索 URL：

```bash
python excel/jd_main.py
```

交互式输入搜索关键词：

```bash
python excel/jd_search.py
```

默认输出文件为：

```text
D:\jd_result.xlsx
```

Excel 中包含 `商品总览` 工作表，以及按商品拆分的评论工作表。

### 方案二：写入 MySQL

固定使用 `jd_config.py` 中的默认搜索 URL：

```bash
python mysql/jd_main_mysql.py
```

交互式输入搜索关键词：

```bash
python mysql/jd_search_mysql.py
```

默认数据库配置位于 `mysql/store_to_mysql.py` 的 `DB_CONFIG`：

| 配置项 | 默认值 |
| --- | --- |
| host | localhost |
| port | 3306 |
| user | root |
| password | （空，建议用 `--password` 参数传入，避免明文泄露） |
| database | jd_spider |
| charset | utf8mb4 |

### 从 Excel 导入 MySQL

默认导入 `D:\jd_result.xlsx`：

```bash
python mysql/store_to_mysql.py
```

指定 Excel 文件：

```bash
python mysql/store_to_mysql.py D:\jd_result.xlsx
```

覆盖数据库连接参数：

```bash
python mysql/store_to_mysql.py D:\jd_result.xlsx --host 192.168.1.100 --port 3306 --user admin --password yourpass --database jd_spider
```

## 生成可视化看板

### 从 Excel 生成

使用默认 Excel 路径 `D:\jd_result.xlsx`：

```bash
python excel/generate_dashboard.py
```

指定 Excel 文件：

```bash
python excel/generate_dashboard.py D:\jd_result.xlsx
```

默认输出：

```text
excel/dashboard.html
```

### 从 MySQL 生成

使用默认数据库配置：

```bash
python mysql/generate_dashboard_mysql.py
```

默认输出：

```text
mysql/dashboard.html
```

指定输出文件：

```bash
python mysql/generate_dashboard_mysql.py --output dashboard_mysql.html
```

覆盖数据库连接参数：

```bash
python mysql/generate_dashboard_mysql.py --host 192.168.1.100 --port 3306 --user admin --password yourpass --database jd_spider --output dashboard_mysql.html
```

看板包含以下内容：

- 商品数量、评论数量、平均好评率、平均评论长度。
- 商品价格对比。
- 销量与好评率对比。
- 评论情感分布。
- 评论长度分布。
- 全局和分商品热门关键词。
- 商品明细表。

## 示例截图

项目包含两张样例图片：

![商品总览](样例图片/商品总览.png)

![商品评论](样例图片/商品评论.png)

## MySQL 表结构

程序会自动创建数据库和表。

### `products` 商品总览表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | INT, PK, AUTO_INCREMENT | 主键 |
| product_name | VARCHAR(255) | 商品名称 |
| price | VARCHAR(50) | 价格 |
| promotion | VARCHAR(500) | 活动或促销信息 |
| store_name | VARCHAR(255) | 店铺名称 |
| sales_text | VARCHAR(100) | 销量原文 |
| sales_num | INT | 解析后的销量数值 |
| good_rate | INT | 好评率百分比 |
| detail_link | VARCHAR(500) | 商品详情链接 |
| crawl_time | DATETIME | 采集时间 |

### `comments` 评论表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | INT, PK, AUTO_INCREMENT | 主键 |
| product_id | INT | 关联 `products.id` |
| product_name | VARCHAR(255) | 商品名称冗余字段 |
| comment_text | TEXT | 评论原文 |
| sentiment | ENUM | `positive`、`neutral`、`negative` |
| pos_score | INT | 正面词命中数 |
| neg_score | INT | 负面词命中数 |
| comment_length | INT | 评论字数 |
| crawl_time | DATETIME | 采集时间 |

## 情感分析

项目使用简单词典匹配法进行中文评论情感分析：

- 正面词命中数大于负面词命中数，标记为 `positive`。
- 负面词命中数大于正面词命中数，标记为 `negative`。
- 两者相等，标记为 `neutral`。

Excel 看板中的词典位于 `excel/generate_dashboard.py`。MySQL 入库时使用的词典位于 `mysql/store_to_mysql.py`。

## 服务器部署

服务器通常无法直接扫码登录，推荐先在本地生成登录态，再上传到服务器。

1. 本地运行一次并扫码登录：

```bash
python excel/jd_main.py
```

2. 将 `jd_user_data/` 上传到服务器项目根目录。

```bash
tar -czf jd_user_data.tar.gz jd_user_data/
scp jd_user_data.tar.gz user@your-server:/path/to/JD_Spider/
```

3. 在服务器解压：

```bash
cd /path/to/JD_Spider
tar -xzf jd_user_data.tar.gz
```

4. 修改 `jd_config.py`：

```python
HEADLESS = True
```

5. 运行爬虫：

```bash
python excel/jd_main.py
```

如果登录态失效，需要在本地重新扫码并重新上传 `jd_user_data/`。

## 常见问题

### PowerShell 查看 README 出现乱码

README 使用 UTF-8 编码。PowerShell 读取时建议显式指定编码：

```powershell
Get-Content README.md -Encoding UTF8
```

### 没有抓到商品

优先检查：

- 是否已经成功登录京东。
- 京东页面是否出现验证码或风控提示。
- `jd_config.py` 中的商品卡片、名称、价格等 CSS 选择器是否仍然有效。
- `MAX_PRODUCTS` 是否设置过大导致加载不稳定。

### 没有抓到评论

优先检查：

- 商品详情页链接是否为 `https://item.jd.com/数字.html` 格式。
- 评论入口选择器是否变化。
- 是否被京东要求重新登录或验证。
- `MAX_COMMENTS_PER_PRODUCT` 和 `SCROLL_RETRIES` 是否设置合理。

### MySQL 连接失败

检查：

- MySQL 服务是否已启动。
- 用户名、密码、端口和数据库权限是否正确。
- 远程连接时 MySQL 是否允许外部访问。
- 防火墙或安全组是否放行 3306 端口。

## 注意事项

- 京东页面结构和反爬策略可能变化，脚本失效时优先更新选择器。
- 不建议大批量、高频率采集，避免触发风控。
- Excel 与 MySQL 两套入口互相独立，可以按需要选择其一。
- `legacy/` 目录仅作为原始脚本备份，日常建议使用 `excel/` 或 `mysql/` 下的模块化入口。
- 运行产物如 `jd_user_data/`、`__pycache__/`、生成的 HTML 看板和 Excel 文件，可按需要加入 `.gitignore`。
