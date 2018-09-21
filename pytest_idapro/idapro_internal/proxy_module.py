import os
import sys
import types
import inspect

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
        safe_print("object call_prepare_proxies", o, o.__subject__, type(o),
                   type(o.__subject__))
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
    safe_print("default call_prepare_proxies", type(o), o, type(o).__name__)
    return o


def serialize_data(o):
    if isinstance(o, dict):
        return {k: serialize_data(v) for k, v in o.items()}
    elif isinstance(o, list):
        return [serialize_data(v) for v in o]
    elif isinstance(o, tuple):
        return tuple([serialize_data(v) for v in o])
    elif inspect.isclass(o) and issubclass(o, object):
        return repr(o)
    elif inspect.isclass(o):
        return repr(o)
    elif inspect.isfunction(o):
        return repr(o)
    elif isinstance(o, base_types):
        return o
    return repr(o)
    # TODO: if ProxyClass reached here, it should've need stipped in __call__
    raise RuntimeError("Unsupported serialize", type(o), o,
                       o.__class__.__name__, type(o).__name__)


def init_record(record, subject, records, name, value_type=None):
    record.__subject__ = subject
    record.__subject_name__ = name
    if value_type:
        record.__value_type__ = value_type

    if name in records:
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
    if isinstance(value, AbstractRecord):
        safe_print("Skipping record object", value)
        return value
    elif inspect.isfunction(value):
        safe_print("got function record", value, name)
        return init_record(FunctionRecord(), value, parent_record, name)
    elif inspect.ismethod(value):
        safe_print("got method record", name, value, type(value))
        return init_record(FunctionRecord(), value, parent_record, name)
    elif inspect.isbuiltin(value):
        safe_print("skipping builtin")
        return value
    elif type(value).__name__ == "swigvarlink":
        safe_print("skipping swig C object")
        return value
    elif value is type:
        safe_print("Skipping type")
        return value
    elif inspect.isclass(value) and issubclass(value, BaseException):
        parent_record[name] = {'value_type': 'exception_class'}
        return value
    elif inspect.isclass(value) and issubclass(value, object):
            safe_print("getattr class", value, name, type(value))
            if isinstance(value, AbstractRecord):
                safe_print("INSTANCE")
                return value

            class ProxyClass(value):
                def __new__(cls, *args, **kwargs):
                    safe_print("!!! class record newed", cls, args, kwargs)
                    r = super(ProxyClass, cls).__new__(cls, *args, **kwargs)

                    # __init__ method is not called by python if __new__
                    # returns an object that is not an instance of the same
                    # class type. We therefore have to call __init__ ourselves
                    # before returning a ClassRecord
                    safe_print("class obj type", type(r))
                    if hasattr(cls, '__init__'):
                        cls.__init__(r, *args, **kwargs)

                    safe_print("orig class result", r.__class__)
                    # TODO: class instances should have differing names
                    # perhaps? we may need to somehow seperate different
                    # instances of the same class
                    r = init_record(ClassRecord(), r, parent_record,
                                    value.__name__, "class")
                    safe_print("class result", r.__class__)

                    safe_print("type r", type(r))
                    return r

                def __getattribute__(self, attr, oga=object.__getattribute__):
                    try:
                        safe_print("proxyclass getattr", attr, type(self))
                        return super(ProxyClass, self).__getattribute__(attr)
                    except AttributeError:
                        safe_print("Second attempt")
                        return oga(type(self), attr)

                def __init__(self, *args, **kwargs):
                    safe_print("init called")
                    super(ProxyClass, self).__init__(*args, **kwargs)

                # TODO: should this be logged??
                def __call__(self, *args, **kwargs):
                    safe_print("!!! class record called", self, args, kwargs)
                    return super(ProxyClass, self).__call__(*args, **kwargs)
            safe_print("class mro", ProxyClass.__mro__)
            return init_record(ProxyClass, value, parent_record, name, 'class')
    elif isinstance(value, types.ModuleType):
        if is_idamodule(value.__name__):
            return init_record(ModuleRecord(), value, parent_record, name)
        else:
            safe_print("skipping non-ida module")
            return value
    elif isinstance(value, types.InstanceType):
        return init_record(AbstractRecord(), value, parent_record, name,
                           'oldclass')
    elif isinstance(value, base_types):
        if name != '__dict__':
            parent_record[name] = {'value_type': 'value', 'data': value}
        return value
    else:
        safe_print("record_factroy called", value, name, type(value))
        value = init_record(AbstractRecord(), value, parent_record, name,
                            'unknown')
        safe_print(repr(value))

    return value


# TODO: split proxy and Record objects, use AbstractRecord by Replay as well
# Or should I? what will be the record's subject value??
# maybe Record should always return concrete values?
class AbstractRecord(object):
    __slots__ = ['__subject__', '__records__', '__subject_name__',
                 '__value_type__']

    # TODO: handle callback registrations properly, i.e. execute_sync
    # This should also include recording the input arguments passed
    # to the callbacks themselves (probably by proxying the callback
    def __call__(self, *args, **kwargs):
        # TODO: should also record & replay exceptions within functions
        safe_print("function call", self, args, kwargs)
        calldesc = {'args': serialize_data(args),
                    'kwargs': serialize_data(kwargs),
                    'retval': {}, 'callback': {}}
        self.__records__.setdefault('data', []).append(calldesc)

        args = call_prepare_proxies(args, calldesc)
        kwargs = call_prepare_proxies(kwargs, calldesc)
        safe_print("function call clean args", self, args, kwargs)
        safe_print(self.__subject__)
        try:
            original_retval = self.__subject__(*args, **kwargs)
        except Exception:
            safe_print("Exception encountered in proxied call")
            import traceback
            safe_print(traceback.format_exc())
            raise
        safe_print("function call ret", original_retval)
        retval = record_factory('retval', original_retval, calldesc)
        return retval

    def __getattribute__(self, attr, oga=object.__getattribute__):
        if attr in ('__subject__', '__records__', '__subject_name__',
                    '__value_type__'):
            return oga(self, attr)

        value = getattr(self.__subject__, attr)
        safe_print("getattr sub", self.__subject__)
        safe_print("Getattr called", value, attr, type(value),
                   self.__subject__, self.__subject_name__,
                   self.__value_type__)
        processed_value = record_factory(attr, value, self.__records__)
        return processed_value

    def __setattr__(self, attr, val, osa=object.__setattr__):
        if attr in ('__subject__', '__records__', '__subject_name__',
                    '__value_type__'):
            osa(self, attr, val)
        else:
            setattr(self.__subject__, attr, val)

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


class ClassRecord(AbstractRecord):
    def __getattribute__(self, attr, oga=object.__getattribute__):
        try:
            safe_print("classrecord getattr", attr)
            return super(ClassRecord, self).__getattribute__(attr, oga)
        except AttributeError:
            return oga(self, attr)


def get_records():
    global g_records
    return g_records


def setup():
    safe_print("preloaded modules", sys.modules.keys())
    sys.meta_path.insert(0, ProxyModuleLoader())
