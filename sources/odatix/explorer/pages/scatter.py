import dash

from odatix.explorer.ui.shell import explorer_shell

def layout(**kwargs):
  return explorer_shell("scatter")


dash.register_page(__name__, path="/explorer/scatter", name="Scatter", title="Odatix Explorer - Scatter", order=23, layout=layout)
