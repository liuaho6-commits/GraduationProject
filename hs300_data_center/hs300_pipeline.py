#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
沪深300日线/5分钟线下载、清洗与连续性校验。

默认数据源：东方财富公开 K 线接口。
输出目录：hs300_data_center/data
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import requests
from tqdm import tqdm


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
BASIC_DIR = DATA_DIR / "basic"
RAW_DAILY_DIR = DATA_DIR / "raw" / "daily"
RAW_MINUTE5_DIR = DATA_DIR / "raw" / "minute5"
CLEAN_DAILY_DIR = DATA_DIR / "clean" / "daily"
CLEAN_MINUTE5_DIR = DATA_DIR / "clean" / "minute5"
REPORT_DIR = DATA_DIR / "reports"

COMPONENTS_FILE = BASIC_DIR / "hs300_components.csv"
REPORT_CSV = REPORT_DIR / "validation_report.csv"
REPORT_JSON = REPORT_DIR / "validation_report.json"

PRICE_DIGITS = 4
TOLERANCE = 0.0001


def ensure_dirs() -> None:
    for path in [
        BASIC_DIR,
        RAW_DAILY_DIR,
        RAW_MINUTE5_DIR,
        CLEAN_DAILY_DIR,
        CLEAN_MINUTE5_DIR,
        REPORT_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def to_date_str(value: str) -> str:
    return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")


def normalize_code(code: str) -> str:
    code = str(code).strip()
    if code.startswith(("sh.", "sz.")):
        return code
    if len(code) != 6:
        raise ValueError(f"无法识别股票代码: {code}")
    if code.startswith(("6", "9")):
        return f"sh.{code}"
    return f"sz.{code}"


def eastmoney_secid(code: str) -> str:
    code = normalize_code(code)
    market = "1" if code.startswith("sh.") else "0"
    return f"{market}.{code.split('.', 1)[1]}"


def output_name(code: str) -> str:
    return normalize_code(code).replace(".", "_") + ".csv"


def request_json(url: str, params: dict, retries: int = 3, sleep_seconds: float = 1.0) -> dict:
    last_error: Optional[Exception] = None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
        ),
        "Referer": "https://quote.eastmoney.com/",
    }

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data.get("rc") not in (0, None):
                raise RuntimeError(f"接口返回错误 rc={data.get('rc')}: {data}")
            return data
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                time.sleep(sleep_seconds * attempt)

    raise RuntimeError(f"请求失败: {url} params={params}") from last_error


def load_hs300_components(force: bool = False) -> pd.DataFrame:
    if COMPONENTS_FILE.exists() and not force:
        return pd.read_csv(COMPONENTS_FILE)

    ensure_dirs()
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "500",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fs": "b:BK0500",
        "fields": "f12,f14",
    }
    data = request_json(url, params)
    rows = data.get("data", {}).get("diff", [])
    if not rows:
        raise RuntimeError("未获取到沪深300成分股列表。")

    df = pd.DataFrame(
        {
            "code": [normalize_code(row["f12"]) for row in rows],
            "name": [str(row["f14"]).strip() for row in rows],
        }
    ).drop_duplicates(subset=["code"])
    df = df.sort_values("code").reset_index(drop=True)
    df.to_csv(COMPONENTS_FILE, index=False, encoding="utf-8-sig")
    return df


def fetch_eastmoney_kline(code: str, name: str, klt: str, start: str, end: str) -> pd.DataFrame:
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": eastmoney_secid(code),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": klt,
        "fqt": "1",
        "beg": to_date_str(start),
        "end": to_date_str(end),
    }
    data = request_json(url, params)
    klines = data.get("data", {}).get("klines") or []

    columns = [
        "time",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
        "amplitude",
        "pct_chg",
        "chg",
        "turnover",
    ]
    rows = [line.split(",") for line in klines]
    if not rows:
        time_col = "date" if klt == "101" else "datetime"
        return pd.DataFrame(columns=[time_col, "code", "name", "open", "high", "low", "close", "volume", "amount"])

    df = pd.DataFrame(rows, columns=columns)
    time_col = "date" if klt == "101" else "datetime"
    df.rename(columns={"time": time_col}, inplace=True)
    df["code"] = normalize_code(code)
    df["name"] = name

    keep = [time_col, "code", "name", "open", "high", "low", "close", "volume", "amount"]
    df = df[keep].copy()
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.dropna(subset=["open", "high", "low", "close"], inplace=True)
    return df.reset_index(drop=True)


def select_components(all_components: pd.DataFrame, codes: Optional[str], limit: Optional[int]) -> pd.DataFrame:
    if codes:
        wanted = [normalize_code(item) for item in codes.split(",") if item.strip()]
        known_names = dict(zip(all_components["code"], all_components["name"]))
        rows = [{"code": code, "name": known_names.get(code, code)} for code in wanted]
        return pd.DataFrame(rows)

    df = all_components.copy()
    if limit:
        df = df.head(limit)
    return df.reset_index(drop=True)


def download_files(components: pd.DataFrame, daily_start: str, minute_start: str, end: str, force: bool) -> None:
    ensure_dirs()
    tasks = components.to_dict("records")

    for item in tqdm(tasks, desc="下载日线", unit="股"):
        code = item["code"]
        name = item["name"]
        out_file = RAW_DAILY_DIR / output_name(code)
        if out_file.exists() and not force:
            continue
        df = fetch_eastmoney_kline(code, name, "101", daily_start, end)
        df.to_csv(out_file, index=False, encoding="utf-8-sig")

    for item in tqdm(tasks, desc="下载5分钟线", unit="股"):
        code = item["code"]
        name = item["name"]
        out_file = RAW_MINUTE5_DIR / output_name(code)
        if out_file.exists() and not force:
            continue
        df = fetch_eastmoney_kline(code, name, "5", minute_start, end)
        df.to_csv(out_file, index=False, encoding="utf-8-sig")


def normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df.dropna(subset=["open", "high", "low", "close"], inplace=True)

    for idx in df.index:
        high = max(float(df.at[idx, "high"]), float(df.at[idx, "open"]), float(df.at[idx, "close"]))
        low = min(float(df.at[idx, "low"]), float(df.at[idx, "open"]), float(df.at[idx, "close"]))
        df.at[idx, "high"] = round(high, PRICE_DIGITS)
        df.at[idx, "low"] = round(low, PRICE_DIGITS)

    return df


def make_continuous(df: pd.DataFrame, time_col: str, continuity_scope: str) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col).drop_duplicates(subset=[time_col]).reset_index(drop=True)
    df = normalize_ohlc(df)

    if continuity_scope == "intraday":
        for idx in range(1, len(df)):
            current_day = df.at[idx, time_col].date()
            previous_day = df.at[idx - 1, time_col].date()
            if current_day != previous_day:
                continue

            prev_close = round(float(df.at[idx - 1, "close"]), PRICE_DIGITS)
            df.at[idx, "open"] = prev_close
            df.at[idx, "high"] = round(max(float(df.at[idx, "high"]), prev_close, float(df.at[idx, "close"])), PRICE_DIGITS)
            df.at[idx, "low"] = round(min(float(df.at[idx, "low"]), prev_close, float(df.at[idx, "close"])), PRICE_DIGITS)
    elif continuity_scope == "all":
        for idx in range(1, len(df)):
            prev_close = round(float(df.at[idx - 1, "close"]), PRICE_DIGITS)
            df.at[idx, "open"] = prev_close
            df.at[idx, "high"] = round(max(float(df.at[idx, "high"]), prev_close, float(df.at[idx, "close"])), PRICE_DIGITS)
            df.at[idx, "low"] = round(min(float(df.at[idx, "low"]), prev_close, float(df.at[idx, "close"])), PRICE_DIGITS)
    elif continuity_scope == "none":
        pass
    else:
        raise ValueError(f"未知连续性规则: {continuity_scope}")

    if time_col == "date":
        df[time_col] = df[time_col].dt.strftime("%Y-%m-%d")
    else:
        df[time_col] = df[time_col].dt.strftime("%Y-%m-%d %H:%M")

    return df


def clean_files() -> None:
    ensure_dirs()

    for raw_file in tqdm(sorted(RAW_DAILY_DIR.glob("*.csv")), desc="生成连续日线", unit="文件"):
        df = pd.read_csv(raw_file)
        clean_df = make_continuous(df, "date", continuity_scope="none")
        clean_df.to_csv(CLEAN_DAILY_DIR / raw_file.name, index=False, encoding="utf-8-sig")

    for raw_file in tqdm(sorted(RAW_MINUTE5_DIR.glob("*.csv")), desc="生成连续5分钟线", unit="文件"):
        df = pd.read_csv(raw_file)
        clean_df = make_continuous(df, "datetime", continuity_scope="intraday")
        clean_df.to_csv(CLEAN_MINUTE5_DIR / raw_file.name, index=False, encoding="utf-8-sig")


def count_continuity_breaks(df: pd.DataFrame, time_col: str, continuity_scope: str) -> int:
    if continuity_scope == "none":
        return 0
    if df.empty or len(df) < 2:
        return 0
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col).reset_index(drop=True)
    prev_close = df["close"].shift(1)
    diff = (df["open"] - prev_close).abs()

    if continuity_scope == "intraday":
        same_day = df[time_col].dt.date == df[time_col].shift(1).dt.date
        return int(((diff > TOLERANCE) & same_day).sum())
    if continuity_scope == "all":
        return int((diff.iloc[1:] > TOLERANCE).sum())

    raise ValueError(f"未知连续性规则: {continuity_scope}")


def count_ohlc_breaks(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    high_breaks = df["high"] + TOLERANCE < df[["open", "close"]].max(axis=1)
    low_breaks = df["low"] - TOLERANCE > df[["open", "close"]].min(axis=1)
    return int((high_breaks | low_breaks).sum())


def load_for_validation(path: Path, time_col: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty:
        return df
    df[time_col] = pd.to_datetime(df[time_col])
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["open", "high", "low", "close"])


def file_date_range(df: pd.DataFrame, time_col: str) -> tuple[str, str]:
    if df.empty:
        return "", ""
    return (
        pd.to_datetime(df[time_col]).min().strftime("%Y-%m-%d %H:%M" if time_col == "datetime" else "%Y-%m-%d"),
        pd.to_datetime(df[time_col]).max().strftime("%Y-%m-%d %H:%M" if time_col == "datetime" else "%Y-%m-%d"),
    )


def validate_pair(
    code: str,
    raw_path: Path,
    clean_path: Path,
    time_col: str,
    kind: str,
    continuity_scope: str,
) -> dict:
    raw_df = load_for_validation(raw_path, time_col)
    clean_df = load_for_validation(clean_path, time_col)
    raw_min, raw_max = file_date_range(raw_df, time_col)
    clean_min, clean_max = file_date_range(clean_df, time_col)
    clean_continuity_breaks = count_continuity_breaks(clean_df, time_col, continuity_scope)
    clean_ohlc_breaks = count_ohlc_breaks(clean_df)

    return {
        "code": code,
        "kind": kind,
        "continuity_scope": continuity_scope,
        "raw_rows": int(len(raw_df)),
        "clean_rows": int(len(clean_df)),
        "raw_min_time": raw_min,
        "raw_max_time": raw_max,
        "clean_min_time": clean_min,
        "clean_max_time": clean_max,
        "raw_continuity_breaks": count_continuity_breaks(raw_df, time_col, continuity_scope),
        "clean_continuity_breaks": clean_continuity_breaks,
        "raw_ohlc_breaks": count_ohlc_breaks(raw_df),
        "clean_ohlc_breaks": clean_ohlc_breaks,
        "passed": (
            len(clean_df) > 0
            and clean_continuity_breaks == 0
            and clean_ohlc_breaks == 0
        ),
    }


def iter_codes_from_files() -> Iterable[str]:
    names = {path.name for path in RAW_DAILY_DIR.glob("*.csv")}
    names.update(path.name for path in RAW_MINUTE5_DIR.glob("*.csv"))
    for name in sorted(names):
        stem = Path(name).stem
        yield stem.replace("_", ".")


def validate_files(codes: Optional[Iterable[str]] = None) -> pd.DataFrame:
    ensure_dirs()
    reports: list[dict] = []
    code_list = [normalize_code(code) for code in codes] if codes is not None else list(iter_codes_from_files())

    for code in code_list:
        file_name = output_name(code)
        reports.append(
            validate_pair(
                code=normalize_code(code),
                raw_path=RAW_DAILY_DIR / file_name,
                clean_path=CLEAN_DAILY_DIR / file_name,
                time_col="date",
                kind="daily",
                continuity_scope="none",
            )
        )
        reports.append(
            validate_pair(
                code=normalize_code(code),
                raw_path=RAW_MINUTE5_DIR / file_name,
                clean_path=CLEAN_MINUTE5_DIR / file_name,
                time_col="datetime",
                kind="minute5",
                continuity_scope="intraday",
            )
        )

    report_df = pd.DataFrame(reports)
    report_df.to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")
    REPORT_JSON.write_text(
        json.dumps(reports, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_df


@dataclass
class RunConfig:
    command: str
    daily_start: str
    minute_start: str
    end: str
    codes: Optional[str]
    limit: Optional[int]
    force: bool
    skip_download: bool


def parse_args() -> RunConfig:
    parser = argparse.ArgumentParser(description="沪深300数据下载、清洗与校验")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_options(p: argparse.ArgumentParser) -> None:
        p.add_argument("--daily-start", default="2026-01-01", help="日线开始日期 YYYY-MM-DD")
        p.add_argument("--minute-start", default="2026-04-20", help="5分钟线开始日期 YYYY-MM-DD")
        p.add_argument("--end", default=date.today().strftime("%Y-%m-%d"), help="结束日期 YYYY-MM-DD")
        p.add_argument("--codes", default=None, help="指定股票，逗号分隔，如 sh.600000,sz.000001")
        p.add_argument("--limit", type=int, default=None, help="只处理前 N 只沪深300成分股")
        p.add_argument("--force", action="store_true", help="强制重新下载已有文件")
        p.add_argument("--skip-download", action="store_true", help="跳过下载，只清洗并校验已有 raw 文件")

    sample = subparsers.add_parser("sample", help="下载几只股票的小样本并校验")
    add_common_options(sample)
    sample.set_defaults(
        codes="sh.600000,sz.000001,sz.300750",
        daily_start="2026-01-01",
        minute_start="2026-04-20",
        limit=None,
    )

    run = subparsers.add_parser("run", help="下载、清洗并校验")
    add_common_options(run)

    validate = subparsers.add_parser("validate", help="只校验已有 raw/clean 文件")
    validate.set_defaults(
        daily_start="2026-01-01",
        minute_start="2026-04-20",
        end=date.today().strftime("%Y-%m-%d"),
        codes=None,
        limit=None,
        force=False,
        skip_download=True,
    )

    ns = parser.parse_args()
    return RunConfig(
        command=ns.command,
        daily_start=ns.daily_start,
        minute_start=ns.minute_start,
        end=ns.end,
        codes=ns.codes,
        limit=ns.limit,
        force=ns.force,
        skip_download=ns.skip_download,
    )


def print_report_summary(report_df: pd.DataFrame) -> None:
    if report_df.empty:
        print("未生成校验结果。")
        return

    total = len(report_df)
    passed = int(report_df["passed"].sum())
    clean_breaks = int(report_df["clean_continuity_breaks"].sum() + report_df["clean_ohlc_breaks"].sum())
    raw_breaks = int(report_df["raw_continuity_breaks"].sum() + report_df["raw_ohlc_breaks"].sum())
    print("\n校验完成")
    print(f"- 报告项数: {total}")
    print(f"- clean 通过: {passed}/{total}")
    print(f"- raw 问题数: {raw_breaks}")
    print(f"- clean 问题数: {clean_breaks}")
    print(f"- CSV 报告: {REPORT_CSV}")
    print(f"- JSON 报告: {REPORT_JSON}")

    failed = report_df[~report_df["passed"]]
    if not failed.empty:
        print("\n未通过项：")
        print(failed[["code", "kind", "clean_rows", "clean_continuity_breaks", "clean_ohlc_breaks"]].to_string(index=False))


def main() -> None:
    config = parse_args()
    ensure_dirs()
    selected_code_list: Optional[list[str]] = None

    if config.command in {"sample", "run"} and not config.skip_download:
        components = load_hs300_components(force=config.force)
        selected = select_components(components, config.codes, config.limit)
        selected_code_list = selected["code"].tolist()
        selected_preview = ", ".join(selected_code_list[:8])
        suffix = " ..." if len(selected) > 8 else ""
        print(f"准备下载 {len(selected)} 只股票: {selected_preview}{suffix}")
        download_files(selected, config.daily_start, config.minute_start, config.end, config.force)
    elif config.command in {"sample", "run"}:
        components = load_hs300_components(force=False)
        selected = select_components(components, config.codes, config.limit)
        selected_code_list = selected["code"].tolist()

    if config.command in {"sample", "run"}:
        clean_files()

    report_df = validate_files(selected_code_list)
    print_report_summary(report_df)


if __name__ == "__main__":
    main()
