import json
import os
import random


atag = 'A'
stag = 'S'
htag = 'H'
vtag = 'V'
ntag = 'N'
ltag = 'L'


class netnode(object):
    """Fake an IDB netnode object using JSON files for actual storage of data
    This means we won't store data differently for "different" idb files.
    Currently there's no way to control in tests whether a there are preset
    netnodes or data should start from scratch for each test. We'll need to
    provide markers for that in the future."""

    NETNODE_PATH = "netnodes/"

    def __init__(self, name, namlen=0, do_create=False):
        # TODO: provide control over the initial state of netnode data to the
        # test user
        if name and namlen and len(name) != namlen:
            raise ValueError("Name Length provided but is wrong!")

        if not name:
            name = "unnamed_{}".format(random.randrange(2**32 - 1))
        self.name = self.NETNODE_PATH + name + "_netnode.json"

        if os.path.isfile(name):
            with open(name, 'r') as fh:
                self.data = json.load(fh)
        elif do_create:
            self.data = {}
        else:
            # TBD: do we need to raise an exception here? maybe allow this
            # somehow?
            raise Exception("Did not create a non-existant netnode")

    def __del__(self):
        if not os.path.exists(self.NETNODE_PATH):
            os.mkdir(self.NETNODE_PATH)

        with open(self.name, 'w') as fh:
            json.dump(self.data, fh)

    def hashstr(self, idx, tag=htag):
        # TODO: support different tags
        if tag != htag:
            raise NotImplementedError("Only supporting default tag values")

        if idx not in self.data:
            return None

        return self.data[idx]
