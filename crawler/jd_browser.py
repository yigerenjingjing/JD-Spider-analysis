# -*- coding: utf-8 -*-
"""浏览器初始化、登录态持久化、页面导航。"""

import sys

from DrissionPage import Chromium, ChromiumOptions

import jd_config


def _create_options():
    co = ChromiumOptions()
    co.set_user_data_path(jd_config.USER_DATA_PATH)

    if jd_config.HEADLESS:
        co.set_argument("--headless=new")
        co.set_argument("--no-sandbox")
        co.set_argument("--disable-gpu")
        co.set_argument("--disable-dev-shm-usage")

    return co


def _check_login(tab):
    """访问需登录的订单页，若被重定向到登录页则说明 session 失效。"""
    print("[系统] 正在检测京东登录态...", flush=True)
    try:
        tab.get(jd_config.SESSION_CHECK_URL)
        tab.wait.load_start()
        current_url = tab.url.lower()
        if "login" in current_url or "passport" in current_url:
            return False
        return True
    except Exception:
        return False


def _ensure_login(tab):
    """确保已登录。若未登录，提示扫码并阻塞等待人工操作。"""
    if _check_login(tab):
        print("[系统] 已恢复京东登录状态，无需重复登录。", flush=True)
        return

    print("", flush=True)
    print("=" * 60, flush=True)
    print("  [警告] 京东登录态已过期或首次使用，需要扫码登录。", flush=True)
    print("  请在浏览器中完成登录后，回到终端按回车继续...", flush=True)
    print("=" * 60, flush=True)

    # 打开京东首页供扫码
    tab.get("https://www.jd.com/")
    tab.wait.load_start()

    try:
        input()
    except (EOFError, KeyboardInterrupt):
        print("\n[系统] 用户取消，程序退出。", flush=True)
        sys.exit(0)

    if _check_login(tab):
        print("[系统] 登录成功！后续运行将自动恢复登录态。", flush=True)
    else:
        print("[警告] 仍未检测到登录态，继续尝试运行（可能部分功能不可用）。", flush=True)


def initialize_list_browser():
    """初始化浏览器、检测/恢复登录态、打开搜索列表页并点击销量排序。"""
    print("\n[系统] 正在初始化浏览器...", flush=True)
    dp = Chromium(_create_options())
    tab = dp.new_tab()

    _ensure_login(tab)

    print("[系统] 正在打开搜索列表页...", flush=True)
    tab.get(jd_config.URL)
    tab.wait.load_start()

    print("[系统] 正在等待并点击销量排序...", flush=True)
    tab.wait.ele_displayed("text:销量", timeout=jd_config.TIMEOUT)
    tab.ele("text:销量").click()
    tab.wait.ele_displayed(jd_config.NAME_SELECTORS[0], timeout=jd_config.TIMEOUT)

    print("[系统] 浏览器初始化完成，已进入商品列表页。", flush=True)
    return dp, tab


def create_product_tab(dp):
    """创建可复用的商品工作标签页。"""
    return dp.new_tab()
