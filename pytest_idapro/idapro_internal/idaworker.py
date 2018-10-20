import ida_auto

from multiprocessing.connection import Client
import platform
import logging

logging.basicConfig()
log = logging.getLogger('pytest-idapro.internal.worker')


class IdaWorker(object):
    def __init__(self, conn_addr, *args, **kwargs):
        super(IdaWorker, self).__init__(*args, **kwargs)
        self.daemon = True
        self.conn = Client(conn_addr)
        self.stop = False
        self.quit_ida = True
        self.pytest_config = None
        from PyQt5.QtWidgets import qApp
        self.qapp = qApp

    def run(self):
        try:
            while not self.stop:
                command = self.recv()
                response = self.handle_command(*command)
                if response:
                    self.conn.send(response)
        except RuntimeError:
            log.exception("Runtime error encountered during message handling")
        except EOFError:
            log.info("remote connection closed abruptly, terminating.")
            self.quit_ida = True

        return self.quit_ida

    def recv(self):
        while not self.stop:
            self.qapp.processEvents()
            if not self.conn.poll(1):
                continue

            return self.conn.recv()

    def send(self, *s):
        return self.conn.send(s)

    def handle_command(self, command, *command_args):
        handler_name = "command_" + command
        if not hasattr(self, handler_name):
            raise RuntimeError("Unrecognized command recieved: "
                               "'{}'".format(command))
        log.debug("Received command: {} with args {}".format(command,
                                                             command_args))
        response = getattr(self, handler_name)(*command_args)
        log.debug("Responding: {}".format(response))
        return response

    def command_dependencies(self, action, *plugins):
        # test pytest is installed and return ready if it is
        if action == "check":
            try:
                import pytest
                del pytest

                for plugin in plugins:
                    __import__(plugin)
                return ('dependencies', 'ready')
            except ImportError:
                pass

            # pytest is missing, we'll report so and expect to be requested to
            # install
            self.send('dependencies', 'missing')
        elif action == "install":
            # test at least pip exists, otherwise we're doomed to fail
            try:
                import pip
                del pip
            except ImportError:
                return ('dependencies', 'failed')

            # handle different versions of pip
            try:
                from pip import main as pip_main
            except ImportError:
                # here be dragons
                from pip._internal import main as pip_main

            # ignoring installed six and upgrading is requried to avoid an osx
            # bug see https://github.com/pypa/pip/issues/3165 for more details
            pip_command = ['install', 'pytest'] + list(plugins)
            if platform.system() == 'Darwin':
                pip_command += ['--upgrade', '--user', '--ignore-installed',
                                'six']
            pip_main(pip_command)

            # make sure pytest was successfully installed
            try:
                import pytest
                del pytest
                return ('dependencies', 'ready')
            except ImportError:
                return ('dependencies', 'failed')
        else:
            raise RuntimeError("Unexpected dependencies argument: "
                               "{}".format(action))

    @staticmethod
    def command_autoanalysis(action):
        if action == "wait":
            ida_auto.auto_wait()
            return ('autoanalysis', 'done',)
        else:
            raise RuntimeError("Invalid action received for command: "
                               "{}".format(action))

    def command_configure(self, args, option_dict):
        from _pytest.config import Config
        import plugin_worker

        self.pytest_config = Config.fromdictargs(option_dict, args)
        self.pytest_config.args = args

        plugin = plugin_worker.WorkerPlugin(worker=self)
        self.pytest_config.pluginmanager.register(plugin)

        return ('configure', 'done')

    def command_cmdline_main(self):
        self.send('cmdline_main', 'start')
        self.pytest_config.hook.pytest_cmdline_main(config=self.pytest_config)
        self.send('cmdline_main', 'finish')

    @staticmethod
    def command_ping():
        return ('pong',)

    def command_quit(self, quit_ida):
        self.stop = True
        self.quit_ida = quit_ida
        return ("quitting",)

    @staticmethod
    def command_save_records(dest_file):
        # we have to fetch record_module manually because of how it was loaded
        # from ida's python/init.py
        import sys
        if 'record_module' not in sys.modules:
            return ('save_records', 'failed')
        record_module = sys.modules['record_module']

        record_module.dump_records(dest_file)
        return ('save_records', 'done')
