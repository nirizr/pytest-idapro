#!/usr/bin/python

from setuptools import setup

from pytest_idapro import __version__

setup(
    name='pytest-idapro',
    packages=['pytest_idapro'],
    version=__version__,
    description=('A pytest plugin that mocks idapython modules to perform'
                 'tests outside of IDA in an automated manner.'),
    author='Nir Izraeli',
    author_email='nirizr@gmail.com',
    maintainer='Nir Izraeli',
    maintainer_email='nirizr@gmail.com',
    keywords=['testing', 'pytest', 'idapython', 'idapro'],
    install_requires=['pytest>=2.7'],
    url='https://github.com/nirizr/pytest-idapro',
    classifiers=[
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
    ],
    # the following makes a plugin available to py.test
    entry_points={'pytest11': ['idapro = pytest_idapro.plugin']}
)
