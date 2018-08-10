import os

import pytest


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


@pytest.hookimpl(tryfirst=True)
def pytest_cmdline_main(config):
    ida_path = config.getoption('--ida')
    ida_file = config.getoption('--ida-file')

    # force removal of plugins interfering / incompatible with running
    # internally
    if ida_path:
        config.pluginmanager.set_blocked("pytest-qt")
        config.pluginmanager.set_blocked("xdist")
        config.pluginmanager.set_blocked("xvfb")

    if ida_path and not os.path.isfile(ida_path):
        raise pytest.UsageError("--ida must point to an IDA executable.")
    if ida_file and not ida_path:
        raise pytest.UsageError("--ida-file requires --ida to be specified as "
                                "well")
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
