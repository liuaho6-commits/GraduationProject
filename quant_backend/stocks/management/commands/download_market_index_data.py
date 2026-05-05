import datetime as dt
import math
import time

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from tqdm import tqdm

from stocks.models import (
    MarketIndexBasicInfo,
    MarketIndexDailyData,
    MarketIndexMinuteData,
)


MARKET_INDICES = [
    {
        "code": "sh.000001",
        "name": "上证指数",
        "market": "sh",
        "ak_symbol": "000001",
        "tdx_market": 1,
        "tdx_code": "000001",
    },
    {
        "code": "sz.399001",
        "name": "深证成指",
        "market": "sz",
        "ak_symbol": "399001",
        "tdx_market": 0,
        "tdx_code": "399001",
    },
    {
        "code": "sz.399006",
        "name": "创业板指",
        "market": "sz",
        "ak_symbol": "399006",
        "tdx_market": 0,
        "tdx_code": "399006",
    },
    {
        "code": "sh.000300",
        "name": "沪深300",
        "market": "sh",
        "ak_symbol": "000300",
        "tdx_market": 1,
        "tdx_code": "000300",
    },
]

TDX_SERVERS = [
    ("华为云行情", "124.71.187.122", 7709),
    ("上海双线行情", "47.103.48.45", 7709),
    ("广州电信行情", "119.147.212.81", 7709),
    ("成都电信行情", "218.6.170.47", 7709),
    ("北京联通行情", "123.125.108.14", 7709),
]


def to_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def safe_float(value):
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed):
        return None
    return parsed


def safe_int(value) -> int:
    parsed = safe_float(value)
    if parsed is None:
        return 0
    return int(parsed)


def trading_minutes(day: dt.date):
    minutes = []
    cur = dt.datetime.combine(day, dt.time(9, 31))
    end = dt.datetime.combine(day, dt.time(11, 30))
    while cur <= end:
        minutes.append(cur)
        cur += dt.timedelta(minutes=1)

    cur = dt.datetime.combine(day, dt.time(13, 1))
    end = dt.datetime.combine(day, dt.time(15, 0))
    while cur <= end:
        minutes.append(cur)
        cur += dt.timedelta(minutes=1)
    return minutes


def aggregate_to_5min(code: str, day: dt.date, rows) -> list[MarketIndexMinuteData]:
    if not rows:
        return []

    minutes = trading_minutes(day)
    normalized = []
    for item, minute in zip(rows, minutes):
        price = safe_float(item.get("price"))
        if price is None or price <= 0:
            continue
        normalized.append(
            {
                "time": minute,
                "price": price,
                "volume": safe_int(item.get("vol")),
            }
        )

    bars = []
    for i in range(0, len(normalized), 5):
        chunk = normalized[i:i + 5]
        if len(chunk) < 5:
            continue
        prices = [item["price"] for item in chunk]
        bars.append(
            MarketIndexMinuteData(
                code=code,
                date=timezone.make_aware(chunk[-1]["time"]),
                open=prices[0],
                high=max(prices),
                low=min(prices),
                close=prices[-1],
                volume=sum(item["volume"] for item in chunk),
                amount=None,
                source="pytdx-history-minute",
            )
        )
    return bars


class Command(BaseCommand):
    help = "下载大盘指数 2022 至今的日线和 5 分钟线数据到专用表"
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--start", default="2022-01-01", help="开始日期，格式 YYYY-MM-DD")
        parser.add_argument(
            "--end",
            default=dt.date.today().strftime("%Y-%m-%d"),
            help="结束日期，格式 YYYY-MM-DD",
        )
        parser.add_argument(
            "--codes",
            nargs="*",
            default=[],
            help="可选指数代码，如 sh.000001 sz.399001；默认下载全部预设指数",
        )
        parser.add_argument("--skip-daily", action="store_true", help="跳过日线下载")
        parser.add_argument("--skip-minute", action="store_true", help="跳过 5 分钟线下载")
        parser.add_argument("--force", action="store_true", help="强制覆盖已有数据")
        parser.add_argument("--batch-size", type=int, default=2000, help="批量入库大小")
        parser.add_argument("--sleep", type=float, default=0.02, help="分钟接口每次请求后的暂停秒数")

    def handle(self, *args, **options):
        start = to_date(options["start"])
        end = to_date(options["end"])
        if start > end:
            raise CommandError("start 不能晚于 end")

        selected_codes = set(options["codes"])
        targets = [
            item for item in MARKET_INDICES
            if not selected_codes or item["code"] in selected_codes
        ]
        if not targets:
            raise CommandError("没有匹配到要下载的指数代码")

        self.stdout.write("=" * 80)
        self.stdout.write("大盘指数数据下载")
        self.stdout.write(f"范围: {start} 至 {end}")
        self.stdout.write(f"指数: {', '.join(item['name'] for item in targets)}")
        self.stdout.write(f"强制覆盖: {options['force']}")
        self.stdout.write("=" * 80)

        self.upsert_basic_info(targets)

        daily_dates_by_code = {}
        if not options["skip_daily"]:
            for target in targets:
                daily_dates_by_code[target["code"]] = self.download_daily(
                    target=target,
                    start=start,
                    end=end,
                    force=options["force"],
                    batch_size=options["batch_size"],
                )
        else:
            for target in targets:
                daily_dates_by_code[target["code"]] = list(
                    MarketIndexDailyData.objects.filter(
                        code=target["code"],
                        date__gte=start,
                        date__lte=end,
                    )
                    .order_by("date")
                    .values_list("date", flat=True)
                )

        if not options["skip_minute"]:
            api, server_name = self.connect_tdx()
            self.stdout.write(f"通达信行情服务器: {server_name}")
            try:
                for target in targets:
                    trading_dates = daily_dates_by_code.get(target["code"]) or []
                    if not trading_dates:
                        self.stdout.write(self.style.WARNING(f"{target['name']} 没有日线交易日，跳过分钟线"))
                        continue
                    self.download_minute(
                        api=api,
                        target=target,
                        trading_dates=trading_dates,
                        force=options["force"],
                        sleep_seconds=options["sleep"],
                    )
            finally:
                api.disconnect()

        self.print_count_summary(targets, start, end)

    def upsert_basic_info(self, targets):
        for item in targets:
            MarketIndexBasicInfo.objects.update_or_create(
                code=item["code"],
                defaults={"name": item["name"], "market": item["market"]},
            )

    def download_daily(self, target, start: dt.date, end: dt.date, force: bool, batch_size: int):
        self.stdout.write(f"\n下载日线: {target['name']}")
        rows = self.fetch_daily_from_akshare(target, start, end)
        if rows.empty:
            self.stdout.write(self.style.WARNING("AkShare 日线为空，尝试使用 pytdx 日线兜底"))
            rows = self.fetch_daily_from_tdx(target, start, end)
        if rows.empty:
            self.stdout.write(self.style.WARNING(f"{target['name']} 日线为空"))
            return []

        rows["date"] = pd.to_datetime(rows["date"]).dt.date
        rows = rows[(rows["date"] >= start) & (rows["date"] <= end)].copy()
        rows.sort_values("date", inplace=True)

        if force:
            MarketIndexDailyData.objects.filter(
                code=target["code"],
                date__gte=start,
                date__lte=end,
            ).delete()

        existing_dates = set(
            MarketIndexDailyData.objects.filter(
                code=target["code"],
                date__gte=start,
                date__lte=end,
            ).values_list("date", flat=True)
        )

        objects = []
        for _, row in rows.iterrows():
            if row["date"] in existing_dates:
                continue
            objects.append(
                MarketIndexDailyData(
                    code=target["code"],
                    date=row["date"],
                    open=safe_float(row.get("open")) or 0.0,
                    high=safe_float(row.get("high")) or 0.0,
                    low=safe_float(row.get("low")) or 0.0,
                    close=safe_float(row.get("close")) or 0.0,
                    volume=safe_int(row.get("volume")),
                    amount=safe_float(row.get("amount")),
                    amplitude=safe_float(row.get("amplitude")),
                    change_pct=safe_float(row.get("change_pct")),
                    change_amount=safe_float(row.get("change_amount")),
                    turnover_rate=safe_float(row.get("turnover_rate")),
                    source=row.get("source") or "akshare",
                )
            )

        if objects:
            MarketIndexDailyData.objects.bulk_create(objects, batch_size=batch_size)
        self.stdout.write(self.style.SUCCESS(f"{target['name']} 日线新增 {len(objects)} 条，总交易日 {len(rows)} 条"))
        return list(rows["date"])

    def fetch_daily_from_akshare(self, target, start: dt.date, end: dt.date) -> pd.DataFrame:
        import akshare as ak

        df = ak.index_zh_a_hist(
            symbol=target["ak_symbol"],
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )
        if df.empty:
            return pd.DataFrame()
        df = df.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
                "振幅": "amplitude",
                "涨跌幅": "change_pct",
                "涨跌额": "change_amount",
                "换手率": "turnover_rate",
            }
        )
        df["source"] = "akshare"
        return df

    def fetch_daily_from_tdx(self, target, start: dt.date, end: dt.date) -> pd.DataFrame:
        api, _ = self.connect_tdx()
        try:
            rows = []
            offset = 0
            page_size = 800
            while True:
                page = api.get_index_bars(
                    4,
                    target["tdx_market"],
                    target["tdx_code"],
                    offset,
                    page_size,
                )
                if not page:
                    break
                for item in page:
                    item_date = dt.date(int(item["year"]), int(item["month"]), int(item["day"]))
                    if start <= item_date <= end:
                        rows.append(
                            {
                                "date": item_date,
                                "open": item.get("open"),
                                "high": item.get("high"),
                                "low": item.get("low"),
                                "close": item.get("close"),
                                "volume": item.get("vol"),
                                "amount": item.get("amount"),
                                "source": "pytdx-daily",
                            }
                        )
                oldest = min(
                    dt.date(int(item["year"]), int(item["month"]), int(item["day"]))
                    for item in page
                )
                if oldest < start:
                    break
                offset += page_size
        finally:
            api.disconnect()
        return pd.DataFrame(rows).drop_duplicates(subset=["date"]) if rows else pd.DataFrame()

    def connect_tdx(self):
        from pytdx.hq import TdxHq_API

        last_error = None
        for server_name, host, port in TDX_SERVERS:
            api = TdxHq_API()
            try:
                ok = api.connect(host, port, time_out=5)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
            if ok:
                return api, f"{server_name}({host}:{port})"
        raise CommandError(f"无法连接通达信行情服务器: {last_error}")

    def download_minute(self, api, target, trading_dates, force: bool, sleep_seconds: float):
        self.stdout.write(f"\n下载 5 分钟线: {target['name']}")
        added = 0
        skipped = 0
        failed = 0

        bar = tqdm(trading_dates, desc=target["name"], unit="日")
        for trading_day in bar:
            if not force:
                exists = MarketIndexMinuteData.objects.filter(
                    code=target["code"],
                    date__date=trading_day,
                ).exists()
                if exists:
                    skipped += 1
                    continue

            try:
                rows = api.get_history_minute_time_data(
                    target["tdx_market"],
                    target["tdx_code"],
                    int(trading_day.strftime("%Y%m%d")),
                )
            except Exception:  # noqa: BLE001
                failed += 1
                continue

            objects = aggregate_to_5min(target["code"], trading_day, rows)
            if not objects:
                failed += 1
                continue

            with transaction.atomic():
                MarketIndexMinuteData.objects.filter(
                    code=target["code"],
                    date__date=trading_day,
                ).delete()
                MarketIndexMinuteData.objects.bulk_create(objects, batch_size=64)
            added += len(objects)

            if sleep_seconds:
                time.sleep(sleep_seconds)

        self.stdout.write(
            self.style.SUCCESS(
                f"{target['name']} 5分钟线新增 {added} 条，跳过 {skipped} 个已有交易日，失败 {failed} 个交易日"
            )
        )

    def print_count_summary(self, targets, start: dt.date, end: dt.date):
        self.stdout.write("\n数据量校验")
        for target in targets:
            daily_count = MarketIndexDailyData.objects.filter(
                code=target["code"],
                date__gte=start,
                date__lte=end,
            ).count()
            minute_count = MarketIndexMinuteData.objects.filter(
                code=target["code"],
                date__date__gte=start,
                date__date__lte=end,
            ).count()
            self.stdout.write(f"{target['name']}: 日线 {daily_count} 条，5分钟线 {minute_count} 条")
