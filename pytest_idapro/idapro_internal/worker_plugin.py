import pytest


class WorkerPlugin(object):
    pass

    @pytest.fixture(scope='session')
    def idapro_app(self):
        from PyQt5 import QtWidgets
        yield QtWidgets.qApp
