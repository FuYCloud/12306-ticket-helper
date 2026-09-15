#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChromeDriver 自动下载与更新工具
检测本机 Chrome 版本，从华为云镜像下载匹配的 ChromeDriver，
解压后覆盖到 asset/chromedriver.exe
"""

import os
import re
import sys
import shutil
import zipfile
import subprocess
import urllib.request
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(PROJECT_ROOT, "asset")
DRIVER_PATH = os.path.join(ASSET_DIR, "chromedriver.exe")

HW_MIRROR = "https://mirrors.huaweicloud.com/chromedriver"
CFT_LATEST_RELEASE = "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_{major}"
CFT_DOWNLOAD = "https://storage.googleapis.com/chrome-for-testing-public/{version}/win64/chromedriver-win64.zip"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def get_chrome_version():
    """
    通过 Windows 注册表获取本机 Chrome 版本号。
    返回如 '150.0.7871.187'，失败返回 None。
    """
    reg_paths = [
        (r"HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon", "version"),
        (r"HKEY_LOCAL_MACHINE\SOFTWARE\Google\Chrome\BLBeacon", "version"),
        (r"HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Google\Chrome\BLBeacon", "version"),
    ]
    for reg_path, value_name in reg_paths:
        try:
            result = subprocess.run(
                ["reg", "query", reg_path, "/v", value_name],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                match = re.search(r"REG_SZ\s+([\d.]+)", result.stdout)
                if match:
                    return match.group(1).strip()
        except Exception:
            continue
    return None


def get_matching_driver_version(chrome_version):
    """
    根据 Chrome 主版本号，查询 Chrome for Testing API 获取最新的驱动版本。
    返回如 '150.0.7871.46'，失败返回 None。
    """
    major = chrome_version.split(".")[0]
    url = CFT_LATEST_RELEASE.format(major=major)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            version = resp.read().decode("utf-8").strip()
        if version and version.startswith(major):
            return version
    except Exception as e:
        print(f"  查询 CfT API 失败: {e}")
    return None


def download_file(url, dest_path):
    """下载文件到指定路径，返回是否成功"""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(resp, f)
        return True
    except Exception as e:
        print(f"  下载失败: {e}")
        return False


def extract_chromedriver(zip_path, dest_dir):
    """
    从 zip 中提取 chromedriver.exe 到目标目录。
    华为云和 CfT 的 zip 结构略有不同，需要兼容。
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        target = None
        for name in names:
            if name.endswith("chromedriver.exe"):
                target = name
                break
        if not target:
            return False

        tmp_extract = tempfile.mkdtemp(prefix="chromedriver_")
        zf.extract(target, tmp_extract)
        extracted = os.path.join(tmp_extract, target)

        os.makedirs(dest_dir, exist_ok=True)

        dest_file = os.path.join(dest_dir, "chromedriver.exe")
        shutil.copy2(extracted, dest_file)

        shutil.rmtree(tmp_extract, ignore_errors=True)
        return True


def get_local_driver_version():
    """获取本地已有 chromedriver.exe 的版本，不存在返回 None"""
    if not os.path.exists(DRIVER_PATH):
        return None
    try:
        result = subprocess.run(
            [DRIVER_PATH, "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            match = re.search(r"ChromeDriver\s+([\d.]+)", result.stdout)
            if match:
                return match.group(1).strip()
    except Exception:
        pass
    return None


def main():
    print("=" * 50)
    print("  ChromeDriver 自动安装 / 更新工具")
    print("=" * 50)
    print()

    print("检测本机 Chrome 版本...")
    chrome_ver = get_chrome_version()
    if not chrome_ver:
        print("  ❌ 无法检测到 Chrome 版本，请确认已安装 Google Chrome。")
        print("     可手动到 https://googlechromelabs.github.io/chrome-for-testing/")
        print("     下载对应版本的 chromedriver.exe 放入 asset/ 目录。")
        return 1
    print(f"  本机 Chrome 版本: {chrome_ver}")

    print()
    print("检查本地 ChromeDriver...")
    local_ver = get_local_driver_version()
    if local_ver:
        local_major = local_ver.split(".")[0]
        chrome_major = chrome_ver.split(".")[0]
        if local_major == chrome_major:
            print(f"  本地驱动版本: {local_ver}，与 Chrome 大版本一致，无需更新。")
            return 0
        else:
            print(f"  本地驱动版本: {local_ver}，与 Chrome {chrome_major} 不匹配，需要更新。")
    else:
        print("  未检测到本地 chromedriver.exe，需要下载。")

    print()
    print("查询匹配的 ChromeDriver 版本...")
    driver_ver = get_matching_driver_version(chrome_ver)
    if not driver_ver:
        print("  ❌ 无法查询到匹配的驱动版本。")
        return 1
    print(f"  匹配的驱动版本: {driver_ver}")

    print()
    print("下载 ChromeDriver...")
    tmp_zip = os.path.join(tempfile.gettempdir(), "chromedriver_update.zip")

    hw_url = f"{HW_MIRROR}/{driver_ver}/chromedriver-win64.zip"
    print(f"  尝试华为云镜像: {hw_url}")
    downloaded = download_file(hw_url, tmp_zip)

    if not downloaded:
        print("  华为云镜像下载失败，尝试官方源...")
        cft_url = CFT_DOWNLOAD.format(version=driver_ver)
        print(f"  官方源: {cft_url}")
        downloaded = download_file(cft_url, tmp_zip)

    if not downloaded:
        print("  ❌ 下载失败，请检查网络连接。")
        return 1
    print("  下载完成。")

    print()
    print("解压并安装到 asset/ 目录...")
    if extract_chromedriver(tmp_zip, ASSET_DIR):
        print(f"  ✅ ChromeDriver 已更新到: {DRIVER_PATH}")
    else:
        print("  ❌ 解压失败，zip 中未找到 chromedriver.exe。")
        return 1

    try:
        os.remove(tmp_zip)
    except Exception:
        pass

    new_ver = get_local_driver_version()
    if new_ver:
        print(f"  当前驱动版本: {new_ver}")
        if new_ver.split(".")[0] == chrome_ver.split(".")[0]:
            print("  ✅ 版本匹配，安装成功。")
        else:
            print("  ⚠️ 版本可能不完全匹配，但主版本一致通常可用。")
    return 0


if __name__ == "__main__":
    sys.exit(main())