from .mock import MockObject


# Passed as 'flags' parameter to attach_action_to_menu()
SETMENU_INS = 0  # add menu item before the specified path (default)
SETMENU_APP = 1  # add menu item after the specified path


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
