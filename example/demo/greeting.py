"""
Demo IExposedService triggered by the "greet-every-minute" ScheduledTask, plus the bootstrap
component that creates it. See scheduler/README.md.
"""

import logging

from ycappuccino.api.core_base import YCappuccinoComponent
from ycappuccino.api.endpoints_service import IExposedService, ServiceResult
from ycappuccino.api.storage import IManager
from ycappuccino.scheduler.models.scheduled_task import ScheduledTask

_logger = logging.getLogger(__name__)


class Greeting(IExposedService):
    name = "greeting"
    secure = False

    def __init__(self):
        pass

    async def call(self, method, extra_path, params, body, subject):
        _logger.info("hello from the scheduler")
        return ServiceResult(body={})

    async def start(self):
        pass

    async def stop(self):
        pass


class TaskBootstrap(YCappuccinoComponent):
    """creates the demo ScheduledTask once, at start (see scheduler/README.md)"""

    def __init__(self, manager: IManager):
        self._manager = manager

    async def stop(self):
        pass

    async def start(self):
        task = ScheduledTask()
        task.id("greet-every-minute")
        task.name("Greet every minute")
        task.cron("* * * * *")
        task.service("greeting")
        await self._manager.up_sert_model(task, subject=None)
