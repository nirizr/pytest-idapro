import json
import sys

from .idapro_internal import replay_module

from .plugin_mock import MockDeferredPlugin, modules_list


class ReplayDeferredPlugin(MockDeferredPlugin):
    def __init__(self, config, *args, **kwargs):
        super(ReplayDeferredPlugin, self).__init__(*args, **kwargs)
        self.replay_file = config.getoption('--ida-replay')
        self.config = config
        self.session = None

        with open(self.replay_file, 'rb') as fh:
            self.records = json.load(fh)

    def pytest_configure(self):
        for module_name in modules_list:
            t = {'ida_area': 'ida_range', 'ida_ints': 'ida_bytes',
                 'ida_queue': 'ida_problems', 'ida_srarea': 'ida_segregs'}
            module_name = t.get(module_name, module_name)
            module_record = self.records[module_name]
            module = replay_module.module_replay(module_name, module_record)
            sys.modules[module_name] = module

    @staticmethod
    def pytest_unconfigure():
        for module in modules_list:
            if module not in sys.modules:
                continue
            del sys.modules[module]
