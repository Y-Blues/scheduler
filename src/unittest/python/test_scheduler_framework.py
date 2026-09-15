import unittest

from ycappuccino.core.framework import Framework
from ycappuccino.core.testing import TemporaryApplication, wait_until

APPLICATION = {
    "conf/application.yml": """
        name: schedulertest
        bundle_prefix:
          - ycappuccino.storage
          - PACKAGE
          - ycappuccino.endpoints_service
          - ycappuccino.scheduler
        layers:
          ycappuccino_storage_memory:
            active: true
        components:
          ScheduleExecutor:
            poll_interval: 0.05
        config:
          shell:
            console: false
    """,
    # PACKAGE is scanned (and its components started) before ycappuccino.endpoints_service and
    # ycappuccino.scheduler, per Framework.load_bundles: bundles are installed and their
    # components validated synchronously, package by package, in bundle_prefix order. This
    # guarantees TaskBootstrap has already written the scheduledTask before ScheduleExecutor's
    # own start() reads it (scheduler has no hot reload, see the design spec).
    "PACKAGE/__init__.py": "",
    "PACKAGE/greeting.py": """
        from ycappuccino.api.endpoints_service import IExposedService, ServiceResult


        class Greeting(IExposedService):
            name = "greeting"
            secure = False
            calls = []

            def __init__(self):
                pass

            async def call(self, method, extra_path, params, body, subject):
                Greeting.calls.append(1)
                return ServiceResult(body={})

            async def start(self):
                pass

            async def stop(self):
                pass
    """,
    "PACKAGE/bootstrap.py": """
        from ycappuccino.api.core_base import YCappuccinoComponent
        from ycappuccino.api.storage import IManager
        from ycappuccino.scheduler.models.scheduled_task import ScheduledTask


        class TaskBootstrap(YCappuccinoComponent):
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
    """,
}


class TestSchedulerInFramework(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = TemporaryApplication(APPLICATION).open()
        cls.addClassCleanup(cls.app.close)
        cls.framework = Framework()
        cls.framework.init(cls.app.yml_path)
        cls.addClassCleanup(cls.framework.stop)
        wait_until(lambda: cls.framework.context.get_service_reference("ScheduleExecutor"))

    def test_the_scheduled_task_triggers_the_named_service(self):
        greeting = self.app.module("greeting").Greeting

        wait_until(lambda: len(greeting.calls) > 0, timeout=5)

        self.assertGreater(len(greeting.calls), 0)


if __name__ == "__main__":
    unittest.main()
