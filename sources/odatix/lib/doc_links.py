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

"""
Links to the online documentation, in one place: the commands and the GUI
point to its pages from here.
"""

#: Root of the online documentation. Read the Docs serves the documentation of
#: the main branch under "latest", and that of the last release under "stable",
#: where the root of the site redirects. "stable" is still the documentation of
#: Odatix 3, whose pages have other paths: switch to it once Odatix 4 is
#: released.
DOCS_URL = "https://odatix.readthedocs.io/en/latest/"


def doc_url(path=""):
    """The URL of a page of the documentation, from its path (as in the links of the documentation itself)."""
    return DOCS_URL + path.lstrip("/")


GETTING_STARTED_URL = doc_url("docs/getting-started/")
GLOSSARY_URL = doc_url("docs/glossary/")
OWN_DESIGNS_URL = doc_url("tutorials/own_designs/")
