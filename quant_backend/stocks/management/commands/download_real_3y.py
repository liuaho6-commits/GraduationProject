import baostock as bs
import pandas as pd
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from stocks.models import StockMinuteData
from tqdm import tqdm  # 导入 tqdm 库


class Command(BaseCommand):
    help = '使用 Baostock 下载真实的3年5分钟K线数据 (进度条版)'

    def handle(self, *args, **options):
        # 目标股票池
        TARGET_STOCKS = [
            {'code': 'sh.688256', 'name': '寒武纪'},
            {'code': 'sz.300308', 'name': '中际旭创'},
            {'code': 'sz.300476', 'name': '胜宏科技'},
            {'code': 'sz.300502', 'name': '新易盛'},
            {'code': 'sz.300394', 'name': '天孚通信'},
        ]

        print("=" * 60)
        print("🛠️  数据修复程序启动 (Baostock版 + Tqdm进度条)")
        print("=" * 60)

        # 1. 登陆 Baostock
        lg = bs.login()
        if lg.error_code != '0':
            print(f"❌ 登陆失败: {lg.error_msg}")
            return

        # 2. 清空旧数据
        print(">>> 正在清空旧数据 (请稍候)...")
        StockMinuteData.objects.all().delete()
        print("✅ 旧数据已清空")

        # 3. 设定时间范围 (最近3年)
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=365 * 5)
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        print(f">>> 下载范围: {start_str} 至 {end_str}")

        # 4. 循环下载 (使用 tqdm 包装)
        # unit='股' 表示进度条单位是“只股票”
        pbar = tqdm(TARGET_STOCKS, desc="总进度", unit="股")

        for item in pbar:
            db_code = item['code']
            bs_code = db_code
            name = item['name']

            # 动态更新进度条后方的文字说明
            pbar.set_description(f"正在处理: {name}")

            # 调用接口
            # frequency="5": 5分钟线
            # adjustflag="2": 前复权 (重要！保证K线连续)
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,time,open,high,low,close,volume,amount",
                start_date=start_str,
                end_date=end_str,
                frequency="5",
                adjustflag="2"
            )

            if rs.error_code != '0':
                # 使用 pbar.write 代替 print，防止打断进度条动画
                pbar.write(f"❌ {name} 下载失败: {rs.error_msg}")
                continue

            data_list = []
            while rs.next():
                row = rs.get_row_data()
                try:
                    # 解析时间
                    # Baostock 5分钟线的时间字段通常是 14位: YYYYMMDDHHMMSS
                    time_str = row[1]
                    if len(time_str) > 14:
                        time_str = time_str[:14]  # 截断多余毫秒

                    dt = datetime.datetime.strptime(time_str, "%Y%m%d%H%M%S")
                    dt_aware = timezone.make_aware(dt)

                    data_list.append(StockMinuteData(
                        code=db_code,
                        date=dt_aware,
                        open=float(row[2]),
                        high=float(row[3]),
                        low=float(row[4]),
                        close=float(row[5]),
                        volume=int(row[6]) if row[6] else 0,
                        amount=float(row[7]) if row[7] else 0.0
                    ))
                except Exception:
                    continue

            # 5. 批量入库
            if data_list:
                # 分批插入，避免一次性占用过多内存
                batch_size = 5000
                for i in range(0, len(data_list), batch_size):
                    StockMinuteData.objects.bulk_create(data_list[i:i + batch_size])

                pbar.write(f"✅ {name}: 成功下载 {len(data_list)} 条K线")
            else:
                pbar.write(f"⚠️ {name}: 未获取到数据")

        # 6. 登出
        bs.logout()
        print("\n🎉 所有任务完成！")