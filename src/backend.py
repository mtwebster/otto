import sys


class Backend:
    def screenshot(self, include_pointer, flash):
        pass

    def screenshot_window(self, include_pointer, include_frame, flash):
        pass

    def screenshot_area(self, x, y, w, h, flash):
        pass

    def flash_area(self, x, y, w, h):
        pass

    def select_area(self):
        pass


def get(force_fallback=False):
    if not force_fallback:
        from backends.cinnamon import CinnamonBackend, service_available
        if service_available():
            return CinnamonBackend()
        print('otto: Cinnamon screenshot service unavailable, using X11 fallback',
              file=sys.stderr)
    from backends.x11 import X11Backend
    return X11Backend()
