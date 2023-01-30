"""
WSGI config for poma project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/wsgi/
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "poma.settings")
os.environ.setdefault("DJANGO_CONFIGURATION", "DEV")

from configurations.wsgi import get_wsgi_application

application = get_wsgi_application()
