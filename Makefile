.ONESHELL:

.DEFAULT_GOAL := help

help:
	@awk 'BEGIN {FS = ":.*#"; printf "Usage: make \033[36m<option>\033[0m\n \nOptions:\n"} /^[a-zA-Z0-9_-]+:.*?#/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^#@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: virtualenv
virtualenv:  #: Create a new virtual environment.
	@rm -rf .venv venv
	@python3 -m venv .venv
	@echo "Run 'source .venv/bin/activate' to enable it."

.PHONY: install
install:  #: Install project dependencies.
	@pip3 install -r requirements.txt

.PHONY: fmt
fmt:  #: Format code style.
	@autoflake --in-place src --recursive --remove-all-unused-imports --remove-unused-variables
	isort src
	black -l 88 src

.PHONY: clean
clean:	#: Clean up unnecessary files.
	@find ./ -name '*.pyc' -exec rm -f {} \;
	@find ./ -name '__pycache__' -exec rm -rf {} \;
	@find ./ -name '*.pytest_cache' -exec rm -rf {} \;
	@find ./ -name 'Thumbs.db' -exec rm -f {} \;
	@find ./ -name '*~' -exec rm -f {} \;
	@rm -rf .cache
	@rm -rf .pytest_cache