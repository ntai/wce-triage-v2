
PYPI_USER := $(shell echo $$PYPI_USERNAME)
PYPI_PASSWORD := $(shell echo $$PYPI_PASSWORD)

.PHONY: setup upload install manifest netclient

default: setup

setup: manifest
	python3 setup.py sdist bdist_wheel

bootstrap:
	sudo apt install python3-pip virtualenv
	virtualenv -p python3 py3
	. ./py3/bin/activate && python3 -m pip install --upgrade setuptools wheel twine
	touch bootstrap

upload: 
	twine upload --repository-url https://test.pypi.org/legacy/ dist/* --skip-existing -u ${PYPI_USER} -p ${PYPI_PASSWORD}

check:
	python3 -m twine check

install:
	sudo -H /usr/bin/pip3 install --no-cache-dir --upgrade  -i https://test.pypi.org/simple/ wce_triage

uninstall:
	sudo -H /usr/bin/pip3 uninstall wce_triage

manifest:
	echo include requirements.txt> MANIFEST.in
	echo include Makefile >> MANIFEST.in
	find wce_triage/setup/patches -type f -print |sort | sed -e 's/^/include /' >> MANIFEST.in
	find wce_triage/setup/share -type f -print |sort | sed -e 's/^/include /' >> MANIFEST.in


netclient:
	sudo rsync -av --delete /disk2/home/triage/wce-triage-v2/wce_triage/ /var/lib/netclient/wcetriage/usr/local/lib/python3.6/dist-packages/wce_triage/
