.PHONY: setup upload install manifest local run ui flask gu uflask

PYPI_USER := $(shell echo $$PYPI_USERNAME)
PYPI_PASSWORD := $(shell echo $$PYPI_PASSWORD)
TESTPYPI_API_TOKEN := $(shell echo $$PYPI_PASSWORD)

PY3 := python3

default: setup

setup: manifest
	. ./venv/bin/activate && python3 setup.py sdist bdist_wheel


venv:
	sudo apt install python3 python3-venv
	$(PY3) -m venv venv

bootstrap: venv
	. ./venv/bin/activate && $(PY3) -m pip install --upgrade pip setuptools wheel twine
	-. ./venv/bin/activate && $(PY3) -m ensurepip --upgrade
	. ./venv/bin/activate && pip install poetry && poetry install
	. ./venv/bin/activate && poetry config repositories.testpypi https://test.pypi.org/legacy/
	. ./venv/bin/activate && poetry config pypi-token.testpypi ${TESTPYPI_API_TOKEN}
	touch bootstrap

upload: 
	#. ./venv/bin/activate && twine upload --repository-url https://test.pypi.org/legacy/ dist/* --skip-existing -u ${PYPI_USER} -p ${PYPI_PASSWORD}
	. ./venv/bin/activate && poetry publish -r testpypi 

check:
	. ./venv/bin/activate && python3 -m twine check

install:
	sudo -H /usr/bin/pip3 install --no-cache-dir --upgrade  -i https://test.pypi.org/simple/ wce_triage

uninstall:
	sudo -H /usr/bin/pip3 uninstall wce_triage

manifest:
	echo include requirements.txt> MANIFEST.in
	echo include Makefile >> MANIFEST.in
	find wce_triage/setup/patches -type f -print |sort | sed -e 's/^/include /' >> MANIFEST.in
	find wce_triage/setup/share -type f -print |sort | sed -e 's/^/include /' >> MANIFEST.in
	echo "include wce_triage/components/cpu_meta.yaml" >> MANIFEST.in
	echo "recursive-include wce_triage/setup/patches *" >> MANIFEST.in
	echo "recursive-include wce_triage/setup/share *" >> MANIFEST.in
	echo "recursive-include wce_triage/ui *" >> MANIFEST.in

local:
	#sudo rsync -av --delete /home/ntai/sand/wce-triage-v2/build/lib/wce_triage/ /var/lib/wcetriage/wcetriage_2004/usr/local/lib/python3.8/dist-packages/wce_triage/
	sudo rsync -av --delete /home/ntai/sand/wce-triage-v2/wce_triage/ /var/lib/wcetriage/wcetriage_2004/usr/local/lib/python3.8/dist-packages/wce_triage/

http:
	. ./venv/bin/activate && PYTHONPATH=${PWD} sudo ./venv/bin/python3 -m wce_triage.http.httpserver

run:
	. ./venv/bin/activate && PYTHONPATH=${PWD} sudo ./venv/bin/uvicorn wce_triage.api.app:socket_app  --host 0.0.0.0 --port 10600

ui:
	rsync -av --delete ../wce-triage-ui/build/ ./wce_triage/ui/
