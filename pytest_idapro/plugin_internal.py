import os
import tempfile
import subprocess

import multiprocessing
import copy

import logging

# logging.basicConfig()
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('pytest-idapro.internal.manager')


class IdaManager(object):
    def __init__(self, ida_path, ida_file):
        self.ida_path = ida_path
        self.ida_file = ida_file
        self.remote_conn, self.conn = multiprocessing.Pipe()
        self.logfile = tempfile.NamedTemporaryFile(delete=False)
        self.stop = False

    def start(self):
        internal_script = os.path.join(os.path.dirname(__file__),
                                       "idaworker_main.py")

        script_args = '{}'.format(self.remote_fd())
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

        # send ping and wait for response to make sure connection is working
        # TODO: add a timeout and raise an exception on failure
        self.command_ping()

        # self.proc.wait()

        return True

    def finish(self, interrupted):
        if interrupted:
            log.warning("Abrupt termination of external test session. worker "
                        "log: %s", self.logfile.read())
        log.info("Stopping...")
        if not self.proc.poll():
            self.proc.kill()
        self.stop = True

    def __del__(self):
        log.info("%s", self.logfile.read())

    def remote_fd(self):
        return self.remote_conn.fileno()

    def command_ping(self):
        self.send('ping')
        self.recv('pong')

    def command_dependencies(self):
        self.send('dependencies', 'check')
        if self.recv('dependencies') == ('ready',):
            return

        self.send('dependencies', 'install')
        self.recv('dependencies', 'ready')

    def command_autoanalysis_wait(self):
        self.send('autoanalysis', 'wait')
        self.recv('autoanalysis', 'done')

    def command_configure(self, config):
        option_dict = copy.deepcopy(vars(config.option))
        option_dict["plugins"].append("no:cacheprovider")
        self.send('configure', config.args, option_dict)
        self.recv('configure', 'done')

    def command_cmdline_main(self):
        self.send('cmdline_main')
        self.recv('cmdline_main', 'start')

    def command_collect(self):
        self.recv('collection', 'start')
        return self.recv('collection', 'finish')

    def command_runtest(self):
        self.recv('runtest', 'start')
        while True:
            r = self.recv('runtest')
            if r[0] not in ('logstart', 'logfinish'):
                break

            yield r
        # runtest finish will be swallowed by the last while condition,
        # causing it to break.
        # self.recv('runtest', 'finish')

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


class InternalDeferredPlugin(object):
    def __init__(self, config):
        ida_path = config.getoption('--ida')
        ida_file = config.getoption('--ida-file')
        self.ida_manager = IdaManager(ida_path, ida_file)
        self.config = config

    def pytest_runtestloop(self, session):
        try:
            self.ida_manager.start()

            self.ida_manager.command_dependencies()
            self.ida_manager.command_autoanalysis_wait()
            self.ida_manager.command_configure(self.config)
            self.ida_manager.command_cmdline_main()
            collected_tests = self.ida_manager.command_collect()
            # TODO: call hooks, collection start, item and finish
            session.testscollected = len(collected_tests)
            for r in self.ida_manager.command_runtest():
                if r[0] == 'logstart':
                    self.config.hook.pytest_runtest_logstart(nodeid=r[1],
                                                             location=r[2])
                if r[0] == 'logfinish' and hasattr(self.config.hook,
                                                   'pytest_runtest_logfinish'):
                    self.config.hook.pytest_runtest_logfinish(nodeid=r[1],
                                                              location=r[2])

            self.ida_manager.recv('cmdline_main', 'finish')
            self.ida_manager.command_quit()
        except Exception:
            log.exception("Exception encountered in runtestloop")
            raise

        return True

    def pytest_sessionfinish(self, exitstatus):
        self.ida_manager.finish(exitstatus == 2)  # EXIT_ITERRUPTED

    def pytest_collection(self):
        # prohibit collection of test items in master process. test collection
        # should be done by a worker with access to IDA modules
        return True
