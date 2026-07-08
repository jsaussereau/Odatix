import dash

from odatix.explorer.ui.shell import explorer_shell

def layout(**kwargs):
  return explorer_shell("lines")


dash.register_page(__name__, path="/explorer/lines", name="Lines", title="Odatix Explorer - Lines", order=21, layout=layout)
