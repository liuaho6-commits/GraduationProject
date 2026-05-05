from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
import datetime
from .models import (
    MarketIndexBasicInfo,
    MarketIndexDailyData,
    MarketIndexMinuteData,
    StockData,
    StockMinuteData,
    StockBasicInfo,
)
from .serializers import (
    MarketIndexDailyDataSerializer,
    MarketIndexMinuteDataSerializer,
    StockDataSerializer,
    StockMinuteDataSerializer,
)
from trade.time_utils import get_mock_now
import warnings
# 忽略 Django 关于 Naive datetime 的时区警告
warnings.filterwarnings('ignore', category=RuntimeWarning, message=r'.*received a naive datetime.*')

INDEX_ORDER = ['sh.000001', 'sz.399001', 'sz.399006', 'sh.000300']

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def get_historical_close(code, target_date):
    """
    辅助函数：获取指定日期(含)之前的最新收盘价
    """
    if isinstance(target_date, datetime.date) and not isinstance(target_date, datetime.datetime):
        target_time = datetime.datetime.combine(target_date, datetime.time.max)
    else:
        target_time = target_date

    obj = StockData.objects.filter(code=code, date__lte=target_time).order_by('-date').first()
    if obj: return obj.close
    return None


def calc_change(now, ref):
    if now and ref and ref > 0:
        return round((now - ref) / ref * 100, 2)
    return 0.0


def parse_limit(request, default=500, max_value=5000):
    try:
        limit = int(request.GET.get('limit', default))
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, max_value))


@api_view(['GET'])
def get_market_index_list_api(request):
    """
    获取大盘指数概览卡片数据。
    """
    index_info = list(MarketIndexBasicInfo.objects.all())
    index_info.sort(key=lambda item: INDEX_ORDER.index(item.code) if item.code in INDEX_ORDER else 99)

    data = []
    for info in index_info:
        latest = MarketIndexDailyData.objects.filter(code=info.code).order_by('-date').first()
        if not latest:
            data.append({
                'code': info.code,
                'name': info.name,
                'market': info.market,
                'price': 0,
                'change': 0,
                'change_amount': 0,
                'date': None,
                'volume': 0,
                'amount': 0,
            })
            continue

        prev = MarketIndexDailyData.objects.filter(code=info.code, date__lt=latest.date).order_by('-date').first()
        change = latest.change_pct
        if change is None:
            change = calc_change(latest.close, prev.close if prev else None)

        data.append({
            'code': info.code,
            'name': info.name,
            'market': info.market,
            'price': latest.close,
            'change': round(change or 0, 2),
            'change_amount': latest.change_amount if latest.change_amount is not None else (
                round(latest.close - prev.close, 2) if prev else 0
            ),
            'date': latest.date.strftime('%Y-%m-%d'),
            'volume': latest.volume,
            'amount': latest.amount or 0,
        })

    return Response({
        'code': 200,
        'data': data,
    })


@api_view(['GET'])
def get_market_index_data_api(request, index_code):
    """
    获取大盘指数 K 线数据。freq=daily 返回日线，freq=min/5min 返回 5 分钟线。
    """
    info = MarketIndexBasicInfo.objects.filter(code=index_code).first()
    name = info.name if info else '未知指数'
    freq = request.GET.get('freq', 'daily')
    limit = parse_limit(request, default=1200 if freq == 'daily' else 500)

    if freq in ['min', '5min']:
        queryset = MarketIndexMinuteData.objects.filter(code=index_code).order_by('-date')[:limit]
        final_data_list = list(reversed(list(queryset)))
        serializer_cls = MarketIndexMinuteDataSerializer
    else:
        queryset = MarketIndexDailyData.objects.filter(code=index_code).order_by('-date')[:limit]
        final_data_list = list(reversed(list(queryset)))
        serializer_cls = MarketIndexDailyDataSerializer
        freq = 'daily'

    latest = final_data_list[-1] if final_data_list else None
    serializer = serializer_cls(final_data_list, many=True)

    return Response({
        'code': 200,
        'name': name,
        'index_code': index_code,
        'freq': freq,
        'latest_price': latest.close if latest else 0,
        'latest_time': latest.date.strftime('%Y-%m-%d %H:%M:%S') if latest and hasattr(latest.date, 'hour') else (
            latest.date.strftime('%Y-%m-%d') if latest else ''
        ),
        'data': serializer.data,
    })


@api_view(['GET'])
def get_stock_data_api(request, stock_code):
    """
    获取股票详情数据 (K线图)
    """
    info = StockBasicInfo.objects.filter(code=stock_code).first()
    name = info.name if info else "未知股票"
    freq = request.GET.get('freq', 'daily')  # 默认为日线，或者 min
    target_date_str = request.GET.get('date', None)

    # 1. 获取上帝时间
    mock_now = get_mock_now()

    # 2. 准备“墙上时间” (Wall Clock Time)
    if timezone.is_aware(mock_now):
        mock_naive = timezone.make_naive(mock_now)
    else:
        mock_naive = mock_now

    pre_close = 0
    final_data_list = []

    print(f"\n[API] Stock: {stock_code} | Freq: {freq} | MockTime(Naive): {mock_naive}")

    # ==========================================
    # 🟢 场景 A: 分时/5分钟K线 (freq='min')
    # ==========================================
    if freq == 'min':
        # 如果是指定日期回看 (历史回测用)
        if target_date_str:
            try:
                # 依然保持“只看那一天”的逻辑
                queryset = StockMinuteData.objects.filter(
                    code=stock_code,
                    date__contains=target_date_str
                ).order_by('date')
                final_data_list = list(queryset)

                # 获取那一天的昨收
                check_date = datetime.datetime.strptime(target_date_str, '%Y-%m-%d').date()
                last_daily = StockData.objects.filter(code=stock_code, date__lt=check_date).order_by('-date').first()
                if last_daily: pre_close = last_daily.close
            except Exception as e:
                print(f"[API Error] 历史查询出错: {e}")
                final_data_list = []

        # 🟢 场景 B: 默认/实时查看 (同花顺模式)
        else:
            # 这里的核心改动：不再只查“mock_now 当天”，而是查“mock_now 之前最近的 N 条”
            # 这样前端就能拿到跨天的数据，实现连续缩放

            LIMIT_COUNT = 500  # 拿最近 500 根 5分钟K线

            # 为了防止漏数据，先宽容查到“明天”
            query_limit_date = mock_naive + datetime.timedelta(days=1)

            # 倒序查出来
            candidates = StockMinuteData.objects.filter(
                code=stock_code,
                date__lte=query_limit_date
            ).order_by('-date')[:1000]  # 多拿点方便内存过滤

            raw_data = list(candidates)

            # 内存过滤：严格确保不显示“未来”数据 (mock_now 之后的数据)
            valid_data = []
            for item in raw_data:
                # 剥离时区进行比较
                if timezone.is_aware(item.date):
                    item_naive = timezone.make_naive(item.date)
                else:
                    item_naive = item.date

                if item_naive <= mock_naive:
                    valid_data.append(item)

                if len(valid_data) >= LIMIT_COUNT:
                    break

            # 翻转回正序 (旧 -> 新)
            final_data_list = list(reversed(valid_data))

            if final_data_list:
                # 昨收逻辑：取这批数据里第一根K线之前的那个收盘价
                first_ts = final_data_list[0].date
                last_daily = StockData.objects.filter(
                    code=stock_code,
                    date__lt=first_ts.date()
                ).order_by('-date').first()
                if last_daily:
                    pre_close = last_daily.close

        serializer_cls = StockMinuteDataSerializer

    # ==========================================
    # 🟢 场景 C: 日线 (freq='daily')
    # ==========================================
    else:
        # 这里绝对不动，保持你原有的逻辑
        mock_date = mock_naive.date()

        queryset = StockData.objects.filter(
            code=stock_code,
            date__lte=mock_date
        ).order_by('-date')[:500]

        final_data_list = list(reversed(queryset))
        serializer_cls = StockDataSerializer

    serializer = serializer_cls(final_data_list, many=True)

    return Response({
        'code': 200,
        'name': name,
        'stock_code': stock_code,
        'freq': freq,
        'target_date': target_date_str,
        'pre_close': pre_close,
        'current_mock_time': mock_now.strftime('%Y-%m-%d %H:%M:%S'),
        'data': serializer.data
    })


@api_view(['GET'])
def get_market_list_api(request):
    # 保持原样，不需要修改
    mock_now = get_mock_now()
    if timezone.is_aware(mock_now):
        mock_naive = timezone.make_naive(mock_now)
    else:
        mock_naive = mock_now

    mock_today = mock_naive.date()
    stocks = StockBasicInfo.objects.all()
    full_data = []

    # ... 省略中间代码，避免字数过多，这部分并未修改 ...
    # 如果你需要我完整贴出 get_market_list_api 也可以，但它和K线展示无关
    # 为了安全起见，建议你只替换上面的 get_stock_data_api 函数

    # 这里简单把 get_market_list_api 的核心逻辑复述一遍，防止你覆盖时丢失
    # (实际上你只需要把上面的 get_stock_data_api 替换掉原本的即可)

    # ... (以下为原本的 get_market_list_api 逻辑) ...
    date_1w = mock_today - datetime.timedelta(days=7)
    date_1y = mock_today - datetime.timedelta(days=365)
    date_2y = mock_today - datetime.timedelta(days=365 * 2)
    date_3y = mock_today - datetime.timedelta(days=365 * 3)

    for stock in stocks:
        candidates = StockMinuteData.objects.filter(
            code=stock.code,
            date__lte=mock_now + datetime.timedelta(days=1)
        ).order_by('-date')[:50]

        last_min = None
        for cand in candidates:
            cand_naive = timezone.make_naive(cand.date) if timezone.is_aware(cand.date) else cand.date
            if cand_naive <= mock_naive:
                last_min = cand
                break

        if last_min:
            price = last_min.close
            last_date = last_min.date
            prev_day_orig = StockData.objects.filter(code=stock.code, date__lt=last_min.date.date()).order_by(
                '-date').first()
            prev_close = prev_day_orig.close if prev_day_orig else 0
        else:
            last_day = StockData.objects.filter(code=stock.code, date__lte=mock_today).order_by('-date').first()
            if last_day:
                price = last_day.close
                last_date = last_day.date
                prev_day = StockData.objects.filter(code=stock.code, date__lt=last_day.date).order_by('-date').first()
                prev_close = prev_day.close if prev_day else 0
            else:
                price = 0
                last_date = None
                prev_close = 0

        price_1w = get_historical_close(stock.code, date_1w)
        price_1y = get_historical_close(stock.code, date_1y)
        price_2y = get_historical_close(stock.code, date_2y)
        price_3y = get_historical_close(stock.code, date_3y)

        full_data.append({
            'code': stock.code,
            'name': stock.name,
            'price': price,
            'date': last_date if isinstance(last_date, str) or last_date is None else last_date.strftime(
                '%Y-%m-%d %H:%M'),
            'change': calc_change(price, prev_close),
            'change_1w': calc_change(price, price_1w),
            'change_1y': calc_change(price, price_1y),
            'change_2y': calc_change(price, price_2y),
            'change_3y': calc_change(price, price_3y),
        })

    sort_prop = request.GET.get('sort_prop', 'code')
    sort_order = request.GET.get('sort_order', 'ascending')

    if full_data and sort_prop in full_data[0]:
        reverse = (sort_order == 'descending')
        full_data.sort(key=lambda x: x.get(sort_prop) or 0, reverse=reverse)

    paginator = StandardResultsSetPagination()
    page_data = paginator.paginate_queryset(full_data, request)

    return paginator.get_paginated_response(page_data)
