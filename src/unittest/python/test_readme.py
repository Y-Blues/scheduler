"""
The examples of README.md, kept runnable.
"""

import shutil
import unittest
from datetime import datetime
from unittest import mock

from scheduler_fixtures import create_manager

from ycappuccino.api.endpoints_service import IExposedService, IServiceEndpoint, ServiceResult
from ycappuccino.scheduler.cron import next_fire_time
from ycappuccino.scheduler.executor import ScheduleExecutor
from ycappuccino.scheduler.models.scheduled_task import ScheduledTask


# section "Exemple"
class Greeting(IExposedService):
    name = "greeting"
    secure = False

    def __init__(self):
        pass

    async def call(self, method, extra_path, params, body, subject):
        return ServiceResult(body={})

    async def start(self):
        pass

    async def stop(self):
        pass


# section "Tester avec scheduler"
class FakeEndpoint(IServiceEndpoint):
    def __init__(self):
        self.calls = []

    async def call(self, name, method, extra_path, params, body, subject):
        self.calls.append(name)
        return ServiceResult(body={})

    async def start(self):
        pass

    async def stop(self):
        pass


class TestReadmeExamples(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.manager, directory = create_manager()
        self.addCleanup(shutil.rmtree, directory, True)

    async def test_model_section(self):
        task = ScheduledTask()
        task.id("greet-every-minute")
        task.name("Greet every minute")
        task.cron("* * * * *")
        task.service("greeting")
        await self.manager.up_sert_model(task)

        stored = (await self.manager.get_one("scheduledTask", "greet-every-minute")).get_storage_model()
        self.assertEqual(stored["service"], "greeting")

    async def test_greeting_service(self):
        result = await Greeting().call("POST", [], {}, {}, None)
        self.assertEqual(result.body, {})

    async def test_a_due_task_triggers_its_service(self):
        endpoint = FakeEndpoint()
        executor = ScheduleExecutor(mock.Mock(), endpoint, mock.Mock())
        now = datetime(2026, 1, 1, 10, 0)
        executor._tasks["t1"] = {"_id": "t1", "cron": "* * * * *", "service": "greeting"}
        executor._next_fire["t1"] = now

        await executor._fire_due_tasks(now)

        self.assertEqual(endpoint.calls, ["greeting"])

    async def test_next_fire_time_is_a_plain_datetime(self):
        after = datetime(2026, 1, 1, 2, 0)

        self.assertEqual(next_fire_time("0 3 * * *", after), datetime(2026, 1, 1, 3, 0))


if __name__ == "__main__":
    unittest.main()
