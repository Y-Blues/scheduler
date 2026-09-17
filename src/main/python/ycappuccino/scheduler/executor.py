"""
ScheduleExecutor: loads scheduledTask at start() and fires IServiceEndpoint.call on schedule.

See spec (2026-09-15-scheduler-design.md) for the design decisions: subject=None on triggered
calls (targets must be secure=False), tasks loaded once at start (no hot reload), a background
thread woken every `poll_interval` seconds rather than sched.scheduler.
"""

import asyncio
import threading
from datetime import datetime, timedelta
from typing import Optional

from ycappuccino.api.core import IActivityLogger
from ycappuccino.api.core_base import YCappuccinoComponent, YCappuccinoType
from ycappuccino.api.endpoints_service import IServiceEndpoint
from ycappuccino.api.storage import IManager
from ycappuccino.scheduler.cron import next_fire_time

_ITEM_ID = "scheduledTask"
_ONE_MINUTE = timedelta(minutes=1)


class ScheduleExecutor(YCappuccinoComponent):

    def __init__(
        self,
        manager: IManager,
        endpoint: IServiceEndpoint,
        logger: YCappuccinoType(IActivityLogger, "(name=main)"),
        poll_interval: float = 1.0,
    ) -> None:
        self._manager = manager
        self._endpoint = endpoint
        self._logger = logger
        self._poll_interval = poll_interval
        self._tasks: dict = {}
        self._next_fire: dict = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    async def start(self) -> None:
        models = await self._manager.get_many(_ITEM_ID, subject=None)
        now = datetime.now()
        for model in models:
            document = model.get_storage_model()
            task_id = document["_id"]
            self._tasks[task_id] = document
            # catches up on the current minute if it already matches, see spec section 3
            self._next_fire[task_id] = next_fire_time(document["cron"], now - _ONE_MINUTE)

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            now = datetime.now()
            if any(next_fire <= now for next_fire in self._next_fire.values()):
                asyncio.run(self._fire_due_tasks(now))
            self._stop_event.wait(self._poll_interval)

    async def _fire_due_tasks(self, now: datetime) -> None:
        for task_id, next_fire in list(self._next_fire.items()):
            if next_fire > now:
                continue
            document = self._tasks[task_id]
            try:
                await self._endpoint.call(document["service"], "POST", [], {}, {}, None)
            except Exception:
                self._logger.warning(f"scheduled call to {document['service']!r} (task {task_id!r}) failed")
            self._next_fire[task_id] = next_fire_time(document["cron"], now)
