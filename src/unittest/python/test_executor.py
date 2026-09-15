import time
import unittest
from datetime import datetime, timedelta
from unittest import mock

from ycappuccino.api.endpoints_service import IServiceEndpoint, ServiceResult
from ycappuccino.scheduler.executor import ScheduleExecutor


class FakeServiceEndpoint(IServiceEndpoint):

    def __init__(self):
        self.calls = []
        self.error = None
        self.failing_services = set()

    async def call(self, name, method, extra_path, params, body, subject):
        self.calls.append((name, method, extra_path, params, body, subject))
        if self.error is not None and name in self.failing_services:
            raise self.error
        return ServiceResult(body={})

    async def start(self):
        pass

    async def stop(self):
        pass


def _seed(executor, task_id, cron, service, next_fire):
    executor._tasks[task_id] = {"_id": task_id, "cron": cron, "service": service}
    executor._next_fire[task_id] = next_fire


class TestFireDueTasks(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.endpoint = FakeServiceEndpoint()
        self.executor = ScheduleExecutor(mock.Mock(), self.endpoint, mock.Mock())

    async def test_a_due_task_is_called_with_a_system_subject(self):
        now = datetime(2026, 1, 1, 10, 0)
        _seed(self.executor, "t1", "* * * * *", "greeting", now)

        await self.executor._fire_due_tasks(now)

        self.assertEqual(len(self.endpoint.calls), 1)
        name, method, extra_path, params, body, subject = self.endpoint.calls[0]
        self.assertEqual((name, method, extra_path, params, body, subject), ("greeting", "POST", [], {}, {}, None))

    async def test_a_task_not_yet_due_is_not_called(self):
        now = datetime(2026, 1, 1, 10, 0)
        _seed(self.executor, "t1", "* * * * *", "greeting", now + timedelta(minutes=5))

        await self.executor._fire_due_tasks(now)

        self.assertEqual(self.endpoint.calls, [])

    async def test_next_fire_is_recomputed_after_firing(self):
        now = datetime(2026, 1, 1, 10, 0)
        _seed(self.executor, "t1", "* * * * *", "greeting", now)

        await self.executor._fire_due_tasks(now)

        self.assertEqual(self.executor._next_fire["t1"], datetime(2026, 1, 1, 10, 1))

    async def test_several_independent_tasks(self):
        now = datetime(2026, 1, 1, 10, 0)
        _seed(self.executor, "t1", "* * * * *", "greeting", now)
        _seed(self.executor, "t2", "0 3 * * *", "cleanup", now + timedelta(hours=1))

        await self.executor._fire_due_tasks(now)

        called_services = [call[0] for call in self.endpoint.calls]
        self.assertEqual(called_services, ["greeting"])

    async def test_an_endpoint_error_is_logged_and_does_not_stop_other_tasks(self):
        now = datetime(2026, 1, 1, 10, 0)
        failing_endpoint = FakeServiceEndpoint()
        failing_endpoint.error = RuntimeError("boom")
        failing_endpoint.failing_services = {"broken"}
        logger = mock.Mock()
        executor = ScheduleExecutor(mock.Mock(), failing_endpoint, logger)
        _seed(executor, "t1", "* * * * *", "broken", now)
        _seed(executor, "t2", "* * * * *", "healthy", now)

        await executor._fire_due_tasks(now)

        logger.warning.assert_called_once()
        self.assertEqual(executor._next_fire["t1"], datetime(2026, 1, 1, 10, 1))
        self.assertEqual(executor._next_fire["t2"], datetime(2026, 1, 1, 10, 1))


class TestLifecycle(unittest.IsolatedAsyncioTestCase):

    async def test_start_and_stop_do_not_block(self):
        manager = mock.Mock()

        async def get_many(*args, **kwargs):
            return []

        manager.get_many = get_many
        executor = ScheduleExecutor(manager, FakeServiceEndpoint(), mock.Mock(), poll_interval=0.01)

        started_at = time.monotonic()
        await executor.start()
        await executor.stop()

        self.assertLess(time.monotonic() - started_at, 2.0)


if __name__ == "__main__":
    unittest.main()
