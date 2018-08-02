import pytest
import _pytest

try:
    from plugin_base import BasePlugin
except ImportError:
    from .plugin_base import BasePlugin


class WorkerPlugin(BasePlugin):
    def __init__(self, worker, *args, **kwargs):
        super(WorkerPlugin, self).__init__(*args, **kwargs)
        self.worker = worker
        self.config = None

    def pytest_cmdline_main(self, config):
        self.config = config

    def pytest_collection(self):
        self.worker.send('collection', 'start')

    def pytest_collection_finish(self, session):
        items = [i.nodeid for i in session.items]
        self.worker.send('collection', 'finish', items)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtestloop(self, session):
        self.worker.send('runtest', 'start')
        yield
        self.worker.send('runtest', 'finish')

    def pytest_runtest_logstart(self, nodeid, location):
        self.worker.send('runtest', 'logstart', nodeid, location)

    # the pytest_runtest_logfinish hook was introduced in pytest 3.4
    if hasattr(_pytest.hookspec, "pytest_runtest_logfinish"):
        def pytest_runtest_logfinish(self, nodeid, location):
            self.worker.send('runtest', 'logfinish', nodeid, location)

    def pytest_runtest_logreport(self, report):
        pass

    @pytest.fixture(scope='session')
    def idapro_app(self):
        from PyQt5 import QtWidgets
        yield QtWidgets.qApp
