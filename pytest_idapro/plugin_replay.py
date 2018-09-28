import json
import inspect
try:
    import exceptions
except ImportError:
    import builtins as exceptions

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

        with open(self.replay_file, 'rb') as fh:
            self.records = json.load(fh)

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


def score(instance, args, kwargs, name):
    caller = inspect.stack()[3]

    print("Calculating", args, kwargs, name, caller[1:])
    print("Verses", instance['args'], instance['kwargs'], instance['name'], instance['caller_file'], instance['caller_line'], instance['caller_function'])

    s = 0
    s += 100 if str(name) != str(instance['name']) else 0
    s += sum(10 for a1, a2 in zip(args, instance['args'])
             if str(a1) != str(a2))
    s += sum(10 for a1, a2 in zip(kwargs, instance['kwargs'])
             if str(a1) != str(a2))
    s += abs(caller[2] - instance['caller_line'])
    s += 100 if str(caller[1]) != str(instance['caller_file']) else 0
    s += 100 if str(caller[3]) != str(instance['caller_function']) else 0

    print("Scored", s)

    return s


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
                print("classreplay.__new__", cls, args, kwargs,
                      cls.__records__)
                o = super(ClassReplay, cls).__new__(cls)

                args = list(args)
                data = cls.__records__['data']

                def key_func(i):
                    return score(i, args, kwargs, cls.__name__), i
                instances = sorted(map(key_func, data))
                if len(instances) == 0:
                    raise Exception("Failed matching", args, kwargs)
                # if instances[0][0] != 0:
                #     raise Exception("Non zero score", args, kwargs,
                #                     cls.__name__, inspect.stack()[1],
                #                     instances[0])
                # if sum(1 for i in instances if i[0] == 0) > 1:
                #     raise Exception("More than one zero scores", args,
                #                     kwargs, cls.__name__,
                #                     inspect.stack()[1], instances)
                print("matched", instances[0])
                print("with", args, kwargs,
                      cls.__name__, inspect.stack()[1])
                return init_replay(o, name, instances[0][1])

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
        ex_cls = getattr(exceptions, record['class_name'])
        # Make sure retireved class is actually an exception class, to
        # prevent potential code-execution using an arbitrary builtin class
        # load
        if not issubclass(ex_cls, BaseException):
            return Exception
        return ex_cls
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
