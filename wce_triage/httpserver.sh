#!/bin/sh

export PYTHONPATH=$PWD
python3 http/httpserver.py $*
