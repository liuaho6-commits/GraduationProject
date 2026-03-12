import requests
import json
import time


def test_backtest_api():
    print("=" * 60)
    print("开始验证回测 API 接口响应 (Evidence-First)")
    print("=" * 60)

    url = "http://127.0.0.1:8000/api/backtest/run/"

    payload = {
        "task_name": "API测试_双十一算力爆发期",
        "start_date": "2025-09-01",
        "end_date": "2025-11-30",
        "initial_capital": 500000.0
    }

    print(f"📡 正在向 {url} 发送 POST 请求...")
    print(f"📦 请求参数: {payload}")

    start_time = time.time()
    try:
        response = requests.post(url, json=payload)
        cost_time = time.time() - start_time

        print(f"\n⏱️ 接口耗时: {cost_time:.2f} 秒")
        print(f"📥 HTTP 状态码: {response.status_code}")

        # 解析返回的 JSON
        data = response.json()

        if data.get("code") == 200:
            print("\n✅ API 调用成功！核心返回数据如下：")
            res_data = data["data"]
            print(f"  -> 任务 ID: {res_data['task_id']}")
            print(f"  -> 任务名称: {res_data['task_name']}")
            print(f"  -> 年化收益率: {res_data['annualized_return'] * 100:.2f}%")
            print(f"  -> 最终资金: {res_data['final_capital']} 元")
            print(f"  -> 资金曲线数据量: {len(res_data['equity_curve'])} 天")

            print("\n📈 资金曲线(前3天):")
            print(json.dumps(res_data['equity_curve'][:3], indent=2, ensure_ascii=False))
        else:
            print(f"\n❌ API 返回了业务错误: {data['message']}")

    except requests.exceptions.ConnectionError:
        print("\n❌ 致命错误: 无法连接到 Django 服务器。")
        print("请确保你已经新开了一个终端，并运行了: python manage.py runserver")


if __name__ == "__main__":
    test_backtest_api()