import cairo

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, GdkX11

from Xlib import X, display as xdisplay

from backend import Backend


_FLASH_HOLD_MS = 75
_FLASH_TICK_MS = 8
_FLASH_FADE_FACTOR = 0.9
_FLASH_LOW_THRESHOLD = 0.1


def _fire_flash(x, y, w, h):
    """Briefly flood the given screen rect with white as visual capture
    feedback, then fade out (on composited screens) or just blink (on
    unredirected ones). Click-through, no focus, no taskbar entry."""
    if w <= 0 or h <= 0:
        return
    win = Gtk.Window(type=Gtk.WindowType.POPUP)
    win.set_decorated(False)
    win.set_skip_taskbar_hint(True)
    win.set_skip_pager_hint(True)
    win.set_keep_above(True)
    win.set_accept_focus(False)
    win.set_focus_on_map(False)
    win.override_background_color(
        Gtk.StateFlags.NORMAL, Gdk.RGBA(1.0, 1.0, 1.0, 1.0))
    win.realize()
    win.get_window().input_shape_combine_region(cairo.Region(), 0, 0)

    win.move(x, y)
    win.resize(w, h)
    win.set_opacity(1.0)
    win.show_all()

    composited = win.get_screen().is_composited()
    state = {'opacity': 1.0}

    def fade():
        state['opacity'] *= _FLASH_FADE_FACTOR
        if state['opacity'] <= _FLASH_LOW_THRESHOLD:
            win.destroy()
            return GLib.SOURCE_REMOVE
        win.set_opacity(state['opacity'])
        return GLib.SOURCE_CONTINUE

    def start_fade():
        if not composited:
            win.destroy()
            return GLib.SOURCE_REMOVE
        GLib.timeout_add(_FLASH_TICK_MS, fade)
        return GLib.SOURCE_REMOVE

    GLib.timeout_add(_FLASH_HOLD_MS, start_fade)


_xdisplay = None


def _get_xdisplay():
    global _xdisplay
    if _xdisplay is None:
        try:
            _xdisplay = xdisplay.Display()
        except Exception:
            _xdisplay = None
    return _xdisplay


def _root_pixbuf():
    display = Gdk.Display.get_default()
    if display is None:
        return None
    screen = display.get_default_screen()
    root = screen.get_root_window()
    w, h = root.get_width(), root.get_height()
    return Gdk.pixbuf_get_from_window(root, 0, 0, w, h)


def _find_wm_xid(d, start_xid):
    """Walk up the X11 tree to the toplevel that is a direct child of root.
    For SSD apps the WM reparents the client into a frame window, so the
    returned xid differs from start_xid. For CSD apps (no reparenting) the
    returned xid equals start_xid."""
    try:
        win = d.create_resource_object('window', start_xid)
        for _ in range(32):
            tree = win.query_tree()
            if tree.parent is None:
                return None
            if tree.parent.id == tree.root.id:
                return win.id
            win = tree.parent
    except Exception:
        return None
    return None


def _foreign_window(xid):
    try:
        return GdkX11.X11Window.foreign_new_for_display(
            Gdk.Display.get_default(), xid)
    except Exception:
        return None


def _x11_geometry(d, xid):
    try:
        xwin = d.create_resource_object('window', xid)
        geom = xwin.get_geometry()
        return (geom.x, geom.y, geom.width, geom.height)
    except Exception:
        return None


def _gtk_frame_extents(gdk_window):
    d = _get_xdisplay()
    if d is None:
        return None
    try:
        xid = gdk_window.get_xid()
        xwin = d.create_resource_object('window', xid)
        prop = xwin.get_full_property(d.intern_atom('_GTK_FRAME_EXTENTS'),
                                      X.AnyPropertyType)
    except Exception:
        return None
    if prop is None or prop.format != 32 or len(prop.value) < 4:
        return None
    return tuple(prop.value[:4])




def _active_window_rect():
    display = Gdk.Display.get_default()
    if display is None:
        return None
    screen = display.get_default_screen()
    window = screen.get_active_window()
    if window is None:
        return None
    frame = window.get_frame_extents()
    x, y, w, h = frame.x, frame.y, frame.width, frame.height
    csd = _gtk_frame_extents(window)
    if csd is not None:
        left, right, top, bottom = csd
        x += left
        y += top
        w -= left + right
        h -= top + bottom
    return (x, y, w, h)


def _clamp_rect(root, x, y, w, h):
    x = max(0, x)
    y = max(0, y)
    w = min(w, root.get_width() - x)
    h = min(h, root.get_height() - y)
    if w <= 0 or h <= 0:
        return None
    return (x, y, w, h)


class X11Backend(Backend):
    def screenshot(self, include_pointer, flash):
        pixbuf = _root_pixbuf()
        if flash and pixbuf is not None:
            _fire_flash(0, 0, pixbuf.get_width(), pixbuf.get_height())
        return pixbuf

    def screenshot_window(self, include_pointer, include_frame, flash):
        display = Gdk.Display.get_default()
        if display is None:
            return None
        window = display.get_default_screen().get_active_window()
        if window is None:
            return None
        frame = window.get_frame_extents()
        csd = _gtk_frame_extents(window)

        # Figure out whether the WM reparented us (SSD) or not (CSD). For
        # SSD apps we need to capture from the WM frame window so the
        # server-drawn titlebar/borders are included; for CSD we capture
        # from the active window itself so the client's own decorations
        # (and transparent rounded-corner pixels) come through.
        client_xid = None
        try:
            client_xid = window.get_xid()
        except Exception:
            pass
        d = _get_xdisplay()
        wm_xid = _find_wm_xid(d, client_xid) if (d is not None and client_xid is not None) else None
        is_ssd = wm_xid is not None and wm_xid != client_xid

        capture_window = window
        if is_ssd:
            wm_window = _foreign_window(wm_xid)
            if wm_window is not None:
                capture_window = wm_window

        # frame_extents has different semantics for CSD vs SSD:
        #   CSD: returns the X11 toplevel rect, which INCLUDES the client-
        #        drawn shadow padding (we strip it later via _GTK_FRAME_EXTENTS).
        #   SSD: returns the visible WM frame rect, EXCLUDING the WM's own
        #        shadow padding around the frame.
        # For SSD the X11 WM-frame window is actually larger than frame_extents
        # because Muffin extends it out for shadow rendering. We have to query
        # the X11 frame's true position and shift our capture origin by
        # (frame.xy - wm_geom.xy) so we don't grab the shadow corner.
        offset_x, offset_y = 0, 0
        wm_geom = _x11_geometry(d, wm_xid) if (d is not None and wm_xid is not None) else None
        if wm_geom is not None:
            cand_x = frame.x - wm_geom[0]
            cand_y = frame.y - wm_geom[1]
            if 0 <= cand_x <= 256 and 0 <= cand_y <= 256:
                offset_x, offset_y = cand_x, cand_y

        # Under compositing, pixbuf_get_from_window reads from the window's
        # offscreen pixmap, preserving its actual alpha.
        pixbuf = Gdk.pixbuf_get_from_window(capture_window, offset_x, offset_y,
                                            frame.width, frame.height)
        if pixbuf is None:
            rect = _active_window_rect()
            root = _root_pixbuf()
            if rect is None or root is None:
                return None
            clamped = _clamp_rect(root, *rect)
            if clamped is None:
                return None
            x, y, w, h = clamped
            return root.new_subpixbuf(x, y, w, h).copy()

        # CSD shadow trim only applies to the CSD path. SSD captures from
        # the WM frame, which doesn't have _GTK_FRAME_EXTENTS shadow padding.
        if not is_ssd and csd is not None:
            left, right, top, bottom = csd
            pw = pixbuf.get_width()
            ph = pixbuf.get_height()
            pixbuf = pixbuf.new_subpixbuf(
                left, top, pw - left - right, ph - top - bottom).copy()

        if flash:
            _fire_flash(frame.x, frame.y, frame.width, frame.height)

        return pixbuf

    def screenshot_area(self, x, y, w, h, flash):
        root = _root_pixbuf()
        if root is None:
            return None
        clamped = _clamp_rect(root, x, y, w, h)
        if clamped is None:
            return None
        cx, cy, cw, ch = clamped
        pixbuf = root.new_subpixbuf(cx, cy, cw, ch).copy()
        if flash:
            _fire_flash(cx, cy, cw, ch)
        return pixbuf

    def flash_area(self, x, y, w, h):
        _fire_flash(x, y, w, h)

    def select_area(self):
        return _AreaSelector().run()


class _AreaSelector:
    def __init__(self):
        self.result = None
        self._start = None
        self._current = None
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
        left = top = 2**31 - 1
        right = bottom = -(2**31)
        for i in range(display.get_n_monitors()):
            g = display.get_monitor(i).get_geometry()
            left = min(left, g.x)
            top = min(top, g.y)
            right = max(right, g.x + g.width)
            bottom = max(bottom, g.y + g.height)
        self.window.move(left, top)
        self.window.resize(right - left, bottom - top)
        self._origin = (left, top)

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

    def run(self):
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
