from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from django.apps import apps
from .models import Strategy, Order, Position
from stocks.models import StockMinuteData, StockData
from .serializers import StrategySerializer, OrderSerializer
from .time_utils import get_mock_now
import datetime
from decimal import Decimal


# ================= 系统时间接口 =================
class SystemTimeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = get_mock_now()
        return Response(
            {'code': 200, 'data': {'system_time': now.strftime('%Y-%m-%d %H:%M:%S'), 'timestamp': now.timestamp()}})


# ================= 持仓同步工具 =================
def sync_positions(user):
    now = get_mock_now()
    if timezone.is_naive(now): now = timezone.make_aware(now)
    orders = Order.objects.filter(user=user, status='filled', order_time__lte=now).order_by('order_time')
    real_holdings = {}
    for order in orders:
        vol = int(order.volume)
        if order.direction == 'buy':
            real_holdings[order.stock_code] = real_holdings.get(order.stock_code, 0) + vol
        elif order.direction == 'sell':
            current = real_holdings.get(order.stock_code, 0)
            real_holdings[order.stock_code] = max(0, current - vol)

    for code, vol in real_holdings.items():
        if vol > 0:
            Position.objects.update_or_create(user=user, stock_code=code, defaults={'volume': vol})
        else:
            Position.objects.filter(user=user, stock_code=code).update(volume=0)

    all_db_positions = Position.objects.filter(user=user)
    for pos in all_db_positions:
        if pos.stock_code not in real_holdings:
            pos.volume = 0
            pos.save()


# ================= 资产计算逻辑 =================
def calculate_asset_status(user, target_time, use_minute_data=False):
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
    avg_costs = {}
    temp_holdings = {}

    for order in orders:
        price = Decimal(str(order.price))
        vol = int(order.volume)
        cost = price * Decimal(vol)
        if order.direction == 'buy':
            cash -= cost
            holdings[order.stock_code] = holdings.get(order.stock_code, 0) + vol

            old_vol = temp_holdings.get(order.stock_code, 0)
            old_cost = avg_costs.get(order.stock_code, Decimal(0))
            if (old_vol + vol) > 0:
                avg_costs[order.stock_code] = (old_cost * old_vol + price * vol) / (old_vol + vol)
                temp_holdings[order.stock_code] = old_vol + vol
        elif order.direction == 'sell':
            cash += cost
            holdings[order.stock_code] = max(0, holdings.get(order.stock_code, 0) - vol)
            temp_holdings[order.stock_code] = max(0, temp_holdings.get(order.stock_code, 0) - vol)

    market_value = Decimal('0.0')
    current_holdings_cost = Decimal('0.0')

    # 🔴 调试价格查找
    debug_price_info = ""

    for code, vol in holdings.items():
        if vol <= 0: continue
        current_holdings_cost += avg_costs.get(code, Decimal(0)) * vol
        price = Decimal('0.0')

        # 严格限制：15:00前禁止偷看当日StockData
        can_use_daily = target_time.hour >= 15

        daily_row = None
        if can_use_daily:
            daily_row = StockData.objects.filter(code=code, date=target_time.date()).first()

        if daily_row:
            price = Decimal(str(daily_row.close))
            debug_price_info = f"{code}: {price} (Daily)"
        else:
            day_start = target_time.replace(hour=0, minute=0, second=0)
            minute_row = StockMinuteData.objects.filter(code=code, date__lte=target_time, date__gte=day_start).order_by(
                '-date').first()
            if minute_row:
                price = Decimal(str(minute_row.close))
                debug_price_info = f"{code}: {price} (Minute {minute_row.date.strftime('%H:%M')})"
            else:
                prev_daily = StockData.objects.filter(code=code, date__lt=target_time.date()).order_by('-date').first()
                if prev_daily:
                    price = Decimal(str(prev_daily.close))
                    debug_price_info = f"{code}: {price} (PrevDaily)"

        market_value += Decimal(vol) * price

    return cash + market_value, market_value, cash, current_holdings_cost, debug_price_info


# ================= 收益表现 (带调试) =================
class PerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query_type = request.GET.get('type', 'daily')
        now = get_mock_now()
        if timezone.is_naive(now): now = timezone.make_aware(now)
        data = []

        UserProfile = apps.get_model('users', 'UserProfile')
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.initial_capital <= 0:
                profile.initial_capital = Decimal('200000.0')
                profile.save()
            initial_capital = profile.initial_capital
        except:
            initial_capital = Decimal('200000.0')

        if query_type == 'intraday':
            start = now.replace(hour=9, minute=30, second=0, microsecond=0)
            yesterday_close_time = (start - datetime.timedelta(days=1)).replace(hour=15, minute=0, second=0)

            # 获取昨收状态
            base_assets, _, _, base_invested, _ = calculate_asset_status(request.user, yesterday_close_time)
            if base_assets <= 0: base_assets = initial_capital

            curr = start
            print(f"\n======== [DEBUG INTRADAY] {now.date()} ========")

            while curr <= now:
                # 获取当前状态
                # 注意：这里我们接收第4个参数 curr_invested
                curr_assets, _, _, curr_invested, price_info = calculate_asset_status(request.user, curr, True)

                profit = curr_assets - base_assets

                # 🟢 修正分母：使用当前投入成本 (curr_invested)
                # 如果没持仓，分母退化为 initial_capital (避免除以0)
                denominator = curr_invested if curr_invested > 0 else initial_capital

                rate = (profit / denominator) * 100

                # 🔴 打印调试日志 (只打印整点，防止刷屏)
                if curr.minute == 0 or curr.minute == 30:
                    print(f"时间: {curr.strftime('%H:%M')} | 价格源: {price_info}")
                    print(f"   盈亏: {profit:.2f} (Curr: {curr_assets:.2f} - Base: {base_assets:.2f})")
                    print(f"   分母: {denominator:.2f} (投入成本)")
                    print(f"   收益率: {rate:.4f}%")
                    print("------------------------------------------------")

                data.append({'time': curr.strftime('%H:%M'), 'total_return_rate': round(float(rate), 2),
                             'profit': round(float(profit), 2)})

                curr += datetime.timedelta(minutes=5)
                if curr.hour == 11 and curr.minute > 30: curr = curr.replace(hour=13, minute=0)
            print("================================================\n")
        else:
            # 日线逻辑
            start_date = (now - datetime.timedelta(days=30)).date()
            curr = start_date
            prev_assets = initial_capital
            while curr <= now.date():
                target = datetime.datetime.combine(curr, datetime.time(15, 0))
                if timezone.is_naive(target): target = timezone.make_aware(target)
                if target > now: target = now

                assets, _, _, invested_cost, _ = calculate_asset_status(request.user, target)
                total_profit = assets - initial_capital

                # 🟢 日线分母修正
                denominator = invested_cost if invested_cost > 0 else initial_capital
                rate = (total_profit / denominator) * 100

                data.append({
                    'date': curr.strftime('%Y-%m-%d'),
                    'total_return_rate': round(float(rate), 2),
                    'profit': round(float(total_profit), 2),
                    'day_profit': round(float(assets - prev_assets), 2)
                })
                prev_assets = assets
                curr += datetime.timedelta(days=1)

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
class StrategyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        strats = Strategy.objects.filter(user=request.user)
        return Response({'code': 200, 'data': StrategySerializer(strats, many=True).data})


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
                    pos.avg_price = float(
                        (Decimal(str(pos.avg_price or 0)) * pos.volume + price * vol) / (pos.volume + vol))
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
            return Response({'code': 200, 'msg': '交易成功'})
        except Exception as e:
            return Response({'code': 500, 'msg': f'交易失败: {str(e)}'})


class PositionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, stock_code):
        sync_positions(request.user)
        code = stock_code.strip()
        pos = Position.objects.filter(user=request.user, stock_code=code).first()
        return Response({'code': 200, 'data': {'volume': pos.volume if pos else 0}})