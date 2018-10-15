import inspect
try:
    import exceptions
except ImportError:
    import builtins as exceptions


def module_replay(module_name, module_record):
    return init_replay(ModuleReplay(), module_name, module_record)


def init_replay(replay, object_name, records):
    replay.__object_name__ = object_name
    replay.__records__ = records
    replay.__name__ = object_name

    return replay


# TODO: only have one copy of this
oga = object.__getattribute__
osa = object.__setattr__


try:
    str_types = (str, unicode)
    int_types = (int, long)
except NameError:
    str_types = (str,)
    int_types = (int,)


def clean_arg(arg):
    """Cleanup argument's representation for comparison by removing the
    terminating memory address"""
    if isinstance(arg, AbstractReplay):
        r = arg.__records__
        args = map(clean_arg, r.get('args', []))
        kwargs = {k: clean_arg(v) for k, v in r.get('kwargs', {})}
        name = r.get('name', {}).get('raw_value', '')
        print("NAME", name)
        return name + ";" + str(args) + ";" + str(kwargs)

    if isinstance(arg, int_types) or arg is None:
        return arg

    if isinstance(arg, str_types):
        arg = str(arg)
    else:
        arg = repr(arg)

    parts = arg.split()

    if (len(parts) > 2 and arg[0] == '<' and arg[-1] == '>' and
        parts[-2] == 'at' and parts[-1][:2] == '0x'):
        arg = " ".join(parts[:-2]) + '>'

    return arg


def instance_score(instance, name, args, kwargs, caller, call_count):
    print("Local", args, kwargs, name, caller[1:])
    instance_desc = instance['instance_desc']
    print("Verses", instance_desc['args'], instance_desc['kwargs'],
          instance_desc['name'], instance_desc['caller_file'],
          instance_desc['caller_line'], instance_desc['caller_function'])

    s = 0
    s += 100 if str(name) != str(instance_desc['name']) else 0
    s += sum(10 for a, b in zip(args, instance_desc['args'])
             if a != clean_arg(b))
    s += sum(10 for a, b in zip(kwargs.items(),
                                instance_desc['kwargs'].items())
             if a[0] != b[0] or a[1] != clean_arg(b[1]))
    s += abs(caller[2] - instance_desc['caller_line'])
    s += 5 * abs(call_count  - instance_desc['call_index'])
    s += 100 if str(caller[1]) != str(instance_desc['caller_file']) else 0
    s += 100 if str(caller[3]) != str(instance_desc['caller_function']) else 0

    print("Scored", s)

    return s, instance


def instance_select(replay_cls, data_type, name, args, kwargs):
    caller = inspect.stack()[2]
    instances = replay_cls.__records__[data_type]
    if 'replay_call_count' in replay_cls.__records__:
        replay_cls.__records__['replay_call_count'] += 1
    else:
        replay_cls.__records__['replay_call_count'] = 0
    call_count = replay_cls.__records__['replay_call_count']
    args = [clean_arg(a) for a in args]
    kwargs = {k: clean_arg(v) for k, v in kwargs.items()}

    def instance_score_wrap(instance):
        return instance_score(instance, name, args, kwargs, caller, call_count)

    instances = sorted(map(instance_score_wrap, instances))

    if len(instances) == 0:
        raise Exception("Failed matching", args, kwargs)
    # TODO: ideally this should be included but it fails for some tests when
    # I'm guessting multiple instances are identical. Should validate and see
    # if we can remove duplicates somewhere, preferably in the recording code
    # if instances[0][0] != 0:
    #     raise Exception("Non zero score", args, kwargs, name, caller,
    #                    instances[0])
    # zero_instances = [i[1] for i in instances if i[0] == 0]
    # if len(set(map(str, zero_instances)))  > 1:
    #     raise Exception("More than one zero scores", args, kwargs, name,
    #                     caller, zero_instances)

    print("matched", instances[0])
    print("with", args, kwargs, name, caller)

    return instances[0][1]


def replay_factory(name, records):
    record = records[name]
    value_type = record['value_type']
    if value_type == 'value' or value_type == 'override':
        return record['raw_data']
    elif value_type == 'module':
        return init_replay(AbstractReplay(), name, record['data'])
    elif value_type == 'class':
        class ClassReplay(AbstractReplay):
            def __new__(cls, *args, **kwargs):
                print("classreplay.__new__", cls, args, kwargs,
                      cls.__records__)
                o = super(ClassReplay, cls).__new__(cls)

                instance = instance_select(cls, 'instance_data', cls.__name__,
                                           args, kwargs)

                return init_replay(o, name, instance)

        return init_replay(ClassReplay, name, record)
    elif value_type == 'function':
        return init_replay(FunctionReplay(), name, record)
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
    def __getattribute__(self, attr):
        object_name = oga(self, '__object_name__')
        records = oga(self, '__records__')
        if attr == '__object_name__' or attr == '__name__':
            return object_name
        elif attr == '__records__':
            return records

        print("getattr called for {} in {} with {}".format(attr, object_name,
                                                           records.get(attr,
                                                                       None)))

        # TODO: this should probably done better, really record those (and
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

    def __setattr__(self, attr, val):
        if attr == '__object_name__' or attr == '__records__':
            osa(self, attr, val)
        else:
            self.__records__[attr] = {'raw_data': val,
                                      'value_type': 'override'}


class ModuleReplay(AbstractReplay):
    pass


class FunctionReplay(AbstractReplay):
    def __call__(self, *args, **kwargs):
        instance = instance_select(self, 'call_data', self.__name__, args,
                                   kwargs)
        instance_desc = instance['instance_desc']

        if 'callback' in instance_desc and instance_desc['callback']:
            for arg in args + tuple(kwargs.values()):
                print("callback", arg)
                if not inspect.isfunction(arg):
                    continue
                callbacks = instance_desc['callback'][arg.__name__]
                # TODO: improve logic over just picking the first available
                callback_data = callbacks['call_data'][0]
                callback_args = callback_data['instance_desc']
                print("calling {} with {}".format(arg, callback_args))
                arg(*callback_args['args'], **callback_args['kwargs'])
                # TODO: validate return value is correct

        if 'exception' in instance_desc:
            raise replay_factory('exception', instance_desc)
        return replay_factory('retval', instance_desc)