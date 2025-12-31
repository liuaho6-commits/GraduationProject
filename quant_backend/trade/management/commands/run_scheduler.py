import logging
from django.conf import settings
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util

from trade.tasks import run_active_strategies, record_intraday_assets

logger = logging.getLogger(__name__)


@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    """删除超过7天的旧任务执行记录，防止数据库膨胀"""
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class Command(BaseCommand):
    help = "Runs APScheduler."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        # ================= 添加任务 =================

        # 1. 每 1 分钟执行一次策略
        scheduler.add_job(
            run_active_strategies,
            trigger=CronTrigger(second="0"),  # 每分钟的第0秒触发
            id="run_strategies",
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'run_strategies'.")

        # 2. 每 5 分钟记录一次资产曲线
        scheduler.add_job(
            record_intraday_assets,
            trigger=CronTrigger(minute="*/5"),  # 0, 5, 10...
            id="record_assets",
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'record_assets'.")

        # 3. 每天清理一次数据库里的旧日志
        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(
                day_of_week="mon", hour="00", minute="00"
            ),
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added weekly job: 'delete_old_job_executions'.")

        try:
            logger.info("Starting scheduler...")
            print("调度器启动成功！按 Ctrl+C 退出")
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Stopping scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler shut down successfully!")