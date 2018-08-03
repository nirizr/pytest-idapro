import inspect
import pytest
import json


class IDAProEntriesScanner(pytest.Module):
    def __init__(self, *args, **kwargs):
        super(IDAProEntriesScanner, self).__init__(*args, **kwargs)

        self.idapro_plugin_entries = set()
        self.idapro_action_entries = set()

    def istestfunction(self, obj, name):
        if name == "PLUGIN_ENTRY":
            self.idapro_plugin_entries.add(obj)

    def istestclass(self, obj, name):
        if any(cls.__name__ == 'action_handler_t'
               for cls in inspect.getmro(obj)):
            self.idapro_action_entries.add(obj)


class BasePlugin(object):
    def __init__(self, *args, **kwargs):
        super(BasePlugin, self).__init__(*args, **kwargs)
        self.idapro_plugin_entries = set()
        self.idapro_action_entries = set()

    def pytest_collect_file(self, path, parent):
        if not path.ext == '.py':
            return

        scanner = IDAProEntriesScanner(path, parent)
        scanner.collect()

        self.idapro_plugin_entries |= scanner.idapro_plugin_entries
        self.idapro_action_entries |= scanner.idapro_action_entries

    def pytest_generate_tests(self, metafunc):
        if 'idapro_plugin_entry' in metafunc.fixturenames:
            metafunc.parametrize('idapro_plugin_entry',
                                 self.idapro_plugin_entries)
        if 'idapro_action_entry' in metafunc.fixturenames:
            metafunc.parametrize('idapro_action_entry',
                                 self.idapro_action_entries)

    @staticmethod
    def deserialize_report(report):
        return PytestJSONDecoder().dencode(report)

    @staticmethod
    def serialize_report(report):
        return PytestJSONEncoder().encode(report)


class PytestJSONDecoder(json.JSONDecoder):
    def __init__(self):
        super(PytestJSONDecoder, self).__init__(object_hook=self.object_hook)

    def object_hook(self, d):
        if not '__json_type__' in d:
            return d

        from _pytest.reports import BaseReport
        if d['__json_type__'] == "BaseReport":
            return BaseReport(**d['__value__'])


class PytestJSONEncoder(json.JSONEncoder):
    def default(self, o):
        from py.path import local
        from _pytest import reports
        from _pytest.reports import BaseReport
        if isinstance(o, local):
            return str(o)
        if isinstance(o, BaseReport):
            return {'__json_type__': 'BaseReport',
                    '__value__': vars(o)}

        return super(PytestJSONEncoder, self).default(o)
