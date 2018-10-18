#!/usr/bin/python

from setuptools import setup, find_packages
import re

__version__ = re.search(
    r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]',  # It excludes inline comment too
    open('pytest_idapro/__init__.py').read()).group(1)

setup(
    name='pytest-idapro',
    packages=find_packages(),
    version=__version__,
    description=('A pytest plugin for idapython. Allows a pytest setup to run '
                 'tests outside and inside IDA in an automated manner by '
                 'runnig pytest inside IDA and by mocking idapython api'),
    author='Nir Izraeli',
    author_email='nirizr@gmail.com',
    maintainer='Nir Izraeli',
    maintainer_email='nirizr@gmail.com',
    keywords=['testing', 'pytest', 'idapython', 'idapro'],
    install_requires=['pytest>=2.7', 'pytest-xvfb'],
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
