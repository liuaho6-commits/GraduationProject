import sys
import os
import logging
from django.apps import AppConfig
from django.conf import settings
from django_apscheduler import util

logger = logging.getLogger(__name__)


# 🟢 修正：将清理函数移到类外面，定义为模块级函数
# 这样 APScheduler 才能通过路径 (trade.apps.delete_old_job_executions) 找到并序列化它
@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    """删除超过7天的旧任务执行记录，防止数据库膨胀"""
    # 在函数内部导入模型，避免在应用启动初期引发 AppRegistryNotReady 错误
    from django_apscheduler.models import DjangoJobExecution
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class TradeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "trade"

    def ready(self):
        """
        Django 应用启动时执行
        """
        if os.environ.get('RUN_MAIN') == 'true':
            from .scheduler import start_scheduler
            start_scheduler()

    def start_scheduler(self):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            from django_apscheduler.jobstores import DjangoJobStore

            # 引入你的任务函数
            from trade.tasks import run_active_strategies, record_intraday_assets

            scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
            scheduler.add_jobstore(DjangoJobStore(), "default")

            # ================= 添加任务 =================

            # 1. 每 1 分钟执行一次策略
            scheduler.add_job(
                run_active_strategies,
                trigger=CronTrigger(second="0"),
                id="run_strategies",
                max_instances=1,
                replace_existing=True,
            )

            # 2. 每 5 分钟记录一次资产曲线
            scheduler.add_job(
                record_intraday_assets,
                trigger=CronTrigger(minute="*/5"),
                id="record_assets",
                max_instances=1,
                replace_existing=True,
            )

            # 3. 每周清理一次旧日志 (直接引用上方的模块级函数)
            scheduler.add_job(
                delete_old_job_executions,
                trigger=CronTrigger(day_of_week="mon", hour="00", minute="00"),
                id="delete_old_job_executions",
                max_instances=1,
                replace_existing=True,
            )

            # 启动调度器
            scheduler.start()

            print("\n" + "=" * 60)
            print(">>> 🟢 量化交易调度器 (BackgroundScheduler) 已随后端自动启动")
            print(">>> 策略每1分钟执行一次，资产每5分钟记录一次")
            print("=" * 60 + "\n")

        except Exception as e:
            logger.error(f"调度器启动失败: {e}")
            # 打印简单错误信息，避免刷屏
            print(f"\n>>> 🔴 调度器启动异常: {str(e)}\n")