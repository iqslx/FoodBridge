"""WSGI entry point for PythonAnywhere and other Python web hosts."""
import sys
from pathlib import Path

project = str(Path(__file__).resolve().parent)
if project not in sys.path:
    sys.path.insert(0, project)

from foodbridge import create_app
application = create_app()
