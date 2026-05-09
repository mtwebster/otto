from gi.repository import Gdk, GdkPixbuf

from .backend import Backend


def _root_pixbuf() -> GdkPixbuf.Pixbuf | None:
    display = Gdk.Display.get_default()
    if display is None:
        return None
    screen = display.get_default_screen()
    root = screen.get_root_window()
    w, h = root.get_width(), root.get_height()
    return Gdk.pixbuf_get_from_window(root, 0, 0, w, h)


def _active_window_rect() -> tuple[int, int, int, int] | None:
    display = Gdk.Display.get_default()
    if display is None:
        return None
    screen = display.get_default_screen()
    window = screen.get_active_window()
    if window is None:
        return None
    frame = window.get_frame_extents()
    return (frame.x, frame.y, frame.width, frame.height)


class X11Backend(Backend):
    def screenshot(self, include_pointer: bool, flash: bool) -> GdkPixbuf.Pixbuf | None:
        return _root_pixbuf()

    def screenshot_window(self, include_pointer: bool, include_frame: bool, flash: bool) -> GdkPixbuf.Pixbuf | None:
        rect = _active_window_rect()
        root = _root_pixbuf()
        if rect is None or root is None:
            return None
        x, y, w, h = rect
        x = max(0, x)
        y = max(0, y)
        w = min(w, root.get_width() - x)
        h = min(h, root.get_height() - y)
        if w <= 0 or h <= 0:
            return None
        return root.new_subpixbuf(x, y, w, h).copy()

    def screenshot_area(self, x: int, y: int, w: int, h: int, flash: bool) -> GdkPixbuf.Pixbuf | None:
        root = _root_pixbuf()
        if root is None:
            return None
        x = max(0, x)
        y = max(0, y)
        w = min(w, root.get_width() - x)
        h = min(h, root.get_height() - y)
        if w <= 0 or h <= 0:
            return None
        return root.new_subpixbuf(x, y, w, h).copy()

    def select_area(self) -> tuple[int, int, int, int] | None:
        from .area_select import select_area
        return select_area()
