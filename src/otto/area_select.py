import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, GLib, Gtk


class _AreaSelector:
    def __init__(self):
        self.result: tuple[int, int, int, int] | None = None
        self._start: tuple[int, int] | None = None
        self._current: tuple[int, int] | None = None
        self._loop = GLib.MainLoop()

        self.window = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.window.set_decorated(False)
        self.window.set_keep_above(True)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_app_paintable(True)

        screen = self.window.get_screen()
        visual = screen.get_rgba_visual()
        self._rgba = visual is not None
        if self._rgba:
            self.window.set_visual(visual)

        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        geom = monitor.get_geometry()
        self.window.move(geom.x, geom.y)
        self.window.resize(geom.width, geom.height)
        self._origin = (geom.x, geom.y)

        self.window.set_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
        )
        self.window.connect('button-press-event', self._on_press)
        self.window.connect('button-release-event', self._on_release)
        self.window.connect('motion-notify-event', self._on_motion)
        self.window.connect('key-press-event', self._on_key)
        self.window.connect('draw', self._on_draw)

        cursor = Gdk.Cursor.new_for_display(display, Gdk.CursorType.CROSSHAIR)
        self.window.realize()
        self.window.get_window().set_cursor(cursor)

    def run(self) -> tuple[int, int, int, int] | None:
        self.window.show_all()
        self._loop.run()
        self.window.destroy()
        return self.result

    def _on_press(self, _w, event):
        if event.button == 1:
            self._start = (int(event.x_root), int(event.y_root))
            self._current = self._start
            self.window.queue_draw()
        return True

    def _on_motion(self, _w, event):
        if self._start is not None:
            self._current = (int(event.x_root), int(event.y_root))
            self.window.queue_draw()
        return True

    def _on_release(self, _w, event):
        if event.button == 1 and self._start is not None:
            x1, y1 = self._start
            x2, y2 = int(event.x_root), int(event.y_root)
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            if w > 0 and h > 0:
                self.result = (x, y, w, h)
            self._loop.quit()
        return True

    def _on_key(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            self._loop.quit()
        return True

    def _on_draw(self, _w, cr):
        if self._rgba:
            cr.set_source_rgba(0, 0, 0, 0.25)
            cr.set_operator(1)  # OVER
            cr.paint()
        else:
            cr.set_source_rgb(0.5, 0.5, 0.5)
            cr.paint()

        if self._start is None or self._current is None:
            return False

        ox, oy = self._origin
        x1, y1 = self._start
        x2, y2 = self._current
        x, y = min(x1, x2) - ox, min(y1, y2) - oy
        w, h = abs(x2 - x1), abs(y2 - y1)

        if self._rgba:
            cr.set_operator(0)  # CLEAR
            cr.rectangle(x, y, w, h)
            cr.fill()
            cr.set_operator(1)  # OVER

        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.set_line_width(1.0)
        cr.rectangle(x + 0.5, y + 0.5, w, h)
        cr.stroke()
        return False


def select_area() -> tuple[int, int, int, int] | None:
    return _AreaSelector().run()
