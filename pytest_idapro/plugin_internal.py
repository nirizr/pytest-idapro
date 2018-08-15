import os
import tempfile
import subprocess

from multiprocessing.connection import Listener
import platform
import copy

import logging

logging.basicConfig()
log = logging.getLogger('pytest-idapro.internal.manager')


class InternalDeferredPlugin(object):
    def __init__(self, config):
        self.ida_path = config.getoption('--ida')
        self.ida_file = config.getoption('--ida-file')
        self.config = config
        self.session = None
        self.listener = Listener()
        self.conn = None
        self.logfile = tempfile.NamedTemporaryFile(delete=False)
        self.proc = None
        self.stop = False

    def ida_start(self):
        internal_script = os.path.join(os.path.dirname(__file__),
                                       "main_idaworker.py")

        script_args = '{}'.format(self.listener.address)
        args = [
            self.ida_path,
            # autonomous mode. IDA will not display dialog boxes.
            # Designed to be used together with -S switch.
            "-A",
            "-S\"{}\" {}".format(internal_script, script_args),
            "-L{}".format(self.logfile.name),
            # Load user-provided or start with an empty database
            self.ida_file if self.ida_file else "-t"
        ]
        log.debug("worker execution arguments: %s", args)
        self.proc = subprocess.Popen(args=args)

        # accept a single connection
        self.conn = self.listener.accept()
        self.listener.close()
        self.listener = None

    def ida_finish(self, interrupted):
        if interrupted:
            log.warning("Abrupt termination of external test session. worker "
                        "log: %s", self.logfile.read())
        log.info("Stopping...")
        if self.proc:
            self.proc.poll()
            if self.proc.returncode is None:
                self.proc.kill()
        self.stop = True

    def command_ping(self):
        self.send('ping')
        self.recv('pong')

    def command_dependencies(self):
        plugins = []
        if (hasattr(self.config.option, 'cov_source') and
            self.config.option.cov_source):
            plugins.append("pytest_cov")

        self.send('dependencies', 'check', *plugins)
        if self.recv('dependencies') == ('ready',):
            return

        self.send('dependencies', 'install', *plugins)
        self.recv('dependencies', 'ready')

    def command_autoanalysis_wait(self):
        self.send('autoanalysis', 'wait')
        self.recv('autoanalysis', 'done')

    def command_configure(self, config):
        option_dict = copy.deepcopy(vars(config.option))

        # block interfering plugins
        option_dict['plugins'].append("no:cacheprovider")
        option_dict['plugins'].append("no:pytest-qt")
        option_dict['plugins'].append("no:xdist")
        option_dict['plugins'].append("no:xvfb")
        option_dict['usepdb'] = False

        # cleanup our own plugin configuration
        option_dict["plugins"].append("no:idapro")
        del option_dict['ida']
        del option_dict['ida_file']

        if platform.system() == "Windows":
            # remove capturing, this doesn't properly work in windows
            option_dict["plugins"].append("no:terminal")
            option_dict["capture"] = "sys"
        self.send('configure', config.args, option_dict)
        self.recv('configure', 'done')

    def command_cmdline_main(self):
        self.send('cmdline_main')
        self.recv('cmdline_main', 'start')

    def command_collect(self):
        self.recv('collection', 'start')
        self.config.hook.pytest_collectstart()

        while True:
            r = self.recv('collection')
            if r[0] == 'report':
                report = self.deserialize_report("collect", r[1])
                self.config.hook.pytest_collectreport(report=report)
            elif r[0] == 'finish':
                collected_tests = r[1]
                self.session.testscollected = len(collected_tests)
                self.config.hook.pytest_collection_finish(session=self.session)
                break
            elif r[0] == 'modifyitems':
                self.config.hook.pytest_collection_modifyitems(
                    session=self.session,
                    config=self.config,
                    items=r[1])
            else:
                raise RuntimeError("Invalid collect response received: "
                                   "{}".format(r))

    def command_runtest(self):
        while True:
            r = self.recv('runtest')
            if r[0] == 'logstart':
                self.config.hook.pytest_runtest_logstart(nodeid=r[1],
                                                         location=r[2])
            elif r[0] == 'logreport':
                report = self.deserialize_report("test", r[1])
                self.config.hook.pytest_runtest_logreport(report=report)
            elif r[0] == 'logfinish':
                # the pytest_runtest_logfinish hook was introduced in pytest3.4
                if hasattr(self.config.hook, 'pytest_runtest_logfinish'):
                    self.config.hook.pytest_runtest_logfinish(nodeid=r[1],
                                                              location=r[2])
            elif r[0] == 'finish':
                break
            else:
                raise RuntimeError("Invalid runtest response received: "
                                   "{}".format(r))

    def command_quit(self):
        self.send('quit')
        self.recv('quitting')

    def send(self, *s):
        log.debug("Sending: %s", s)
        return self.conn.send(s)

    def recv(self, *args):
        try:
            while not self.conn.poll(1):
                if self.stop:
                    raise KeyboardInterrupt

            r = self.conn.recv()
            log.debug("Received: %s", r)
        except Exception:
            log.critical("Exception during receive, worker output: %s",
                         self.logfile.read())
            raise

        if args and r[:len(args)] != args:
            raise RuntimeError("Invalid response recieved; while expecting "
                               "'{}' got '{}'".format(args, r))

        return r[len(args):]

    def deserialize_report(self, reporttype, report):
        from _pytest.runner import TestReport, CollectReport
        from pytest import Item
        if 'result' in report:
            newresult = []
            for item in report['result']:
                item_obj = Item(item['name'], config=self.config,
                                session=self.session)
                newresult.append(item_obj)
            report['result'] = newresult
        if reporttype == "test":
            return TestReport(**report)
        elif reporttype == "collect":
            return CollectReport(**report)
        else:
            raise RuntimeError("Invalid report type: {}".format(reporttype))

    def pytest_runtestloop(self, session):
        self.session = session
        try:
            self.ida_start()
            self.command_ping()

            self.command_dependencies()
            self.command_autoanalysis_wait()
            self.command_configure(self.config)
            self.command_cmdline_main()

            self.command_collect()
            response = self.recv()

            if response == ('runtest', 'start'):
                self.command_runtest()
                exitstatus = self.recv('session', 'finish')
            elif response[:2] == ('session', 'finish'):
                exitstatus = response[2]
            else:
                raise RuntimeError("Unexpected response: {}".format(response))

            # TODO: The same exit status will be derived by pytest. might be
            # useful to make sure they match
            del exitstatus

            self.recv('cmdline_main', 'finish')
            self.command_quit()
        except Exception:
            self.ida_finish(True)
            raise

        return True

    def pytest_sessionfinish(self, exitstatus):
        self.ida_finish(exitstatus == 2)  # EXIT_ITERRUPTED

    @staticmethod
    def pytest_collection():
        # prohibit collection of test items in master process. test collection
        # should be done by a worker with access to IDA modules
        return True
