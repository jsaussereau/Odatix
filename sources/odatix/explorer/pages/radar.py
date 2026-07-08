import dash

from odatix.explorer.ui.shell import explorer_shell

def layout(**kwargs):
  return explorer_shell("radar")


dash.register_page(__name__, path="/explorer/radar", name="Radar", title="Odatix Explorer - Radar", order=25, layout=layout)
