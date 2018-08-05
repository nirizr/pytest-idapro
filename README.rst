|Build Status| |PyPI|

pytest-idapro
=============

a pytest module for The Interactive Disassembler and IDAPython, by executing an
internal pyetest runner inside IDA or mocking IDAPython functionality outside
of IDA.

Basic usage
-----------

pytest-idapro can execute tests in two forms:

1. Mocking IDAPython API and definitions therefore allowing tests to run with no
   IDA instance installed. This is primarily used in Continuous Integration
   environemnts where IDA installation is unavailable. This is the default mode.
   This is incomplete at the moment.
2. By providing the `--ida` flag and an IDA executable, ipytest-idapro will
   run a worker pytest instance inside IDA, execute all tests and collect
   results in main pytest process (this behavior is somewhat similar to the
   xdist plugin)

.. |Build Status| image:: https://travis-ci.org/nirizr/pytest-idapro.svg?branch=master
   :alt: Build Status
   :target: https://travis-ci.org/nirizr/pytest-idapro
.. |PyPI| image:: https://img.shields.io/pypi/v/pytest-idapro.svg
   :alt: PyPI
   :target: https://pypi.python.org/pypi/pytest-idapro
