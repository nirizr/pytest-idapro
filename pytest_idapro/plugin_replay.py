import pickle
import json
import inspect
import exceptions

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
    replay.__name__ = object_name

    return replay


def replay_factory(name, records):
    record = records[name]
    value_type = record['value_type']
    if value_type == 'value' or value_type == 'override':
        return record['data']
    elif value_type == 'module':
        return init_replay(AbstractReplay(), name, record['data'])
    elif value_type == 'class':
        class ClassReplay(AbstractReplay):
            def __new__(cls, *args, **kwargs):
                print("classreplay.__new__", cls, args, kwargs, cls.__records__)
                o = super(ClassReplay, cls).__new__(cls)

                # TODO: handle more than one better
                args = list(args)
                for instance in cls.__records__['data']:
                    if (instance['args'] == args and
                        instance['kwargs'] == kwargs and
                        instance['name'] == cls.__name__):
                        return init_replay(o, name, instance)
                raise Exception("Failed matching", cls.__records__['data'], args, kwargs)

        return init_replay(ClassReplay, name, record)
    elif value_type == 'function':
        return init_replay(FunctionReplay(), name, record)
    elif value_type == 'proxy':
        return init_replay(AbstractReplay(), name, record['data'])
    elif value_type == 'exception':
        # TODO: make sure there's a msg in here
        cls = replay_factory('exception_class', record)
        return cls(*record['args'])
    elif value_type == 'exception_class':
        if not hasattr(exceptions, record['class_name']):
            return Exception

        return getattr(exceptions, record['class_name'])
    else:
        raise ValueError("Unhandled value type", name, record)


class AbstractReplay(object):
    __slots__ = ["__object_name__", "__records__"]

    def __getattribute__(self, attr, oga=object.__getattribute__):
        object_name = oga(self, '__object_name__')
        records = oga(self, '__records__')
        if attr == '__object_name__' or attr == '__name__':
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

        # TODO: improve logic over just picking the first available
        # based on matching variables or something
        data = self.__records__['data'][0]

        if 'callback' in data and data['callback']:
            for arg in args + tuple(kwargs.values()):
                # TODO: improve logic over just picking the first available
                if not inspect.isfunction(arg):
                    continue
                arg_data = data['callback'].get(arg.__name__, None)['data'][0]
                if not arg_data:
                    continue
                print("calling {} with {}".format(arg, arg_data))
                arg(*arg_data['args'], **arg_data['kwargs'])
                # TODO: validate return value is correct

        print(self.__records__)
        if 'exception' in data:
            raise replay_factory('exception', data)
        return replay_factory('retval', data)
