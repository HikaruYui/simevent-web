#!/usr/bin/env python
# Fungsi file: Titik masuk perintah Django, seperti runserver, migrate, check, dan test.

import os
import sys
from dotenv import load_dotenv

# Muat variabel lingkungan dari file .env
load_dotenv()

from django.core.management import execute_from_command_line


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    execute_from_command_line(sys.argv)