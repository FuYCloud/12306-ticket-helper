#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
12306 车站 Cookie 值获取工具
输入车站中文名，自动从 12306 获取对应的 cookie 值并复制到剪贴板
支持连续查询与模糊搜索：输入 1 继续，输入 2 退出
"""

import sys
import os
import re
import urllib.request

try:
    import pyperclip
except ImportError:
    print("错误：缺少 pyperclip 模块。")
    print("请先运行：python -m pip install pyperclip")
    sys.exit(1)

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "station_name.js.cache")
STATION_URL = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"

MAX_DISPLAY = 30


def download_station_data():
    """下载车站数据，失败时使用缓存"""
    try:
        print("正在从 12306 获取车站数据...")
        req = urllib.request.Request(
            STATION_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(data)
        return data
    except Exception as e:
        print(f"下载失败：{e}")
        if os.path.exists(CACHE_FILE):
            print("使用本地缓存数据...")
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return f.read()
        else:
            print("错误：无法获取车站数据，且没有本地缓存。")
            print("请检查网络连接后重试。")
            sys.exit(1)


def parse_stations(js_text):
    """
    解析 station_name.js 内容
    格式：@bjb|北京北|VAP|beijingbei|bjb|0|0357|北京|||
    返回 {中文名: 电报码}
    """
    match = re.search(r"station_names\s*=\s*'(.*)'", js_text, re.S)
    if not match:
        print("错误：无法解析车站数据格式。")
        sys.exit(1)
    raw = match.group(1)
    stations = {}
    for item in raw.split("@"):
        if not item:
            continue
        parts = item.split("|")
        if len(parts) < 3:
            continue
        name = parts[1].strip()
        telecode = parts[2].strip()
        if name and telecode:
            stations[name] = telecode
    return stations


def chinese_to_unicode_escape(text):
    """将中文转换为 %uXXXX 格式（大写）"""
    result = []
    for ch in text:
        if ord(ch) > 127:
            result.append("%u{:04X}".format(ord(ch)))
        else:
            result.append(ch)
    return "".join(result)


def output_cookie(station_name, telecode):
    """生成 cookie、打印信息并复制到剪贴板"""
    unicode_part = chinese_to_unicode_escape(station_name)
    cookie_value = f"{unicode_part}%2C{telecode}"

    print(f"\n车站：{station_name}")
    print(f"电报码：{telecode}")
    print(f"Cookie 值：{cookie_value}")

    try:
        pyperclip.copy(cookie_value)
        print("✅ Cookie 值已复制到剪贴板！")
    except Exception as e:
        print(f"⚠️ 复制到剪贴板失败：{e}")
        print("请手动复制上面的 Cookie 值。")


def sort_matches(matches, keyword):
    """
    按相关性排序：
    1. 以关键词开头的优先（如输入“杭”，“杭州东”排在“上杭”前面）
    2. 名称短的优先（短名通常是主站，如“杭州”在“杭州东”前）
    3. 字典序
    """
    def sort_key(name):
        is_prefix = 0 if name.startswith(keyword) else 1
        return (is_prefix, len(name), name)
    return sorted(matches, key=sort_key)


def pick_from_matches(matches, stations, keyword):
    """
    列出模糊匹配结果，让用户按编号选择。
    返回选中的车站名，或 None 表示放弃。
    """
    matches = sort_matches(matches, keyword)

    if len(matches) > MAX_DISPLAY:
        total = len(matches)
        print(f"\n未找到精确匹配，共找到 {total} 个相关车站，"
              f"仅显示前 {MAX_DISPLAY} 个（按相关度排序）：")
        matches = matches[:MAX_DISPLAY]
        truncated = True
    else:
        print(f"\n未找到精确匹配，共找到 {len(matches)} 个相关车站"
              f"（按相关度排序）：")
        truncated = False

    for idx, name in enumerate(matches, 1):
        print(f"  {idx:>3}. {name}  ({stations[name]})")

    if truncated:
        print(f"\n提示：结果较多，输入更完整的关键词（如“上海”而非“上”）可缩小范围。")

    print("\n输入编号选择，直接回车放弃本次查询：")
    choice = input("> ").strip()
    if not choice:
        return None
    if not choice.isdigit():
        print("无效输入，放弃本次查询。")
        return None
    idx = int(choice)
    if idx < 1 or idx > len(matches):
        print("编号超出范围，放弃本次查询。")
        return None
    return matches[idx - 1]


def query_once(stations):
    """执行一次查询"""
    station_name = input("请输入车站中文名：").strip()

    if not station_name:
        print("错误：车站名不能为空。\n")
        return

    search_name = station_name
    if search_name.endswith("站"):
        search_name = search_name[:-1]

    if search_name in stations:
        output_cookie(search_name, stations[search_name])
        return

    matches = [name for name in stations if search_name in name]
    if not matches:
        print(f"未找到与“{station_name}”相关的车站。\n")
        return

    picked = pick_from_matches(matches, stations, search_name)
    if picked is None:
        print("已取消本次查询。\n")
        return

    output_cookie(picked, stations[picked])


def ask_continue():
    """询问是否继续查询"""
    while True:
        choice = input("\n输入 1 继续查询，输入 2 退出脚本：").strip()
        if choice == "1":
            print()
            return True
        elif choice == "2":
            return False
        else:
            print("无效输入，请输入 1 或 2。")


def main():
    js_text = download_station_data()
    stations = parse_stations(js_text)
    print(f"已加载 {len(stations)} 个车站。\n")

    while True:
        query_once(stations)
        if not ask_continue():
            print("已退出。")
            break


if __name__ == "__main__":
    main()