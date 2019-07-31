
PYPI_USER := $(shell echo $$PYPI_USERNAME)
PYPI_PASSWORD := $(shell echo $$PYPI_PASSWORD)

.PHONY: setup upload install manifest

default: setup

setup: manifest
	python3 setup.py sdist bdist_wheel

upload: 
	twine upload --repository-url https://test.pypi.org/legacy/ dist/* --skip-existing -u ${PYPI_USER} -p ${PYPI_PASSWORD}

check:
	python3 -m twine check

install:
	sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage

uninstall:
	sudo -H pip3 uninstall wce_triage

manifest:
	echo include requirements.txt> MANIFEST.in
	find wce_triage/setup/patches -type f -print | sed -e 's/^/include /' >> MANIFEST.in

bootstrap:
	sudo python3 -m pip install --upgrade setuptools wheel twine
