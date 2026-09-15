import shutil
import unittest

from scheduler_fixtures import create_manager

from ycappuccino.scheduler.models.scheduled_task import ScheduledTask


class TestScheduledTask(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.manager, directory = create_manager()
        self.addCleanup(shutil.rmtree, directory, True)

    async def test_round_trip_through_the_manager(self):
        task = ScheduledTask()
        task.id("greet-every-minute")
        task.name("Greet every minute")
        task.cron("* * * * *")
        task.service("greeting")

        await self.manager.up_sert_model(task)
        stored = (await self.manager.get_one("scheduledTask", "greet-every-minute")).get_storage_model()

        self.assertEqual(stored["name"], "Greet every minute")
        self.assertEqual(stored["cron"], "* * * * *")
        self.assertEqual(stored["service"], "greeting")


if __name__ == "__main__":
    unittest.main()
