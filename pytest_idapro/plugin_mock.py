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
                'ida_offset', 'ida_pro', 'ida_queue', 'ida_registry',
                'ida_search', 'ida_segment', 'ida_srarea', 'ida_strlist',
                'ida_struct', 'ida_typeinf', 'ida_ua', 'ida_xref']
modules_list.extend(['idaapi', 'idc', 'idautils'])


class MockDeferredPlugin(BasePlugin):
    def __init__(self, *args, **kwargs):
        super(MockDeferredPlugin, self).__init__(*args, **kwargs)
        self.qapp = None
        self.tapp = None

    @staticmethod
    def pytest_configure(config):
        del config

        for module_name in modules_list:
            module = getattr(idapro_mock, module_name)
            sys.modules[module_name] = module

    @staticmethod
    def pytest_unconfigure(config):
        del config

        for module in modules_list:
            del sys.modules[module]

        # TODO: if this is deleted here it should also be created in
        # pytest_configure instead of idapro_mock.idc
        if idapro_mock.idc.tempidadir:
            import shutil
            shutil.rmtree(idapro_mock.idc.tempidadir)
            idapro_mock.idc.tempidadir = None

    @pytest.fixture(scope='session')
    def idapro_app(self):
        self.qapp = QtWidgets.QApplication([])
        qmainwin = QtWidgets.QMainWindow()
        qmdiarea = QtWidgets.QMdiArea()
        qmainwin.setCentralWidget(qmdiarea)
        qmenu = QtWidgets.QMenu()
        qmainwin.setMenuWidget(qmenu)
        self.tapp = threading.Thread(target=self.qapp.exec_)
        self.tapp.start()
        yield self.qapp
