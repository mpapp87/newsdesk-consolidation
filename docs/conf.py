"""Initialize Django for Sphinx autodoc without requiring a running database."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "news_project.test_settings")
import django

django.setup()
project = "NewsDesk"
extensions = ["sphinx.ext.autodoc"]
html_theme = "alabaster"
exclude_patterns = ["_build"]
