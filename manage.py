#!/usr/bin/env python
"""Provide the command-line entry point for NewsDesk administration."""

import os
import sys


def main():
    """Run Django management commands using the NewsDesk settings."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "news_project.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
