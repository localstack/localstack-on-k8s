VENV_DIR ?= .venv
PIP_CMD ?= pip3
VENV_RUN = . $(VENV_DIR)/bin/activate

usage:      ## Show this help
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/:.*##\s*/##/g' | awk -F'##' '{ printf "%-25s %s\n", $$1, $$2 }'

install:    ## Install the dependencies in a virtualenv
	test -d $(VENV_DIR) || virtualenv $(VENV_DIR)
	$(VENV_RUN); $(PIP_CMD) install -e .

init:       ## Initialize the Kubernetes cluster and install LocalStack
	$(VENV_RUN); python -m l8k.run install

deploy:     ## Deploy a sample app on the LocalStack instance
	$(VENV_RUN); python -m l8k.run deploy

lint:
	$(VENV_RUN); python -m pflake8 --show-source l8k

format:
	$(VENV_RUN); python -m isort l8k; python -m black l8k

.PHONY: usage install init lint format
