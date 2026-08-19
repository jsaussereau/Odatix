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

import dash

from odatix.gui.jobs_config.common import page_path
from odatix.gui.jobs_config.layout import layout
from odatix.gui.page_scope import scoped

# Callbacks of the jobs_config package (callbacks_config / _run / _sim) are
# anchored to this scope, which only this page embeds.
PAGE_SCOPE = "jobs_config"
layout = scoped(PAGE_SCOPE, layout)

from odatix.gui.jobs_config import callbacks_config
from odatix.gui.jobs_config import callbacks_run
from odatix.gui.jobs_config import callbacks_sim

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Job Selection',
    name='Run jobs',
    order=3,
)
