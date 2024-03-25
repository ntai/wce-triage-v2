.PHONY: setup upload install manifest local run ui flask gu uflask

PYPI_USER := $(shell echo $$PYPI_USERNAME)
PYPI_PASSWORD := $(shell echo $$PYPI_PASSWORD)

PY3 := python3

default: setup

setup: manifest
	. ./venv/bin/activate && python3 setup.py sdist bdist_wheel

bootstrap:
	sudo apt install python3 python3-venv
	$(PY3) -m venv venv
	. ./venv/bin/activate && $(PY3) -m pip install --upgrade pip setuptools wheel twine
	-. ./venv/bin/activate && $(PY3) -m ensurepip --upgrade
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
	echo "include wce_triage/components/cpu_meta.yaml" >> MANIFEST.in
	echo "recursive-include wce_triage/setup/patches *" >> MANIFEST.in
	echo "recursive-include wce_triage/setup/share *" >> MANIFEST.in
	echo "recursive-include wce_triage/ui *" >> MANIFEST.in

local:
	#sudo rsync -av --delete /home/ntai/sand/wce-triage-v2/build/lib/wce_triage/ /var/lib/wcetriage/wcetriage_2004/usr/local/lib/python3.8/dist-packages/wce_triage/
	sudo rsync -av --delete /home/ntai/sand/wce-triage-v2/wce_triage/ /var/lib/wcetriage/wcetriage_2004/usr/local/lib/python3.8/dist-packages/wce_triage/

run:
	. ./venv/bin/activate && PYTHONPATH=${PWD} sudo ./venv/bin/python3 -m wce_triage.http.httpserver

flask:
	. ./venv/bin/activate && PYTHONPATH=${PWD} FLASK_ENVIRONMENT=development FLASK_APP=wce_triage.backend.app:create_app sudo -E --preserve-env=PATH,PYTHONPATH,FLASK_DEBUG,FLASK_APP,FLASK_ENVIRONMENT ${PWD}/venv/bin/flask run --host 0.0.0.0 --port 10600

uflask:
	. ./venv/bin/activate && PYTHONPATH=${PWD} FLASK_ENVIRONMENT=development FLASK_APP=wce_triage.backend.app:create_app ${PWD}/venv/bin/flask run --host 0.0.0.0 --port 10600

gu:
	. ./venv/bin/activate && PYTHONPATH=${PWD} FLASK_ENVIRONMENT=development FLASK_APP=wce_triage.backend.app:app sudo -E --preserve-env=PATH,PYTHONPATH,FLASK_DEBUG,FLASK_APP,FLASK_ENVIRONMENT ${PWD}/venv/bin/gunicorn -w 4 -b 0.0.0.0:10600 'wce_triage.backend.app:create_app()'


ui:
	rsync -av --delete ../wce-triage-ui/build/ ./wce_triage/ui/

user:
	. ./venv/bin/activate && PYTHONPATH=${PWD} FLASK_ENVIRONMENT=development FLASK_APP=wce_triage.backend.app:app flask run --host 0.0.0.0 --port 10600
