import akshare as ak
import pandas as pd
from django.core.management.base import BaseCommand
from django.utils.timezone import make_aware  # 🟢 核心修复：引入时区转换工具
from stocks.models import StockData, StockMinuteData, StockBasicInfo
import time
from tqdm import tqdm
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = '初始化数据：下载指定股票的【3年日线】和【3年分钟线】数据'

    def handle(self, *args, **options):
        # 目标股票池
        TARGET_STOCKS = [
            {'code': 'sh.688256', 'name': '寒武纪'},
            {'code': 'sz.300308', 'name': '中际旭创'},
            {'code': 'sz.300476', 'name': '胜宏科技'},
            {'code': 'sz.300502', 'name': '新易盛'},
            {'code': 'sz.300394', 'name': '天孚通信'},
        ]

        # 计算3年前的日期
        three_years_ago_str = (datetime.now() - timedelta(days=365 * 3)).strftime('%Y-%m-%d %H:%M:%S')
        start_date_daily = (datetime.now() - timedelta(days=365 * 3)).strftime('%Y%m%d')
        end_date_daily = datetime.now().strftime('%Y%m%d')

        print(f"⚠️  警告：将清空旧数据，并下载最近3年的日线 + 分钟线数据。")

        if input("确认继续? (y/n): ").lower() != 'y':
            return

        # 1. 清空旧数据
        print("\n>>> [1/3] 清理数据库...")
        StockData.objects.all().delete()
        StockMinuteData.objects.all().delete()
        StockBasicInfo.objects.all().delete()

        # 重建基本信息
        for item in TARGET_STOCKS:
            StockBasicInfo.objects.create(code=item['code'], name=item['name'])

        # 2. 循环下载
        print("\n>>> [2/3] 开始下载数据 (警告已屏蔽)...")

        pbar = tqdm(TARGET_STOCKS, desc="总体进度", unit="只")

        for item in pbar:
            code = item['code']
            symbol = code.split('.')[1]
            name = item['name']

            pbar.set_description(f"正在处理: {name}")

            try:
                # --- A. 下载日线数据 (3年) ---
                df_daily = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date_daily,
                    end_date=end_date_daily,
                    adjust="qfq"
                )

                if not df_daily.empty:
                    daily_objs = []
                    for _, row in df_daily.iterrows():
                        daily_objs.append(StockData(
                            code=code,
                            date=row['日期'],  # 日线由于是 DateField，直接存字符串没问题
                            open=row['开盘'], high=row['最高'], low=row['最低'], close=row['收盘'],
                            volume=row['成交量'], amount=row['成交额']
                        ))
                    StockData.objects.bulk_create(daily_objs)

                # --- B. 下载分钟数据 (3年) ---
                df_min = ak.stock_zh_a_hist_min_em(
                    symbol=symbol,
                    period='5',
                    adjust='qfq',
                    start_date=three_years_ago_str
                )

                if not df_min.empty:
                    min_objs = []
                    for _, row in df_min.iterrows():
                        # 🟢 核心修复：手动解析字符串并加上时区信息
                        # akshare 返回的时间格式通常是 '2023-10-27 14:55:00'
                        naive_time = datetime.strptime(row['时间'], "%Y-%m-%d %H:%M:%S")
                        aware_time = make_aware(naive_time)

                        min_objs.append(StockMinuteData(
                            code=code,
                            date=aware_time,  # 存入带时区的时间对象，Django 就不会报警了
                            open=row['开盘'], high=row['最高'], low=row['最低'], close=row['收盘'],
                            volume=row['成交量'], amount=row['成交额']
                        ))

                        if len(min_objs) >= 2000:
                            StockMinuteData.objects.bulk_create(min_objs)
                            min_objs = []

                    if min_objs:
                        StockMinuteData.objects.bulk_create(min_objs)

            except Exception as e:
                tqdm.write(f"❌ {name} 下载出错: {e}")

            time.sleep(0.5)

        print("\n🎉 所有数据初始化完成！")