import sys
import importlib
import inspect
import threading

from . import idapro_mock

from PyQt5 import QtWidgets
import pytest


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


idapro_plugin_entries = []
idapro_action_entries = []


def pytest_configure(config):
    del config
    for module_name in modules_list:
        module = getattr(idapro_mock, module_name)
        sys.modules[module_name] = module


def pytest_unconfigure(config):
    del config
    for module in modules_list:
        del sys.modules[module]

    if idapro_mock.idc.tempidadir:
        import shutil
        shutil.rmtree(idapro_mock.idc.tempidadir)
        idapro_mock.idc.tempidadir = None


@pytest.fixture(scope='session')
def idapro_app():
    qapp = QtWidgets.QApplication([])
    qmainwin = QtWidgets.QMainWindow()
    qmdiarea = QtWidgets.QMdiArea()
    qmainwin.setCentralWidget(qmdiarea)
    qmenu = QtWidgets.QMenu()
    qmainwin.setMenuWidget(qmenu)
    t = threading.Thread(target=qapp.exec_)
    t.start()
    yield qapp


class IDAProEntriesScanner(pytest.Module):
    def istestfunction(self, obj, name):
        if name == "PLUGIN_ENTRY":
            idapro_plugin_entries.append(obj)

    def istestclass(self, obj, name):
        if any(cls.__name__ == 'action_handler_t'
               for cls in inspect.getmro(obj)):
            idapro_action_entries.append(obj)


def pytest_collect_file(path, parent):
    if not path.ext == '.py':
        return

    scanner = IDAProEntriesScanner(path, parent)
    scanner.collect()


def pytest_generate_tests(metafunc):
    if 'idapro_plugin_entry' in metafunc.fixturenames:
        metafunc.parametrize('idapro_plugin_entry', idapro_plugin_entries)
    if 'idapro_action_entry' in metafunc.fixturenames:
        metafunc.parametrize('idapro_action_entry', idapro_action_entries)
