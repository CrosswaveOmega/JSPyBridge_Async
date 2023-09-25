# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys

sys.path.insert(0, os.path.abspath('../src/'))

project = 'AsyncJavascriptBridge'
copyright = '2023, TauCetiV'
author = 'TauCetiV'
release = '0.1.2'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [  'sphinx.highlighting', 'sphinx.ext.autodoc','sphinx.ext.napoleon','sphinx.ext.intersphinx','sphinx.ext.extlinks']
# Links used for cross-referencing stuff in other documentation
intersphinx_mapping = {
  'py': ('https://docs.python.org/3', None),
  'aio': ('https://docs.aiohttp.org/en/stable/', None),
  'req': ('https://requests.readthedocs.io/en/latest/', None)
}

extlinks = {
  'nodejs': ('https://nodejs.org/api/events.html%s', '%s')
}
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# Optional: Set the Pygments style for code highlighting
pygments_style='sphinx'

highlight_options = {
  'default': {'stripall': True},
  'javascript': {'startinline': True},
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'classic'
html_static_path = ['_static']

html_theme_options = {
    'sidebarwidth':'300px',
    'stickysidebar': True,
    'visitedlinkcolor': None,
}