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

    def pytest_collectreport(self, report):
        serialized_report = self.serialize_report(report)
        self.worker.send('collection', 'report', serialized_report)

    def pytest_collection_modifyitems(self, items):
        # TODO: cannot serialize items, passing an empty list for now
        # items = [i.nodeid for i in items]
        self.worker.send('collection', 'modifyitems', [])

    def pytest_deselected(self, items):
        items = [i.nodeid for i in items]
        self.worker.send('collection', 'deselected', items)

    def pytest_collection_finish(self, session):
        session.items.sort(key=lambda i: i.nodeid)
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
        serialized_report = self.serialize_report(report)
        self.worker.send('runtest', 'logreport', serialized_report)

    # unsupported
    def pytest_internalerror(self, excrepr, excinfo):
        self.worker.send('internalerr', excrepr, excinfo)

    def pytest_sessionstart(self, session):
        self.worker.send('session', 'start')

    def pytest_report_header(self, config, startdir):
        self.worker.send('report', 'header', startdir)

    def pytest_terminal_summary(self, terminalreporter):
        self.worker.send('report', 'terminalsummary')

    @pytest.hookimpl(hookwrapper=True)
    def pytest_sessionfinish(self, exitstatus):
        yield
        self.worker.send('session', 'finish', exitstatus)

    @pytest.fixture(scope='session')
    def idapro_app(self):
        from PyQt5 import QtWidgets
        yield QtWidgets.qApp

    @staticmethod
    def serialize_report(report):
        from py.path import local
        from pytest import Item

        d = vars(report).copy()
        if hasattr(report.longrepr, "toterminal"):
            d['longrepr'] = str(report.longrepr)
        else:
            d['longrepr'] = report.longrepr

        for name, value in d.items():
            if isinstance(value, local):
                d[name] = str(value)
            elif name == "result":
                d['result'] = [{'name': item.name} for item in d['result']
                               if isinstance(item, Item)]

        return d
