"""Hook decorator and related data structures."""

from collections.abc import Callable


# class to represent a @hook
class PillHook:
    """Represents a hook function loaded from a plugin."""

    def __init__(self, name: str, func: Callable, priority: int):
        """Create a PillHook.

        Args:
            name: Hook name.
            func: Underlying callable.
            priority: Hook priority (higher executes first).
        """
        self.function = func
        self.name = name
        self.priority = priority
        self.plugin_id = None

    def __repr__(self) -> str:
        """Return a compact debug representation."""
        return f"PillHook(plugin_id={self.plugin_id}, name={self.name}, priority={self.priority})"


def hook(*args: str | Callable, priority: int = 1) -> Callable:
    """Decorate a function as a Morpheus hook.

    Args:
        *args: Optional hook name or function.
        priority: Hook priority (higher executes first).

    Returns:
        A decorator that wraps the function into a PillHook.
    """

    def _make_with_name(hook_name: str) -> Callable:
        def _make_hook(func: Callable[[str], str]) -> PillHook:
            hook_ = PillHook(name=hook_name, func=func, priority=priority)
            return hook_

        return _make_hook

    if len(args) == 1 and isinstance(args[0], str):
        # if the argument is a string, then we use the string as the hook name
        # Example usage: @hook("search", priority=2)
        return _make_with_name(args[0])
    elif len(args) == 1 and callable(args[0]):
        # if the argument is a function, then we use the function name as the hook name
        # Example usage: @hook
        return _make_with_name(args[0].__name__)(args[0])
    elif len(args) == 0:
        # if there are no arguments, then we use the function name as the hook name
        # Example usage: @hook(priority=2)
        def _partial(func: Callable[[str], str]) -> PillHook:
            return _make_with_name(func.__name__)(func)

        return _partial
    else:
        raise ValueError("Too many arguments for hook decorator")
