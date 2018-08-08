|Build Status| |PyPI|

pytest-idapro
=============

A pytest module for The Interactive Disassembler and IDAPython, by executing an
internal pytest runner inside IDA or mocking IDAPython functionality outside of
IDA.

Motivation
----------

As the avarage IDAPython plugin size increases, the need of proper unitests
becomes more evident. The purpose of this pytest plugin is to ease unittesting
IDAPython plugins and scripts.

Basic usage
-----------

pytest-idapro can execute tests in two forms:

1. Mocking IDAPython API and definitions therefore allowing tests to run with no
   IDA instance installed. This is primarily used in Continuous Integration
   environemnts where IDA installation is unavailable. This is the default mode.
   This is incomplete at the moment.
2. By providing the :code:`--ida` flag and an IDA executable, ipytest-idapro will
   run a worker pytest instance inside IDA, execute all tests and collect
   results in main pytest process (this behavior is somewhat similar to the
   xdist plugin). By defualt IDA will open use a temporary empty database file,
   use the :code:`--ida-file`  flag to specify IDB or binary file for IDA to
   analyze.

Fixtures
--------

Pytest `Fixtures <https://docs.pytest.org/en/latest/fixture.html>`_ are
exteremly powerful when writing tests, and pytest-idapro currently comes with
two helpful fixtures:

1. :code:`idapro_plugin_entry` - pytest-idapro will automatically identify all ida
   plugin entry points (functions named :code:`PLUGIN_ENTRY`) across your code base
   and let you easily writing tests for all plugin objects defined.
2. :code:`idapro_action_entry` - pytest-idapro will automatically identify all ida
   actions (objects inheriting the :code:`action_handler_t` class) throughout your
   code and again, let you easily write tests for all of your actions.

.. |Build Status| image:: https://travis-ci.org/nirizr/pytest-idapro.svg?branch=master
   :alt: Build Status
   :target: https://travis-ci.org/nirizr/pytest-idapro
.. |PyPI| image:: https://img.shields.io/pypi/v/pytest-idapro.svg
   :alt: PyPI
   :target: https://pypi.python.org/pypi/pytest-idapro
