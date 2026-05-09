import argparse
import gettext
import os
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, GLib, Gtk

from . import _config
from . import backend
from . import filename as filename_module
from . import util
from .config import Settings


_ = gettext.gettext


class OttoApplication(Gtk.Application):
    def __init__(self, args: argparse.Namespace):
        super().__init__(
            application_id='org.x.Otto',
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.args = args
        self.settings = Settings()
        self.backend = backend.get(force_fallback=os.environ.get('OTTO_FORCE_FALLBACK') == '1')
        self._exit_code = 0

    def do_activate(self):
        args = self.args
        if args.clipboard:
            self._run_clipboard()
        elif args.file:
            self._run_save_to_file(args.file)
        elif args.interactive:
            self._run_interactive()
        else:
            self._run_quick_capture()

    def _resolve_mode(self) -> str:
        if self.args.window:
            return 'window'
        if self.args.area:
            return 'area'
        return 'screen'

    def _capture_now(self, mode: str, include_pointer: bool, flash: bool):
        try:
            if mode == 'window':
                return self.backend.screenshot_window(include_pointer, True, flash)
            if mode == 'area':
                rect = self.backend.select_area()
                if rect is None:
                    return None
                x, y, w, h = rect
                return self.backend.screenshot_area(x, y, w, h, flash)
            return self.backend.screenshot(include_pointer, flash)
        except Exception as exc:
            print(f'otto: capture failed: {exc}', file=sys.stderr)
            return None

    def capture(self, mode: str, include_pointer: bool, delay: int, on_done):
        flash = True

        def do_capture():
            pixbuf = self._capture_now(mode, include_pointer, flash)
            on_done(pixbuf)
            return GLib.SOURCE_REMOVE

        if delay > 0:
            GLib.timeout_add_seconds(delay, do_capture)
        else:
            GLib.idle_add(do_capture)

    def _run_quick_capture(self):
        self.hold()
        mode = self._resolve_mode()
        include_pointer = self.args.include_pointer or self.settings.include_pointer
        delay = self.args.delay if self.args.delay is not None else 0

        def done(pixbuf):
            self.release()
            if pixbuf is None:
                self._exit_code = 1
                self.quit()
                return
            self._show_preview(pixbuf)

        self.capture(mode, include_pointer, delay, done)

    def _run_interactive(self):
        from .ui.options_dialog import OptionsDialog
        dialog = OptionsDialog(self)
        dialog.show_all()

    def _run_clipboard(self):
        self.hold()
        mode = self._resolve_mode()
        include_pointer = self.args.include_pointer or self.settings.include_pointer
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

    def _run_save_to_file(self, path: str):
        self.hold()
        mode = self._resolve_mode()
        include_pointer = self.args.include_pointer or self.settings.include_pointer
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

    def _show_preview(self, pixbuf):
        from .ui.preview_window import PreviewWindow
        suggested = filename_module.build_filename(
            preferred_dir=self.settings.last_save_directory or self.settings.auto_save_directory,
            file_type=self.settings.default_file_type or 'png',
        )
        win = PreviewWindow(self, pixbuf, suggested_path=suggested)
        win.show_all()

    @property
    def exit_code(self) -> int:
        return self._exit_code


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='otto',
        description=_('Take screenshots of your screen, windows, or selected areas'),
        add_help=True,
    )
    parser.add_argument('-c', '--clipboard', action='store_true',
                        help=_('Send the grab directly to the clipboard'))
    parser.add_argument('-w', '--window', action='store_true',
                        help=_('Grab the active window instead of the entire screen'))
    parser.add_argument('-a', '--area', action='store_true',
                        help=_('Grab a selected area of the screen'))
    parser.add_argument('-p', '--include-pointer', action='store_true',
                        help=_('Include the pointer in the screenshot'))
    parser.add_argument('-d', '--delay', type=int, default=None, metavar='SECONDS',
                        help=_('Take the screenshot after a delay'))
    parser.add_argument('-i', '--interactive', action='store_true',
                        help=_('Interactively set options before taking the screenshot'))
    parser.add_argument('-f', '--file', metavar='PATH',
                        help=_('Save the screenshot directly to PATH'))
    parser.add_argument('--version', action='store_true',
                        help=_('Print version and exit'))
    parser.add_argument('-b', '--include-border', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('-B', '--remove-border', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('-e', '--border-effect', metavar='EFFECT',
                        help=argparse.SUPPRESS)
    return parser


def _warn_deprecated(args: argparse.Namespace) -> None:
    if args.include_border or args.remove_border:
        print('otto: --include-border / --remove-border are deprecated and ignored',
              file=sys.stderr)
    if args.border_effect:
        print('otto: --border-effect is deprecated and ignored', file=sys.stderr)


def main() -> int:
    gettext.bindtextdomain(_config.GETTEXT_PACKAGE, _config.LOCALEDIR)
    gettext.textdomain(_config.GETTEXT_PACKAGE)

    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.version:
        print(f'otto {_config.VERSION}')
        return 0

    if args.window and args.area:
        parser.error(_('cannot combine --window and --area'))

    _warn_deprecated(args)

    app = OttoApplication(args)
    app.run([])
    return app.exit_code
