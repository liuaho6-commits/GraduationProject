import os
import sys
import django
from datetime import datetime

# ==========================================
# 1. 初始化 Django 环境
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

# ==========================================
# 2. 诊断逻辑
# ==========================================
from stocks.models import StockMinuteData
from trade.time_utils import get_mock_now
from django.utils import timezone


def run_debug():
    print("--------------------------------------------------")
    print("🔍 数据诊断工具 v2.0")

    # --- A. 获取系统时间 ---
    mock_now = get_mock_now()
    if timezone.is_aware(mock_now):
        mock_naive = timezone.make_naive(mock_now)
    else:
        mock_naive = mock_now

    print(f"当前系统 MockTime: {mock_now}")

    # --- B. 确定股票代码格式 (核心修复) ---
    user_input_code = 'sh.688256'
    target_code = user_input_code

    # 1. 尝试直接查询
    exists = StockMinuteData.objects.filter(code=target_code).exists()

    if not exists:
        print(f"\n⚠️ 警告: 数据库中未找到代码 '{user_input_code}'")

        # 2. 尝试去掉前缀查询 (例如 'sh.688256' -> '688256')
        stripped_code = user_input_code.split('.')[-1]
        if StockMinuteData.objects.filter(code=stripped_code).exists():
            print(f"✅ 发现匹配: 数据库实际存储格式为 '{stripped_code}' (无前缀)")
            target_code = stripped_code
        else:
            # 3. 实在找不到，打印数据库里到底有什么
            print("❌ 错误: 数据库里找不到该股票数据。")
            print("👀 数据库中存在的代码示例 (前5个):")
            sample_codes = StockMinuteData.objects.values_list('code', flat=True).distinct()[:5]
            print(f"   {list(sample_codes)}")
            print("请检查爬虫入库逻辑或更换测试代码。")
            return

    print(f"\n👉 锁定目标股票: {target_code}")

    # --- C. 获取数据进行诊断 ---
    # 使用 contains 宽松匹配日期，防止时区导致日期判定偏移
    target_date_str = mock_naive.strftime('%Y-%m-%d')
    print(f"正在查询日期: {target_date_str} ...")

    all_data = list(StockMinuteData.objects.filter(
        code=target_code,
        date__contains=target_date_str
    ).order_by('date'))

    print(f"今日数据总量: {len(all_data)} 条")

    if not all_data:
        print("❌ 今日无数据。")
        return

    # --- D. 分析“悬空/未来”数据 ---
    future_data = []

    for item in all_data:
        # 统一转为 Naive 时间比对
        item_time = item.date
        if timezone.is_aware(item_time):
            item_time = timezone.make_naive(item_time)

        if item_time > mock_naive:
            future_data.append(item)

    print(f"\n-------- 诊断结果 --------")
    print(f"✅ 有效历史数据 (<= MockTime): {len(all_data) - len(future_data)} 条")
    print(f"⚠️ 未来数据 (> MockTime): {len(future_data)} 条")

    if future_data:
        first_fut = future_data[0]
        last_fut = future_data[-1]
        print(f"   -> 未来数据时间范围: {first_fut.date} ~ {last_fut.date}")
        print(f"   -> 第一条未来数据 Volume: {first_fut.volume}")

        # 核心判断
        if first_fut.volume == 0:
            print("\n💡 根源确认: 数据库包含了预填充的未来时间点 (Volume=0)。")
            print("   问题: 前端 ECharts 把这些 0 值渲染出来了，导致线‘掉下来’或‘悬空’。")
            print("   修复: 必须在 views.py 中过滤掉 `date > mock_now` 的数据。")
        else:
            print("\n🔴 严重异常: 未来数据竟然有成交量！请检查数据生成脚本。")
    else:
        print("\n✅ 正常: 后端未返回未来数据。如果图表仍有问题，请检查前端 ECharts 配置。")


if __name__ == "__main__":
    run_debug()