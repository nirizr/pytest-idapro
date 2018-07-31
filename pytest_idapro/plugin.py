import pytest

import os
import inspect


def pytest_addoption(parser):
    group = parser.getgroup("idapro", "interactive disassembler testing "
                                      "facilities")
    group._addoption('--ida', help="Run inside an IDA instance instead of "
                                   "mocking IDA up.")
    group._addoption('--ida-file', help="Provide a file to load by IDA, "
                                        "either IDB or any other readable "
                                        "format. If no file is provided, an "
                                        "empty database will be automatically "
                                        "loaded.")


def pytest_cmdline_main(config):
    ida_path = config.getoption('--ida')
    if ida_path and not os.path.isfile(ida_path):
        raise pytest.UsageError("--ida must point to an IDA executable.")
    ida_file = config.getoption('--ida-file')
    if ida_file and not os.path.isfile(ida_file):
        raise pytest.UsageError("--ida-file must point to an IDA file.")
    # TODO: free text ida args?


def pytest_configure(config):
    if config.getoption('--ida'):
        from . import plugin_internal
        deferred_plugin = plugin_internal.InternalDeferredPlugin(config)
    else:
        from . import plugin_mock
        deferred_plugin = plugin_mock.MockDeferredPlugin()
    config.pluginmanager.register(deferred_plugin)


idapro_plugin_entries = []
idapro_action_entries = []


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
