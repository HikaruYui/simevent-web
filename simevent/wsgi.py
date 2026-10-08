"""
WSGI config for simevent project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simevent.settings')
application = get_wsgi_application()
