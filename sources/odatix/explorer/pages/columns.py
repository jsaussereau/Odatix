import dash

from odatix.explorer.ui.shell import explorer_shell

def layout(**kwargs):
  return explorer_shell("columns")


dash.register_page(__name__, path="/explorer/columns", name="Columns", title="Odatix Explorer - Columns", order=22, layout=layout)
