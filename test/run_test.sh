#!/bin/sh

export PYTHONPATH=$(dirname $PWD)
echo PYTHONPATH=$PYTHONPATH
python3 -m unittest
