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

`ScheduleExecutor` charge les `scheduledTask` existantes une seule fois, à son démarrage, puis se déclenche tout seul ; aucune configuration supplémentaire n'est nécessaire. `poll_interval` (en secondes, défaut `1.0`) est réglable via `components: ScheduleExecutor: {poll_interval: 1.0}`.

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

`ScheduledTask` est un `@Item` normal (`secure_read=True, secure_write=True`) : `http_server` expose `/api/crud/scheduled-tasks` sans code supplémentaire (lister, créer, modifier, supprimer). Une modification prend effet au **prochain redémarrage** de l'application : les tâches sont chargées une seule fois, au démarrage de `ScheduleExecutor` (pas de rechargement à chaud, voir la conception).

**Important** : l'appel déclenché passe `subject=None` (appel système, voir la conception). Le service ciblé par une tâche planifiée doit donc être `secure=False`.

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

`ScheduleExecutor._fire_due_tasks(now)` déclenche les tâches dues sans horloge réelle ni sommeil :

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

La logique de planification elle-même (calcul de la prochaine échéance) se teste directement, sans horloge injectée : `ycappuccino.scheduler.cron.next_fire_time("0 3 * * *", after)` retourne un `datetime`, comparable dans une assertion classique.

## Développer scheduler

```bash
uv sync
uv run python -m unittest discover -s src/unittest/python
```

L'exemple `example/` se lance avec `cd example && uv run --project .. ycappuccino`.
