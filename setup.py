#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name = 'panscola',
    version='0.1',
    scripts=[
        'panscola/filter.py',
    ],
    packages = find_packages(),
)
