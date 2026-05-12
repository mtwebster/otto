import os
import tempfile

from gi.repository import GdkPixbuf, Gio, GLib

from backend import Backend


BUS_NAME = 'org.gnome.Shell.Screenshot'
OBJECT_PATH = '/org/gnome/Shell/Screenshot'
INTERFACE = 'org.gnome.Shell.Screenshot'


def service_available():
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        result = bus.call_sync(
            'org.freedesktop.DBus',
            '/org/freedesktop/DBus',
            'org.freedesktop.DBus',
            'NameHasOwner',
            GLib.Variant('(s)', (BUS_NAME,)),
            GLib.VariantType('(b)'),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
        return result.unpack()[0]
    except GLib.Error:
        return False


class CinnamonBackend(Backend):
    def __init__(self):
        self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def _tempfile(self):
        cache_dir = os.path.join(GLib.get_user_cache_dir(), 'otto')
        os.makedirs(cache_dir, mode=0o700, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix='scr-', suffix='.png', dir=cache_dir)
        os.close(fd)
        os.unlink(path)
        return path

    def _call(self, method, params):
        try:
            result = self._bus.call_sync(
                BUS_NAME, OBJECT_PATH, INTERFACE, method,
                params,
                GLib.VariantType('(bs)'),
                Gio.DBusCallFlags.NONE,
                -1, None,
            )
        except GLib.Error as exc:
            print(f'otto: DBus {method} failed: {exc.message}')
            return None
        return result.unpack()

    def _load_and_unlink(self, path):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
        except GLib.Error:
            pixbuf = None
        try:
            os.unlink(path)
        except OSError:
            pass
        return pixbuf

    def screenshot(self, include_pointer, flash):
        path = self._tempfile()
        result = self._call('Screenshot',
                            GLib.Variant('(bbs)', (include_pointer, flash, path)))
        if not result or not result[0]:
            return None
        return self._load_and_unlink(result[1] or path)

    def screenshot_window(self, include_pointer, include_frame, flash):
        path = self._tempfile()
        result = self._call('ScreenshotWindow',
                            GLib.Variant('(bbbs)', (include_frame, include_pointer, flash, path)))
        if not result or not result[0]:
            return None
        return self._load_and_unlink(result[1] or path)

    def screenshot_area(self, x, y, w, h, flash):
        path = self._tempfile()
        result = self._call('ScreenshotArea',
                            GLib.Variant('(iiiibs)', (x, y, w, h, flash, path)))
        if not result or not result[0]:
            return None
        return self._load_and_unlink(result[1] or path)

    def flash_area(self, x, y, w, h):
        try:
            self._bus.call_sync(
                BUS_NAME, OBJECT_PATH, INTERFACE, 'FlashArea',
                GLib.Variant('(iiii)', (x, y, w, h)),
                None,
                Gio.DBusCallFlags.NONE,
                -1, None,
            )
        except GLib.Error:
            pass

    def select_area(self):
        try:
            result = self._bus.call_sync(
                BUS_NAME, OBJECT_PATH, INTERFACE, 'SelectArea',
                None,
                GLib.VariantType('(iiii)'),
                Gio.DBusCallFlags.NONE,
                -1, None,
            )
        except GLib.Error:
            return None
        return tuple(result.unpack())
