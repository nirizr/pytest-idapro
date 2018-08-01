import inspect
import pytest


class IDAProEntriesScanner(pytest.Module):
    def __init__(self, *args, **kwargs):
        super(IDAProEntriesScanner, self).__init__(*args, **kwargs)

        self.idapro_plugin_entries = []
        self.idapro_action_entries = []

    def istestfunction(self, obj, name):
        if name == "PLUGIN_ENTRY":
            idapro_plugin_entries.append(obj)

    def istestclass(self, obj, name):
        if any(cls.__name__ == 'action_handler_t'
               for cls in inspect.getmro(obj)):
            self.idapro_action_entries.append(obj)


class BasePlugin(object):
    def __init__(self, *args, **kwargs):
        super(BasePlugin, self).__init__(*args, **kwargs)
        self.idapro_plugin_entries = []
        self.idapro_action_entries = []

    def pytest_collect_file(self, path, parent):
        if not path.ext == '.py':
            return

        scanner = IDAProEntriesScanner(path, parent)
        scanner.collect()

        self.idapro_plugin_entries = []
        self.idapro_action_entries = []

    def pytest_generate_tests(self, metafunc):
        if 'idapro_plugin_entry' in metafunc.fixturenames:
            metafunc.parametrize('idapro_plugin_entry',
                                 self.idapro_plugin_entries)
        if 'idapro_action_entry' in metafunc.fixturenames:
            metafunc.parametrize('idapro_action_entry',
                                 self.idapro_action_entries)
