#!/bin/sh

BASEDIR=$(dirname $(realpath "$0"))
echo BASEDIR=$BASEDIR
export PYTHONPATH=$BASEDIR/../wce_triage
echo PYTHONPATH=$PYTHONPATH
python3 -m unittest
