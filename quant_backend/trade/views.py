from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from django.apps import apps
from .models import Strategy, Order, Position, DailyPerformance, SystemSettings
from stocks.models import StockMinuteData, StockData
from .serializers import StrategySerializer, OrderSerializer, PositionSerializer
from .time_utils import get_mock_now
import datetime
from decimal import Decimal
from collections import defaultdict
import bisect


# ================= 系统时间接口 =================
class SystemTimeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = get_mock_now()
        return Response(
            {'code': 200, 'data': {'system_time': now.strftime('%Y-%m-%d %H:%M:%S'), 'timestamp': now.timestamp()}})


# ================= 持仓同步工具 =================
def sync_positions(user):
    """
    根据订单记录强制校准持仓表，消除数据不一致
    """
    now = get_mock_now()
    if timezone.is_naive(now): now = timezone.make_aware(now)

    # 获取所有已成交订单
    orders = Order.objects.filter(user=user, status='filled', order_time__lte=now).order_by('order_time')

    # 内存计算真实持仓
    real_holdings = {}
    for order in orders:
        vol = int(order.volume)
        if order.direction == 'buy':
            real_holdings[order.stock_code] = real_holdings.get(order.stock_code, 0) + vol
        elif order.direction == 'sell':
            current = real_holdings.get(order.stock_code, 0)
            real_holdings[order.stock_code] = max(0, current - vol)

    # 写入数据库
    for code, vol in real_holdings.items():
        if vol > 0:
            Position.objects.update_or_create(user=user, stock_code=code, defaults={'volume': vol})
        else:
            Position.objects.filter(user=user, stock_code=code).update(volume=0)

    # 清理数据库中残留的幽灵持仓
    all_db_positions = Position.objects.filter(user=user)
    for pos in all_db_positions:
        if pos.stock_code not in real_holdings or real_holdings[pos.stock_code] == 0:
            if pos.volume != 0:
                pos.volume = 0
                pos.save()


# ================= 资产计算逻辑 (单点计算兜底用) =================
def calculate_asset_status(user, target_time):
    """
    计算指定时间点的资产状态 (用于日线图补全今日数据)
    """
    if timezone.is_naive(target_time): target_time = timezone.make_aware(target_time)
    UserProfile = apps.get_model('users', 'UserProfile')
    try:
        profile = UserProfile.objects.get(user=user)
        cash_base = profile.initial_capital if profile.initial_capital > 0 else Decimal('200000.0')
    except:
        cash_base = Decimal('200000.0')

    cash = cash_base
    holdings = {}

    orders = Order.objects.filter(user=user, status='filled', order_time__lte=target_time).order_by('order_time')

    for order in orders:
        price = Decimal(str(order.price))
        vol = int(order.volume)
        cost = price * Decimal(vol)
        if order.direction == 'buy':
            cash -= cost
            holdings[order.stock_code] = holdings.get(order.stock_code, 0) + vol
        elif order.direction == 'sell':
            cash += cost
            holdings[order.stock_code] = max(0, holdings.get(order.stock_code, 0) - vol)

    market_value = Decimal('0.0')

    for code, vol in holdings.items():
        if vol <= 0: continue
        price = Decimal('0.0')
        can_use_daily = target_time.hour >= 15

        daily_row = None
        if can_use_daily:
            daily_row = StockData.objects.filter(code=code, date=target_time.date()).first()

        if daily_row:
            price = Decimal(str(daily_row.close))
        else:
            day_start = target_time.replace(hour=0, minute=0, second=0)
            minute_row = StockMinuteData.objects.filter(code=code, date__lte=target_time, date__gte=day_start).order_by(
                '-date').first()
            if minute_row:
                price = Decimal(str(minute_row.close))
            else:
                prev_daily = StockData.objects.filter(code=code, date__lt=target_time.date()).order_by('-date').first()
                if prev_daily:
                    price = Decimal(str(prev_daily.close))

        market_value += Decimal(vol) * price

    return cash + market_value, market_value, cash, Decimal('0.0'), ""


# ================= 收益表现 (混合模式：日线查库/分时实时) =================
# ================= 收益表现 (混合模式：日线查库/分时实时) =================
class PerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query_type = request.GET.get('type', 'daily')
        now = get_mock_now()
        if timezone.is_naive(now): now = timezone.make_aware(now)

        user = request.user
        UserProfile = apps.get_model('users', 'UserProfile')
        DailyPerformance = apps.get_model('trade', 'DailyPerformance')

        # 强制获取最新状态
        profile = UserProfile.objects.get(user=user)
        current_balance = profile.balance  # 这是绝对真理
        initial_capital = profile.initial_capital if profile.initial_capital > 0 else Decimal('200000.0')

        data = []

        # 🟢 场景 A: 分时图 (日内收益) - 维持实时计算 (倒推锚定法)
        if query_type == 'intraday':
            effective_now = now

            # 1. 如果当前时间早于 09:00，则退回到上一个交易日的 15:00
            if effective_now.hour < 9:
                effective_now -= datetime.timedelta(days=1)
                while effective_now.weekday() >= 5:  # 跳过周末
                    effective_now -= datetime.timedelta(days=1)
                effective_now = effective_now.replace(hour=15, minute=0, second=0, microsecond=0)

            # 🟢 核心修复：基于数据库事实的节假日/非交易日终极判定！
            day_start = effective_now.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = effective_now.replace(hour=23, minute=59, second=59, microsecond=999999)

            # 去数据库看看今天到底有没有产生 5 分钟线数据
            has_market_data = StockMinuteData.objects.filter(
                date__gte=day_start,
                date__lte=day_end
            ).exists()

            if not has_market_data:
                # 只要数据库没数据，不管今天是周几，绝对是休市日/节假日！
                # 直接返回空数组，前端收到后会自动停止画线并开启遮罩
                return Response({'code': 200, 'data': []})

            # 2. 锚定有效当天的 09:30 为起点
            start = effective_now.replace(hour=9, minute=30, second=0, microsecond=0)

            # 3. 如果时间超过了 15:00，将计算无情截断在 15:00
            if effective_now.hour >= 15:
                effective_now = effective_now.replace(hour=15, minute=0, second=0, microsecond=0)

            # 处于 09:00 - 09:30 之间时，无数据，前端显示休市遮罩
            if effective_now < start:
                return Response({'code': 200, 'data': []})

            # 4. 确定基准（昨收资产）：坚决和 UserInfoView (顶部卡片) 保持同一个数据源！
            yesterday_perf = DailyPerformance.objects.filter(
                user=user, date__lt=now.date()
            ).order_by('-date').first()

            if yesterday_perf:
                base_assets = Decimal(str(yesterday_perf.total_assets))
            else:
                base_assets = initial_capital

            # 5. 获取今日所有订单
            orders_today = Order.objects.filter(
                user=user,
                status='filled',
                order_time__gte=start,
                order_time__lte=effective_now
            ).order_by('order_time')

            # 6. 倒推计算
            cash_change_today = Decimal('0.0')
            for o in orders_today:
                cost = Decimal(str(o.price)) * Decimal(o.volume)
                if o.direction == 'buy':
                    cash_change_today -= cost
                else:
                    cash_change_today += cost

            start_cash = current_balance - cash_change_today

            current_positions_qs = Position.objects.filter(user=user, volume__gt=0)
            current_holdings = {p.stock_code: p.volume for p in current_positions_qs}

            start_holdings = current_holdings.copy()
            for o in reversed(orders_today):
                if o.direction == 'buy':
                    start_holdings[o.stock_code] = start_holdings.get(o.stock_code, 0) - o.volume
                else:
                    start_holdings[o.stock_code] = start_holdings.get(o.stock_code, 0) + o.volume

            start_holdings = {k: v for k, v in start_holdings.items() if v > 0}

            active_stocks = set(start_holdings.keys())
            for o in orders_today:
                active_stocks.add(o.stock_code)

            price_cache = defaultdict(list)
            last_prices = {}

            if active_stocks:
                for code in active_stocks:
                    last_daily = StockData.objects.filter(code=code, date__lt=start.date()).order_by('-date').first()
                    last_prices[code] = Decimal(str(last_daily.close)) if last_daily else Decimal('0.0')

                minutes = StockMinuteData.objects.filter(
                    code__in=active_stocks,
                    date__gte=start,
                    date__lte=effective_now
                ).order_by('date').values('code', 'date', 'close')

                for m in minutes:
                    dt = m['date']
                    if timezone.is_naive(dt): dt = timezone.make_aware(dt)
                    price_cache[m['code']].append((dt, Decimal(str(m['close']))))

            curr = start
            curr_cash = start_cash
            curr_holdings = defaultdict(int, start_holdings)
            order_idx = 0
            num_orders = len(orders_today)

            while curr <= effective_now:
                while order_idx < num_orders:
                    o = orders_today[order_idx]
                    o_time = o.order_time if timezone.is_aware(o.order_time) else timezone.make_aware(o.order_time)
                    if o_time > curr: break

                    cost = Decimal(str(o.price)) * Decimal(o.volume)
                    if o.direction == 'buy':
                        curr_cash -= cost
                        curr_holdings[o.stock_code] += o.volume
                    else:
                        curr_cash += cost
                        curr_holdings[o.stock_code] -= o.volume
                    order_idx += 1

                mv = Decimal('0.0')
                for code, vol in curr_holdings.items():
                    if vol <= 0: continue
                    price = last_prices.get(code, Decimal(0))
                    data_list = price_cache.get(code)
                    if data_list:
                        idx = bisect.bisect_right(data_list, (curr, Decimal('99999999')))
                        if idx > 0:
                            price = data_list[idx - 1][1]
                            last_prices[code] = price
                    mv += Decimal(vol) * price

                curr_assets = curr_cash + mv
                profit = curr_assets - base_assets
                rate = (profit / base_assets * 100) if base_assets > 0 else 0

                data.append({
                    'time': curr.strftime('%H:%M'),
                    'total_return_rate': round(float(rate), 2),
                    'profit': round(float(profit), 2)
                })

                curr += datetime.timedelta(minutes=5)
                if curr.hour == 11 and curr.minute > 30:
                    curr = curr.replace(hour=13, minute=0)

            # 强制缝合当前最新点
            profile.update_asset_cache()
            final_profit = profile.last_total_assets - base_assets
            final_rate = (final_profit / base_assets * 100) if base_assets > 0 else 0

            current_time_str = effective_now.strftime('%H:%M')
            if data and data[-1]['time'] == current_time_str:
                data[-1]['profit'] = round(float(final_profit), 2)
                data[-1]['total_return_rate'] = round(float(final_rate), 2)
            else:
                data.append({
                    'time': current_time_str,
                    'total_return_rate': round(float(final_rate), 2),
                    'profit': round(float(final_profit), 2)
                })

        # 🟢 场景 B: 日线图
        else:
            history = DailyPerformance.objects.filter(user=user).order_by('date')

            for h in history:
                profit_calc = float(h.total_assets) - float(initial_capital)

                data.append({
                    'date': h.date.strftime('%Y-%m-%d'),
                    'total_return_rate': round(h.total_return_rate, 2),
                    'profit': round(profit_calc, 2),
                    'day_profit': round(float(h.day_profit), 2),
                    'total_assets': round(float(h.total_assets), 2)
                })

            today_str = now.date().strftime('%Y-%m-%d')
            has_today = any(d['date'] == today_str for d in data)

            if not has_today:
                assets, _, _, _, _ = calculate_asset_status(request.user, now)

                total_profit = assets - initial_capital
                rate = (total_profit / initial_capital) * 100

                prev_assets = Decimal(str(data[-1]['total_assets'])) if data else initial_capital
                day_profit = assets - prev_assets

                data.append({
                    'date': today_str,
                    'total_return_rate': round(float(rate), 2),
                    'profit': round(float(total_profit), 2),
                    'day_profit': round(float(day_profit), 2),
                    'total_assets': round(float(assets), 2)
                })

        return Response({'code': 200, 'data': data})

# ================= 资金划转 =================
class FundTransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            amount = Decimal(str(request.data.get('amount', 0)))
            with transaction.atomic():
                UserProfile = apps.get_model('users', 'UserProfile')
                profile = UserProfile.objects.select_for_update().get(user=request.user)
                if amount < 0 and profile.balance < abs(amount):
                    return Response({'code': 400, 'msg': '余额不足'})
                if profile.initial_capital <= 0: profile.initial_capital = Decimal('200000.0')

                profile.balance += amount
                profile.initial_capital += amount
                profile.save()
            return Response({'code': 200, 'msg': '操作成功', 'data': {'balance': float(profile.balance)}})
        except Exception as e:
            return Response({'code': 500, 'msg': str(e)})


# ================= 其他视图 =================
# ================= 策略管理接口 =================
class StrategyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取用户的策略列表"""
        strats = Strategy.objects.filter(user=request.user).order_by('-create_time')
        return Response({'code': 200, 'data': StrategySerializer(strats, many=True).data})

    def post(self, request):
        """创建或修改策略 (包含启动/停止状态切换)"""
        data = request.data
        strategy_id = data.get('id')

        try:
            if strategy_id:
                # 1. 更新已存在的策略 (例如前端点击了"启动"或"停止")
                strategy = Strategy.objects.get(id=strategy_id, user=request.user)
                if 'status' in data:
                    strategy.status = data['status']
                if 'code' in data:
                    strategy.code = data['code']
                if 'stock_pool' in data:
                    strategy.stock_pool = data['stock_pool']
                if 'name' in data:
                    strategy.name = data['name']
                strategy.save()
                return Response({'code': 200, 'msg': f'策略 [{strategy.name}] 更新成功'})
            else:
                # 2. 创建新策略
                strategy = Strategy.objects.create(
                    user=request.user,
                    name=data.get('name', '新建量化策略'),
                    code=data.get('code', ''),
                    stock_pool=data.get('stock_pool', ''),
                    status='stopped'  # 默认停止，防止意外运行
                )
                return Response({'code': 200, 'msg': '策略创建成功', 'data': {'id': strategy.id}})

        except Strategy.DoesNotExist:
            return Response({'code': 404, 'msg': '策略不存在或无权操作'})
        except Exception as e:
            return Response({'code': 500, 'msg': f'策略操作失败: {str(e)}'})

    def delete(self, request):
        """删除策略"""
        strategy_id = request.data.get('id') or request.query_params.get('id')
        if not strategy_id:
            return Response({'code': 400, 'msg': '缺少策略 ID'})
        try:
            strategy = Strategy.objects.get(id=strategy_id, user=request.user)
            strategy.delete()
            return Response({'code': 200, 'msg': '策略已删除'})
        except Strategy.DoesNotExist:
            return Response({'code': 404, 'msg': '策略不存在'})

class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by('-order_time')[:50]
        return Response({'code': 200, 'data': OrderSerializer(orders, many=True).data})


class PlaceOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        try:
            sync_positions(user)
        except Exception as e:
            print(f"持仓同步警告: {e}")

        data = request.data
        try:
            with transaction.atomic():
                UserProfile = apps.get_model('users', 'UserProfile')
                profile = UserProfile.objects.select_for_update().get(user=user)

                price = Decimal(str(data.get('price', 0)))
                vol = int(data.get('volume', 0))
                code = data.get('stock_code').strip()
                direction = data.get('direction')

                if direction == 'buy':
                    cost = price * Decimal(vol)
                    if profile.balance < cost: return Response({'code': 400, 'msg': '余额不足'})
                    profile.balance -= cost
                    profile.save()
                    pos, _ = Position.objects.get_or_create(user=user, stock_code=code)
                    # 均价安全计算
                    curr_vol = Decimal(pos.volume)
                    curr_avg = Decimal(str(pos.avg_price or 0))
                    new_cost = curr_avg * curr_vol + price * Decimal(vol)
                    new_vol = curr_vol + Decimal(vol)
                    pos.avg_price = float(new_cost / new_vol) if new_vol > 0 else 0.0
                    pos.volume += vol
                    pos.save()
                elif direction == 'sell':
                    pos = Position.objects.filter(user=user, stock_code=code).first()
                    if not pos: return Response({'code': 400, 'msg': f'未持有该股票: {code}'})
                    if pos.volume < vol: return Response({'code': 400, 'msg': f'持仓不足 (可用: {pos.volume})'})
                    pos.volume -= vol
                    pos.save()
                    profile.balance += price * Decimal(vol)
                    profile.save()

                mock_now = get_mock_now()
                if timezone.is_naive(mock_now): mock_now = timezone.make_aware(mock_now)
                Order.objects.create(user=user, stock_code=code, direction=direction, price=float(price), volume=vol,
                                     status='filled', order_time=mock_now)
                profile.update_asset_cache()
            return Response({'code': 200, 'msg': '交易成功'})
        except Exception as e:
            return Response({'code': 500, 'msg': f'交易失败: {str(e)}'})


# ================= 持仓列表视图 =================
class PositionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            sync_positions(request.user)
        except:
            pass

        positions = Position.objects.filter(user=request.user, volume__gt=0)
        results = []
        now = get_mock_now()
        if timezone.is_naive(now): now = timezone.make_aware(now)

        for pos in positions:
            price = Decimal('0.0')
            can_use_daily = now.hour >= 15
            daily_row = None
            if can_use_daily:
                daily_row = StockData.objects.filter(code=pos.stock_code, date=now.date()).first()

            if daily_row:
                price = Decimal(str(daily_row.close))
            else:
                day_start = now.replace(hour=0, minute=0, second=0)
                minute_row = StockMinuteData.objects.filter(
                    code=pos.stock_code, date__lte=now, date__gte=day_start
                ).order_by('-date').first()
                if minute_row:
                    price = Decimal(str(minute_row.close))
                else:
                    prev_daily = StockData.objects.filter(code=pos.stock_code, date__lt=now.date()).order_by(
                        '-date').first()
                    if prev_daily:
                        price = Decimal(str(prev_daily.close))
                    else:
                        price = Decimal(str(pos.avg_price or 0))

            market_value = price * Decimal(pos.volume)
            cost = Decimal(str(pos.avg_price or 0)) * Decimal(pos.volume)
            profit = market_value - cost
            profit_rate = (profit / cost * 100) if cost > 0 else 0

            data = PositionSerializer(pos).data
            data['current_price'] = float(price)
            data['market_value'] = float(market_value)
            data['profit'] = float(profit)
            data['profit_rate'] = float(profit_rate)
            results.append(data)

        return Response({'code': 200, 'data': results})


# ================= 持仓详情视图 (已补回) =================
class PositionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, stock_code):
        try:
            sync_positions(request.user)
        except:
            pass

        code = stock_code.strip()
        pos = Position.objects.filter(user=request.user, stock_code=code).first()
        return Response({
            'code': 200,
            'data': {
                'stock_code': code,
                'volume': pos.volume if pos else 0
            }
        })


# ================= 上帝控制台接口 =================
class SystemControlView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        action = request.data.get('action')
        try:
            settings = SystemSettings.get_settings()
            if action == 'set_speed':
                speed = float(request.data.get('speed', 1.0))
                settings.time_speed = speed
                settings.save()
                return Response({'code': 200, 'msg': f'流速已调整为 {speed}x', 'data': {'speed': speed}})
            elif action == 'set_time':
                target_time_str = request.data.get('target_time')
                if not target_time_str: return Response({'code': 400, 'msg': '缺少 target_time'})

                import datetime
                if len(target_time_str) <= 10: target_time_str += " 09:30:00"
                new_time = datetime.datetime.fromisoformat(target_time_str)
                if timezone.is_naive(new_time): new_time = timezone.make_aware(new_time)

                settings.current_mock_time = new_time
                settings.save()
                settings.hard_reset_world()
                return Response({'code': 200, 'msg': f'时间已跃迁至 {new_time}', 'data': {'current_time': new_time}})
            else:
                return Response({'code': 400, 'msg': '未知操作'})
        except Exception as e:
            return Response({'code': 500, 'msg': str(e)})

    def get(self, request):
        settings = SystemSettings.get_settings()
        return Response({
            'code': 200,
            'data': {
                'current_time': settings.current_mock_time,
                'time_speed': settings.time_speed,
                'skip_non_trading': settings.skip_non_trading
            }
        })