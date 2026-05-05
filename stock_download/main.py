from pathlib import Path
import traceback

import akshare as ak
import pandas as pd


OUT_DIR = Path("data/akshare_5min")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_akshare_minute_df(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    将 AKShare 中文字段统一成英文，方便后面用 PySpark / pandas 处理。
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    rename_map = {
        "时间": "datetime",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "涨跌幅": "pct_chg",
        "涨跌额": "change",
        "成交量": "volume",
        "成交额": "amount",
        "振幅": "amplitude",
        "换手率": "turnover",
        "均价": "avg_price",
    }

    df = df.rename(columns=rename_map)

    if "datetime" not in df.columns:
        raise ValueError(f"返回数据中没有时间字段，实际字段为：{df.columns.tolist()}")

    df["symbol"] = symbol
    df["datetime"] = pd.to_datetime(df["datetime"])

    numeric_cols = [
        "open", "close", "high", "low",
        "pct_chg", "change", "volume", "amount",
        "amplitude", "turnover", "avg_price",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values(["symbol", "datetime"])
    df = df.drop_duplicates(subset=["symbol", "datetime"])

    return df


def fetch_5min_one_stock(
    symbol: str,
    start_date: str = "2023-01-01 09:30:00",
    end_date: str = "2026-05-05 15:00:00",
    adjust: str = "",
) -> pd.DataFrame:
    """
    symbol: 股票代码，不带市场前缀，例如 000001、600000
    adjust: "" 不复权；"qfq" 前复权；"hfq" 后复权
    """
    print(f"开始下载：{symbol}, {start_date} -> {end_date}, adjust={adjust!r}")

    raw_df = ak.stock_zh_a_hist_min_em(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        period="5",
        adjust=adjust,
    )

    print("AKShare 原始返回字段：", raw_df.columns.tolist())
    print("AKShare 原始返回行数：", len(raw_df))

    df = normalize_akshare_minute_df(raw_df, symbol)

    if df.empty:
        print("没有返回数据。")
        return df

    print("清洗后行数：", len(df))
    print("最早时间：", df["datetime"].min())
    print("最晚时间：", df["datetime"].max())
    print(df.head())
    print(df.tail())

    return df


def save_df(df: pd.DataFrame, symbol: str):
    if df.empty:
        return

    parquet_path = OUT_DIR / f"{symbol}_5min.parquet"
    csv_path = OUT_DIR / f"{symbol}_5min.csv"

    try:
        df.to_parquet(parquet_path, index=False)
        print(f"已保存 Parquet：{parquet_path}")
    except Exception as e:
        print("保存 Parquet 失败，改存 CSV：", e)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"已保存 CSV：{csv_path}")


if __name__ == "__main__":
    symbol = "000001"

    try:
        df = fetch_5min_one_stock(
            symbol=symbol,
            start_date="2023-01-01 09:30:00",
            end_date="2026-05-05 15:00:00",
            adjust="",      # 先用不复权测试；也可以改成 "qfq" 或 "hfq"
        )

        save_df(df, symbol)

    except Exception:
        print("下载失败，错误如下：")
        traceback.print_exc()