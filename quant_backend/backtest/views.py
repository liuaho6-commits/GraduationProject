import traceback
from datetime import datetime
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model

from backtest.models import BacktestTask, BacktestResult
from backtest.engine import SparkBacktestEngine
# 🟢 引入基础信息模型，用于映射名称
from stocks.models import StockBasicInfo

User = get_user_model()


class RunBacktestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            task_name = data.get('task_name', f"多因子回测_{datetime.now().strftime('%m%d_%H%M')}")
            start_date = data.get('start_date', '2025-01-01')
            end_date = data.get('end_date', '2025-12-31')
            initial_capital = float(data.get('initial_capital', 100000.0))

            weight_mom = float(data.get('weight_mom', 0.5))
            weight_bias = float(data.get('weight_bias', 0.5))
            top_n = int(data.get('top_n', 2))

            user = User.objects.first()
            if not user:
                return JsonResponse({"code": 500, "message": "错误：系统无用户，请先创建管理员"})

            task = BacktestTask.objects.create(
                user=user,
                task_name=task_name,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                factor_weights={"momentum": weight_mom, "bias": weight_bias, "top_n": top_n},
                status='running'
            )

            engine = SparkBacktestEngine(task_id=task.id)
            sdf = engine.load_data(start_date, end_date)
            factor_sdf = engine.compute_multi_factors(sdf, weight_mom=weight_mom, weight_bias=weight_bias)
            portfolio_df = engine.simulate_strategy(factor_sdf, top_n=top_n)
            engine.stop()

            if portfolio_df.empty:
                raise ValueError("回测区间内未产生有效交易数据")

            final_equity_ratio = portfolio_df['equity'].iloc[-1]
            days = len(portfolio_df)

            # 计算累计总收益率
            total_return = final_equity_ratio - 1
            annualized_return = total_return * (252 / days) if days > 0 else 0

            equity_curve = []
            trade_records = []

            # 🟢 核心优化：一次性将所有股票代码和名称查出转化为字典，坚决避免N+1次查库拖慢回测！
            all_stocks_dict = dict(StockBasicInfo.objects.values_list('code', 'name'))

            for _, row in portfolio_df.iterrows():
                current_equity = round(float(row['equity']) * initial_capital, 2)
                daily_ret = round(float(row['portfolio_return']), 4)

                raw_stocks = row.get('buy_stocks', [])
                try:
                    stock_list = list(raw_stocks)
                    if len(stock_list) > 0:
                        parsed_list = []
                        for item in stock_list:
                            item_str = str(item)
                            # 🟢 解析 "代码:价格" 格式
                            if ":" in item_str:
                                code, price = item_str.split(":", 1)
                                name = all_stocks_dict.get(code, code) # 查不到就显示代码兜底
                                parsed_list.append(f"{name}({price})")
                            else:
                                parsed_list.append(item_str)
                        stocks_str = ", ".join(parsed_list)
                    else:
                        stocks_str = "空仓避险"
                except Exception:
                    stocks_str = "空仓避险"

                equity_curve.append({
                    "date": row['date'],
                    "equity": current_equity,
                    "daily_return": daily_ret
                })

                trade_records.append({
                    "date": row['date'],
                    "stocks": stocks_str,
                    "daily_return": daily_ret,
                    "equity": current_equity
                })

            BacktestResult.objects.create(
                task=task,
                annualized_return=annualized_return,
                equity_curve=equity_curve,
                positions_history=trade_records
            )

            task.status = 'completed'
            task.save()

            return JsonResponse({
                "code": 200,
                "data": {
                    "task_id": task.id,
                    "total_return": round(total_return, 4),
                    "annualized_return": round(annualized_return, 4),
                    "final_capital": equity_curve[-1]['equity'],
                    "equity_curve": equity_curve,
                    "trade_records": trade_records
                }
            })

        except Exception as e:
            if 'task' in locals():
                task.status = 'failed'
                task.error_message = str(e)
                task.save()
            traceback.print_exc()
            return JsonResponse({"code": 500, "message": f"引擎回测失败: {str(e)}"})