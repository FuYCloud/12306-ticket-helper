# utils/cookie_manager.py
"""
扫码记录管理：保存、加载、列出、删除 12306 登录 Cookie。
每条记录包含：账号名称、保存时间、Cookie 列表。
"""

import os
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
COOKIE_FILE = os.path.join(DATA_DIR, "cookies.json")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_all():
    """加载所有记录，返回列表"""
    _ensure_dir()
    if not os.path.exists(COOKIE_FILE):
        return []
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_all(records):
    """保存所有记录"""
    _ensure_dir()
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def list_records():
    """列出所有记录，按最近使用时间降序"""
    records = _load_all()
    records.sort(key=lambda r: r.get("last_used", 0), reverse=True)
    return records


def save_record(account_name, cookies):
    """
    保存/覆盖一条记录。
    如果 account_name 已存在，则覆盖其 cookie 和 last_used；
    否则新增一条。
    """
    records = _load_all()
    now = time.time()

    for rec in records:
        if rec.get("account") == account_name:
            rec["cookies"] = cookies
            rec["last_used"] = now
            rec["saved_at"] = now
            _save_all(records)
            return "updated"

    records.append({
        "account": account_name,
        "cookies": cookies,
        "saved_at": now,
        "last_used": now,
    })
    _save_all(records)
    return "created"


def touch_record(account_name):
    """更新某条记录的 last_used 时间"""
    records = _load_all()
    now = time.time()
    for rec in records:
        if rec.get("account") == account_name:
            rec["last_used"] = now
            _save_all(records)
            return True
    return False


def get_record(account_name):
    """按账号名获取一条记录"""
    for rec in _load_all():
        if rec.get("account") == account_name:
            return rec
    return None


def delete_record(account_name):
    """删除一条记录"""
    records = _load_all()
    new_records = [r for r in records if r.get("account") != account_name]
    if len(new_records) == len(records):
        return False
    _save_all(new_records)
    return True