import dash

from odatix.explorer.ui.shell import explorer_shell

def layout(**kwargs):
  return explorer_shell("scatter3d")


dash.register_page(__name__, path="/explorer/scatter3d", name="Scatter 3D", title="Odatix Explorer - Scatter 3D", order=24, layout=layout)
