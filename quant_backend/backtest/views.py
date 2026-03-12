import traceback
from datetime import datetime
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model

from backtest.models import BacktestTask, BacktestResult
from backtest.engine import SparkBacktestEngine

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

            # 【新增】接收前端传来的动态因子参数
            weight_mom = float(data.get('weight_mom', 0.5))
            weight_bias = float(data.get('weight_bias', 0.5))
            top_n = int(data.get('top_n', 2))

            user = User.objects.first()
            if not user:
                return JsonResponse({"code": 500, "message": "错误：请先创建超级管理员"})

            # 记录因子的配置到任务中
            factor_weights = {
                "momentum": weight_mom,
                "bias": weight_bias,
                "top_n_select": top_n
            }

            task = BacktestTask.objects.create(
                user=user,
                task_name=task_name,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                factor_weights=factor_weights,
                status='running'
            )

            # 调用升级后的多因子引擎
            engine = SparkBacktestEngine(task_id=task.id)
            sdf = engine.load_data(start_date, end_date)

            # 传入权重
            factor_sdf = engine.compute_multi_factors(sdf, weight_mom=weight_mom, weight_bias=weight_bias)

            # 传入选股数量
            portfolio_df = engine.simulate_strategy(factor_sdf, top_n=top_n)

            engine.stop()

            if portfolio_df.empty:
                raise ValueError("回测区间内未产生有效交易数据")

            portfolio_df = portfolio_df.fillna(0)
            final_equity_ratio = portfolio_df['equity'].iloc[-1]

            days = len(portfolio_df)
            annualized_return = (final_equity_ratio - 1) * (252 / days) if days > 0 else 0

            equity_curve = []
            for _, row in portfolio_df.iterrows():
                equity_curve.append({
                    "date": row['date'],
                    "equity": round(row['equity'] * initial_capital, 2),
                    "daily_return": round(row['portfolio_return'], 4)
                })

            BacktestResult.objects.create(
                task=task,
                annualized_return=annualized_return,
                equity_curve=equity_curve
            )

            task.status = 'completed'
            task.save()

            return JsonResponse({
                "code": 200,
                "message": "回测成功",
                "data": {
                    "task_id": task.id,
                    "task_name": task.task_name,
                    "annualized_return": round(annualized_return, 4),
                    "final_capital": equity_curve[-1]['equity'],
                    "equity_curve": equity_curve
                }
            })

        except Exception as e:
            if 'task' in locals():
                task.status = 'failed'
                task.error_message = str(e)
                task.save()
            if 'engine' in locals():
                engine.stop()
            traceback.print_exc()
            return JsonResponse({"code": 500, "message": f"引擎回测失败: {str(e)}"})