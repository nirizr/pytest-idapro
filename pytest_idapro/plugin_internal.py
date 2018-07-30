import pytest

import os
import tempfile
import subprocess

import multiprocessing


class InternalDeferredPlugin(object):
    def __init__(self, config):
        self.ida_path = config.getoption('--ida')
        self.ida_file = config.getoption('--ida-file')
        self.remote_conn, self.conn = multiprocessing.Pipe()

    def pytest_runtestloop(self, session):
        internal_script = os.path.join(os.path.dirname(__file__),
                                       "idapro_internal",
                                       "idapro_internal.py")

        script_args = '{}'.format(self.remote_conn.fileno())
        logfile = tempfile.NamedTemporaryFile(delete=False)
        args = [
            self.ida_path,
            # autonomous mode. IDA will not display dialog boxes.
            # Designed to be used together with -S switch.
            "-A",
            "-S\"{}\" {}".format(internal_script, script_args),
            "-L{}".format(logfile.name),
            # Load user-provided or start with an empty database
            self.ida_file if self.ida_file else "-t"
        ]
        print(args)
        proc = subprocess.Popen(args=args)
        self.conn.send("ping")
        self.conn.send("ping")
        if self.conn.poll(2):
            print(self.conn.recv())
        # TODO: actually handle responses from worker IDA process
        proc.wait()
        print(logfile.read())
        return True

    def pytest_collection(self):
        # prohibit collection of test items in master process. test collection
        # should be done by a worker with access to IDA modules
        return True

    @pytest.fixture(scope='session')
    def idapro_app(self):
        yield None
