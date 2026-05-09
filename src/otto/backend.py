import sys
from abc import ABC, abstractmethod

from gi.repository import GdkPixbuf


class Backend(ABC):
    @abstractmethod
    def screenshot(self, include_pointer: bool, flash: bool) -> GdkPixbuf.Pixbuf | None:
        ...

    @abstractmethod
    def screenshot_window(self, include_pointer: bool, include_frame: bool, flash: bool) -> GdkPixbuf.Pixbuf | None:
        ...

    @abstractmethod
    def screenshot_area(self, x: int, y: int, w: int, h: int, flash: bool) -> GdkPixbuf.Pixbuf | None:
        ...

    @abstractmethod
    def select_area(self) -> tuple[int, int, int, int] | None:
        ...


def get(force_fallback: bool = False) -> Backend:
    if not force_fallback:
        from .backend_dbus import DBusBackend, dbus_service_available
        if dbus_service_available():
            return DBusBackend()
        print('otto: DBus screenshot service unavailable, using X11 fallback',
              file=sys.stderr)
    from .backend_x11 import X11Backend
    return X11Backend()
