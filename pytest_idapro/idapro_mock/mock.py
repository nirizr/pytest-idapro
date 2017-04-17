class MockObject(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
        msg = "<{}(mock), args: {}, kwargs: {}".format(self.__class__.__name__,
                                                       self.args, self.kwargs)
        return msg
