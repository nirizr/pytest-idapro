import pytest

import os
import tempfile
import subprocess

import multiprocessing

import inspect
from functools import wraps

import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('pytest-idapro.internal.manager')


def command_decorator(expected_response=None, prefix="command_"):
    def decorator(func):
        if not func.__name__.startswith(prefix):
            raise ValueError("command_decorator can only be used on "
                             "'command_' prefixed functions. Used on: "
                             "{}".format(func))

        @wraps(func)
        def wrap(self, *args, **kwargs):
            send = func.__name__[len(prefix):]
            self.send(send)
            if not expected_response:
                return func(self, *args, **kwargs)

            response = self.recv()
            command_args = response.split(None, 1)
            command = command_args.pop()
            if (isinstance(expected_response, str) and
                command != expected_response):
                raise RuntimeError("Invalid response recieved for '{}' "
                                   "command: {}".format(func.__name__,
                                                        response))

            # expose relevant arguments in function signature
            func_args = {'response', 'command', 'command_args'}
            func_args &= set(inspect.getargspec(func)[0])
            kwargs.update({k: locals()[k] for k in func_args})
            return func(self, *args, **kwargs)
        return wrap
    return decorator


class IdaManager(object):
    def __init__(self, ida_path, ida_file):
        self.ida_path = ida_path
        self.ida_file = ida_file
        self.remote_conn, self.conn = multiprocessing.Pipe()
        self.logfile = tempfile.NamedTemporaryFile(delete=False)

    def start(self):
        internal_script = os.path.join(os.path.dirname(__file__),
                                       "idapro_internal",
                                       "idapro_internal.py")

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

    def __del__(self):
        log.info("%s", self.logfile.read())

    def remote_fd(self):
        return self.remote_conn.fileno()

    @command_decorator(expected_response="pong")
    def command_ping(self):
        pass

    @command_decorator(expected_response="quitting")
    def command_quit(self):
        pass

    def send(self, s):
        log.debug("Sending: %s", s)
        return self.conn.send(s)

    def recv(self):
        try:
            r = self.conn.recv()
            log.debug("Received: %s", r)
            return r
        except Exception:
            log.critical("Exception during receive, worker output: %s",
                         self.logfile.read())
            raise


class InternalDeferredPlugin(object):
    def __init__(self, config):
        ida_path = config.getoption('--ida')
        ida_file = config.getoption('--ida-file')
        self.ida_manager = IdaManager(ida_path, ida_file)

    def pytest_runtestloop(self, session):
        self.ida_manager.start()

        self.ida_manager.command_quit()

        # TODO: when should this return?
        del self.ida_manager
        return True

    def pytest_collection(self):
        # prohibit collection of test items in master process. test collection
        # should be done by a worker with access to IDA modules
        return True

    @pytest.fixture(scope='session')
    def idapro_app(self):
        yield None
