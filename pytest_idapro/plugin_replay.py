import os
import json

from .idapro_internal import replay_module

from .plugin_mock import MockDeferredPlugin


module_aliases = {'ida_area': 'ida_range', 'ida_ints': 'ida_bytes',
                  'ida_queue': 'ida_problems', 'ida_srarea': 'ida_segregs'}


class ReplayDeferredPlugin(MockDeferredPlugin):
    def __init__(self, config, *args, **kwargs):
        super(ReplayDeferredPlugin, self).__init__(*args, **kwargs)
        self.replay_file = config.getoption('--ida-replay')
        self.config = config
        self.session = None

        with open(self.replay_file, 'rb') as fh:
            self.records = json.load(fh)

        base_paths = set()
        root_dir = self.config.rootdir.strpath
        for p in self.config.getoption('file_or_dir'):
            base_paths.add(os.path.abspath(os.path.join(root_dir, p)) + "/")
        replay_module.setup(base_paths)

    def get_module(self, module_name):
        module_name = module_aliases.get(module_name, module_name)
        module_record = self.records[module_name]
        return replay_module.module_replay(module_name, module_record)

    @staticmethod
    def pytest_collection_finish(session):
        session.items.sort(key=lambda i: i.nodeid)
