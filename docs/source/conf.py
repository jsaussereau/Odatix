# Configuration file for the Sphinx documentation builder.

import os 
# -- Project information

project = 'Odatix'
copyright = '2022-2025, Jonathan Saussereau'
author = 'Jonathan Saussereau'

def read_version():
    version_file = os.path.join(os.pardir, os.pardir, "sources", "odatix", "version.txt")
    with open(version_file, "r") as file:
        return file.read().strip()

version = read_version()
release = version

# -- General configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    "sphinx_inline_tabs",
    "sphinx_copybutton",
    "sphinx_toolbox.collapse",
    "sphinx_design",
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'sphinx': ('https://www.sphinx-doc.org/en/master/', None),
}
intersphinx_disabled_domains = ['std']

templates_path = ['_templates']

# -- Options for HTML output

html_theme = 'furo'

html_static_path = ['_static']
html_css_files = [
    'css/custom.css',
]

# -- Options for EPUB output
epub_show_urls = 'footnote'
