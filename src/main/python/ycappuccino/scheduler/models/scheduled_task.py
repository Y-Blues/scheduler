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

    def __init__(self, a_dict: dict | None = None) -> None:
        super().__init__(a_dict)
        self._name = None
        self._cron = None
        self._service = None

    @Property(name="name")
    def name(self, a_value: str) -> None:
        self._name = a_value

    @Property(name="cron")
    def cron(self, a_value: str) -> None:
        self._cron = a_value

    @Property(name="service")
    def service(self, a_value: str) -> None:
        self._service = a_value
