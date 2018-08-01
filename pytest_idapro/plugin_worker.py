import pytest

try:
    from plugin_base import BasePlugin
except ImportError:
    from .plugin_base import BasePlugin


class WorkerPlugin(BasePlugin):
    @pytest.fixture(scope='session')
    def idapro_app(self):
        from PyQt5 import QtWidgets
        yield QtWidgets.qApp
