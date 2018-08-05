#!/bin/bash

rm -r ./dist/
./setup.py sdist --format zip
twine upload ./dist/* -r pypi
