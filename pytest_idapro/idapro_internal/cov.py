"""
A pytest-cov helper used to silence that external pytest session when pytest
executes an IDA instance. The actual collection will be performed by the
internal IDA session, while all this cov_controller instance will do is
overwrite it with an empty coverage session.

Instead, we'll replace pytest-cov's copy of a Central CovController class with
ReadOnlyController which will swallow several functions and will forward
other relevant methods and attributes.

Replacing an object's __class__ is indeed a smell, but a simple solution to our
overriding problem.
"""

import sys


from pytest_cov.engine import Central


class CovReadOnlyController(Central):
    def start(self):
        self.cov_append = True
        super(CovReadOnlyController, self).start()

    def finish(self):
        # Mostly do nothing instead of overwriting cov files
        node_desc = self.get_node_desc(sys.platform, sys.version_info)
        self.node_descs.add(node_desc)

    def summary(self, stream):
        # Just load coverage from file (saved by internal session) and then act
        # as normal
        self.cov.load()
        return super(CovReadOnlyController, self).summary(stream)

    @classmethod
    def silence(cls, cov_obj):
        if not isinstance(cov_obj, Central):
            raise Exception("Requeted to silence a non-central cov_controller "
                            "object: {}".format(cov_obj))

        cov_obj.__class__ = cls
