import os
import django
import time
import datetime
from decimal import Decimal

# 1. 初始化 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

from django.conf import settings
from django.db import connection, reset_queries
from django.contrib.auth.models import User
from django.utils import timezone
from trade.views import calculate_asset_status
from trade.time_utils import get_mock_now

# 强制开启 DEBUG 模式以统计 SQL
settings.DEBUG = True


def run_diagnosis():
    print("======== 🚀 收益曲线性能诊断启动 ========")

    # 获取测试用户
    user = User.objects.first()
    if not user:
        print("❌ 错误: 数据库中没有用户，无法测试")
        return
    print(f"👤 测试用户: {user.username}")

    # 模拟 PerformanceView 中的 Intraday 逻辑
    now = get_mock_now()
    if timezone.is_naive(now): now = timezone.make_aware(now)

    # 强制设定一个测试区间（例如过去4小时）
    # 如果刚开盘没数据，就倒推一天
    start_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now.hour < 9:
        start_time -= datetime.timedelta(days=1)
        now = start_time.replace(hour=15, minute=0)

    curr = start_time
    end_time = now

    print(f"🕒 模拟时间范围: {start_time} -> {end_time}")
    print("⏳ 开始执行循环计算...")

    # === 性能计数器 ===
    total_start = time.time()
    loop_count = 0
    reset_queries()
    initial_query_count = len(connection.queries)

    # 复刻 views.py 中的循环逻辑
    while curr <= end_time:
        iter_start = time.time()

        # 核心瓶颈点
        calculate_asset_status(user, curr, use_minute_data=True)

        iter_end = time.time()
        loop_count += 1

        # 每10次打印一次进度
        if loop_count % 10 == 0:
            print(f"   -> 第 {loop_count} 次计算耗时: {(iter_end - iter_start) * 1000:.2f}ms")

        curr += datetime.timedelta(minutes=5)
        # 跳过午休逻辑
        if curr.hour == 11 and curr.minute > 30:
            curr = curr.replace(hour=13, minute=0)

    total_end = time.time()
    final_query_count = len(connection.queries)
    total_queries = final_query_count - initial_query_count
    total_time = total_end - total_start

    print("\n======== 📊 诊断报告 ========")
    print(f"1. 总耗时: {total_time:.4f} 秒")
    print(f"2. 循环次数: {loop_count} 次")
    print(f"3. 数据库查询总数: {total_queries} 次 😱")
    if loop_count > 0:
        print(f"4. 平均每点查询数: {total_queries / loop_count:.1f} 次")

    print("\n[🔍 SQL 频次分析 - Top 3]")
    from collections import Counter
    sql_list = [q['sql'].split('WHERE')[0] for q in connection.queries[initial_query_count:]]
    for sql, count in Counter(sql_list).most_common(3):
        print(f"  {count}次: {sql[:60]}...")

    print("\n✅ 诊断结束。如果查询数过百，说明存在严重的 N+1 问题。")


if __name__ == '__main__':
    run_diagnosis()