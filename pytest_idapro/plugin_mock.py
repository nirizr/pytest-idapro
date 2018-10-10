import sys
import threading

from . import idapro_mock

from PyQt5 import QtWidgets
import pytest

from .plugin_base import BasePlugin

modules_list = ['ida_allins', 'ida_area', 'ida_auto', 'ida_bytes', 'ida_dbg',
                'ida_diskio', 'ida_entry', 'ida_enum', 'ida_expr', 'ida_fixup',
                'ida_fpro', 'ida_frame', 'ida_funcs', 'ida_gdl', 'ida_graph',
                'ida_hexrays', 'ida_ida', 'ida_idaapi', 'ida_idd', 'ida_idp',
                'ida_ints', 'ida_kernwin', 'ida_lines', 'ida_loader',
                'ida_moves', 'ida_nalt', 'ida_name', 'ida_netnode',
                'ida_offset', 'ida_pro', 'ida_problems', 'ida_queue',
                'ida_registry', 'ida_search', 'ida_segment', 'ida_segregs',
                'ida_srarea', 'ida_strlist', 'ida_struct', 'ida_typeinf',
                'ida_ua', 'ida_xref', 'ida_range']
modules_list.extend(['idaapi', 'idc', 'idautils'])


class MockDeferredPlugin(BasePlugin):
    def __init__(self, *args, **kwargs):
        super(MockDeferredPlugin, self).__init__(*args, **kwargs)
        self.app = None
        self.app_menu = None
        self.app_window = None
        self.app_thread = None

    def pytest_configure(self):
        for module_name in modules_list:
            sys.modules[module_name] = self.get_module(module_name)

    @staticmethod
    def get_module(module_name):
        return getattr(idapro_mock, module_name)

    @staticmethod
    def pytest_unconfigure():
        for module in modules_list:
            if module not in sys.modules:
                continue
            del sys.modules[module]

        # TODO: if this is deleted here it should also be created in
        # pytest_configure instead of idapro_mock.idc
        if idapro_mock.idc.tempidadir:
            import shutil
            shutil.rmtree(idapro_mock.idc.tempidadir)
            idapro_mock.idc.tempidadir = None

    def pytest_sessionstart(self):
        # Create main Qt objects
        self.app = QtWidgets.QApplication([])
        qmdiarea = QtWidgets.QMdiArea()
        self.app_menu = QtWidgets.QMenu()

        # Create and initialize QMainWindow
        self.app_window = QtWidgets.QMainWindow()
        self.app_window.setCentralWidget(qmdiarea)
        self.app_window.setMenuWidget(self.app_menu)
        self.app_window.show()

        # Create and start a Qt main thread
        self.app_thread = threading.Thread(target=self.app.exec_)
        self.app_thread.start()

    @pytest.fixture()
    def idapro_app(self):
        return self.app

    @pytest.fixture()
    def idapro_app_window(self):
        return self.app_window

    @pytest.fixture()
    def idapro_app_menu(self):
        return self.app_menu

    @pytest.fixture()
    def idapro_app_thread(self):
        return self.app_thread
