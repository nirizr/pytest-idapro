from .mock import MockObject

# TODO: support other pyqt libraries
from PyQt5 import QtWidgets

# Passed as 'flags' parameter to attach_action_to_menu()
SETMENU_INS = 0  # add menu item before the specified path (default)
SETMENU_APP = 1  # add menu item after the specified path


# Values returned by action_handler_t's update method to control action's
# availability. ENABLE means action controllers are enabled and available,
# DISABLE means they're unavailable. rest of the enum controlls when to query
# again for availability change by calling update.
AST_ENABLE_ALWAYS = 0
AST_ENABLE_FOR_IDB = 1
AST_ENABLE_FOR_FORM = 2
AST_ENABLE = 3
AST_DISABLE_ALWAYS = 4
AST_DISABLE_FOR_IDB = 5
AST_DISABLE_FOR_FORM = 6
AST_DISABLE = 7


class action_handler_t(MockObject):
    pass


class action_desc_t(MockObject):
    pass


class py_load_custom_icon_fn(MockObject):
    pass


class register_action(MockObject):
    pass


class attach_action_to_menu(MockObject):
    pass


class attach_action_to_toolbar(MockObject):
    pass


# Values used to configure specifics of the execute_sync API function, used to
# en-queue python callables into the execution queue of IDA's main thread.
# Since IDA is not thread-safe, it is unsupported to call certain kernel API
# and specifically database function (or functions that may attempt to interact
# with the database) from any thread except the main thread.
# We mock this functionality by directly calling callback function, without any
# enforcement or validation of called functions (and whether they manipulate
# the database). This might be a future improvement.
MFF_FAST = 0
MFF_READ = 1
MFF_WRITE = 2
MFF_NOWAIT = 4


def execute_sync(callback, reqf):
    r = callback()
    if reqf & MFF_NOWAIT:
        return r
    return None


# PluginForm is a Dialog enhancement that allows dockable dialogs in IDA among
# other improvements and interfaces IDA has with dialogs, including some for
# backwards-compatability since when IDA did not provide an easy direct
# interface with Qt
FORM_VALUE = "##FORM_ID##"


class PluginForm(QtWidgets.QDialog, MockObject):
    def OnCreate(self, form):
        pass

    def Show(self, title=""):
        self.OnCreate(FORM_VALUE)
        QtWidgets.QDialog.show(self)

    def FormToPyQtWidget(self, form):
        assert form == FORM_VALUE

        # Normally, PluginForm is not a QtDialog object and retrieveing the
        # widget requires calling IDA API, however while mocking PluginForm, we
        # made it a sinlge object, so that API returns it's self object
        return self


# Just let this be called and do nothing, there's no need to execute or return
def request_refresh(mask, cnd=True):
    pass


# Just let this be called and do nothing, there's no need to execute or return
def refresh_idaview_anyway():
    pass
