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
    group._addoption('--ida-record', help="Record all IDA API interactions "
                                          "to specified json file, to later "
                                          "be used with the --ida-replay flag "
                                          "to simulate test execution without "
                                          "an IDA instance.")
    group._addoption('--ida-replay', help="Provide a recording of a previous "
                                          "IDA test execution. It will be "
                                          "replayed without an IDA executable "
                                          "as response to IDA API calls.")
    group._addoption('--ida-keep', action="store_true", default=False,
                     help="Keep IDA instance running instead of terminating "
                          "it. Only acceptable with --ida.")


@pytest.hookimpl(tryfirst=True)
def pytest_cmdline_main(config):
    ida_path = config.getoption('--ida')
    ida_file = config.getoption('--ida-file')
    ida_record = config.getoption('--ida-record')
    ida_replay = config.getoption('--ida-replay')
    ida_keep = config.getoption('--ida-keep')

    # force removal of plugins interfering / incompatible with running
    # internally
    if ida_path:
        config.pluginmanager.set_blocked("pytest-qt")
        config.pluginmanager.set_blocked("xdist")
        config.pluginmanager.set_blocked("xvfb")
        config.pluginmanager.set_blocked("xvfb.looponfail")

    if ida_path and not os.path.isfile(ida_path):
        raise pytest.UsageError("--ida must point to an IDA executable.")
    if ida_file and not ida_path:
        raise pytest.UsageError("--ida-file requires --ida to be specified as "
                                "well")
    if ida_file and not os.path.isfile(ida_file):
        raise pytest.UsageError("--ida-file must point to an IDA file.")

    # record related validation
    if ida_record and not ida_path:
        raise pytest.UsageError("Cannot record without running in an IDA "
                                "instance")

    # replay related validations
    if ida_replay and ida_path:
        raise pytest.UsageError("Cannot replay while running in an IDA "
                                "instance")
    if ida_replay and not os.path.isfile(ida_replay):
        raise pytest.UsageError("--ida-replay must point to an IDA session "
                                "recording file.")

    if ida_keep and not ida_path:
        raise pytest.UsageError("--ida-keep is only meaningful when --ida is "
                                "also provided.")
    # TODO: free text ida args?


def pytest_configure(config):
    if config.getoption('--ida'):
        from . import plugin_internal
        deferred_plugin = plugin_internal.InternalDeferredPlugin(config)
    elif config.getoption('--ida-replay'):
        from . import plugin_replay
        deferred_plugin = plugin_replay.ReplayDeferredPlugin(config)
    else:
        from . import plugin_mock
        deferred_plugin = plugin_mock.MockDeferredPlugin()
    config.pluginmanager.register(deferred_plugin)
