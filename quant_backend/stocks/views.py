from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
import datetime
from .models import StockData, StockMinuteData, StockBasicInfo
from .serializers import StockDataSerializer, StockMinuteDataSerializer
from trade.time_utils import get_mock_now


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def get_historical_close(code, target_date):
    """获取历史收盘价"""
    if isinstance(target_date, datetime.date) and not isinstance(target_date, datetime.datetime):
        target_time = datetime.datetime.combine(target_date, datetime.time.max)
    else:
        target_time = target_date

    obj = StockData.objects.filter(code=code, date__lte=target_time).order_by('-date').first()
    if obj: return obj.close

    obj_min = StockMinuteData.objects.filter(code=code, date__lte=target_time).order_by('-date').first()
    if obj_min: return obj_min.close

    return None


@api_view(['GET'])
def get_stock_data_api(request, stock_code):
    info = StockBasicInfo.objects.filter(code=stock_code).first()
    name = info.name if info else "未知股票"
    freq = request.GET.get('freq', 'daily')
    target_date_str = request.GET.get('date', None)
    mock_now = get_mock_now()

    pre_close = 0  # 初始化昨收价

    if freq == 'min':
        queryset = StockMinuteData.objects.filter(code=stock_code, date__lte=mock_now)

        # 🟢 1. 计算昨收价 (pre_close)
        # 确定查询基准日期：如果有指定日期则用指定日期，否则用模拟当前时间
        current_query_date = mock_now.date()
        if target_date_str:
            try:
                current_query_date = datetime.datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        # 获取小于基准日期的最近一条日线收盘价作为昨收
        last_daily = StockData.objects.filter(
            code=stock_code,
            date__lt=current_query_date
        ).order_by('-date').first()

        if last_daily:
            pre_close = last_daily.close

        # 2. 筛选分时数据
        if target_date_str:
            try:
                target_date = datetime.datetime.strptime(target_date_str, '%Y-%m-%d').date()
                if target_date > mock_now.date():
                    data_list = []
                else:
                    queryset = queryset.filter(date__date=target_date).order_by('date')
                    data_list = queryset
            except ValueError:
                data_list = []
        else:
            queryset = queryset.order_by('-date')[:1000]
            data_list = reversed(queryset)
        serializer_cls = StockMinuteDataSerializer
    else:
        queryset = StockData.objects.filter(code=stock_code, date__lte=mock_now.date())
        queryset = queryset.order_by('-date')[:500]
        data_list = reversed(queryset)
        serializer_cls = StockDataSerializer

    serializer = serializer_cls(data_list, many=True)
    return Response({
        'code': 200,
        'name': name,
        'stock_code': stock_code,
        'freq': freq,
        'target_date': target_date_str,
        'pre_close': pre_close,  # 🟢 返回计算好的昨收价
        'current_mock_time': mock_now.strftime('%Y-%m-%d %H:%M:%S'),
        'data': serializer.data
    })


@api_view(['GET'])
def get_market_list_api(request):
    """
    全市场行情列表 (支持内存排序)
    """
    mock_now = get_mock_now()
    mock_today = mock_now.date()

    # 1. 获取所有股票基础信息
    stocks = StockBasicInfo.objects.all()

    # 2. 准备历史锚点
    date_1w = mock_today - datetime.timedelta(days=7)
    date_1y = mock_today - datetime.timedelta(days=365)
    date_2y = mock_today - datetime.timedelta(days=365 * 2)
    date_3y = mock_today - datetime.timedelta(days=365 * 3)

    full_data = []

    # 3. 全量计算 (为了排序，必须先算出所有股票的涨跌幅)
    # 注意：如果股票数量非常大(>5000)，这里可以考虑引入缓存或定时任务优化
    for stock in stocks:
        # A. 获取最新价
        last_min = StockMinuteData.objects.filter(code=stock.code, date__lte=mock_now).order_by('-date').first()
        if last_min:
            price = last_min.close
            last_date = last_min.date
        else:
            last_day = StockData.objects.filter(code=stock.code, date__lte=mock_today).order_by('-date').first()
            if last_day:
                price = last_day.close
                last_date = last_day.date
            else:
                price = 0
                last_date = None

        # B. 获取基准价
        prev_day = StockData.objects.filter(code=stock.code, date__lt=mock_today).order_by('-date').first()
        prev_close = prev_day.close if prev_day else 0

        price_1w = get_historical_close(stock.code, date_1w)
        price_1y = get_historical_close(stock.code, date_1y)
        price_2y = get_historical_close(stock.code, date_2y)
        price_3y = get_historical_close(stock.code, date_3y)

        def calc_change(now, ref):
            if now and ref and ref > 0:
                return round((now - ref) / ref * 100, 2)
            return 0.0

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

    # 4. 内存排序 (核心修复点)
    sort_prop = request.GET.get('sort_prop', 'code')  # 默认按代码排
    sort_order = request.GET.get('sort_order', 'ascending')  # ascending / descending

    if sort_prop in full_data[0]:
        reverse = (sort_order == 'descending')
        # 处理 None 值防止排序报错
        full_data.sort(key=lambda x: x.get(sort_prop) or 0, reverse=reverse)

    # 5. 分页返回
    paginator = StandardResultsSetPagination()
    page_data = paginator.paginate_queryset(full_data, request)

    return paginator.get_paginated_response(page_data)