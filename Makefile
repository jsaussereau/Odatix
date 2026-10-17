# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

########################################################
# Paths
########################################################

SOURCE_DIR              = sources

########################################################
# Installation
########################################################

BUILD_CMD               = python -m build $(SOURCE_DIR)
VENV                    = venv
VENV_PYTHON             = $(VENV)/bin/python
INSTALL_BUILD_CMD       = $(VENV_PYTHON) -m pip install build

########################################################
# Build
########################################################

.PHONY: build
build: $(VENV_PYTHON)
	$(BUILD_CMD)

$(VENV_PYTHON):
	python -m venv $(VENV)
	$(INSTALL_BUILD_CMD)

########################################################
# Documentation
########################################################

API_DOCS_CMD            = python docs/tools/gen_api_reference.py

.PHONY: api-docs
api-docs:
	$(API_DOCS_CMD)

.PHONY: api-docs-check
api-docs-check:
	$(API_DOCS_CMD) --check

# Builds the site in a temporary directory, fails on two pages written to the
# same path, then checks every internal link and anchor of what was built.
.PHONY: docs-check
docs-check:
	@out=$$(mktemp -d); \
	hugo --source docs --printPathWarnings --destination "$$out" > "$$out.log" 2>&1; \
	status=$$?; \
	cat "$$out.log"; \
	if grep -q "Duplicate target paths" "$$out.log"; then status=1; fi; \
	if [ $$status -eq 0 ]; then python docs/tools/check_links.py "$$out" || status=1; fi; \
	rm -rf "$$out" "$$out.log"; \
	exit $$status

########################################################
# Tests
########################################################

.PHONY: test
test:
	python -m pytest

.PHONY: test-fast
test-fast:
	python -m pytest -m "not integration and not gui"

.PHONY: test-coverage
test-coverage:
	python -m pytest --cov=odatix --cov-report=term-missing --cov-report=xml