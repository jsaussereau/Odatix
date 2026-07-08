import dash

from odatix.explorer.ui.shell import explorer_shell

def layout(**kwargs):
  return explorer_shell("overview")


dash.register_page(__name__, path="/explorer/overview", name="Overview", title="Odatix Explorer - Overview", order=26, layout=layout)
