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
The Monitor page: jobtender's web monitor (jobtender.web.page), in the look of
the GUI and leading where the GUI goes once a session is done -- the Explorer,
or the RTL analysis dashboard after an analysis.
"""

import dash

from odatix.gui.icons import icon as odatix_icon
from odatix.gui.utils import get_key_from_url
import odatix.gui.ui_components as ui
from odatix.gui.page_scope import scoped

from jobtender.web import kit as jobtender_kit
from jobtender.web import register_assets


class OdatixKit(jobtender_kit.Kit):
    """The monitor as a page of the GUI."""

    page_path = "/monitor"
    overlay_class = "overlay-odatix"
    popup_class = "popup-odatix"
    home_href = "/"
    session_links = (
        ("Run jobs", "/choose_job_type", "primary"),
        ("Back to home", "/", "secondary"),
    )
    title = "Odatix - Monitor"
    no_session_hint = "Start jobs from Run jobs, or choose a session of another workspace in the list above."

    def icon(self, name, width="24px", height="24px", className="", offset=False, id=""):
        return odatix_icon(name, width=width, height=height, className=className, offset=offset, id=id)

    def icon_button(self, icon, color, text="", id=None, multiline=False, width="115px", center=False,
                    style=None, tooltip="", tooltip_options="bottom"):
        return ui.icon_button(icon=icon, color=color, text=text, id=id, multiline=multiline, width=width,
                              center=center, style=style or {}, tooltip=tooltip, tooltip_options=tooltip_options)

    def feedback(self, id, className=""):
        return ui.feedback(id, className=className)

    def error(self, message):
        return ui.error(message)

    def success(self, message):
        return ui.success(message)

    def scoped(self, scope, layout):
        return scoped(scope, layout)

    def finished_dialog(self, counts, search):
        # An analysis run (every job of the session is one, or the run that
        # opened the page says so) ends on its verdicts and opens the analysis
        # dashboard rather than the charts.
        if not (bool(counts.get("analysis")) or get_key_from_url(search, "explorer") == "analysis"):
            return None
        total = int(counts.get("total") or 0)
        failed = int(counts.get("failed") or 0)
        longest = int(counts.get("longest_elapsed") or 0)
        title, badge, glyph, message, stats = _analysis_finished(
            total, failed, longest, _analysis_verdicts(counts.get("designs")))
        return {
            "title": title, "badge": badge, "glyph": glyph, "message": message, "stats": stats,
            "href": "/explorer/analysis",
            "close_label": "Close session and open RTL analysis",
            "keep_label": "open RTL analysis",
        }

    def finished_destination(self, counts, search):
        return {"href": "/explorer", "close_label": "Close session and open Explorer", "keep_label": "open Explorer"}


icon = OdatixKit().icon

jobtender_kit.configure(OdatixKit())
# The page's scripts and stylesheet are served from jobtender; the GUI's own
# stylesheets come after them, and its theme gives them their colors.
register_assets()
from jobtender.web import page  # noqa: E402  (after the kit: the page is built with it)

page_path = page.page_path

dash.register_page(
    __name__,
    path=page.page_path,
    title='Odatix - Monitor',
    update_title='Odatix - Monitor',
    name='Monitor',
    order=6,
    layout=page.layout,
)


######################################
# The end of an analysis
######################################

def _analysis_verdicts(designs):
    """How the analyses of `designs` concluded, as {status: count}, or None.

    Read from what the session recorded in the results of the workspace (what
    the RTL analysis dashboard shows): the job statuses only say whether the
    tool ran, never whether it found errors in the design. None when nothing
    can be read, so the dialog says no verdict rather than a wrong one.
    """
    designs = [str(design) for design in (designs or []) if str(design or "").strip()]
    if not designs:
        return None
    try:
        import odatix.lib.analysis as analysis
        from odatix.gui.utils import get_workspace
        results = analysis.read_results(get_workspace().paths.result_path, designs=designs)
    except Exception:
        return None
    if not results:
        return None
    verdicts = {}
    for result in results:
        verdicts[result.status] = verdicts.get(result.status, 0) + 1
    return verdicts


def _analysis_finished(total, failed, longest, verdicts):
    """Title, badge, glyph, message and stats of the dialog that ends an analysis.

    An analysis job succeeds when its tool ran, whatever it found: "completed
    successfully" would read as "the design is fine". The dialog gives the
    verdicts instead, or else says where to read them.
    """
    import odatix.lib.analysis as analysis

    title = "Analysis finished"
    if verdicts:
        attention = sum(
            verdicts.get(status, 0)
            for status in (analysis.STATUS_FAILED, analysis.STATUS_TOOL_FAILURE, analysis.STATUS_INCOMPLETE)
        )
        if attention:
            badge, glyph = "monitor-finished-badge failed", icon("cross", className="icon", width="30px", height="30px")
        elif verdicts.get(analysis.STATUS_WARNING, 0):
            badge, glyph = "monitor-finished-badge warning", icon("analysis", className="icon", width="30px", height="30px")
        else:
            badge, glyph = "monitor-finished-badge success", icon("check", className="icon", width="30px", height="30px")
        analyzed = sum(verdicts.values())
        parts = [
            "{0} {1}".format(verdicts[status], analysis.STATUS_LABELS.get(status, status).lower())
            for status in analysis.STATUSES if verdicts.get(status)
        ]
        message = "{0} analyzed: {1}. The details are in the RTL analysis dashboard.".format(
            page.plural(analyzed, "design"), ", ".join(parts))
        stats = [
            page.finished_stat(verdicts[status], analysis.STATUS_LABELS.get(status, status), _VERDICT_STAT_KINDS.get(status, "total"))
            for status in analysis.STATUSES if verdicts.get(status)
        ][:3]
    else:
        badge, glyph = "monitor-finished-badge", icon("analysis", className="icon", width="30px", height="30px")
        if failed:
            message = "{0} ran, {1} of them could not finish. What the tools found is in the RTL analysis dashboard.".format(
                page.plural(total, "analysis job"), failed)
        else:
            message = "{0} ran. What the tools found is in the RTL analysis dashboard.".format(page.plural(total, "analysis job"))
        stats = [page.finished_stat(total, "Jobs", "total")]
        if failed:
            stats.append(page.finished_stat(failed, "Not finished", "failed"))
    stats.append(page.finished_stat(page.format_hms(longest), "Longest", "time"))
    return title, badge, glyph, message, stats


# Color of the dialog's figure for each analysis verdict (see style.css).
_VERDICT_STAT_KINDS = {
    "failed": "failed",
    "tool_failure": "failed",
    "incomplete": "failed",
    "warning": "warning",
    "passed": "done",
    "unsupported": "total",
}
