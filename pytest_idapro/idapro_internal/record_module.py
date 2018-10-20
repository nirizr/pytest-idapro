import os
import sys
import types
import inspect
import json
import logging
import re


# A global variable holding all collected recordings
g_records = {}

# A global regex matching base paths to be stripped, it'll be assigned by
# setup
g_paths_re = None


def logger():
    return logging.getLogger('pytest_idapro.internal.record')


def dump_records(records_file):
    # use our speciallized json enocoder to dump all collected records to json
    records = json.dumps(g_records, cls=RecordJSONEncoder)
    records = g_paths_re.sub('', records)
    records = re.sub(' at 0x[0-9a-fA-F]{1,16}>', '>', records)

    with open(records_file, 'wb') as fh:
        fh.write(records)


def setup(base_paths):
    global g_paths_re

    # define the global paths regex
    g_paths_re = re.compile('({})'.format("|".join(base_paths)))

    # install a module loader to inject a record module wrapper instead of IDA
    # modules
    sys.meta_path.insert(0, RecordModuleLoader())


def is_idamodule(fullname):
    if fullname in ('idaapi', 'idc', 'idautils', 'idaapi.py', 'idc.py',
                    'idautils.py'):
        return True
    return fullname.startswith("ida_")


class RecordModuleLoader(object):
    def __init__(self):
        super(RecordModuleLoader, self).__init__()
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

        # otherwise, we'll create a module record
        # lock itself from continuously claiming to find ida modules, so that
        # the call to __import__ will not reach here again causing an infinite
        # recursion
        self.loading.add(fullname)
        real_module = __import__(fullname, None, None, "*")
        self.loading.remove(fullname)

        record = record_factory(fullname, real_module, g_records)
        sys.modules[fullname] = record

        return record


base_types = (int, str, dict, list, tuple, set)
try:
    base_types += (unicode, long, types.NoneType)
    str_types = (str, unicode)
    int_types = (int, long)
except NameError:
    base_types += (type(None),)
    str_types = (str,)
    int_types = (int,)


def call_prepare_records(o, pr):
    """Prepare record arguments for a recorded call
    This is mostly about striping the record object, but will also re-wrap
    functions passed as arguments, as those could be callback functions that
    should be called by the replay core when needed.
    """
    if isinstance(o, dict):
        return {k: call_prepare_records(v, pr) for k, v in o.items()}
    elif isinstance(o, list):
        return [call_prepare_records(v, pr) for v in o]
    elif isinstance(o, tuple):
        return tuple([call_prepare_records(v, pr) for v in o])
    elif hasattr(o, '__subject__') or type(o).__name__ == 'RecordClass':
        return o.__subject__
    elif inspect.isfunction(o):
        # if object is an unrecorded function, we'll need to record it
        # specifically for the call, so any callback functions will be
        # registered by us
        # TODO: this is unlikely but we will currently miss callbacks that
        # are recorded objects
        return record_factory(o.__name__, o, pr['callback'])
    elif isinstance(o, base_types):
        return o

    logger().warn("default call_prepare_records for %s", o)
    return o


def serialize_record(o):
    if (hasattr(o, '__instance_records__') and
        o.__instance_records__ and
        o.__instance_records__.__records__):
        r = o.__instance_records__.__records__['instance_desc']
        args = map(serialize_record, r.get('args', []))
        kwargs = {k: serialize_record(v)
                  for k, v in r.get('kwargs', {}).items()}
        return str(r.get('name', '')) + ";" + str(args) + ";" + str(kwargs)
    elif isinstance(o, int_types) or o is None:
        return o
    elif isinstance(o, str_types):
        return str(o)

    return repr(o)


class RecordJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if (hasattr(o, '__instance_records__') and
            o.__instance_records__ and
            o.__instance_records__.__records__):
            return serialize_record(o)
        elif hasattr(o, '__subject__'):
            cls = o.__class__
            if cls.__name__ == 'RecordClass':
                return cls.__subject_name__ + ";" + repr(o)
            else:
                return cls.__name__ + ";" + repr(o)
        elif (isinstance(o, type) or isinstance(o, types.InstanceType) or
              inspect.isbuiltin(o) or isinstance(o, types.ModuleType) or
              isinstance(o, types.InstanceType) or inspect.isclass(o) or
              inspect.isfunction(o)):
            return repr(o)

        try:
            return super(RecordJSONEncoder, self).default(o)
        except TypeError:
            logger().warn("Unsupported serializion of %s", o)
            return repr(o)


def record_callstack():
    if len(inspect.stack()) <= 2:
        return []

    callstack_records = []
    for cs in inspect.stack()[2:]:
        if cs[3].startswith('pytest_'):
            break
        if not (is_idamodule(os.path.basename(cs[1])) or
                '/_pytest/' in cs[1] or '/pytestqt/' in cs[1] or
                '/pytest_idapro/' in cs[1] or '/python2.7/' in cs[1]):
            record = {'caller_file': cs[1], 'caller_line': cs[2],
                      'caller_function': cs[3], 'caller_text': cs[4]}
            callstack_records.append(record)
    return callstack_records


def init_record(record, subject, records, name, data_type=None):
    if hasattr(record, '__subject__') and record.__subject__ != subject:
        raise Exception("Trying to override subject", record.__subject__,
                        subject, name, record)

    record.__subject__ = subject
    record.__subject_name__ = name

    if name is None:
        record.__records__ = {'value_type': record.__value_type__}
        records.setdefault(data_type, []).append(record.__records__)
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


oga = object.__getattribute__


def record_factory(name, value, parent_record):
    if (isinstance(value, AbstractRecord) or inspect.isbuiltin(value) or
        (inspect.isclass(value) and issubclass(value, BaseException)) or
        type(value).__name__ in ("swigvarlink", "PyCObject") or
        value is type or type(value).__name__[0] == "Q"):
        return value
    elif inspect.isfunction(value) or inspect.ismethod(value):
        return init_record(FunctionRecord(), value, parent_record, name)
    elif isinstance(value, BaseException):
        parent_record[name] = {'value_type': 'exception', 'args': value.args,
                               'kwargs': {},
                               'exception_class': value.__class__.__name__}
        return value
    elif inspect.isclass(value) and issubclass(value, object):
        if hasattr(value, '__subject__'):
            value = value.__subject__
        if not is_idamodule(value.__module__):
            return value

        class RecordClass(value):
            __value_type__ = 'class'

            def __new__(cls, *args, **kwargs):
                obj = super(RecordClass, cls).__new__(cls, *args, **kwargs)

                r = init_record(InstanceRecord(), obj, parent_record[name],
                                None, 'instance_data')
                init_desc = {}
                init_desc['args'] = args
                init_desc['kwargs'] = kwargs
                if cls.__name__ == 'RecordClass':
                    init_desc['name'] = cls.__subject_name__
                else:
                    init_desc['name'] = cls.__name__
                init_desc['callstack'] = record_callstack()
                r.__records__['instance_desc'] = init_desc

                if 'call_count' not in parent_record[name]:
                    parent_record[name]['call_count'] = 0
                else:
                    parent_record[name]['call_count'] += 1
                init_desc['call_index'] = parent_record[name]['call_count']

                obj.__instance_records__ = r

                # __init__ method is not called by python if __new__
                # returns an object that is not an instance of the same
                # class type. We therefore have to call __init__ ourselves
                # before returning a InstanceRecord
                if hasattr(cls, '__init__'):
                    cls.__init__(obj, *args, **kwargs)

                return r

            def __getattribute__(self, attr):
                if attr in ('__subject__', '__records__', '__subject_name__',
                            '__value_type__', '__instance_records__'):
                    return oga(self, attr)

                if attr == "__class__":
                    return oga(self, '__class__')

                try:
                    r = super(RecordClass, self).__getattribute__(attr)
                except AttributeError:
                    r = oga(self, attr)

                r = record_factory(attr, r,
                                   self.__instance_records__.__records__)
                return r

        return init_record(RecordClass, value, parent_record, name)
    elif isinstance(value, types.ModuleType):
        if is_idamodule(value.__name__):
            return init_record(ModuleRecord(), value, parent_record, name)
        return value
    elif isinstance(value, types.InstanceType):
        return init_record(OldInstanceRecord(), value, parent_record, name)
    elif isinstance(value, base_types):
        if name != '__dict__':
            parent_record[name] = {'value_type': 'value', 'raw_data': value}
        return value

    logger().warn("record_factory failed for %s", value)
    value = init_record(AbstractRecord(), value, parent_record, name)
    return value


class AbstractRecord(object):
    __value_type__ = "unknown"

    def __call__(self, *args, **kwargs):
        call_desc = {'args': args,
                     'kwargs': kwargs,
                     'name': self.__subject_name__,
                     'callback': {}}

        # You'd imagine this is always true, right? well.. not in IDA ;)
        call_desc['callstack'] = record_callstack()

        if 'call_data' not in self.__records__:
            self.__records__['call_data'] = []
            self.__records__['call_count'] = 0
        else:
            self.__records__['call_count'] += 1
        call_desc['call_index'] = self.__records__['call_count']
        # TODO: can this be united with instance's call to init_record?
        self.__records__['call_data'].append({'instance_desc': call_desc})

        args = call_prepare_records(args, call_desc)
        kwargs = call_prepare_records(kwargs, call_desc)
        try:
            original_retval = self.__subject__(*args, **kwargs)
        except Exception as ex:
            record_factory('exception', ex, call_desc)
            raise
        retval = record_factory('retval', original_retval, call_desc)
        return retval

    def __getattribute__(self, attr):
        if attr in ('__subject__', '__records__', '__subject_name__',
                    '__value_type__'):
            return oga(self, attr)

        value = getattr(self.__subject__, attr)
        processed_value = record_factory(attr, value, self.__records__)
        return processed_value

    def __setattr__(self, attr, value):
        if attr in ('__subject__', '__records__', '__subject_name__',
                    '__value_type__'):
            object.__setattr__(self, attr, value)
        else:
            setattr(self.__subject__, attr, value)

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
    # this will forward all unique method calls to the recorded object
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

    def __getattribute__(self, attr):
        try:
            return super(InstanceRecord, self).__getattribute__(attr)
        except AttributeError:
            return oga(self, attr)


class OldInstanceRecord(AbstractRecord):
    __value_type__ = 'oldinstance'
