# scheduler natif : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tâches récurrentes natives : un modèle `@Item` `ScheduledTask` (nom, expression cron, nom du service ciblé) et un composant `ScheduleExecutor` qui, au démarrage, arme un planificateur en mémoire et déclenche `IServiceEndpoint.call(service, "POST", [], {}, {}, subject=None)` à chaque échéance.

**Architecture:** Un module pur sans composant (`cron.py`, fonction `next_fire_time`), un modèle `@Item` (`ScheduledTask`), un composant natif sans interface dédiée (`ScheduleExecutor`, thread de fond + `threading.Event`, logique de déclenchement dans une méthode async séparée pour rester testable sans horloge réelle). Aucune route HTTP nouvelle : `http_server` expose déjà `/api/crud/scheduled-tasks`.

**Tech Stack:** Python ≥ 3.10, uv, Pelix/iPOPO 3, unittest (`IsolatedAsyncioTestCase`), aucune dépendance externe nouvelle.

**Spec:** `scheduler/docs/superpowers/specs/2026-09-15-scheduler-design.md`

## Global Constraints

- Racine du workspace : `/home/yaiba/Documents/yblues`. `scheduler` est un dépôt git séparé ; aucune tâche de ce plan ne touche `api`, `core`, `storage`, `endpoints_storage`, `http_server`, `endpoints_service`, `permissions_app` ou `scripts`.
- Commande de test, lancée depuis `scheduler` : `uv run python -m unittest discover -s src/unittest/python`.
- `requires-python = ">=3.10"`.
- **Aucun décorateur sur les classes de composants** (`ScheduleExecutor` est une classe native ordinaire).
- Les appels déclenchés par une tâche planifiée utilisent `subject=None` (voir spec, section Décisions) : les services ciblés doivent être `secure=False`.
- Les lectures internes de `scheduledTask` par `ScheduleExecutor` se font `subject=None` (lecture système, comme dans `permissions_app`).
- Committer après la revue de chaque tâche : `git -c user.name="Aurélien Pisu" -c user.email="aurelien.pisu@gmail.com" commit -m "scheduler: <message court>"`, jamais pendant qu'un sous-agent travaille encore dans le dépôt, jamais de ligne d'attribution, jamais de push.

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `pyproject.toml` | projet uv, dépendances locales éditables |
| `src/main/python/ycappuccino/scheduler/cron.py` | `next_fire_time(expression, after) -> datetime` |
| `src/main/python/ycappuccino/scheduler/models/scheduled_task.py` | `ScheduledTask` |
| `src/main/python/ycappuccino/scheduler/executor.py` | `ScheduleExecutor` |
| `example/conf/application.yml`, `example/conf/config.properties`, `example/demo/greeting.py` | exemple exécutable |
| `README.md` | documentation |

---

### Task 1 : projet uv, suppression du legacy, `cron.py`

**Files:**
- Modify: `scheduler/pyproject.toml` (tout le fichier)
- Create: `scheduler/.gitignore` (déjà `data`, ajouter `.venv`, `__pycache__`, `dist`)
- Delete (`git rm`) : `build.py`, `setup.py`, `src/main/python/ycappuccino/scheduler/bundles/` (dossier complet), `src/main/python/ycappuccino/scheduler/models/scheduler.py`, `src/main/python/ycappuccino/scheduler/models/task.py`, `src/main/python/ycappuccino/scheduler/conf/` (dossier complet)
- Create: `scheduler/src/main/python/ycappuccino/scheduler/__init__.py` (contenu remplacé)
- Create: `scheduler/src/main/python/ycappuccino/scheduler/cron.py`
- Create: `scheduler/src/unittest/python/test_cron.py`

**Interfaces:**
- Produces: `ycappuccino.scheduler.cron.next_fire_time(expression: str, after: datetime) -> datetime`.

- [ ] **Step 1: Remove the PyBuilder project and legacy files**

```bash
cd scheduler
git rm -q -r build.py setup.py \
  src/main/python/ycappuccino/scheduler/bundles \
  src/main/python/ycappuccino/scheduler/models/scheduler.py \
  src/main/python/ycappuccino/scheduler/models/task.py \
  src/main/python/ycappuccino/scheduler/conf
mkdir -p src/unittest/python
```

Si l'une de ces suppressions est refusée par le système de permissions : ne pas contourner, s'arrêter et le signaler dans le rapport final (un module qui échoue à s'importer n'est qu'un warning pour `core`, pas bloquant).

`scheduler/pyproject.toml` :

```toml
[project]
name = "ycappuccino-scheduler"
version = "0.1.0"
description = "YCappuccino scheduler: recurring tasks calling a named IExposedService"
requires-python = ">=3.10"
dependencies = [
    "ycappuccino-api",
    "ycappuccino-core",
    "ycappuccino-storage",
    "ycappuccino-endpoints-service",
]

[build-system]
requires = ["uv_build>=0.12.13,<0.13"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "ycappuccino.scheduler"
module-root = "src/main/python"

[tool.uv.sources]
ycappuccino-api = { path = "../api", editable = true }
ycappuccino-core = { path = "../core", editable = true }
ycappuccino-storage = { path = "../storage", editable = true }
ycappuccino-endpoints-service = { path = "../endpoints_service", editable = true }
```

`scheduler/.gitignore` :

```
data
.venv
__pycache__
dist
```

`scheduler/src/main/python/ycappuccino/scheduler/__init__.py` :

```python
"""recurring tasks calling a named IExposedService on a cron schedule"""
```

Run (depuis `scheduler`) : `uv sync`
Expected: environnement créé, les quatre dépendances locales installées en éditable.

- [ ] **Step 2: Write the failing tests for `cron.next_fire_time`**

`scheduler/src/unittest/python/test_cron.py` :

```python
import unittest
from datetime import datetime

from ycappuccino.scheduler.cron import next_fire_time


class TestNextFireTime(unittest.TestCase):

    def test_every_minute(self):
        after = datetime(2026, 1, 1, 10, 30, 15)

        self.assertEqual(next_fire_time("* * * * *", after), datetime(2026, 1, 1, 10, 31))

    def test_exact_minute_and_hour(self):
        after = datetime(2026, 1, 1, 10, 0)

        self.assertEqual(next_fire_time("0 3 * * *", after), datetime(2026, 1, 2, 3, 0))

    def test_after_the_hour_moves_to_next_day(self):
        after = datetime(2026, 1, 1, 4, 0)

        self.assertEqual(next_fire_time("0 3 * * *", after), datetime(2026, 1, 2, 3, 0))

    def test_list_of_minutes(self):
        after = datetime(2026, 1, 1, 10, 0)

        self.assertEqual(next_fire_time("0,15,30,45 * * * *", after), datetime(2026, 1, 1, 10, 15))

    def test_range(self):
        after = datetime(2026, 1, 1, 10, 0)

        self.assertEqual(next_fire_time("0 9-17 * * *", after), datetime(2026, 1, 1, 10, 0).replace(hour=10, minute=0))

    def test_range_excludes_outside_hours(self):
        after = datetime(2026, 1, 1, 18, 0)

        self.assertEqual(next_fire_time("0 9-17 * * *", after), datetime(2026, 1, 2, 9, 0))

    def test_step(self):
        after = datetime(2026, 1, 1, 10, 1)

        self.assertEqual(next_fire_time("*/15 * * * *", after), datetime(2026, 1, 1, 10, 15))

    def test_range_with_step(self):
        after = datetime(2026, 1, 1, 0, 0)

        self.assertEqual(next_fire_time("0 8-20/4 * * *", after), datetime(2026, 1, 1, 8, 0))

    def test_month_rollover(self):
        after = datetime(2026, 1, 31, 23, 59)

        self.assertEqual(next_fire_time("0 0 1 * *", after), datetime(2026, 2, 1, 0, 0))

    def test_year_rollover(self):
        after = datetime(2026, 12, 31, 23, 59)

        self.assertEqual(next_fire_time("0 0 1 1 *", after), datetime(2027, 1, 1, 0, 0))

    def test_specific_month(self):
        after = datetime(2026, 1, 1, 0, 0)

        self.assertEqual(next_fire_time("0 0 1 6 *", after), datetime(2026, 6, 1, 0, 0))

    def test_weekday_sunday_is_zero(self):
        # 2026-01-04 is a Sunday
        after = datetime(2026, 1, 1, 0, 0)

        self.assertEqual(next_fire_time("0 0 * * 0", after), datetime(2026, 1, 4, 0, 0))

    def test_day_of_month_and_weekday_are_combined_with_and(self):
        # documented simplification: both restricted fields must match (not POSIX cron's OR).
        # 2026-01-01 is a Thursday (weekday 4); the 1st that is also a Thursday is 2026-01-01 itself,
        # so from just after midnight the next match is 2026-02-05 (first Thursday-the-5th... actually
        # the next day that is both day=1 and weekday=4)
        after = datetime(2026, 1, 1, 0, 1)

        result = next_fire_time("0 0 1 * 4", after)

        self.assertEqual(result.day, 1)
        self.assertEqual(result.isoweekday() % 7, 4)

    def test_no_solution_raises(self):
        with self.assertRaises(ValueError):
            next_fire_time("0 0 31 2 *", datetime(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify they fail**

Run (depuis `scheduler`) : `uv run python -m unittest discover -s src/unittest/python -p test_cron.py`
Expected: `ModuleNotFoundError: No module named 'ycappuccino.scheduler.cron'`.

- [ ] **Step 4: Implement `cron.py`**

`scheduler/src/main/python/ycappuccino/scheduler/cron.py` :

```python
"""
Minimal 5-field cron expression parser and "next fire time" computation, pure and
dependency-free (see spec: no croniter, day-of-month/weekday combined with AND).
"""

from datetime import datetime, timedelta

_MAX_YEARS = 4


def next_fire_time(expression: str, after: datetime) -> datetime:
    """earliest minute-aligned datetime strictly after `after` matching expression
    ("minute hour day month weekday", weekday 0=Sunday..6=Saturday); ValueError if none
    is found within _MAX_YEARS years of `after`"""
    minutes, hours, days, months, weekdays = _parse(expression)
    candidate = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)
    deadline = candidate.replace(year=candidate.year + _MAX_YEARS)

    while candidate < deadline:
        if candidate.month not in months:
            candidate = _first_of_next_month(candidate)
            continue
        if candidate.day not in days or _cron_weekday(candidate) not in weekdays:
            candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
            continue
        if candidate.hour not in hours:
            candidate = (candidate + timedelta(hours=1)).replace(minute=0)
            continue
        if candidate.minute not in minutes:
            candidate = candidate + timedelta(minutes=1)
            continue
        return candidate

    raise ValueError(f"no fire time for {expression!r} within {_MAX_YEARS} years of {after!r}")


def _cron_weekday(moment: datetime) -> int:
    return moment.isoweekday() % 7  # Monday=1..Saturday=6, Sunday=0


def _first_of_next_month(moment: datetime) -> datetime:
    if moment.month == 12:
        return moment.replace(year=moment.year + 1, month=1, day=1, hour=0, minute=0)
    return moment.replace(month=moment.month + 1, day=1, hour=0, minute=0)


def _parse(expression: str):
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields (minute hour day month weekday), got {expression!r}")
    minute, hour, day, month, weekday = fields
    return (
        _parse_field(minute, 0, 59),
        _parse_field(hour, 0, 23),
        _parse_field(day, 1, 31),
        _parse_field(month, 1, 12),
        _parse_field(weekday, 0, 6),
    )


def _parse_field(field: str, low: int, high: int) -> set:
    values = set()
    for part in field.split(","):
        values |= _parse_part(part, low, high)
    return values


def _parse_part(part: str, low: int, high: int) -> set:
    range_part, _, step_text = part.partition("/")
    step = int(step_text) if step_text else 1
    if range_part == "*":
        start, end = low, high
    elif "-" in range_part:
        start_text, end_text = range_part.split("-")
        start, end = int(start_text), int(end_text)
    else:
        return {int(range_part)}
    return set(range(start, end + 1, step))
```

- [ ] **Step 5: Run tests to verify they pass**

Run (depuis `scheduler`) : `uv run python -m unittest discover -s src/unittest/python`
Expected: `OK`.

---

### Task 2 : modèle `ScheduledTask`

**Files:**
- Create: `scheduler/src/main/python/ycappuccino/scheduler/models/scheduled_task.py`
- Modify: `scheduler/src/main/python/ycappuccino/scheduler/models/__init__.py` (vide, déjà présent)
- Create: `scheduler/src/unittest/python/scheduler_fixtures.py`
- Test: `scheduler/src/unittest/python/test_scheduled_task.py`

**Interfaces:**
- Consumes: `ycappuccino.api.decorators.Item/Property`, `ycappuccino.api.models.Model`, `ycappuccino.core.decorator_app.App` (déjà construits).
- Produces: `ScheduledTask` (collection `scheduled_tasks`, item `scheduledTask`, pluriel `scheduled-tasks`, `secure_read=True, secure_write=True`) avec `name`, `cron`, `service`. `scheduler_fixtures.create_manager()` : un `Manager` réel sur `MemoryStorage`, même forme que `storage`/`endpoints_service`.

- [ ] **Step 1: Write the fixtures and the failing test**

`scheduler/src/unittest/python/scheduler_fixtures.py` :

```python
"""
Fixtures shared by the scheduler tests: a real Manager on MemoryStorage, no framework.
"""

import os
import tempfile

from ycappuccino.storage.files import LocalFileStore
from ycappuccino.storage.items import ItemManager
from ycappuccino.storage.manager import Manager
from ycappuccino.storage.memory import MemoryStorage

# importing the model registers it with ItemManager
from ycappuccino.scheduler.models import scheduled_task  # noqa: F401


def create_manager():
    """manager on a memory storage; the caller removes the returned directory"""
    directory = tempfile.mkdtemp()
    manager = Manager(MemoryStorage(), ItemManager(), [], [], LocalFileStore(os.path.join(directory, "files")))
    return manager, directory
```

`scheduler/src/unittest/python/test_scheduled_task.py` :

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `scheduler`) : `uv run python -m unittest discover -s src/unittest/python -p test_scheduled_task.py`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`scheduler/src/main/python/ycappuccino/scheduler/models/scheduled_task.py` :

```python
"""
ScheduledTask: a cron expression and the name of the IExposedService it triggers.
"""

from ycappuccino.api.decorators import Item, Property
from ycappuccino.api.models import Model
from ycappuccino.core.decorator_app import App


@App(name="ycappuccino_scheduler")
@Item(
    collection="scheduled_tasks", name="scheduledTask", plural="scheduled-tasks",
    secure_read=True, secure_write=True,
)
class ScheduledTask(Model):

    def __init__(self, a_dict=None):
        super().__init__(a_dict)
        self._name = None
        self._cron = None
        self._service = None

    @Property(name="name")
    def name(self, a_value):
        self._name = a_value

    @Property(name="cron")
    def cron(self, a_value):
        self._cron = a_value

    @Property(name="service")
    def service(self, a_value):
        self._service = a_value
```

- [ ] **Step 4: Run tests to verify they pass**

Run (depuis `scheduler`) : `uv run python -m unittest discover -s src/unittest/python`
Expected: `OK`.

---

### Task 3 : `ScheduleExecutor`

**Files:**
- Create: `scheduler/src/main/python/ycappuccino/scheduler/executor.py`
- Test: `scheduler/src/unittest/python/test_executor.py`

**Interfaces:**
- Consumes (Task 1/2) : `cron.next_fire_time`, `scheduler_fixtures.create_manager`, `ScheduledTask`. `ycappuccino.api.storage.IManager`, `ycappuccino.api.endpoints_service.IServiceEndpoint`, `ycappuccino.api.core.IActivityLogger`, `ycappuccino.api.core_base.YCappuccinoType`.
- Produces: `ScheduleExecutor(manager, endpoint, logger, poll_interval=1.0)`, une classe `YCappuccinoComponent` ordinaire, méthode async `_fire_due_tasks(now)` testable isolément.

- [ ] **Step 1: Write the failing tests**

`scheduler/src/unittest/python/test_executor.py` :

```python
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

    async def call(self, name, method, extra_path, params, body, subject):
        self.calls.append((name, method, extra_path, params, body, subject))
        if self.error is not None:
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `scheduler`) : `uv run python -m unittest discover -s src/unittest/python -p test_executor.py`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`scheduler/src/main/python/ycappuccino/scheduler/executor.py` :

```python
"""
ScheduleExecutor: loads scheduledTask at start() and fires IServiceEndpoint.call on schedule.

See spec (2026-09-15-scheduler-design.md) for the design decisions: subject=None on triggered
calls (targets must be secure=False), tasks loaded once at start (no hot reload), a background
thread woken every `poll_interval` seconds rather than sched.scheduler.
"""

import asyncio
import threading
from datetime import datetime
from typing import Optional

from ycappuccino.api.core import IActivityLogger
from ycappuccino.api.core_base import YCappuccinoComponent, YCappuccinoType
from ycappuccino.api.endpoints_service import IServiceEndpoint
from ycappuccino.api.storage import IManager
from ycappuccino.scheduler.cron import next_fire_time

_ITEM_ID = "scheduledTask"


class ScheduleExecutor(YCappuccinoComponent):

    def __init__(
        self,
        manager: IManager,
        endpoint: IServiceEndpoint,
        logger: YCappuccinoType(IActivityLogger, "(name=main)"),
        poll_interval: float = 1.0,
    ):
        self._manager = manager
        self._endpoint = endpoint
        self._logger = logger
        self._poll_interval = poll_interval
        self._tasks: dict = {}
        self._next_fire: dict = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    async def start(self):
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

    async def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self):
        while not self._stop_event.is_set():
            now = datetime.now()
            if any(next_fire <= now for next_fire in self._next_fire.values()):
                asyncio.run(self._fire_due_tasks(now))
            self._stop_event.wait(self._poll_interval)

    async def _fire_due_tasks(self, now: datetime):
        for task_id, next_fire in list(self._next_fire.items()):
            if next_fire > now:
                continue
            document = self._tasks[task_id]
            try:
                await self._endpoint.call(document["service"], "POST", [], {}, {}, None)
            except Exception:
                self._logger.warning(f"scheduled call to {document['service']!r} (task {task_id!r}) failed")
            self._next_fire[task_id] = next_fire_time(document["cron"], now)


from datetime import timedelta as _timedelta  # noqa: E402

_ONE_MINUTE = _timedelta(minutes=1)
```

(Le dernier import est délibérément placé après la classe pour rester à côté de son unique usage sans polluer l'en-tête ; à la relecture, préférer le remonter en haut du fichier avec les autres imports si cela lit mieux — fonctionnellement identique.)

- [ ] **Step 4: Run tests to verify they pass**

Run (depuis `scheduler`) : `uv run python -m unittest discover -s src/unittest/python`
Expected: `OK`.

---

### Task 4 : intégration au framework, exemple, README et vérification finale

**Files:**
- Test: `scheduler/src/unittest/python/test_scheduler_framework.py`
- Test: `scheduler/src/unittest/python/test_readme.py`
- Create: `scheduler/README.md`
- Modify: `scheduler/example/conf/application.yml` (tout le fichier)
- Create: `scheduler/example/conf/config.properties` (si nécessaire)
- Create: `scheduler/example/demo/__init__.py`, `scheduler/example/demo/greeting.py`

**Interfaces:**
- Consumes : tout ce qui précède.

- [ ] **Step 1: Write the integration test**

`scheduler/src/unittest/python/test_scheduler_framework.py` :

```python
import unittest

from ycappuccino.core.framework import Framework
from ycappuccino.core.testing import TemporaryApplication, wait_until

APPLICATION = {
    "conf/application.yml": """
        name: schedulertest
        bundle_prefix:
          - ycappuccino.storage
          - ycappuccino.endpoints_service
          - ycappuccino.scheduler
          - PACKAGE
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
        Greeting = self.app.module("greeting").Greeting

        # TaskBootstrap writes the task at its own start(); ScheduleExecutor may have already
        # loaded its tasks before that if it started first, so also wait for the task to exist
        # before expecting a call is unnecessary here: bundle_prefix order lists PACKAGE last but
        # component start order across bundles is not guaranteed — poll for the actual effect.
        wait_until(lambda: len(Greeting.calls) > 0, timeout=5)

        self.assertGreater(len(Greeting.calls), 0)


if __name__ == "__main__":
    unittest.main()
```

Note pour l'implémenteur : si l'ordre de démarrage entre `TaskBootstrap` (écrit la tâche) et `ScheduleExecutor` (la charge à son propre `start()`) n'est pas garanti par le framework et que le test est flaky, inverser la dépendance : faire dépendre `ScheduleExecutor` d'un signal, ou plus simplement charger la tâche directement dans les fichiers de `APPLICATION` via un composant qui s'exécute avant (par exemple en donnant à `TaskBootstrap` une dépendance fictive sur rien et en acceptant un `wait_until` avec un timeout plus long ; si after investigation l'ordre est bien non déterministe, écrire la tâche via un fichier de données préchargé par `MemoryStorage` n'est pas possible — dans ce cas, le plus simple est de laisser `ScheduleExecutor` recharger si aucune tâche n'était présente à son démarrage n'est PAS fait ici (hors périmètre, voir spec) : la solution retenue est que `TaskBootstrap` **précède** `ScheduleExecutor` dans `bundle_prefix`, ce qui n'influence pas l'ordre de démarrage des composants (seulement le scan) — si le flake se produit réellement en pratique, le corriger en faisant de `ScheduleExecutor` une dépendance de `TaskBootstrap` inversée n'a pas de sens ; la solution robuste est alors de donner à `TaskBootstrap` un poids de démarrage antérieur via une dépendance explicite sur `IManager` seul (déjà le cas) et d'accepter que ce test vérifie un comportement asynchrone de bout en bout avec `wait_until`, pas un ordre garanti.

- [ ] **Step 2: Run the integration test**

Run (depuis `scheduler`) : `uv run python -m unittest discover -s src/unittest/python -p test_scheduler_framework.py`
Expected: `OK`. Si le test est flaky à cause de l'ordre de démarrage `TaskBootstrap`/`ScheduleExecutor`, mesurer d'abord (relancer 5-10 fois) avant de changer la conception ; un simple `wait_until` plus long côté `Greeting.calls` suffit généralement puisque `ScheduleExecutor` réévalue toutes les `poll_interval` (0.05s) secondes et qu'une tâche créée après son chargement initial ne sera vue qu'au prochain redémarrage (documenté, pas un bug) — **si c'est le cas en pratique**, corriger le test en créant la tâche AVANT de démarrer le framework serait impossible (pas de framework pour appeler `up_sert`) ; la correction alors correcte est de donner à `ScheduleExecutor` une dépendance constructeur sur un composant `TaskBootstrap | None` optionnel pour forcer son démarrage après, ou plus simplement d'écrire la tâche via une pré-population du fichier `MemoryStorage` que le composant `ScheduleExecutor` lira — trancher au moment de l'implémentation selon ce que révèle le premier run, et documenter le choix final dans le README/spec si l'ordre s'avère non trivial.

- [ ] **Step 3: Write the README**

`scheduler/README.md` (même structure que `endpoints_service/README.md`) :

````markdown
# ycappuccino-scheduler

Tâches récurrentes natives : un modèle `ScheduledTask` (nom, expression cron, nom d'un `IExposedService`) et un composant `ScheduleExecutor` qui l'exécute à l'heure dite.

Conception : [docs/superpowers/specs/2026-09-15-scheduler-design.md](docs/superpowers/specs/2026-09-15-scheduler-design.md).

Prérequis : lire les README de [core](../core/README.md), [storage](../storage/README.md) et [endpoints_service](../endpoints_service/README.md).

## Mise en place

```bash
uv add --editable ../scheduler
```

`conf/application.yml` :

```yaml
bundle_prefix:
  - ycappuccino.storage
  - ycappuccino.endpoints_service
  - ycappuccino.scheduler
  - myapp
layers:
  ycappuccino_storage_memory:
    active: true
```

`ScheduleExecutor` charge les `scheduledTask` existantes au démarrage et se déclenche ensuite tout seul ; aucune configuration supplémentaire n'est nécessaire (`poll_interval`, en secondes, est réglable via `components: ScheduleExecutor: {poll_interval: 1.0}`).

## Modèle

```python
from ycappuccino.scheduler.models.scheduled_task import ScheduledTask

task = ScheduledTask()
task.id("greet-every-minute")
task.name("Greet every minute")
task.cron("* * * * *")       # minute heure jour mois jour-de-semaine (0=dimanche)
task.service("greeting")      # nom d'un IExposedService (endpoints_service)
await manager.up_sert_model(task)
```

`ScheduledTask` est un `@Item` normal (`secure_read=True, secure_write=True`) : `http_server` expose `/api/crud/scheduled-tasks` sans code supplémentaire.

**Important** : l'appel déclenché passe `subject=None` (appel système, voir la conception). Le service ciblé doit donc être `secure=False`.

## Exemple

```python
from ycappuccino.api.endpoints_service import IExposedService, ServiceResult


class Greeting(IExposedService):
    name = "greeting"
    secure = False

    def __init__(self):
        pass

    async def call(self, method, extra_path, params, body, subject):
        print("hello from the scheduler")
        return ServiceResult(body={})

    async def start(self):
        pass

    async def stop(self):
        pass
```

Une `ScheduledTask` avec `cron="* * * * *"` et `service="greeting"` appelle `Greeting.call` chaque minute.

## Tester avec scheduler

`ScheduleExecutor._fire_due_tasks(now)` déclenche les tâches dues sans horloge réelle :

```python
import unittest
from datetime import datetime
from unittest import mock

from ycappuccino.api.endpoints_service import IServiceEndpoint, ServiceResult
from ycappuccino.scheduler.executor import ScheduleExecutor


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


class TestGreeting(unittest.IsolatedAsyncioTestCase):
    async def test_a_due_task_triggers_its_service(self):
        endpoint = FakeEndpoint()
        executor = ScheduleExecutor(mock.Mock(), endpoint, mock.Mock())
        now = datetime(2026, 1, 1, 10, 0)
        executor._tasks["t1"] = {"_id": "t1", "cron": "* * * * *", "service": "greeting"}
        executor._next_fire["t1"] = now

        await executor._fire_due_tasks(now)

        self.assertEqual(endpoint.calls, ["greeting"])
```

## Développer scheduler

```bash
uv sync
uv run python -m unittest discover -s src/unittest/python
```

L'exemple `example/` se lance avec `cd example && uv run --project .. ycappuccino`.
````

- [ ] **Step 4: Write the README test**

`scheduler/src/unittest/python/test_readme.py` : reprend exactement l'exemple de la section « Tester avec scheduler » du README (le test est la source de vérité ; ajuster le README si nécessaire pour qu'il corresponde caractère pour caractère à ce test).

- [ ] **Step 5: Run the README test**

Run (depuis `scheduler`) : `uv run python -m unittest discover -s src/unittest/python -p test_readme.py`
Expected: `OK`.

- [ ] **Step 6: Rebuild the example**

`scheduler/example/conf/application.yml` :

```yaml
---
name: scheduler-demo
bundle_prefix:
  - ycappuccino.storage
  - ycappuccino.endpoints_service
  - ycappuccino.scheduler
  - demo
layers:
  ycappuccino_storage_memory:
    active: true
config:
  http_server:
    active: false
```

`scheduler/example/demo/__init__.py` : fichier vide.

`scheduler/example/demo/greeting.py` : le composant `Greeting` (section Exemple du README) et un `TaskBootstrap` (`YCappuccinoComponent`, dépend d'`IManager`) qui crée la `ScheduledTask` `greet-every-minute` à son `start()`, comme dans le test d'intégration.

- [ ] **Step 7: Final verification**

Run (depuis `scheduler`) : `uv run python -m unittest discover -s src/unittest/python`
Expected: `OK` pour tous les tests (`test_cron`, `test_scheduled_task`, `test_executor`, `test_scheduler_framework`, `test_readme`).

Puis vérifier que l'exemple démarre sans erreur (quelques secondes, arrêté au `Ctrl+C` ou via un timeout de commande) :

```bash
cd example && timeout 5 uv run --project .. ycappuccino; cd ..
```

Expected: pas de traceback dans la sortie ni dans `example/data/log/Log-Activity-main.log`.
