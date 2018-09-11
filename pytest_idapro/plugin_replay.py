import pickle
import json

import sys

from .plugin_mock import MockDeferredPlugin, modules_list

import logging

logging.basicConfig()
log = logging.getLogger('pytest-idapro.internal.manager')


class ReplayDeferredPlugin(MockDeferredPlugin):
    def __init__(self, config, *args, **kwargs):
        super(ReplayDeferredPlugin, self).__init__(*args, **kwargs)
        self.replay_file = config.getoption('--ida-replay')
        self.config = config
        self.session = None

        if self.replay_file.endswith(".json"):
            with open(self.replay_file, 'rb') as fh:
                self.records = json.load(fh)
        elif self.replay_file.endswith(".pickle"):
            with open(self.replay_file, 'rb') as fh:
                self.records = pickle.load(fh)
        else:
            raise ValueError("Invalid file extension provided for replay file")

    def pytest_configure(self):
        for module_name in modules_list:
            if module_name in self.records:
                module_record = self.records[module_name]
            else:
                # TODO: get a generic solution for this hack
                # translate alias library names
                t = {'ida_area': 'ida_range', 'ida_ints': 'ida_bytes',
                     'ida_queue': 'ida_problems', 'ida_srarea': 'ida_segregs'}
                module_record = self.records[t[module_name]]
            module = init_replay(ModuleReplay(), module_name, module_record)
            sys.modules[module_name] = module

    @staticmethod
    def pytest_unconfigure():
        for module in modules_list:
            del sys.modules[module]


def init_replay(replay, object_name, records):
    replay.__object_name__ = object_name
    replay.__records__ = records

    return replay


def replay_factory(name, records):
    record = records[name]
    value_type = record['value_type']
    if value_type == 'value':
        return record['data']
    elif value_type == 'module':
        return init_replay(AbstractReplay(), name, record['data'])
    elif value_type == 'class':
        class ClassReplay(AbstractReplay):
            def __new__(cls, *args, **kwargs):
                print("classreplay.__new__", cls, args, kwargs)
                return super(ClassReplay, cls).__new__(cls, *args, **kwargs)

        return init_replay(ClassReplay, name, record)
    elif value_type == 'function':
        return init_replay(FunctionReplay(), name, record)
    elif value_type == 'proxy':
        return init_replay(AbstractReplay(), name, record['data'])
    else:
        raise ValueError("Unhandled value type", name, record)


class AbstractReplay(object):
    __slots__ = ["__object_name__", "__records__"]

    def __getattribute__(self, attr, oga=object.__getattribute__):
        object_name = oga(self, '__object_name__')
        records = oga(self, '__records__')
        if attr == '__object_name__':
            return object_name
        elif attr == '__records__':
            return records

        print("getattr called for {} in {} with {}".format(attr, object_name,
                                                           records.get(attr,
                                                                       None)))

        # TODO: this should probably done better, really proxy those (and
        # other) values.
        if attr == "__bases__":
            return tuple()
            # return oga(self, '__class__').__bases__
        if attr == '__subclasses__':
            def get_subclasses():
                return oga(self, '__class__').__subclasses__
            return get_subclasses
        if attr not in records:
            raise ValueError("Missing attribute", attr, object_name, records)

        return replay_factory(attr, records)

    def __setattr__(self, attr, val, osa=object.__setattr__):
        if attr == '__object_name__' or attr == '__records__':
            osa(self, attr, val)
        else:
            self.__records__[attr] = {'data': val, 'value_type': 'override'}


class ModuleReplay(AbstractReplay):
    pass


class FunctionReplay(AbstractReplay):
    def __call__(self, *args, **kwargs):
        # if we don't have calls recorded, just return None as a guess value
        if not self.__records__['data']:
            return None

        print(self.__records__)
        return replay_factory('retval', self.__records__['data'][0])
