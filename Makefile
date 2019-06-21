
PYPI_USER := ntai
PYPI_PASSWORD := ps8AVW4p@jT$98Ud

.PHONY: setup upload install

default: setup

setup:
	python3 setup.py sdist bdist_wheel

upload:
	python3 -m twine upload --repository-url https://test.pypi.org/legacy/ dist/* --skip-existing -u ${PYPI_USER}

check:
	python3 -m twine check

install:
	sudo -H pip3 install --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage

uninstall:
	sudo -H pip3 uninstall wce_triage
