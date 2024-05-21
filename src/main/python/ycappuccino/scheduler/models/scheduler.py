from ycappuccino.core.decorator_app import App

from ycappuccino.api.decorators import Item, ItemReference, Empty, Property, Reference
from ycappuccino.api.models import Model

"""
    model that describe a scheduler
"""


@Empty()
def empty():
    _empty = Scheduler()
    _empty.id("test")
    _empty.name("test")
    return _empty


@App(name="ycappuccino.scheduler")
@Item(
    collection="schedulers",
    name="scheduler",
    plural="schedulers",
    secure_write=True,
    secure_read=True,
)
class Scheduler(Model):
    def __init__(self, a_dict=None):
        super().__init__(a_dict)
        self._name = None
        self._cron = None

    @Property(name="name")
    def name(self, a_value):
        self._name = a_value

    @Property(name="cron")
    def cron(self, a_value):
        self._cron = a_value


empty()
