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

    # 模拟重新撮合，计算当前剩余现金和持仓
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
    debug_price_info = ""

    # 计算持仓市值
    for code, vol in holdings.items():
        if vol <= 0: continue
        price = Decimal('0.0')

        # 严格限制：15:00前禁止偷看当日日线StockData
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

    # 返回: 总资产, 市值, 现金, (占位符), 调试信息
    return cash + market_value, market_value, cash, Decimal('0.0'), debug_price_info


# ================= 收益表现 (修正版) =================
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
            # 这是用户的本金（包含累计充值）
            initial_capital = profile.initial_capital
        except:
            initial_capital = Decimal('200000.0')

        # 🟢 场景 A: 分时图 (日内收益)
        if query_type == 'intraday':
            start = now.replace(hour=9, minute=30, second=0, microsecond=0)
            yesterday_close_time = (start - datetime.timedelta(days=1)).replace(hour=15, minute=0, second=0)

            # 1. 获取昨收总资产 (作为今日涨跌的基准分母)
            # 注意：如果昨天是周末，这里应该逻辑上找最近一个交易日，但简单起见先取前一天
            base_assets, _, _, _, _ = calculate_asset_status(request.user, yesterday_close_time)

            # 极端的边界情况：如果是新用户第一天，昨收资产为0，则用本金作为基准
            if base_assets <= 0:
                base_assets = initial_capital

            curr = start

            # 打印调试信息
            print(f"\n======== [修正版] INTRA-DAY {now.date()} ========")
            print(f"基准资产 (昨收): {base_assets:.2f}")

            while curr <= now:
                # 获取当前时刻的总资产
                curr_assets, _, _, _, _ = calculate_asset_status(request.user, curr, True)

                # 🟢 修正：日内收益额 = 当前资产 - 昨收资产
                profit = curr_assets - base_assets

                # 🟢 修正：日内收益率 = (收益额 / 昨收资产) * 100%
                # 这才符合“今天账户涨了几个点”的定义，和仓位无关
                rate = (profit / base_assets) * 100

                data.append({
                    'time': curr.strftime('%H:%M'),
                    'total_return_rate': round(float(rate), 2),
                    'profit': round(float(profit), 2)
                })

                curr += datetime.timedelta(minutes=5)
                # 跳过午休
                if curr.hour == 11 and curr.minute > 30:
                    curr = curr.replace(hour=13, minute=0)
            print("================================================\n")

        # 🟢 场景 B: 日线图 (累计收益)
        else:
            # 这里的 start_date 决定了前端能拉取多远的历史数据
            start_date = (now - datetime.timedelta(days=365)).date()  # 默认最近1年

            curr = start_date
            prev_assets = initial_capital

            if curr > now.date(): curr = now.date()

            while curr <= now.date():
                target = datetime.datetime.combine(curr, datetime.time(15, 0))
                if timezone.is_naive(target): target = timezone.make_aware(target)
                # 还没到今天的15点，就用现在的时间算
                if target > now: target = now

                assets, _, _, _, _ = calculate_asset_status(request.user, target)

                # 🟢 修正：累计收益额 = 当前资产 - 初始本金
                total_profit = assets - initial_capital

                # 🟢 修正：累计收益率 = (累计收益 / 初始本金) * 100%
                # 无论是否空仓，分母始终是本金，收益率曲线会非常平滑
                rate = (total_profit / initial_capital) * 100

                # 当日盈亏 = 今日资产 - 昨日资产 (估算)
                day_profit = assets - prev_assets

                data.append({
                    'date': curr.strftime('%Y-%m-%d'),
                    'total_return_rate': round(float(rate), 2),
                    'profit': round(float(total_profit), 2),
                    'day_profit': round(float(day_profit), 2),
                    'total_assets': round(float(assets), 2)  # 前端如果需要显示总资产曲线可用
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
                # 🟢 关键：出入金时同步调整本金，确保收益率计算准确
                profile.initial_capital += amount

                profile.save()
            return Response({'code': 200, 'msg': '操作成功', 'data': {'balance': float(profile.balance)}})
        except Exception as e:
            return Response({'code': 500, 'msg': str(e)})


# ================= 其他视图 (保持不变) =================
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
                profile.update_asset_cache()
            return Response({'code': 200, 'msg': '交易成功'})
        except Exception as e:
            return Response({'code': 500, 'msg': f'交易失败: {str(e)}'})


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from django.apps import apps
from .models import Strategy, Order, Position, DailyPerformance
from stocks.models import StockMinuteData, StockData
from .serializers import StrategySerializer, OrderSerializer, PositionSerializer  # 记得引入 PositionSerializer
from .time_utils import get_mock_now
import datetime
from decimal import Decimal


# ... (保留你之前的 SystemTimeView, sync_positions, calculate_asset_status 等代码) ...

# ================= 🟢 新增：持仓列表视图 =================
class PositionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. 先同步一次持仓，确保数据准确
        try:
            # 这里的 sync_positions 需要引用你原有代码中的函数
            from .views import sync_positions
            sync_positions(request.user)
        except:
            pass

        # 2. 获取所有持仓
        positions = Position.objects.filter(user=request.user, volume__gt=0)

        # 3. 构造返回数据（包含现价、市值、盈亏）
        results = []
        now = get_mock_now()
        if timezone.is_naive(now): now = timezone.make_aware(now)

        for pos in positions:
            # 获取最新价格逻辑 (复制自 calculate_asset_status 的逻辑)
            price = Decimal('0.0')
            # 严格限制：15:00前禁止偷看当日日线StockData
            can_use_daily = now.hour >= 15

            daily_row = None
            if can_use_daily:
                daily_row = StockData.objects.filter(code=pos.stock_code, date=now.date()).first()

            if daily_row:
                price = Decimal(str(daily_row.close))
            else:
                day_start = now.replace(hour=0, minute=0, second=0)
                minute_row = StockMinuteData.objects.filter(code=pos.stock_code, date__lte=now,
                                                            date__gte=day_start).order_by('-date').first()
                if minute_row:
                    price = Decimal(str(minute_row.close))
                else:
                    prev_daily = StockData.objects.filter(code=pos.stock_code, date__lt=now.date()).order_by(
                        '-date').first()
                    if prev_daily:
                        price = Decimal(str(prev_daily.close))
                    else:
                        price = Decimal(str(pos.avg_price))  # 兜底

            # 计算指标
            market_value = price * Decimal(pos.volume)
            cost = Decimal(str(pos.avg_price)) * Decimal(pos.volume)
            profit = market_value - cost
            profit_rate = (profit / cost * 100) if cost > 0 else 0

            # 序列化基础信息
            data = PositionSerializer(pos).data
            # 追加动态信息
            data['current_price'] = float(price)
            data['market_value'] = float(market_value)
            data['profit'] = float(profit)
            data['profit_rate'] = float(profit_rate)

            results.append(data)

        return Response({'code': 200, 'data': results})


# ... (保留 FundTransferView, StrategyView 等其他代码) ...
class PositionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, stock_code):
        sync_positions(request.user)
        code = stock_code.strip()
        pos = Position.objects.filter(user=request.user, stock_code=code).first()
        return Response({'code': 200, 'data': {'volume': pos.volume if pos else 0}})


# ... (保留原有的引用) ...
from .models import SystemSettings  # 确保引入 SystemSettings


# ... (保留原有的 SystemTimeView, PositionListView 等视图) ...

# ================= 🟢 新增：上帝控制台接口 =================
class SystemControlView(APIView):
    """
    上帝模式控制台：明确区分【调速】和【时间穿越】
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        action = request.data.get('action')  # 'set_speed' 或 'set_time'

        try:
            settings = SystemSettings.get_settings()

            # 🟢 场景1：仅调整流速 (绝不重置数据)
            if action == 'set_speed':
                speed = float(request.data.get('speed', 1.0))
                settings.time_speed = speed
                settings.save()  # 普通保存，models.py 里已经没有魔法逻辑了
                return Response({'code': 200, 'msg': f'流速已调整为 {speed}x', 'data': {'speed': speed}})

            # 🟢 场景2：时间穿越 (显式触发重置)
            elif action == 'set_time':
                target_time_str = request.data.get('target_time')
                if not target_time_str:
                    return Response({'code': 400, 'msg': '缺少 target_time 参数'})

                # 解析时间
                if isinstance(target_time_str, str):
                    import datetime
                    # 简单处理 ISO 格式，建议前端传标准格式
                    # 如果只有日期，补全时间
                    if len(target_time_str) <= 10:
                        target_time_str += " 09:30:00"

                    # 转换为 datetime 对象 (根据你的环境可能需要 tz info)
                    new_time = datetime.datetime.fromisoformat(target_time_str)
                    if timezone.is_naive(new_time):
                        new_time = timezone.make_aware(new_time)

                # 1. 更新时间
                settings.current_mock_time = new_time
                settings.save()

                # 2. 🟢 显式调用重置逻辑
                settings.hard_reset_world()

                return Response({
                    'code': 200,
                    'msg': f'时间已跃迁至 {new_time}，世界已重置',
                    'data': {'current_time': new_time}
                })

            else:
                return Response({'code': 400, 'msg': '未知操作 action'})

        except Exception as e:
            return Response({'code': 500, 'msg': str(e)})

    def get(self, request):
        """获取当前设置状态"""
        settings = SystemSettings.get_settings()
        return Response({
            'code': 200,
            'data': {
                'current_time': settings.current_mock_time,
                'time_speed': settings.time_speed,
                'skip_non_trading': settings.skip_non_trading
            }
        })