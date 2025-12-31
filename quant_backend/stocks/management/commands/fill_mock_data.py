import akshare as ak
import pandas as pd
import numpy as np
import random
import time
import warnings
# 🟢 修复1：引入 date 类
from datetime import datetime, timedelta, date
from tqdm import tqdm
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from stocks.models import StockData, StockMinuteData, StockBasicInfo


class Command(BaseCommand):
    help = '全能重置：清空 -> 下载真实数据 -> 模拟缺失数据'

    def handle(self, *args, **options):
        # 1. 设置环境
        warnings.filterwarnings("ignore")  # 屏蔽警告

        TARGET_STOCKS = [
            {'code': 'sh.688256', 'name': '寒武纪'},
            {'code': 'sz.300308', 'name': '中际旭创'},
            {'code': 'sz.300476', 'name': '胜宏科技'},
            {'code': 'sz.300502', 'name': '新易盛'},
            {'code': 'sz.300394', 'name': '天孚通信'},
        ]

        # 计算时间范围 (最近3年)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * 3)

        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')
        start_date_fmt = start_date.strftime('%Y-%m-%d %H:%M:%S')

        print("\n" + "=" * 60)
        print("🚀  全能重置脚本启动 (修复版)")
        print(f"🎯  目标：{len(TARGET_STOCKS)} 只股票")
        print("=" * 60 + "\n")

        if input("⚠️  警告：此操作将【彻底清空】所有数据并重新生成，确认吗？(y/n): ").lower() != 'y':
            return

        # ================= 第一步：清空数据 =================
        print("\n>>> [1/3] 正在清空数据库...")
        StockMinuteData.objects.all().delete()
        StockData.objects.all().delete()
        StockBasicInfo.objects.all().delete()

        # 重建股票列表
        for item in TARGET_STOCKS:
            StockBasicInfo.objects.create(code=item['code'], name=item['name'])
        print("✅  旧数据已清除")

        # ================= 第二步：下载真实数据 =================
        print("\n>>> [2/3] 正在下载真实数据 (Akshare)...")

        for item in TARGET_STOCKS:
            code = item['code']
            symbol = code.split('.')[1]
            name = item['name']
            print(f"   正在处理: {name} ({code})...")

            try:
                # 1. 下载日线 (3年完整版)
                df_daily = ak.stock_zh_a_hist(
                    symbol=symbol, period="daily", start_date=start_date_str, end_date=end_date_str, adjust="qfq"
                )
                if not df_daily.empty:
                    daily_objs = [
                        StockData(
                            code=code,
                            date=row['日期'],
                            open=row['开盘'], high=row['最高'], low=row['最低'], close=row['收盘'],
                            volume=row['成交量'], amount=row['成交额']
                        ) for _, row in df_daily.iterrows()
                    ]
                    StockData.objects.bulk_create(daily_objs)

                # 2. 下载分钟线 (能下多少下多少)
                df_min = ak.stock_zh_a_hist_min_em(
                    symbol=symbol, period='5', adjust='qfq', start_date=start_date_fmt
                )
                if not df_min.empty:
                    min_objs = []
                    for _, row in df_min.iterrows():
                        # 处理时间格式
                        dt_obj = pd.to_datetime(row['时间']).to_pydatetime()
                        if timezone.is_naive(dt_obj): dt_obj = timezone.make_aware(dt_obj)

                        min_objs.append(StockMinuteData(
                            code=code,
                            date=dt_obj,
                            open=row['开盘'], high=row['最高'], low=row['最低'], close=row['收盘'],
                            volume=row['成交量'], amount=row['成交额']
                        ))
                    StockMinuteData.objects.bulk_create(min_objs)
                    print(f"      -> 获取到 {len(min_objs)} 条真实分钟数据")

                time.sleep(0.5)

            except Exception as e:
                print(f"      ❌ 下载出错: {e}")

        # ================= 第三步：智能补全 =================
        print("\n>>> [3/3] 正在智能补全缺失的历史分钟数据...")
        self.fill_gaps()

    def fill_gaps(self):
        """扫描所有日线，如果某天没有分钟数据，就生成高仿真数据"""
        all_daily = StockData.objects.all().order_by('code', 'date')
        to_create = []

        pbar = tqdm(all_daily, desc="检查并补全", unit="日")

        for daily in pbar:
            # 🟢 修复2：更健壮的日期类型判断
            if isinstance(daily.date, str):
                dt = datetime.strptime(daily.date, "%Y-%m-%d").date()
            elif isinstance(daily.date, datetime):
                dt = daily.date.date()
            elif isinstance(daily.date, date):
                dt = daily.date
            else:
                # 兜底
                dt = datetime.now().date()

            day_start = timezone.make_aware(datetime.combine(dt, datetime.min.time()))
            day_end = timezone.make_aware(datetime.combine(dt, datetime.max.time()))

            # 检查数据库里这一天有没有刚才下载的真实数据
            if StockMinuteData.objects.filter(code=daily.code, date__range=(day_start, day_end)).exists():
                continue

            # 启动模拟引擎
            mock_data = self.generate_simulation(daily, day_start)
            to_create.extend(mock_data)

            if len(to_create) >= 5000:
                StockMinuteData.objects.bulk_create(to_create)
                to_create = []

        if to_create:
            StockMinuteData.objects.bulk_create(to_create)

        print("\n🎉  所有工作完成！")

    def generate_simulation(self, daily, day_start):
        """
        终极模拟算法：布朗桥 + 强约束
        """
        n_points = 49

        # 1. 布朗桥随机路径
        dt = 1.0 / (n_points - 1)
        t = np.linspace(0, 1, n_points)
        dW = np.random.normal(0, np.sqrt(dt), n_points)
        dW[0] = 0
        W = np.cumsum(dW)
        bridge = W - t * W[-1]

        # 2. 叠加趋势
        trend = np.linspace(daily.open, daily.close, n_points)

        # 3. 动态振幅
        real_range = daily.high - daily.low
        if real_range == 0: real_range = daily.open * 0.001

        price_curve = trend + bridge * real_range * 1.5

        # 4. 强制约束
        price_curve[0] = daily.open
        price_curve[-1] = daily.close
        price_curve = np.clip(price_curve, daily.low, daily.high)

        if n_points > 5:
            indices = list(range(5, 44))
            idx_h = random.choice(indices)
            indices.remove(idx_h)
            idx_l = random.choice(indices)
            price_curve[idx_h] = daily.high
            price_curve[idx_l] = daily.low

        # 5. 转K线
        data_list = []
        times = []

        curr = day_start.replace(hour=9, minute=35)
        for _ in range(24):
            times.append(curr);
            curr += timedelta(minutes=5)
        curr = day_start.replace(hour=13, minute=5)
        for _ in range(24):
            times.append(curr);
            curr += timedelta(minutes=5)

        vol_curve = (np.linspace(-1, 1, 48) ** 2) + 0.2

        for i in range(48):
            p_open = price_curve[i]
            p_close = price_curve[i + 1]

            base_h = max(p_open, p_close)
            base_l = min(p_open, p_close)

            shadow = real_range * 0.03
            p_high = min(base_h + random.random() * shadow, daily.high)
            p_low = max(base_l - random.random() * shadow, daily.low)

            vol = int((daily.volume / 48) * vol_curve[i] * random.uniform(0.6, 1.4))

            data_list.append(StockMinuteData(
                code=daily.code,
                date=times[i],
                open=round(p_open, 2),
                high=round(p_high, 2),
                low=round(p_low, 2),
                close=round(p_close, 2),
                volume=vol,
                amount=vol * p_close
            ))

        return data_list