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