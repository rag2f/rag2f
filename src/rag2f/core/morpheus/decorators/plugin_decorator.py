"""Plugin lifecycle override decorator."""


# class to represent a @plugin override
class PillPluginDecorator:
    """Wrap a plugin lifecycle override function."""

    def __init__(self, function):
        """Create a wrapper around a plugin override function."""
        self.function = function
        self.name = function.__name__


def plugin(func):
    """Decorate a function as a plugin lifecycle override."""
    return PillPluginDecorator(func)
