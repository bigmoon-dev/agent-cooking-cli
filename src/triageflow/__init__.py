__all__ = ["__version__", "register_hook", "emit", "set_hook_error_handler"]

__version__ = "0.1.5"

from .core import emit, register_hook, set_hook_error_handler
