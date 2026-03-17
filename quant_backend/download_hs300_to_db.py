#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将沪深300股票的日线、5分钟线和股票名称先下载到本地，再写入 GraduationProject 的 MySQL 数据库。

设计目标
--------
1. 兼容现有 Django 项目表结构：
   - stocks.StockBasicInfo
   - stocks.StockData
   - stocks.StockMinuteData
2. 先落本地 CSV，再上传数据库
3. 支持断点续传（下载 / 上传分阶段状态落盘）
4. 支持进度条（tqdm）
5. 代码格式沿用项目里已有的 `sh.600000` / `sz.000001`

默认数据源
----------
使用 baostock：
- 可直接拿到沪深300成分股
- 可下载日线
- 可下载 5 分钟线
- 不需要单独 token

注意
----
1. 5 分钟线数据量很大，默认按“月”拆文件，并按月上传，方便断点续传。
2. 这版脚本按项目当前模型字段写入：
   - 日线表: stock_data_daily
   - 分钟表: stock_data_minute
   - 基本信息表: stocks_stockbasicinfo（Django 默认表名）
3. 如果你后面给 StockBasicInfo 显式指定了 db_table，也不影响 ORM 写入。
"""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
from tqdm import tqdm


# -----------------------------
# 路径与 Django 初始化
# -----------------------------
def find_project_root() -> Path:
    """
    兼容两种放置方式：
    1) 推荐：GraduationProject/raw_data/download_hs300_to_db.py
    2) 临时：任意位置执行，但当前工作目录是 GraduationProject
    """
    cwd = Path.cwd().resolve()
    candidates = [
        cwd,
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
    ]
    for c in candidates:
        if (c / "quant_backend" / "manage.py").exists():
            return c
    raise FileNotFoundError(
        "未找到项目根目录。请把脚本放到 GraduationProject/raw_data/ 下执行，"
        "或在 GraduationProject 根目录下执行。"
    )


PROJECT_ROOT = find_project_root()
RAW_DATA_DIR = PROJECT_ROOT / "raw_data" / "hs300_cache"
STATE_FILE = RAW_DATA_DIR / "state.json"
BASIC_FILE = RAW_DATA_DIR / "basic" / "hs300_basic.csv"
DAILY_DIR = RAW_DATA_DIR / "daily"
MIN5_DIR = RAW_DATA_DIR / "minute5"

RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
(BASIC_FILE.parent).mkdir(parents=True, exist_ok=True)
DAILY_DIR.mkdir(parents=True, exist_ok=True)
MIN5_DIR.mkdir(parents=True, exist_ok=True)


def setup_django():
    sys.path.insert(0, str(PROJECT_ROOT / "quant_backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "quant_backend.settings")
    import django
    django.setup()


setup_django()

from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime
from stocks.models import StockBasicInfo, StockData, StockMinuteData  # noqa: E402


# -----------------------------
# 工具函数
# -----------------------------
def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {
            "version": 1,
            "updated_at": None,
            "basic": {"downloaded": False, "uploaded": False},
            "daily": {},
            "minute5": {},
        }
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    atomic_write_json(STATE_FILE, state)


def month_iter(start_date: date, end_date: date) -> Iterable[Tuple[date, date, str]]:
    cur = date(start_date.year, start_date.month, 1)
    end_anchor = date(end_date.year, end_date.month, 1)
    while cur <= end_anchor:
        last_day = calendar.monthrange(cur.year, cur.month)[1]
        month_start = cur
        month_end = date(cur.year, cur.month, last_day)
        real_start = max(month_start, start_date)
        real_end = min(month_end, end_date)
        label = f"{cur.year:04d}-{cur.month:02d}"
        if real_start <= real_end:
            yield real_start, real_end, label
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)


def sanitize_code(code: str) -> str:
    return code.strip()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def retry(times_: int = 3, sleep_seconds: int = 2):
    def deco(func):
        def wrapper(*args, **kwargs):
            last_err = None
            for i in range(times_):
                try:
                    return func(*args, **kwargs)
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    if i < times_ - 1:
                        time.sleep(sleep_seconds)
            raise last_err
        return wrapper
    return deco


# -----------------------------
# Baostock 数据下载
# -----------------------------
@retry(times_=3, sleep_seconds=2)
def bs_login():
    import baostock as bs
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock 登录失败: {lg.error_code} | {lg.error_msg}")
    return bs


def bs_to_df(rs) -> pd.DataFrame:
    rows: List[List[str]] = []
    while (rs.error_code == "0") and rs.next():
        rows.append(rs.get_row_data())
    df = pd.DataFrame(rows, columns=rs.fields)
    return df


@retry(times_=3, sleep_seconds=2)
def fetch_hs300_basic(bs) -> pd.DataFrame:
    rs = bs.query_hs300_stocks()
    if rs.error_code != "0":
        raise RuntimeError(f"query_hs300_stocks 失败: {rs.error_code} | {rs.error_msg}")
    df = bs_to_df(rs)
    if df.empty:
        raise RuntimeError("query_hs300_stocks 返回为空。")
    # 常见字段：date, code, code_name
    keep_cols = [c for c in ["date", "code", "code_name"] if c in df.columns]
    df = df[keep_cols].copy()
    df.rename(columns={"code_name": "name"}, inplace=True)
    df["code"] = df["code"].map(sanitize_code)
    return df[["code", "name"]].drop_duplicates(subset=["code"]).sort_values("code").reset_index(drop=True)


@retry(times_=3, sleep_seconds=2)
def fetch_daily_df(bs, code: str, stock_name: str, start_date: str, end_date: str) -> pd.DataFrame:
    fields = "date,code,open,high,low,close,volume,amount"
    rs = bs.query_history_k_data_plus(
        code,
        fields,
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="2",   # 前复权
    )
    if rs.error_code != "0":
        raise RuntimeError(f"日线下载失败 {code}: {rs.error_code} | {rs.error_msg}")
    df = bs_to_df(rs)
    if df.empty:
        return pd.DataFrame(columns=["date", "code", "name", "open", "high", "low", "close", "volume", "amount"])
    df["name"] = stock_name
    return df[["date", "code", "name", "open", "high", "low", "close", "volume", "amount"]]


@retry(times_=3, sleep_seconds=2)
def fetch_min5_df(bs, code: str, stock_name: str, start_date: str, end_date: str) -> pd.DataFrame:
    fields = "date,time,code,open,high,low,close,volume,amount"
    rs = bs.query_history_k_data_plus(
        code,
        fields,
        start_date=start_date,
        end_date=end_date,
        frequency="5",
        adjustflag="2",   # 前复权
    )
    if rs.error_code != "0":
        raise RuntimeError(f"5分钟线下载失败 {code}: {rs.error_code} | {rs.error_msg}")
    df = bs_to_df(rs)
    if df.empty:
        return pd.DataFrame(columns=["datetime", "code", "name", "open", "high", "low", "close", "volume", "amount"])

    # time 常见格式示例：093500 / 20240102100000000 / 20240102100000
    def parse_bs_minute(row) -> Optional[str]:
        raw_date = str(row["date"]).strip()
        raw_time = str(row["time"]).strip()

        # 优先从 time 中解析完整时间戳
        digits = "".join(ch for ch in raw_time if ch.isdigit())

        dt = None
        if len(digits) >= 14:
            dt = datetime.strptime(digits[:14], "%Y%m%d%H%M%S")
        elif len(digits) == 6:
            dt = datetime.strptime(f"{raw_date} {digits}", "%Y-%m-%d %H%M%S")
        elif len(digits) == 4:
            dt = datetime.strptime(f"{raw_date} {digits}", "%Y-%m-%d %H%M")
        else:
            # 最后兜底，直接拼 date
            return None

        return dt.strftime("%Y-%m-%d %H:%M:%S")

    df["datetime"] = df.apply(parse_bs_minute, axis=1)
    df = df[df["datetime"].notna()].copy()
    df["name"] = stock_name
    return df[["datetime", "code", "name", "open", "high", "low", "close", "volume", "amount"]]


def write_csv(df: pd.DataFrame, path: Path) -> None:
    ensure_parent(path)
    df.to_csv(path, index=False, encoding="utf-8-sig")


# -----------------------------
# 本地下载阶段
# -----------------------------
def download_basic_info(bs, state: dict, force: bool = False) -> pd.DataFrame:
    if BASIC_FILE.exists() and state["basic"].get("downloaded") and not force:
        return pd.read_csv(BASIC_FILE)

    df = fetch_hs300_basic(bs)
    write_csv(df, BASIC_FILE)
    state["basic"]["downloaded"] = True
    save_state(state)
    return df


def download_daily_files(
    bs,
    basic_df: pd.DataFrame,
    state: dict,
    daily_start: date,
    end_date: date,
    force: bool = False,
) -> None:
    tasks = basic_df[["code", "name"]].to_dict("records")
    bar = tqdm(tasks, desc="下载日线", unit="股")
    for item in bar:
        code = sanitize_code(item["code"])
        name = item["name"]
        out_file = DAILY_DIR / f"{code.replace('.', '_')}.csv"

        done = state["daily"].get(code, {}).get("downloaded", False)
        if done and out_file.exists() and not force:
            continue

        df = fetch_daily_df(
            bs=bs,
            code=code,
            stock_name=name,
            start_date=daily_start.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
        write_csv(df, out_file)

        state["daily"].setdefault(code, {})
        state["daily"][code]["downloaded"] = True
        state["daily"][code]["file"] = str(out_file.relative_to(PROJECT_ROOT))
        state["daily"][code]["rows"] = int(len(df))
        save_state(state)


def download_min5_files(
    bs,
    basic_df: pd.DataFrame,
    state: dict,
    minute_start: date,
    end_date: date,
    force: bool = False,
) -> None:
    month_tasks: List[Tuple[str, str, date, date, str]] = []
    for item in basic_df[["code", "name"]].to_dict("records"):
        code = sanitize_code(item["code"])
        name = item["name"]
        for real_start, real_end, label in month_iter(minute_start, end_date):
            month_tasks.append((code, name, real_start, real_end, label))

    bar = tqdm(month_tasks, desc="下载5分钟线", unit="月片段")
    for code, name, real_start, real_end, label in bar:
        state["minute5"].setdefault(code, {})
        out_dir = MIN5_DIR / code.replace(".", "_")
        out_file = out_dir / f"{label}.csv"

        done = state["minute5"][code].get(label, {}).get("downloaded", False)
        if done and out_file.exists() and not force:
            continue

        df = fetch_min5_df(
            bs=bs,
            code=code,
            stock_name=name,
            start_date=real_start.strftime("%Y-%m-%d"),
            end_date=real_end.strftime("%Y-%m-%d"),
        )
        write_csv(df, out_file)

        state["minute5"][code].setdefault(label, {})
        state["minute5"][code][label]["downloaded"] = True
        state["minute5"][code][label]["file"] = str(out_file.relative_to(PROJECT_ROOT))
        state["minute5"][code][label]["rows"] = int(len(df))
        save_state(state)


# -----------------------------
# 数据库上传阶段
# -----------------------------
def upload_basic_info(state: dict, force: bool = False) -> None:
    if state["basic"].get("uploaded") and not force:
        return

    df = pd.read_csv(BASIC_FILE)
    objs = []
    for _, row in df.iterrows():
        objs.append(
            StockBasicInfo(
                code=str(row["code"]).strip(),
                name=str(row["name"]).strip(),
            )
        )

    # 名称可能变化，逐个 update_or_create 更稳
    for obj in tqdm(objs, desc="上传股票名称", unit="股"):
        StockBasicInfo.objects.update_or_create(
            code=obj.code,
            defaults={"name": obj.name},
        )

    state["basic"]["uploaded"] = True
    save_state(state)


def _safe_float(v) -> float:
    if pd.isna(v) or v == "":
        return 0.0
    return float(v)


def _safe_int(v) -> int:
    if pd.isna(v) or v == "":
        return 0
    return int(float(v))


def upload_daily_files(state: dict, force: bool = False, batch_size: int = 2000) -> None:
    items = sorted(state["daily"].items(), key=lambda x: x[0])
    bar = tqdm(items, desc="上传日线到数据库", unit="股")
    for code, meta in bar:
        if meta.get("uploaded") and not force:
            continue

        file_path = PROJECT_ROOT / meta["file"]
        if not file_path.exists():
            raise FileNotFoundError(f"找不到日线文件: {file_path}")

        df = pd.read_csv(file_path)
        if df.empty:
            state["daily"][code]["uploaded"] = True
            save_state(state)
            continue

        df["date"] = pd.to_datetime(df["date"]).dt.date

        min_date = df["date"].min()
        max_date = df["date"].max()

        with transaction.atomic():
            # 为保证可重复执行，这里按 code + 日期范围先删后插
            StockData.objects.filter(code=code, date__gte=min_date, date__lte=max_date).delete()

            buffer = []
            for _, row in df.iterrows():
                buffer.append(
                    StockData(
                        code=code,
                        date=row["date"],
                        open=_safe_float(row["open"]),
                        high=_safe_float(row["high"]),
                        low=_safe_float(row["low"]),
                        close=_safe_float(row["close"]),
                        volume=_safe_int(row["volume"]),
                        amount=_safe_float(row["amount"]),
                    )
                )
                if len(buffer) >= batch_size:
                    StockData.objects.bulk_create(buffer, batch_size=batch_size)
                    buffer = []

            if buffer:
                StockData.objects.bulk_create(buffer, batch_size=batch_size)

        state["daily"][code]["uploaded"] = True
        save_state(state)


def upload_min5_files(state: dict, force: bool = False, batch_size: int = 2000) -> None:
    tasks: List[Tuple[str, str, dict]] = []
    for code, months in state["minute5"].items():
        for label, meta in months.items():
            tasks.append((code, label, meta))
    tasks.sort(key=lambda x: (x[0], x[1]))

    bar = tqdm(tasks, desc="上传5分钟线到数据库", unit="月片段")
    for code, label, meta in bar:
        if meta.get("uploaded") and not force:
            continue

        file_path = PROJECT_ROOT / meta["file"]
        if not file_path.exists():
            raise FileNotFoundError(f"找不到 5 分钟文件: {file_path}")

        df = pd.read_csv(file_path)
        if df.empty:
            state["minute5"][code][label]["uploaded"] = True
            save_state(state)
            continue

        df["datetime"] = pd.to_datetime(df["datetime"])
        min_dt = df["datetime"].min().to_pydatetime()
        max_dt = df["datetime"].max().to_pydatetime()

        with transaction.atomic():
            # 为保证可重复执行，这里按 code + 时间范围先删后插
            StockMinuteData.objects.filter(code=code, date__gte=min_dt, date__lte=max_dt).delete()

            buffer = []
            for _, row in df.iterrows():
                buffer.append(
                    StockMinuteData(
                        code=code,
                        date=row["datetime"].to_pydatetime(),
                        open=_safe_float(row["open"]),
                        high=_safe_float(row["high"]),
                        low=_safe_float(row["low"]),
                        close=_safe_float(row["close"]),
                        volume=_safe_int(row["volume"]),
                        amount=_safe_float(row["amount"]),
                    )
                )
                if len(buffer) >= batch_size:
                    StockMinuteData.objects.bulk_create(buffer, batch_size=batch_size)
                    buffer = []

            if buffer:
                StockMinuteData.objects.bulk_create(buffer, batch_size=batch_size)

        state["minute5"][code][label]["uploaded"] = True
        save_state(state)


# -----------------------------
# 参数与主流程
# -----------------------------
@dataclass
class Args:
    daily_start: date
    minute_start: date
    end: date
    force_download: bool
    force_upload: bool
    skip_download: bool
    skip_upload: bool


def parse_args() -> Args:
    parser = argparse.ArgumentParser(
        description="下载沪深300日线/5分钟线/股票名称到本地，并上传到 GraduationProject 数据库。"
    )
    parser.add_argument(
        "--daily-start",
        default="2018-01-01",
        help="日线开始日期，格式 YYYY-MM-DD，默认 2018-01-01",
    )
    parser.add_argument(
        "--minute-start",
        default="2024-01-01",
        help="5分钟线开始日期，格式 YYYY-MM-DD，默认 2024-01-01（避免默认数据量过大）",
    )
    parser.add_argument(
        "--end",
        default=date.today().strftime("%Y-%m-%d"),
        help="结束日期，格式 YYYY-MM-DD，默认今天",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="忽略下载断点，强制重新下载本地文件",
    )
    parser.add_argument(
        "--force-upload",
        action="store_true",
        help="忽略上传断点，强制重新上传数据库（脚本会按范围先删后插）",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="跳过下载阶段，只把本地文件上传到数据库",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="跳过上传阶段，只下载到本地",
    )

    ns = parser.parse_args()

    def to_date(s: str) -> date:
        return datetime.strptime(s, "%Y-%m-%d").date()

    return Args(
        daily_start=to_date(ns.daily_start),
        minute_start=to_date(ns.minute_start),
        end=to_date(ns.end),
        force_download=ns.force_download,
        force_upload=ns.force_upload,
        skip_download=ns.skip_download,
        skip_upload=ns.skip_upload,
    )


def print_summary(args: Args) -> None:
    print("=" * 80)
    print("HS300 数据同步脚本")
    print(f"项目根目录      : {PROJECT_ROOT}")
    print(f"本地缓存目录    : {RAW_DATA_DIR}")
    print(f"日线起始日期    : {args.daily_start}")
    print(f"5分钟起始日期   : {args.minute_start}")
    print(f"结束日期        : {args.end}")
    print(f"跳过下载        : {args.skip_download}")
    print(f"跳过上传        : {args.skip_upload}")
    print(f"强制重下        : {args.force_download}")
    print(f"强制重传        : {args.force_upload}")
    print("=" * 80)


def main():
    args = parse_args()
    print_summary(args)

    if args.daily_start > args.end:
        raise ValueError("daily-start 不能晚于 end")
    if args.minute_start > args.end:
        raise ValueError("minute-start 不能晚于 end")

    state = load_state()

    basic_df = None
    bs = None
    try:
        if not args.skip_download:
            bs = bs_login()
            basic_df = download_basic_info(bs, state, force=args.force_download)
            download_daily_files(
                bs=bs,
                basic_df=basic_df,
                state=state,
                daily_start=args.daily_start,
                end_date=args.end,
                force=args.force_download,
            )
            download_min5_files(
                bs=bs,
                basic_df=basic_df,
                state=state,
                minute_start=args.minute_start,
                end_date=args.end,
                force=args.force_download,
            )

        if not args.skip_upload:
            if basic_df is None:
                if not BASIC_FILE.exists():
                    raise FileNotFoundError("缺少本地基础信息文件，请先执行下载阶段。")
                basic_df = pd.read_csv(BASIC_FILE)

            upload_basic_info(state, force=args.force_upload)
            upload_daily_files(state, force=args.force_upload)
            upload_min5_files(state, force=args.force_upload)

        print("\n全部完成。")
        print(f"状态文件：{STATE_FILE}")
        print(f"基础信息：{BASIC_FILE}")
        print(f"日线目录：{DAILY_DIR}")
        print(f"5分钟目录：{MIN5_DIR}")

    finally:
        if bs is not None:
            try:
                bs.logout()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    main()
