import os

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from .. import _config
from .. import util
from . import editor


UI_FILE = os.path.join(_config.PKGDATADIR, 'ui', 'preview-window.ui')


class _CropState:
    __slots__ = ('start', 'current', 'committed')

    def __init__(self):
        self.start: tuple[float, float] | None = None
        self.current: tuple[float, float] | None = None
        self.committed: tuple[float, float, float, float] | None = None


class PreviewWindow:
    def __init__(self, app, pixbuf: GdkPixbuf.Pixbuf, suggested_path: str):
        self.app = app
        self._pixbuf = pixbuf
        self._undo: GdkPixbuf.Pixbuf | None = None
        self._suggested_path = suggested_path
        self._crop_active = False
        self._crop = _CropState()
        self._render_rect = (0, 0, 0, 0, 1.0)  # x, y, w, h, scale (preview-coords)

        self.builder = Gtk.Builder.new_from_file(UI_FILE)
        self.window: Gtk.ApplicationWindow = self.builder.get_object('window')
        self.window.set_application(app)

        self.preview_area: Gtk.DrawingArea = self.builder.get_object('preview_area')
        self.crop_actions: Gtk.Box = self.builder.get_object('crop_actions')
        self.undo_button: Gtk.Button = self.builder.get_object('undo_button')

        self.preview_area.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.preview_area.connect('draw', self._on_draw)
        self.preview_area.connect('button-press-event', self._on_press)
        self.preview_area.connect('motion-notify-event', self._on_motion)
        self.preview_area.connect('button-release-event', self._on_release)

        self.builder.get_object('cancel_button').connect('clicked', self._on_cancel)
        self.builder.get_object('save_button').connect('clicked', self._on_save)
        self.builder.get_object('copy_button').connect('clicked', self._on_copy)
        self.builder.get_object('crop_button').connect('clicked', self._on_crop)
        self.builder.get_object('rotate_cw_button').connect('clicked',
            lambda _b: self._apply(editor.rotate_cw))
        self.builder.get_object('rotate_ccw_button').connect('clicked',
            lambda _b: self._apply(editor.rotate_ccw))
        self.builder.get_object('flip_h_button').connect('clicked',
            lambda _b: self._apply(editor.flip_horizontal))
        self.builder.get_object('flip_v_button').connect('clicked',
            lambda _b: self._apply(editor.flip_vertical))
        self.undo_button.connect('clicked', self._on_undo)
        self.builder.get_object('crop_apply_button').connect('clicked', self._on_crop_apply)
        self.builder.get_object('crop_cancel_button').connect('clicked', self._on_crop_cancel)

        accel = Gtk.AccelGroup()
        accel.connect(Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK,
                      Gtk.AccelFlags.VISIBLE, lambda *_: self._on_undo(None) or True)
        self.window.add_accel_group(accel)

    def show_all(self):
        self.window.show_all()
        self.crop_actions.hide()

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------

    def _on_draw(self, widget: Gtk.DrawingArea, cr) -> bool:
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
        rx, ry, rw, rh, _ = self._render_rect
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

    def _current_selection_widget_coords(self) -> tuple[float, float, float, float] | None:
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

    # ------------------------------------------------------------------
    # operations
    # ------------------------------------------------------------------

    def _apply(self, op):
        self._undo = self._pixbuf
        self._pixbuf = op(self._pixbuf)
        self.undo_button.set_sensitive(True)
        self.preview_area.queue_draw()

    def _on_undo(self, _button):
        if self._undo is None:
            return
        self._pixbuf = self._undo
        self._undo = None
        self.undo_button.set_sensitive(False)
        self.preview_area.queue_draw()

    # ------------------------------------------------------------------
    # save / copy / cancel
    # ------------------------------------------------------------------

    def _on_cancel(self, _button):
        self.window.destroy()
        self.app.quit()

    def _on_copy(self, _button):
        util.copy_pixbuf_to_clipboard(self._pixbuf)
        GLib.idle_add(self._after_copy)

    def _after_copy(self):
        self.window.destroy()
        self.app.quit()
        return GLib.SOURCE_REMOVE

    def _on_save(self, _button):
        dialog = Gtk.FileChooserNative.new(
            'Save Screenshot',
            self.window,
            Gtk.FileChooserAction.SAVE,
            'Save',
            'Cancel',
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
                text='Failed to save screenshot',
                secondary_text=str(exc),
            )
            err.run()
            err.destroy()
            return

        self.app.settings.last_save_directory = os.path.dirname(path)
        self.window.destroy()
        self.app.quit()
