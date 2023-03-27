
.PHONY: setup upload install manifest local run ui

PYPI_USER := $(shell echo $$PYPI_USERNAME)
PYPI_PASSWORD := $(shell echo $$PYPI_PASSWORD)

PY3 := python3

default: setup

setup: manifest
	. ./venv/bin/activate && python3 setup.py sdist bdist_wheel

bootstrap:
	sudo apt install $(PY3) $(PY3)-venv 
	$(PY3) -m venv venv
	. ./venv/bin/activate && $(PY3) -m pip install --upgrade setuptools wheel twine
	. ./venv/bin/activate && $(PY3) -m ensurepip --upgrade
	. ./venv/bin/activate && pip install -r requirements.txt
	touch bootstrap

upload: 
	. ./venv/bin/activate && twine upload --repository-url https://test.pypi.org/legacy/ dist/* --skip-existing -u ${PYPI_USER} -p ${PYPI_PASSWORD}

check:
	. ./venv/bin/activate && python3 -m twine check

install:
	sudo -H /usr/bin/pip3 install --no-cache-dir --upgrade  -r requirements.txt
	sudo -H /usr/bin/pip3 install --no-cache-dir --upgrade  -i https://test.pypi.org/simple/ wce_triage

uninstall:
	sudo -H /usr/bin/pip3 uninstall wce_triage

manifest:
	echo include requirements.txt> MANIFEST.in
	echo include Makefile >> MANIFEST.in
	find wce_triage/setup/patches -type f -print |sort | sed -e 's/^/include /' >> MANIFEST.in
	find wce_triage/setup/share -type f -print |sort | sed -e 's/^/include /' >> MANIFEST.in
	echo "recursive-include wce_triage/ui" >> MANIFEST.in

local:
	sudo rsync -av --delete /home/ntai/sand/wce-triage-v2/wce_triage/ /var/lib/netclient/wcetriage_amd64/usr/local/lib/python3.6/dist-packages/wce_triage/
	sudo rsync -av --delete /home/ntai/sand/wce-triage-v2/wce_triage/ /var/lib/netclient/wcetriage_x32/usr/local/lib/python3.6/dist-packages/wce_triage/

run:
	. ./venv/bin/activate && PYTHONPATH=${PWD} sudo ./venv/bin/python3 -m wce_triage.http.httpserver

flask:
	. ./venv/bin/activate && PYTHONPATH=${PWD} FLASK_APP=wce_triage.backend.app:create_app FLASK_ENV=development sudo -E flask wce --host localhost --port 8400 --wcedir /usr/local/share/wce

ui:
	rsync -av --delete ../wce-triage-ui/build/ ./wce_triage/ui/
