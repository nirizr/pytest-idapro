import os
import sys
import types
import inspect
import json

_orig_stdout = sys.stdout
_orig_stderr = sys.stderr


# override print to remove dependencies
# because stdout/err are replaced with IDA's, using it will cause an inifinite
# recursion :)
def safe_print(*args):
    _orig_stdout.write(str(args) + "\n")


def is_idamodule(fullname):
    if fullname in ('idaapi', 'idc', 'idautils'):
        return True
    return fullname.startswith("ida_")


class ProxyModuleLoader(object):
    def __init__(self):
        super(ProxyModuleLoader, self).__init__()
        self.loading = set()

    def find_module(self, fullname, path=None):
        if fullname in self.loading:
            return None
        if path and os.path.normpath(os.path.dirname(__file__)) in path:
            return None
        if not is_idamodule(fullname):
            return None

        return self

    def load_module(self, fullname):
        # for reload to function properly, must return existing instance if one
        # exists
        if fullname in sys.modules:
            return sys.modules[fullname]

        # otherwise, we'll create a module proxy
        # lock itself from continuously claiming to find ida modules, so that
        # the call to __import__ will not reach here again causing an infinite
        # recursion
        self.loading.add(fullname)
        real_module = __import__(fullname, None, None, "*")
        self.loading.remove(fullname)

        record = record_factory(fullname, real_module, g_records)
        sys.modules[fullname] = record

        return record


g_records = {}


base_types = (int, str, dict, list, tuple, set)
try:
    base_types += (unicode, long, types.NoneType)
except NameError:
    base_types += (type(None),)


def call_prepare_proxies(o, pr):
    """Prepare proxy arguments for a proxied call
    This is mostly about striping the proxy object, but will also re-wrap
    functions passed as arguments, as those could be callback functions that
    should be called by the replay core when needed.
    """
    if isinstance(o, dict):
        return {k: call_prepare_proxies(v, pr) for k, v in o.items()}
    elif isinstance(o, list):
        return [call_prepare_proxies(v, pr) for v in o]
    elif isinstance(o, tuple):
        return tuple([call_prepare_proxies(v, pr) for v in o])
    elif hasattr(o, '__subject__') or type(o).__name__ == 'ProxyClass':
        return o.__subject__
    elif inspect.isfunction(o):
        # if object is an unproxied function, we'll need to proxy it
        # specifically for the call, so any callback functions will be
        # registered by us
        # TODO: this is unlikely but we will currently miss callbacks that
        # are proxied objects
        return record_factory(o.__name__, o, pr['callback'])
    elif isinstance(o, base_types):
        return o
    safe_print("WARN: default call_prepare_proxies", type(o), o,
               type(o).__name__)
    return o


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if hasattr(o, '__subject__'):
            o = o.__subject__
        elif isinstance(o, type):
            return repr(o)
        elif isinstance(o, types.InstanceType):
            return repr(o)
        elif inspect.isbuiltin(o):
            return repr(o)
        elif isinstance(o, types.ModuleType):
            return repr(o)
        elif isinstance(o, types.InstanceType):
            return repr(o)
        elif inspect.isclass(o):
            return repr(o)
        elif inspect.isfunction(o):
            return repr(o)
        try:
            return super(JSONEncoder, self).default(o)
        except TypeError:
            safe_print("WARN: Unsupported serialize", type(o), o, type(o).__name__)
            return repr(o)


def init_record(record, subject, records, name):
    if hasattr(record, '__subject__') and record.__subject__ != subject:
        raise Exception("Trying to override subject", record.__subject__,
                        subject, name, record)

    record.__subject__ = subject
    record.__subject_name__ = name

    if name is None:
        record.__records__ = {'value_type': record.__value_type__}
        records.setdefault('data', []).append(record.__records__)
    elif name in records:
        record.__records__ = records[name]
        if record.__records__['value_type'] != record.__value_type__:
            raise RuntimeError("Value types mismatch!", name, records,
                               record.__value_type__, "!=",
                               record.__records__['value_type'])
    else:
        record.__records__ = {'value_type': record.__value_type__}
        records[name] = record.__records__
    return record


def record_factory(name, value, parent_record):
    if (isinstance(value, AbstractRecord) or
        inspect.isbuiltin(value) or
        type(value).__name__ == "swigvarlink" or
        value is type):
        return value
    elif inspect.isfunction(value) or inspect.ismethod(value):
        return init_record(FunctionRecord(), value, parent_record, name)
    elif inspect.isclass(value) and issubclass(value, BaseException):
        # TODO: maybe exceptions should also be proxied as class instances
        # instead of being specially treated? they have attributes etc and
        # right now args is manually handled in the next isinstance
        parent_record[name] = {'value_type': 'exception_class',
                               'class_name': value.__name__}
        return value
    elif isinstance(value, BaseException):
        parent_record[name] = {'value_type': 'exception', 'args': value.args}
        record_factory('exception_class', value.__class__,
                       parent_record[name])
        return value
    elif inspect.isclass(value) and issubclass(value, object):
        if hasattr(value, '__subject__'):
            value = value.__subject__
        if not is_idamodule(value.__module__):
            return value

        class ProxyClass(value):
            __value_type__ = 'class'

            def __new__(cls, *args, **kwargs):
                r = super(ProxyClass, cls).__new__(cls, *args, **kwargs)

                # __init__ method is not called by python if __new__
                # returns an object that is not an instance of the same
                # class type. We therefore have to call __init__ ourselves
                # before returning a InstanceRecord
                if hasattr(cls, '__init__'):
                    cls.__init__(r, *args, **kwargs)

                r = init_record(InstanceRecord(), r, parent_record[name], None)
                r.__records__['args'] = args
                r.__records__['kwargs'] = kwargs
                if cls.__name__ == 'ProxyClass':
                    r.__records__['name'] = cls.__subject_name__
                else:
                    r.__records__['name'] = cls.__name__
                caller = inspect.stack()[1]
                r.__records__['caller_file'] = caller[1]
                r.__records__['caller_line'] = caller[2]
                r.__records__['caller_function'] = caller[3]

                return r

            def __getattribute__(self, attr, oga=object.__getattribute__):
                try:
                    return super(ProxyClass, self).__getattribute__(attr)
                except AttributeError:
                    return oga(type(self), attr)
        return init_record(ProxyClass, value, parent_record, name)
    elif isinstance(value, types.ModuleType):
        if is_idamodule(value.__name__):
            return init_record(ModuleRecord(), value, parent_record, name)
        return value
    elif isinstance(value, types.InstanceType):
        return init_record(OldInstanceRecord(), value, parent_record, name)
    elif isinstance(value, base_types):
        if name != '__dict__':
            parent_record[name] = {'value_type': 'value', 'data': value}
        return value

    safe_print("WARN: record_factroy failed", value, name, type(value))
    value = init_record(AbstractRecord(), value, parent_record, name)
    return value


def get_attribute(record, attr, getter):
    if attr in ('__subject__', '__records__', '__subject_name__',
                '__value_type__'):
        return getter(record, attr)

    value = getattr(record.__subject__, attr)
    processed_value = record_factory(attr, value, record.__records__)
    return processed_value


def set_attribute(record, attr, value, setter):
    if attr in ('__subject__', '__records__', '__subject_name__',
                '__value_type__'):
        setter(record, attr, value)
    else:
        setattr(record.__subject__, attr, value)


class AbstractRecord(object):
    __value_type__ = "unknown"

    def __call__(self, *args, **kwargs):
        calldesc = {'args': args,
                    'kwargs': kwargs,
                    'name': self.__subject_name__,
                    'callback': {}}

        # You'd imagine this is always true, right? well.. not in IDA ;)
        if len(inspect.stack()) > 1:
            caller = inspect.stack()[1]
            calldesc['caller_file'] = caller[1]
            calldesc['caller_line'] = caller[2]
            calldesc['caller_function'] = caller[3]

        self.__records__.setdefault('data', []).append(calldesc)

        args = call_prepare_proxies(args, calldesc)
        kwargs = call_prepare_proxies(kwargs, calldesc)
        try:
            original_retval = self.__subject__(*args, **kwargs)
        except Exception as ex:
            record_factory('exception', ex, calldesc)
            raise
        # TODO: to keep any retval related recorded data we should not pass
        # a temp dict to this record_factory. instead, we should move
        # serialize_data to a json serializaion encode/decode class.
        td = {}
        retval = record_factory('retval', original_retval, td)
        calldesc['retval'] = td['retval']
        return retval

    def __getattribute__(self, attr):
        return get_attribute(self, attr, object.__getattribute__)

    def __setattr__(self, attr, value):
        set_attribute(self, attr, value, object.__setattr__)

    def __delattr__(self, attr):
        delattr(self.__subject__, attr)

    if hasattr(int, '__nonzero__'):
        def __nonzero__(self):
            return bool(self.__subject__)

    def __getitem__(self, arg):
        return self.__subject__[arg]

    def __setitem__(self, arg, val):
        self.__subject__[arg] = val

    def __delitem__(self, arg):
        del self.__subject__[arg]

    def __getslice__(self, i, j):
        return self.__subject__[i:j]

    def __setslice__(self, i, j, val):
        self.__subject__[i:j] = val

    def __delslice__(self, i, j):
        del self.__subject__[i:j]

    def __contains__(self, ob):
        return ob in self.__subject__

    # Ugly code definitions for all special python methods
    # this will forward all unique method calls to the proxied object
    for name in ('repr', 'str', 'hash', 'len', 'abs', 'complex', 'int', 'long',
                 'float', 'iter', 'oct', 'hex', 'bool', 'operator.index',
                 'math.trunc'):
        if (name in ('len', 'complex') or
            hasattr(int, '__%s__' % name.split('.')[-1])):
            if '.' in name:
                name = name.split('.')
                exec("global %s;"
                     "from %s import %s" % (name[1], name[0], name[1]))
                name = name[1]
            exec("def __%s__(self):"
                 "    return %s(self.__subject__)" % (name, name))

    for name in 'cmp', 'coerce', 'divmod':
        if hasattr(int, '__%s__' % name):
            exec("def __%s__(self, ob):"
                 "    return %s(self.__subject__, ob)" % (name, name))

    for name, op in [
        ('lt', '<'), ('gt', '>'), ('le', '<='), ('ge', '>='),
        ('eq', '=='), ('ne', '!=')
    ]:
        exec("def __%s__(self, ob):"
             "    return self.__subject__ %s ob" % (name, op))

    for name, op in [('neg', '-'), ('pos', '+'), ('invert', '~')]:
        exec("def __%s__(self): return %s self.__subject__" % (name, op))

    for name, op in [('or', '|'), ('and', '&'), ('xor', '^'), ('lshift', '<<'),
                     ('rshift', '>>'), ('add', '+'), ('sub', '-'),
                     ('mul', '*'), ('div', '/'), ('mod', '%'),
                     ('truediv', '/'), ('floordiv', '//')]:
        if name == 'div' and not hasattr(int, '__div__'):
            continue
        exec((
            "def __%(name)s__(self, ob):\n"
            "    return self.__subject__ %(op)s ob\n"
            "\n"
            "def __r%(name)s__(self, ob):\n"
            "    return ob %(op)s self.__subject__\n"
            "\n"
            "def __i%(name)s__(self, ob):\n"
            "    self.__subject__ %(op)s=ob\n"
            "    return self\n"
        ) % locals())

    del name, op

    # Oddball signatures

    def __rdivmod__(self, ob):
        return divmod(ob, self.__subject__)

    def __pow__(self, *args):
        return pow(self.__subject__, *args)

    def __ipow__(self, ob):
        self.__subject__ **= ob
        return self

    def __rpow__(self, ob):
        return pow(ob, self.__subject__)


class ModuleRecord(AbstractRecord):
    __value_type__ = "module"


class FunctionRecord(AbstractRecord):
    __value_type__ = "function"


class InstanceRecord(AbstractRecord):
    __value_type__ = "instance"

    def __getattribute__(self, attr, oga=object.__getattribute__):
        try:
            return super(InstanceRecord, self).__getattribute__(attr)
        except AttributeError:
            return oga(self, attr)


class OldInstanceRecord(AbstractRecord):
    __value_type__ = 'oldinstance'


def dump_records(records_file):
    global g_records
    with open(records_file, 'wb') as fh:
        json.dump(g_records, fh, cls=JSONEncoder)


def setup():
    sys.meta_path.insert(0, ProxyModuleLoader())
