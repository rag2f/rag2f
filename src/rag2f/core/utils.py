

import os
import inspect
from typing import Any
import logging

# Set up a module-level logger
logger = logging.getLogger(__name__)

def get_project_path():
    """Path to the folder from which the cat was run (contains data, plugins and static folders)"""
    return os.getcwd()

def get_plugins_path():
    """Allows exposing the plugins' path."""
    return os.path.join(get_project_path(), "plugins")

def get_caller_info(skip=2, return_short=True, return_string=True):
    """Get the name of a caller in the format module.class.method.

    Adapted from: https://gist.github.com/techtonik/2151727

    Parameters
    ----------
    skip :  int
        Specifies how many levels of stack to skip while getting caller name.
    return_string : bool
        If True, returns the caller info as a string, otherwise as a tuple.

    Returns
    -------
    package : str
        Caller package.
    module : str
        Caller module.
    klass : str
        Caller classname if one otherwise None.
    caller : str
        Caller function or method (if a class exist).
    line : int
        The line of the call.


    Notes
    -----
    skip=1 means "who calls me",
    skip=2 "who calls my caller" etc.

    None is returned if skipped levels exceed stack height.
    """

    stack = inspect.stack()
    start = 0 + skip
    if len(stack) < start + 1:
        return None

    parentframe = stack[start][0]

    # module and packagename.
    module_info = inspect.getmodule(parentframe)
    if module_info:
        mod = module_info.__name__.split(".")
        package = mod[0]
        module = ".".join(mod[1:])

    # class name.
    klass = ""
    if "self" in parentframe.f_locals:
        klass = parentframe.f_locals["self"].__class__.__name__

    # method or function name.
    caller = None
    if parentframe.f_code.co_name != "<module>":  # top level usually
        caller = parentframe.f_code.co_name

    # call line.
    line = parentframe.f_lineno

    # Remove reference to frame
    # See: https://docs.python.org/3/library/inspect.html#the-interpreter-stack
    del parentframe

    if return_string:
        if return_short:
            return f"{klass}.{caller}"
        else:
            return f"{package}.{module}.{klass}.{caller}::{line}"
    return package, module, klass, caller, line

def deprecation_warning(message: str, skip=3):
    """Log a deprecation warning with caller's information.
        "skip" is the number of stack levels to go back to the caller info."""

    caller = get_caller_info(skip, return_short=False)

    # Format and log the warning message
    logger.warning(
        f"{caller} Deprecation Warning: {message})"
    )


async def run_sync_or_async(f, *args, **kwargs) -> Any:
    if inspect.iscoroutinefunction(f):
        return await f(*args, **kwargs)
    deprecation_warning(f"Function {f} should be async.")
    return f(*args, **kwargs)
