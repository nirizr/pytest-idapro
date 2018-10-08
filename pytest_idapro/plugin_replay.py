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
            module_record = self.records[module_name]
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


# TODO: only have one copy of this
def clean_arg(arg):
    """Cleanup argument's representation for comparison by removing the
    terminating memory address"""

    sarg = repr(arg)
    if sarg[0] != '<':
        return arg

    if len(sarg.split()) < 2:
        return arg

    parts = sarg.split()
    if parts[-2] == 'at' and parts[-1][-1] == '>' and parts[-1][:2] == '0x':
        return " ".join(parts[:-2]) + '>'

    return arg


def instance_score(instance, name, args, kwargs, caller):
    print("Calculating", args, kwargs, name, caller[1:])
    print("Verses", instance['args'], instance['kwargs'], instance['name'],
          instance['caller_file'], instance['caller_line'],
          instance['caller_function'])

    s = 0
    s += 100 if str(name) != str(instance['name']) else 0
    s += sum(10 for a, b in zip(args, instance['args'])
             if clean_arg(a) != b)
    s += sum(10 for a, b in zip(kwargs.items(), instance['kwargs'].items())
             if a[0] != b[0] or clean_arg(a[1]) != b[1])
    s += abs(caller[2] - instance['caller_line'])
    s += 100 if str(caller[1]) != str(instance['caller_file']) else 0
    s += 100 if str(caller[3]) != str(instance['caller_function']) else 0

    print("Scored", s)

    return s, instance


def instance_select(replay_cls, name, args, kwargs):
    caller = inspect.stack()[2]
    instances = replay_cls.__records__['data']
    args = list(args)

    def instance_score_wrap(instance):
        return instance_score(instance, name, args, kwargs, caller)

    instances = sorted(map(instance_score_wrap, instances))

    if len(instances) == 0:
        raise Exception("Failed matching", args, kwargs)
    # TODO: ideally this should be included but it fails for some tests when
    # I'm guessting multiple instances are identical. Should validate and see
    # if we can remove duplicates somewhere, preferably in the recording code
    # if instances[0][0] != 0:
    #     raise Exception("Non zero score", args, kwargs, name, caller,
    #                    instances[0])
    # if sum(1 for i in instances if i[0] == 0) > 1:
    #     raise Exception("More than one zero scores", args, kwargs, name,
    #                     caller, instances)

    print("matched", instances[0])
    print("with", args, kwargs, name, caller)

    return instances[0][1]


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

                instance = instance_select(cls, cls.__name__, args, kwargs)

                return init_replay(o, name, instance)

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

        try:
            return oga(self, attr)
        except AttributeError:
            pass

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
        instance = instance_select(self, self.__name__, args, kwargs)

        if 'callback' in instance and instance['callback']:
            for arg in args + tuple(kwargs.values()):
                if not inspect.isfunction(arg):
                    continue
                # TODO: improve logic over just picking the first available
                arg_data = instance['callback'][arg.__name__]['data'][0]
                if not arg_data:
                    continue
                print("calling {} with {}".format(arg, arg_data))
                arg(*arg_data['args'], **arg_data['kwargs'])
                # TODO: validate return value is correct

        if 'exception' in instance:
            raise replay_factory('exception', instance)
        return replay_factory('retval', instance)
