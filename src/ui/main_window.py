import os

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

import _config
import util
from . import editor


UI_FILE = os.path.join(_config.PKGDATADIR, 'ui', 'main-window.ui')
ICON_DIR = os.path.join(_config.PKGDATADIR, 'icons')


def _set_image_icon(image, filename, size):
    scale = image.get_scale_factor()
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
        os.path.join(ICON_DIR, filename), size * scale, size * scale, True)
    surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, scale, None)
    image.set_from_surface(surface)


class _CropState:
    def __init__(self):
        self.start = None
        self.current = None


class MainWindow:
    def __init__(self, app):
        self.app = app
        self.builder = Gtk.Builder.new_from_file(UI_FILE)
        self.window = self.builder.get_object('window')
        self.window.set_application(app)

        self.mode_screen = self.builder.get_object('mode_screen')
        self.mode_monitor = self.builder.get_object('mode_monitor')
        self.mode_window = self.builder.get_object('mode_window')
        self.mode_area = self.builder.get_object('mode_area')
        self.pointer_switch = self.builder.get_object('pointer_switch')
        self.delay_spin = self.builder.get_object('delay_spin')
        self.take_button = self.builder.get_object('take_button')

        self.preview_stack = self.builder.get_object('preview_stack')
        self.preview_area = self.builder.get_object('preview_area')
        self.crop_actions = self.builder.get_object('crop_actions')

        self.crop_button = self.builder.get_object('crop_button')
        self.undo_button = self.builder.get_object('undo_button')
        self.copy_button = self.builder.get_object('copy_button')
        self.save_button = self.builder.get_object('save_button')

        self._pixbuf = None
        self._undo = None
        self._suggested_path = None
        self._crop_active = False
        self._crop = _CropState()
        self._render_rect = (0, 0, 0, 0, 1.0)

        self._init_options()
        self._init_preview()
        self._init_actions()
        self._update_action_sensitivity()

    def run(self):
        if self.app.args.interactive:
            self.window.show_all()
        else:
            self._capture(initial=True)

    # ------------------------------------------------------------------
    # init
    # ------------------------------------------------------------------

    def _init_options(self):
        for image_id, filename in (
            ('mode_screen_icon',  'otto-display-symbolic.svg'),
            ('mode_monitor_icon', 'otto-display-symbolic.svg'),
            ('mode_window_icon',  'otto-window-symbolic.svg'),
            ('mode_area_icon',    'otto-selection-symbolic.svg'),
        ):
            _set_image_icon(self.builder.get_object(image_id), filename, 32)

        self.mode_monitor.set_sensitive(Gdk.Display.get_default().get_n_monitors() > 1)

        s = self.app.settings
        args = self.app.args
        self.delay_spin.set_value(args.delay if args.delay is not None else s.delay)
        self.pointer_switch.set_active(args.include_pointer or s.include_pointer)
        if args.window:
            self.mode_window.set_active(True)
        elif args.area:
            self.mode_area.set_active(True)

        for radio in (self.mode_screen, self.mode_monitor, self.mode_window, self.mode_area):
            radio.connect('toggled', self._on_mode_toggled)
        self.take_button.connect('clicked', self._on_take_clicked)
        self._on_mode_toggled(None)

    def _init_preview(self):
        self.preview_area.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.preview_area.connect('draw', self._on_draw)
        self.preview_area.connect('button-press-event', self._on_press)
        self.preview_area.connect('motion-notify-event', self._on_motion)
        self.preview_area.connect('button-release-event', self._on_release)

        self.crop_button.connect('clicked', self._on_crop)
        self.undo_button.connect('clicked', self._on_undo)
        self.copy_button.connect('clicked', self._on_copy)
        self.builder.get_object('crop_apply_button').connect('clicked', self._on_crop_apply)
        self.builder.get_object('crop_cancel_button').connect('clicked', self._on_crop_cancel)

        accel = Gtk.AccelGroup()
        accel.connect(Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK,
                      Gtk.AccelFlags.VISIBLE,
                      lambda *_: self._on_undo(None) or True)
        self.window.add_accel_group(accel)

    def _init_actions(self):
        self.save_button.connect('clicked', self._on_save)
        self.builder.get_object('cancel_button').connect('clicked', self._on_cancel)

        about_action = Gio.SimpleAction.new('about', None)
        about_action.connect('activate', self._on_about)
        self.window.add_action(about_action)

        menu = Gio.Menu()
        menu.append(_('About Otto'), 'win.about')
        self.builder.get_object('menu_button').set_menu_model(menu)

    # ------------------------------------------------------------------
    # mode handling and capture
    # ------------------------------------------------------------------

    def _on_mode_toggled(self, _radio):
        is_area_capture = self.mode_area.get_active() or self.mode_monitor.get_active()
        self.pointer_switch.set_sensitive(not is_area_capture)

    def _resolved_mode(self):
        if self.mode_window.get_active():
            return 'window'
        if self.mode_area.get_active():
            return 'area'
        if self.mode_monitor.get_active():
            return 'monitor'
        return 'screen'

    def _current_monitor_rect(self):
        gdk_window = self.window.get_window()
        if gdk_window is None:
            return None
        monitor = Gdk.Display.get_default().get_monitor_at_window(gdk_window)
        if monitor is None:
            return None
        geom = monitor.get_geometry()
        return (geom.x, geom.y, geom.width, geom.height)

    def _on_take_clicked(self, _b):
        self._capture()

    def _capture(self, initial=False):
        self._crop_active = False
        self.crop_actions.hide()

        mode = self._resolved_mode()
        area_rect = None
        if mode == 'monitor':
            area_rect = self._current_monitor_rect()
            mode = 'area' if area_rect is not None else 'screen'

        include_pointer = self.pointer_switch.get_active() and mode != 'area'

        if initial:
            delay = self.app.args.delay if self.app.args.delay is not None else 0
        else:
            delay = int(self.delay_spin.get_value())
            s = self.app.settings
            s.delay = delay
            s.include_pointer = self.pointer_switch.get_active()

        if self.window.get_visible():
            self.window.hide()

        def done(pixbuf):
            self._set_preview(pixbuf)
            self.window.show_all()

        self.app.capture(mode, include_pointer, delay, done, area_rect=area_rect)

    def _set_preview(self, pixbuf):
        if pixbuf is None:
            self._update_action_sensitivity()
            return
        self._pixbuf = pixbuf
        self._undo = None
        s = self.app.settings
        self._suggested_path = util.build_filename(
            preferred_dir=s.last_save_directory or s.auto_save_directory,
            file_type=s.default_file_type or 'png',
        )
        self._update_action_sensitivity()
        self.preview_area.queue_draw()

    def _update_action_sensitivity(self):
        has_preview = self._pixbuf is not None
        self.preview_stack.set_visible_child_name('preview' if has_preview else 'placeholder')
        self.crop_button.set_sensitive(has_preview)
        self.copy_button.set_sensitive(has_preview)
        self.save_button.set_sensitive(has_preview)
        self.undo_button.set_sensitive(has_preview and self._undo is not None)

    # ------------------------------------------------------------------
    # preview rendering
    # ------------------------------------------------------------------

    def _on_draw(self, widget, cr):
        if self._pixbuf is None:
            return False
        alloc = widget.get_allocation()
        pw, ph = self._pixbuf.get_width(), self._pixbuf.get_height()
        if pw == 0 or ph == 0:
            return False

        scale = min(alloc.width / pw, alloc.height / ph, 1.0)
        rw, rh = pw * scale, ph * scale
        rx = (alloc.width - rw) / 2
        ry = (alloc.height - rh) / 2
        self._render_rect = (rx, ry, rw, rh, scale)

        cr.save()
        cr.translate(rx, ry)
        cr.scale(scale, scale)
        Gdk.cairo_set_source_pixbuf(cr, self._pixbuf, 0, 0)
        cr.paint()
        cr.restore()

        if self._crop_active:
            self._draw_crop_overlay(cr, alloc)

        return False

    def _draw_crop_overlay(self, cr, alloc):
        cr.save()
        cr.set_source_rgba(0, 0, 0, 0.5)
        cr.rectangle(0, 0, alloc.width, alloc.height)
        cr.fill()

        sel = self._current_selection_widget_coords()
        if sel is not None:
            sx, sy, sw, sh = sel
            cr.set_operator(0)  # CLEAR
            cr.rectangle(sx, sy, sw, sh)
            cr.fill()
            cr.set_operator(1)  # OVER
            cr.set_source_rgb(1.0, 1.0, 1.0)
            cr.set_line_width(1.0)
            cr.rectangle(sx + 0.5, sy + 0.5, sw, sh)
            cr.stroke()
        cr.restore()

    def _current_selection_widget_coords(self):
        if self._crop.start is None or self._crop.current is None:
            return None
        x1, y1 = self._crop.start
        x2, y2 = self._crop.current
        return (min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

    # ------------------------------------------------------------------
    # crop interaction
    # ------------------------------------------------------------------

    def _on_press(self, _w, event):
        if not self._crop_active or event.button != 1:
            return False
        self._crop.start = (event.x, event.y)
        self._crop.current = (event.x, event.y)
        self.preview_area.queue_draw()
        return True

    def _on_motion(self, _w, event):
        if not self._crop_active or self._crop.start is None:
            return False
        self._crop.current = (event.x, event.y)
        self.preview_area.queue_draw()
        return True

    def _on_release(self, _w, event):
        if not self._crop_active or event.button != 1:
            return False
        self._crop.current = (event.x, event.y)
        self.preview_area.queue_draw()
        return True

    def _on_crop(self, _button):
        if self._pixbuf is None:
            return
        self._crop_active = True
        self._crop.start = None
        self._crop.current = None
        self.crop_actions.show()
        self.preview_area.queue_draw()

    def _on_crop_cancel(self, _button):
        self._crop_active = False
        self.crop_actions.hide()
        self.preview_area.queue_draw()

    def _on_crop_apply(self, _button):
        sel = self._current_selection_widget_coords()
        self._crop_active = False
        self.crop_actions.hide()
        if sel is None:
            self.preview_area.queue_draw()
            return
        sx, sy, sw, sh = sel
        rx, ry, _rw, _rh, scale = self._render_rect
        if scale <= 0:
            return
        px = (sx - rx) / scale
        py = (sy - ry) / scale
        pw = sw / scale
        ph = sh / scale
        self._apply(lambda p: editor.crop(p, int(px), int(py), int(pw), int(ph)))

    def _apply(self, op):
        self._undo = self._pixbuf
        self._pixbuf = op(self._pixbuf)
        self._update_action_sensitivity()
        self.preview_area.queue_draw()

    def _on_undo(self, _button):
        if self._undo is None:
            return
        self._pixbuf = self._undo
        self._undo = None
        self._update_action_sensitivity()
        self.preview_area.queue_draw()

    # ------------------------------------------------------------------
    # action buttons
    # ------------------------------------------------------------------

    def _on_cancel(self, _b):
        self.window.destroy()
        self.app.quit()

    def _on_copy(self, _b):
        if self._pixbuf is None:
            return
        util.copy_pixbuf_to_clipboard(self._pixbuf)
        GLib.idle_add(self._after_copy)

    def _after_copy(self):
        self.window.destroy()
        self.app.quit()
        return GLib.SOURCE_REMOVE

    def _on_save(self, _b):
        if self._pixbuf is None:
            return
        dialog = Gtk.FileChooserNative.new(
            _('Save Screenshot'),
            self.window,
            Gtk.FileChooserAction.SAVE,
            _('Save'),
            _('Cancel'),
        )
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_current_name(os.path.basename(self._suggested_path))
        suggested_dir = os.path.dirname(self._suggested_path)
        if suggested_dir and os.path.isdir(suggested_dir):
            dialog.set_current_folder(suggested_dir)

        response = dialog.run()
        path = dialog.get_filename() if response == Gtk.ResponseType.ACCEPT else None
        dialog.destroy()
        if not path:
            return

        try:
            util.save_pixbuf(self._pixbuf, path)
        except Exception as exc:
            err = Gtk.MessageDialog(
                transient_for=self.window,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text=_('Failed to save screenshot'),
                secondary_text=str(exc),
            )
            err.run()
            err.destroy()
            return

        self.app.settings.last_save_directory = os.path.dirname(path)
        self.window.destroy()
        self.app.quit()

    def _on_about(self, _action, _param):
        about = Gtk.AboutDialog(transient_for=self.window, modal=True)
        about.set_program_name('Otto')
        about.set_version(_config.VERSION)
        about.set_comments(_('Screenshot tool'))
        about.set_copyright('2026 Linux Mint')
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_website('https://github.com/linuxmint/otto')
        about.set_website_label(_('linuxmint/otto on GitHub'))
        about.set_logo_icon_name('applets-screenshooter')
        about.run()
        about.destroy()
