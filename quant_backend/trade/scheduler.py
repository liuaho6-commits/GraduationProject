import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler.jobstores import DjangoJobStore
from django.conf import settings
# 延迟导入任务，避免模型加载问题
from trade.tasks import clock_tick

logger = logging.getLogger(__name__)

def start_scheduler():
    try:
        scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        # 🟢 核心任务：时钟心跳 (每1秒触发)
        # 这就是让你的模拟时间走起来的动力源
        scheduler.add_job(
            clock_tick,
            trigger=CronTrigger(second="*/1"),
            id="clock_tick",
            max_instances=1,
            replace_existing=True,
        )

        scheduler.start()
        print(">>> 🟢 [God Mode] 时间调度器已启动 (每秒刷新)")
    except Exception as e:
        print(f">>> 🔴 调度器启动失败: {e}")