import os
import sys
import django
from decimal import Decimal

# 设置 Django 环境
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

from backtest.engine import SparkBacktestEngine


def test_engine():
    print("=" * 60)
    print("开始验证 SparkBacktestEngine 回测引擎 (Evidence-First)")
    print("=" * 60)

    # 假设前端传来了回测区间
    start_date = '2025-01-01'
    end_date = '2025-12-31'

    print("[1/4] 初始化引擎...")
    engine = SparkBacktestEngine()

    try:
        print(f"[2/4] 加载 {start_date} 至 {end_date} 的数据...")
        sdf = engine.load_data(start_date, end_date)
        print(f"  -> 数据加载成功！")

        print("[3/4] 计算因子分布矩阵...")
        factor_sdf = engine.compute_momentum_factor(sdf)
        print(f"  -> 因子计算成功！")

        print("[4/4] 模拟策略并生成资金曲线...")
        portfolio_df = engine.simulate_strategy(factor_sdf)

        print("\n✅ 回测引擎跑通！输出资金曲线前 5 天数据：")
        print(portfolio_df.head(5).to_string(index=False))

        print("\n✅ 输出资金曲线最后 5 天数据 (查看最终净值)：")
        print(portfolio_df.tail(5).to_string(index=False))

        final_equity = portfolio_df['equity'].iloc[-1]
        print(f"\n📊 策略区间收益率: {(final_equity - 1) * 100:.2f}%")

    except Exception as e:
        print(f"❌ 运行报错: {e}")
    finally:
        engine.stop()
        print("\n引擎已安全关闭。")
        print("=" * 60)


if __name__ == "__main__":
    test_engine()