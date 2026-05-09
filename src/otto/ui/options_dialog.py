import os

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from .. import _config


UI_FILE = os.path.join(_config.PKGDATADIR, 'ui', 'options-dialog.ui')


class OptionsDialog:
    def __init__(self, app):
        self.app = app
        self.builder = Gtk.Builder.new_from_file(UI_FILE)

        self.window: Gtk.ApplicationWindow = self.builder.get_object('window')
        self.window.set_application(app)

        self.mode_screen = self.builder.get_object('mode_screen')
        self.mode_window = self.builder.get_object('mode_window')
        self.mode_area = self.builder.get_object('mode_area')
        self.pointer_switch = self.builder.get_object('pointer_switch')
        self.delay_spin = self.builder.get_object('delay_spin')
        self.take_button = self.builder.get_object('take_button')

        s = app.settings
        self.delay_spin.set_value(s.delay)
        self.pointer_switch.set_active(s.include_pointer)
        if app.args.window:
            self.mode_window.set_active(True)
        elif app.args.area:
            self.mode_area.set_active(True)

        for radio in (self.mode_screen, self.mode_window, self.mode_area):
            radio.connect('toggled', self._on_mode_toggled)
        self.take_button.connect('clicked', self._on_take_clicked)
        self._on_mode_toggled(None)

    def _on_mode_toggled(self, _radio):
        # area mode has no meaningful "show pointer" semantics
        self.pointer_switch.set_sensitive(not self.mode_area.get_active())

    def _resolved_mode(self) -> str:
        if self.mode_window.get_active():
            return 'window'
        if self.mode_area.get_active():
            return 'area'
        return 'screen'

    def _on_take_clicked(self, _button):
        mode = self._resolved_mode()
        include_pointer = self.pointer_switch.get_active() and mode != 'area'
        delay = int(self.delay_spin.get_value())

        s = self.app.settings
        s.delay = delay
        s.include_pointer = self.pointer_switch.get_active()

        self.window.hide()

        def done(pixbuf):
            self.window.destroy()
            if pixbuf is None:
                self.app.quit()
                return
            self.app._show_preview(pixbuf)

        self.app.capture(mode, include_pointer, delay, done)

    def show_all(self):
        self.window.show_all()
