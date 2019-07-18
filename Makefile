
PYPI_USER := $(shell echo $$PYPI_USERNAME)
PYPI_PASSWORD := $(shell echo $$PYPI_PASSWORD)

.PHONY: setup upload install

default: setup

setup: 
	python3 setup.py sdist bdist_wheel

upload:
	twine upload --repository-url https://test.pypi.org/legacy/ dist/* --skip-existing -u ${PYPI_USER} -p ${PYPI_PASSWORD}

check:
	python3 -m twine check

install:
	sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage

uninstall:
	sudo -H pip3 uninstall wce_triage
