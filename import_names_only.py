import os
import sys
import django
import pandas as pd

# ================= 1. 环境配置 (照旧) =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_PATH = os.path.join(BASE_DIR, "quant_backend")
sys.path.insert(0, PROJECT_PATH)
sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "quant_backend.settings")

try:
    django.setup()
    print("✅ Django 环境加载成功！")
except Exception as e:
    # 尝试扁平结构兼容
    try:
        os.environ["DJANGO_SETTINGS_MODULE"] = "settings"
        django.setup()
        print("✅ Django 环境加载成功 (Settings模式)！")
    except Exception as e2:
        print(f"❌ 环境加载失败: {e}")
        sys.exit(1)

# 导入模型
try:
    from stocks.models import StockBasicInfo
except ImportError:
    from quant_backend.stocks.models import StockBasicInfo


# ================= 2. 导入逻辑 =================

def run_import():
    print("🚀 开始写入股票名称...")

    # --- 方案 A: 手动写入核心股票 (保底，确保这两只一定有) ---
    # 既然你做毕设主要演示这两只，直接写死最稳
    manual_stocks = [
        {"code": "sh.601288", "name": "农业银行", "industry": "银行"},
        {"code": "sz.300308", "name": "中际旭创", "industry": "通信设备"},
        # 如果你的数据库里存的代码没有 sh/sz 前缀，请把上面的 'sh.' 去掉
        # 下面添加无前缀版本，防止匹配不上
        {"code": "601288", "name": "农业银行", "industry": "银行"},
        {"code": "300308", "name": "中际旭创", "industry": "通信设备"},
    ]

    print(f"写入核心关注股票 ({len(manual_stocks)} 条)...")
    for item in manual_stocks:
        # update_or_create: 如果存在就更新名字，不存在就创建
        StockBasicInfo.objects.update_or_create(
            code=item['code'],
            defaults={'name': item['name'], 'industry': item['industry']}
        )
    print("✅ 核心股票写入完成！")

    # --- 方案 B: 尝试从 stock_basic_info.csv 批量导入 ---
    csv_path = os.path.join(BASE_DIR, "raw_data", "stock_basic_info.csv")

    if os.path.exists(csv_path):
        print(f"\n发现列表文件: {csv_path}，正在批量导入...")
        try:
            df = pd.read_csv(csv_path)
            # 简单的列名清洗
            df.rename(columns={'代码': 'code', 'code': 'code',
                               '名称': 'name', 'name': 'name', 'code_name': 'name'}, inplace=True)

            objs = []
            # 咱们只导入有的列
            for _, row in df.iterrows():
                code = str(row['code'])
                name = str(row['name'])
                if code and name:
                    objs.append(StockBasicInfo(code=code, name=name))

            # 批量写入
            StockBasicInfo.objects.bulk_create(objs, ignore_conflicts=True)
            print(f"✅ 批量导入完成！共 {len(objs)} 条。")

        except Exception as e:
            print(f"⚠️ 批量导入出错 (不影响核心股票): {e}")
    else:
        print("\n⚠️ 未找到 stock_basic_info.csv，仅写入了核心股票。(这不影响你后续实验)")


if __name__ == "__main__":
    run_import()

    # 验证一下
    count = StockBasicInfo.objects.count()
    print(f"\n📊 当前数据库中共有 {count} 个股票名称信息。")