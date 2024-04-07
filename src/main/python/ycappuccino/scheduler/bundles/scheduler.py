# app="all"
import json

from ycappuccino_api.core.api import IActivityLogger, IService
from src.main.python.proxy import YCappuccinoRemote
from ycappuccino_api.storage.api import IManager
from ycappuccino_api.scheduler.api import IScheduler
import logging
from pelix.ipopo.decorators import (
    ComponentFactory,
    Requires,
    Validate,
    Invalidate,
    Provides,
    Instantiate,
)
import hashlib

"""
component that implement a scheduler of task
TODO Implem
"""
_logger = logging.getLogger(__name__)


@ComponentFactory("SchedulerService-Factory")
@Provides(
    specifications=[YCappuccinoRemote.__name__, IService.__name__, IScheduler.__name__]
)
@Requires("_log", IActivityLogger.__name__, spec_filter="'(name=main)'")
@Requires("_manager_task", IManager.__name__, spec_filter="'(item_id=task)'")
@Requires("_jwt", IJwt.__name__)
@Instantiate("SchedulerService")
@App(name="ycappuccino.rest-app")
class SchedulerService(IService):

    def __init__(self):
        super(IService, self).__init__()
        self._manager_task = None
        self._log = None
        self._jwt = None

    def is_secure(self):
        return False

    def get_name(self):
        return "scheduler"

    def post(self, a_header, a_url_path, a_body):
        """return tuple of 2 element that admit a dictionnary of header and a body"""
        # execute
        return None

    def put(self, a_header, a_url_path, a_body):
        return None

    def get(self, a_header, a_url_path):
        return None

    def delete(self, a_header, a_url_path):
        return None

    @Validate
    def validate(self, context):
        self._log.info("SchedulerService validating")

        self._log.info("SchedulerService validated")

    @Invalidate
    def invalidate(self, context):
        self._log.info("SchedulerService invalidating")

        self._log.info("SchedulerService invalidated")
