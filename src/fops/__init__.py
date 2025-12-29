__all__ = ("__version__", "core")

import logging
from importlib import metadata

from fops import core

__version__ = metadata.version(__name__)

# Prevent "No handlers could be found" warnings when the library is imported.
# Applications are responsible for configuring handlers/formatters/levels.
logging.getLogger(__name__).addHandler(logging.NullHandler())
