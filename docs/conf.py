"""Initialize Django for Sphinx autodoc without requiring a running database."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "news_project.test_settings")
import django

django.setup()
project = "NewsDesk"
author = "Michael Papp"
release = "1.0.0"
extensions = ["sphinx.ext.autodoc", "sphinx.ext.viewcode", "sphinx.ext.napoleon"]
html_theme = "alabaster"
exclude_patterns = ["_build"]
