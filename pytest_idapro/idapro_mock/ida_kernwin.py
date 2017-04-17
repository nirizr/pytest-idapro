from .mock import MockObject


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
