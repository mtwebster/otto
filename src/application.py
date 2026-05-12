import argparse
import gettext
import os
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, GLib, Gtk

import _config
import backend
import prefs
import util

gettext.install(_config.GETTEXT_PACKAGE, _config.LOCALEDIR)


class OttoApplication(Gtk.Application):
    def __init__(self, args):
        super().__init__(
            application_id='org.x.Otto',
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.args = args
        self.backend = backend.get(force_fallback=os.environ.get('OTTO_FORCE_FALLBACK') == '1')
        self._exit_code = 0

    def do_activate(self):
        args = self.args
        if args.clipboard:
            self._run_clipboard()
        elif args.file:
            self._run_save_to_file(args.file)
        else:
            self._run_window()

    def _resolve_mode(self):
        if self.args.window:
            return 'window'
        if self.args.area:
            return 'area'
        return 'screen'

    def capture(self, mode, include_pointer, delay, on_done, area_rect=None):
        flash = True

        # Monitor mode passes its rect in advance; interactive area mode
        # runs the selector now to get one. Both end up at the same
        # area_rect-driven capture path below, but they take different
        # routes because the DBus ScreenshotArea has no cursor overlay.
        monitor_crop = mode == 'monitor' and area_rect is not None

        if mode == 'area' and area_rect is None:
            area_rect = self.backend.select_area()
            if area_rect is None:
                on_done(None)
                return

        def do_capture():
            try:
                if monitor_crop:
                    full = self.backend.screenshot(include_pointer, False)
                    if full and area_rect is not None:
                        x, y, w, h = area_rect
                        pixbuf = full.new_subpixbuf(x, y, w, h).copy()
                        if flash:
                            self.backend.flash_area(x, y, w, h)
                    else:
                        pixbuf = None
                elif area_rect is not None:
                    x, y, w, h = area_rect
                    pixbuf = self.backend.screenshot_area(x, y, w, h, flash)
                elif mode == 'window':
                    pixbuf = self.backend.screenshot_window(include_pointer, True, flash)
                else:
                    pixbuf = self.backend.screenshot(include_pointer, flash)
            except Exception as exc:
                print(f'otto: capture failed: {exc}', file=sys.stderr)
                pixbuf = None
            on_done(pixbuf)
            return GLib.SOURCE_REMOVE

        if delay > 0:
            GLib.timeout_add_seconds(delay, do_capture)
        else:
            GLib.idle_add(do_capture)

    def _run_window(self):
        from ui.main_window import MainWindow
        win = MainWindow(self)
        win.run()

    def _run_clipboard(self):
        self.hold()
        mode = self._resolve_mode()
        include_pointer = self.args.include_pointer or prefs.get_include_pointer()
        delay = self.args.delay if self.args.delay is not None else 0

        def done(pixbuf):
            if pixbuf is not None:
                util.copy_pixbuf_to_clipboard(pixbuf)
                GLib.idle_add(self._finish_clipboard)
            else:
                self._exit_code = 1
                self.release()
                self.quit()

        self.capture(mode, include_pointer, delay, done)

    def _finish_clipboard(self):
        self.release()
        self.quit()
        return GLib.SOURCE_REMOVE

    def _run_save_to_file(self, path):
        self.hold()
        mode = self._resolve_mode()
        include_pointer = self.args.include_pointer or prefs.get_include_pointer()
        delay = self.args.delay if self.args.delay is not None else 0

        def done(pixbuf):
            if pixbuf is not None:
                try:
                    util.save_pixbuf(pixbuf, path)
                except Exception as exc:
                    print(f'otto: save failed: {exc}', file=sys.stderr)
                    self._exit_code = 1
            else:
                self._exit_code = 1
            self.release()
            self.quit()

        self.capture(mode, include_pointer, delay, done)

    @property
    def exit_code(self):
        return self._exit_code


def _build_arg_parser():
    parser = argparse.ArgumentParser(
        prog='otto',
        description='Take screenshots of your screen, windows, or selected areas',
        add_help=True,
    )
    parser.add_argument('-c', '--clipboard', action='store_true',
                        help='Send the grab directly to the clipboard')
    parser.add_argument('-w', '--window', action='store_true',
                        help='Grab the active window instead of the entire screen')
    parser.add_argument('-a', '--area', action='store_true',
                        help='Grab a selected area of the screen')
    parser.add_argument('-p', '--include-pointer', action='store_true',
                        help='Include the pointer in the screenshot')
    parser.add_argument('-d', '--delay', type=int, default=None, metavar='SECONDS',
                        help='Take the screenshot after a delay')
    parser.add_argument('-i', '--interactive', action='store_true',
                        help='Interactively set options before taking the screenshot')
    parser.add_argument('-f', '--file', metavar='PATH',
                        help='Save the screenshot directly to PATH')
    parser.add_argument('--version', action='store_true',
                        help='Print version and exit')
    return parser

def main():
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.version:
        print(f'otto {_config.VERSION}')
        return 0

    if args.window and args.area:
        parser.error('cannot combine --window and --area')

    app = OttoApplication(args)
    app.run([])
    return app.exit_code
