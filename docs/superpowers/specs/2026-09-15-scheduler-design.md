# scheduler natif : design

Date : 2026-09-15. Sous-projet de la reprise des dépôts YCappuccino, après `core`, `api`, `storage`, `endpoints_storage`, `http_server`, `endpoints_service` (et en parallèle de `permissions_app`, `scripts`).

## Objectif

`scheduler` permet de déclarer des tâches récurrentes (« à chaque minute paire », « tous les jours à 3h »...) dont le déclenchement appelle, par son nom, un `IExposedService` d'`endpoints_service` — la façon native de nommer une action indépendamment du transport. Pas de transport, pas de nouvelle route HTTP : juste un modèle `@Item` (CRUD gratuit via `http_server`) et un composant qui l'exécute.

## Décisions

| Sujet | Décision |
|---|---|
| Style | Composant natif, aucun décorateur |
| Modèles legacy | `Scheduler` et `Task` (legacy) étaient deux modèles quasi identiques (`name` + `cron`), sans référence entre eux ni champ de cible : une duplication sans valeur ajoutée. Fusionnés en un seul modèle `ScheduledTask` |
| Cible d'une tâche | Le **nom** d'un `IExposedService` (`endpoints_service`), pas une référence `@ItemReference` : ce n'est pas un item stocké, c'est un identifiant de service, comme `RolePermission.rights` référence des motifs de permission par leur texte |
| Expression de planification | Cron à 5 champs (`minute heure jour mois jour-de-semaine`), classique et suffisant pour le besoin ; pas un simple intervalle, pour rester compatible avec l'usage legacy (`cron` textuel) |
| Bibliothèque cron | Aucune dépendance externe (`croniter` etc.) : un parseur minimal (`ycappuccino.scheduler.cron`), pur, sans état, testé directement — la logique tient en une centaine de lignes et n'a pas besoin d'un paquet dédié |
| Sémantique jour/semaine | Simplification assumée par rapport à POSIX cron : quand jour-du-mois et jour-de-semaine sont tous les deux contraints (ni l'un ni l'autre à `*`), les deux conditions sont combinées en **ET**, pas en OU comme le vrai cron. La plupart des expressions utiles laissent l'un des deux à `*` ; le comportement OU de POSIX cron est une source de confusion classique, écartée ici pour rester simple |
| Mécanisme d'exécution | Un thread en tâche de fond (`threading.Thread` + `threading.Event`), pas `sched` du stdlib : `sched.scheduler` propose une seule prochaine échéance à la fois côté bibliothèque, alors qu'ici plusieurs tâches à cron différents doivent être réévaluées indépendamment ; une boucle `poll` explicite reste plus simple à lire et à tester qu'un réordonnancement de `sched.scheduler` à chaque `up_sert` |
| Granularité de réveil | `poll_interval` (défaut 1s) : le thread se réveille toutes les secondes, vérifie si une tâche est due (`next_fire <= now`), l'exécute si oui, et recalcule sa prochaine échéance. Suffisant pour une granularité cron à la minute ; documenté comme non adapté à une précision sub-minute |
| Rechargement des tâches | Chargées une seule fois à `start()` (« arme » le planificateur). Une modification faite par CRUD sur `scheduledTask` prend effet au **prochain redémarrage**, pas à chaud. Un rechargement à chaud demanderait un `ITrigger` sur `scheduledTask` ; hors périmètre, noté en section Hors périmètre |
| Sujet des appels déclenchés | `subject=None` (appel système/anonyme), cohérent avec la convention de `permissions_app` (« les lectures système utilisent `subject=None` »). **Conséquence assumée** : `IServiceEndpoint._check` refuse tout service `secure=True` dès que le sujet est `None` (`NotAuthenticated`), donc **les services ciblés par une tâche planifiée doivent être déclarés `secure=False`**. Une alternative — un sujet système dédié (ex. `{"sub": "system", "tid": "system"}`) reconnu par une `IAuthorization` comme `RolePermissionAuthorization` — demanderait qu'un rôle système avec les bons droits existe dans `permissions_app`, une dépendance cross-repo que ce sous-projet ne peut pas créer (il ne doit pas toucher `permissions_app`). Documenté comme contrainte, pas contourné |
| Exposition HTTP | Aucune route nouvelle. `ScheduledTask` est un `@Item` normal : `http_server` expose déjà `/api/crud/scheduled-tasks` (lecture, création, modification, suppression) dès que le modèle est enregistré. Pas de servlet bespoke pour un « lancer maintenant » : hors périmètre (voir plus bas) |
| Erreur d'appel | Une exception levée par `IServiceEndpoint.call` (service introuvable, refusé, ou erreur interne) est journalisée (`IActivityLogger`, warning) et n'interrompt pas la boucle : les autres tâches et les prochaines échéances de la même tâche continuent normalement |

## 1. Modèle (`models/scheduled_task.py`)

```python
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

`secure_read=True, secure_write=True` reprend exactement le legacy (`Scheduler`/`Task`) : consulter ou modifier la planification est une opération sensible, contrôlée comme n'importe quel item par `endpoints_storage`.

## 2. `cron.py` — module pur, sans composant

```python
def next_fire_time(expression: str, after: datetime) -> datetime:
    """earliest minute-aligned datetime strictly after `after` that matches expression
    (5 fields: minute hour day month weekday, weekday 0=Sunday..6=Saturday); raises ValueError
    if no match is found within 4 years of `after` (a malformed expression, e.g. day 31 in February only)"""
```

- Chaque champ accepte `*`, un entier, une liste séparée par des virgules, un intervalle `A-B`, un pas `*/N` ou `A-B/N` — assez pour couvrir l'usage réel sans réimplémenter tout POSIX cron.
- Recherche par sauts (mois puis jour puis heure puis minute), bornée à 4 ans, pas une itération minute par minute sur toute la plage : reste rapide même pour une expression rare (29 février un dimanche).
- Jour de semaine : `0=dimanche..6=samedi` (convention cron classique), calculé depuis `date.isoweekday() % 7`.
- Testé directement, sans horloge injectée ni sommeil réel : on donne un `after` fixe et on vérifie le `datetime` retourné (voir section Tests).

## 3. `ScheduleExecutor` (`executor.py`) — composant natif

```python
class ScheduleExecutor(YCappuccinoComponent):

    def __init__(
        self,
        manager: IManager,
        endpoint: IServiceEndpoint,
        logger: YCappuccinoType(IActivityLogger, "(name=main)"),
        poll_interval: float = 1.0,
    ):
        self._manager, self._endpoint, self._logger = manager, endpoint, logger
        self._poll_interval = poll_interval
        self._tasks: dict[str, dict] = {}       # task id -> storage document
        self._next_fire: dict[str, datetime] = {}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    async def start(self):
        """loads scheduledTask (subject=None), arms an initial next_fire per task, starts the thread"""

    async def stop(self):
        """signals the thread and joins it"""

    async def _fire_due_tasks(self, now: datetime):
        """for every task whose next_fire <= now: calls the target service (errors logged, not raised),
        then recomputes its next_fire from `now`"""

    def _loop(self):
        """background thread body: while not stopped, asyncio.run(_fire_due_tasks(now())) if something
        is due, then _stop_event.wait(poll_interval)"""
```

Points clés :

- **Chargement initial (`start`)** : pour chaque tâche, la première échéance est calculée avec `next_fire_time(cron, now - 1 minute)`, pas `next_fire_time(cron, now)`. Cela permet à une tâche dont le cron correspond à la minute en cours de se déclencher dès le démarrage (utile pour un test d'intégration rapide et pour ne pas perdre la minute de démarrage), au prix d'un déclenchement possible dans la même minute que le redémarrage — accepté, cohérent avec « un scheduler qui redémarre rattrape la minute en cours ».
- **`_fire_due_tasks` est async et pure vis-à-vis du thread** : elle ne fait qu'itérer sur `self._tasks`/`self._next_fire` et appeler `self._endpoint.call(service, "POST", [], {}, {}, None)`. Testable directement avec un faux `IServiceEndpoint` et un `now` choisi, **sans attendre un vrai minuteur** (voir Tests).
- **Le thread (`_loop`) est le seul endroit qui touche l'horloge réelle et `asyncio.run`** : il n'est exercé qu'en test d'intégration (framework réel) et dans un test de cycle de vie court (`start`/`stop` ne bloque pas).
- Aucune interface dédiée n'est publiée pour `ScheduleExecutor` (rien d'autre n'en dépend), comme `AccountBootStrap` dans `permissions_app`.

## 4. CRUD et « lancer maintenant »

`ScheduledTask` étant un `@Item` enregistré, `http_server` expose automatiquement :

| Méthode | Route | Effet |
|---|---|---|
| GET | `/api/crud/scheduled-tasks` | liste des tâches planifiées |
| GET | `/api/crud/scheduled-tasks/<id>` | une tâche |
| POST | `/api/crud/scheduled-tasks` | créer une tâche (effective au prochain redémarrage) |
| PUT | `/api/crud/scheduled-tasks/<id>` | modifier une tâche (effective au prochain redémarrage) |
| DELETE | `/api/crud/scheduled-tasks/<id>` | supprimer une tâche |

Aucune route ni servlet supplémentaire n'est nécessaire. Un « lancer maintenant » (déclencher une tâche planifiée hors de son cron) n'est pas fourni : il n'ajouterait qu'un appel direct à `IServiceEndpoint.call(service, ...)`, que l'appelant peut déjà faire lui-même sans passer par `scheduler` — inutile de dupliquer ce chemin ici (voir Hors périmètre).

## 5. Packaging et exemple

```
scheduler/
  pyproject.toml
  README.md
  example/
    conf/application.yml
    conf/config.properties
    demo/__init__.py
    demo/greeting.py        # IExposedService de démonstration, appelé par la tâche planifiée
  src/main/python/ycappuccino/scheduler/
    __init__.py
    cron.py                 # next_fire_time
    executor.py             # ScheduleExecutor
    models/
      __init__.py
      scheduled_task.py      # ScheduledTask
  src/unittest/python/
    test_cron.py
    test_executor.py
    test_scheduler_framework.py
    test_readme.py
```

- **`pyproject.toml`** (uv, `uv_build`) : projet `ycappuccino-scheduler`, module `ycappuccino.scheduler`, racine `src/main/python`. Dépendances : `ycappuccino-api`, `ycappuccino-core`, `ycappuccino-storage`, `ycappuccino-endpoints-service`, toutes en source de chemin local éditable. Aucune dépendance externe.
- **Supprimés** : `build.py`, `setup.py`, `src/main/python/ycappuccino/scheduler/bundles/` (bundle iPOPO legacy), `src/main/python/ycappuccino/scheduler/models/scheduler.py` et `task.py` (remplacés par `scheduled_task.py`), `src/main/python/ycappuccino/scheduler/conf/config.yaml` (déclarait une couche `ycappuccino_scheduler` sans utilité ici : aucun composant de ce sous-projet ne porte de `__ycappuccino_layer__`).
- **Exemple** : couche mémoire de `storage`, un `IExposedService` de démonstration (`Greeting`, `secure=False`) et une `ScheduledTask` qui l'appelle chaque minute (`cron="* * * * *"`), créée par un petit composant de démarrage (`up_sert` direct, pas de fichier de données).
- **README** : mise en place, modèle, exemple, avertissement sur `secure=False`, section « Développer scheduler ».

## 6. Tests

| Fichier | Contenu |
|---|---|
| `test_cron.py` | champ `*`, entier, liste, intervalle, pas (`*/N`, `A-B/N`) ; combinaison mois/jour/heure/minute ; passage au mois suivant, à l'année suivante ; jour-de-semaine (dimanche=0) ; jour-du-mois et jour-de-semaine combinés en ET ; expression sans solution (`ValueError`) |
| `test_executor.py` | `_fire_due_tasks` appelle le bon service quand `next_fire <= now`, n'appelle rien sinon, recalcule `next_fire` après déclenchement, plusieurs tâches indépendantes, une exception du endpoint est journalisée et n'interrompt pas les autres tâches ; `start`/`stop` démarrent et arrêtent le thread sans bloquer (avec un `poll_interval` court) |
| `test_scheduler_framework.py` | démarrage du framework réel (`TemporaryApplication`/`Framework`), `ScheduleExecutor` publié, une tâche `cron="* * * * *"` ciblant un service de test déclenche réellement un appel peu après le démarrage (le rattrapage de la minute en cours évite d'attendre une minute complète), sans mock de threading |
| `test_readme.py` | les exemples du README (déclaration du modèle, exécution directe de `_fire_due_tasks`) restent exécutables |

## 7. Hors périmètre

- **Rechargement à chaud** des tâches modifiées par CRUD : nécessiterait un `ITrigger` sur `scheduledTask` réarmant l'échéance en mémoire ; les tâches sont chargées une fois, au démarrage.
- **« Lancer maintenant »** dédié : un appelant qui veut déclencher une action immédiatement utilise directement `IServiceEndpoint.call`, sans passer par `scheduler`.
- **Sujet système authentifié** pour appeler des services `secure=True` depuis une tâche planifiée : demanderait une coordination avec `permissions_app` (rôle système) hors périmètre de ce sous-projet.
- **Persistance de l'historique des exécutions** (dernière exécution, succès/échec) : pas demandé, ajouterait un modèle supplémentaire ; les échecs sont seulement journalisés.
- **Cron à la seconde** ou fenêtres `poll_interval` inférieures à la seconde : la granularité cron est la minute, `poll_interval` par défaut est en secondes.

## 8. Risques

- **`poll_interval` par défaut (1s) réveille le thread 60 fois par minute** même sans tâche due : coût négligeable (une comparaison de `datetime` par tâche), mais documenté si un déploiement a des centaines de tâches.
- **Rattrapage au démarrage** (`next_fire_time(cron, now - 1 minute)`) : un redémarrage répété dans la même minute ne re-déclenche pas la tâche une seconde fois (l'échéance calculée avance après le premier déclenchement), mais un redémarrage juste après un déclenchement normal peut re-déclencher une tâche déjà exécutée cette minute-là si le process a redémarré avant que la minute suivante ne commence. Accepté : un scheduler qui redémarre n'a pas de mémoire fiable de ce qu'il a déjà exécuté sans persister un « dernier déclenchement », hors périmètre.
- **Services sécurisés inaccessibles** aux tâches planifiées (voir Décisions, sujet `subject=None`) : une limitation connue, pas une régression par rapport au legacy (qui n'implémentait déjà pas l'appel réel, `IService.post` retournait `None`).
