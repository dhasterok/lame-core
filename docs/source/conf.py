# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Package lives at src/lame_core -- this makes `import lame_core` work even
# when building docs from an environment that doesn't have lame-core pip
# installed (editable or otherwise).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

project = "lame-core"
copyright = "2025, Shavin Kaluthantri, Derrick Hasterok, and Maggie Li"
author = "Shavin Kaluthantri, Derrick Hasterok, and Maggie Li"
release = "0.1.0"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "numpydoc",
]

autosummary_generate = True
autosummary_imported_members = False
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "**/__pycache__/**", "**/.venv/**", "**/venv/**"]

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "inherited-members": False,
    "show-inheritance": True,
}
autoclass_content = "both"

# see LaME's docs/source/conf.py for why this matters: without it, numpydoc's
# per-class "Methods" table tries to link every inherited PyQt6 method (e.g.
# QWidget.acceptDrops) to an autosummary stub page that never gets generated,
# producing thousands of spurious "stub file not found" warnings.
numpydoc_class_members_toctree = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/pandas-docs/stable/", None),
    # darkdetect removed: it doesn't publish a Sphinx inventory. Its PyPI
    # project page returns its normal HTML page for any URL ending in
    # objects.inv (confirmed via curl), which crashes the build with
    # "invalid inventory header: <!DOCTYPE html>" rather than just warning.
}

# -- Options for HTML output -------------------------------------------------

html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]
html_theme_options = {
    "navbar_start": ["navbar-logo"],
    "navbar_center": ["navbar-nav"],
    "navbar_end": ["navbar-icon-links"],
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/dhasterok/lame-core",
            "icon": "fa-brands fa-github",
            "type": "fontawesome",
        },
    ],
}