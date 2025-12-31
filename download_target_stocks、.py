import akshare as ak
import pandas as pd
import os
import time
from datetime import datetime

# 1. 配置：只下载这两只股票
# 农业银行(601288), 中际旭创(300308)
TARGET_STOCKS = {
    "601288": "农业银行",
    "300308": "中际旭创"
}

# 时间范围：过去 2 年
START_DATE = "20230101"
END_DATE = "20241231"

# 保存路径
OUTPUT_DIR = "raw_data"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

print(f"🎯 开始下载目标股票数据：{list(TARGET_STOCKS.values())}")

for code, name in TARGET_STOCKS.items():
    print(f"\nProcessing {name} ({code})...")

    # ==========================================
    # 策略 A: 下载日线数据 (Daily) - 肯定能下到 2 年
    # ==========================================
    try:
        print(f"  - 正在下载日线数据 ({START_DATE}-{END_DATE})...")
        df_daily = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=START_DATE, end_date=END_DATE,
                                      adjust="qfq")

        # 保存为标准格式
        filename_daily = f"{OUTPUT_DIR}/{code}_daily.csv"
        df_daily.to_csv(filename_daily, index=False)
        print(f"    ✅ 日线保存成功: {filename_daily} (行数: {len(df_daily)})")
    except Exception as e:
        print(f"    ❌ 日线下载失败: {e}")

    # ==========================================
    # 策略 B: 尝试下载 5分钟/1分钟数据 (Intraday)
    # ==========================================
    # 注意：免费接口通常无法提供 2 年完整的 1 分钟数据，这里我们尽可能多下
    try:
        print(f"  - 正在下载 5分钟级数据 (用于精细回测)...")
        # period可选: "1", "5", "15", "30", "60"
        # 建议用 5 分钟，历史数据比 1 分钟更长
        df_min = ak.stock_zh_a_hist_min_em(symbol=code, period="5", adjust="qfq")

        # 加上股票代码列，方便入库
        df_min['code'] = code

        filename_min = f"{OUTPUT_DIR}/{code}_5min.csv"
        df_min.to_csv(filename_min, index=False)
        print(f"    ✅ 5分钟数据保存成功: {filename_min} (行数: {len(df_min)})")
        print(f"       时间范围: {df_min['时间'].iloc[0]} 到 {df_min['时间'].iloc[-1]}")

    except Exception as e:
        print(f"    ❌ 分钟数据下载失败: {e}")

    time.sleep(1)  # 礼貌请求，防止被封

print("\n🎉 所有目标股票数据下载完成！请检查 raw_data 文件夹。")