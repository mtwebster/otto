import io
import os

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk


_PIXBUF_FORMAT_FOR_EXT = {
    '.png':  ('png',  []),
    '.jpg':  ('jpeg', [('quality', '95')]),
    '.jpeg': ('jpeg', [('quality', '95')]),
    '.bmp':  ('bmp',  []),
    '.tif':  ('tiff', []),
    '.tiff': ('tiff', []),
}


def format_for_path(path: str) -> tuple[str, list[tuple[str, str]]]:
    ext = os.path.splitext(path)[1].lower()
    return _PIXBUF_FORMAT_FOR_EXT.get(ext, _PIXBUF_FORMAT_FOR_EXT['.png'])


def save_pixbuf(pixbuf: GdkPixbuf.Pixbuf, path: str) -> None:
    fmt, options = format_for_path(path)
    keys = [k for k, _ in options]
    values = [v for _, v in options]
    pixbuf.savev(path, fmt, keys, values)


def copy_pixbuf_to_clipboard(pixbuf: GdkPixbuf.Pixbuf) -> None:
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_image(pixbuf)
    clipboard.store()


def pixbuf_to_pil(pixbuf: GdkPixbuf.Pixbuf):
    from PIL import Image
    success, buf = pixbuf.save_to_bufferv('png', [], [])
    if not success:
        raise RuntimeError('failed to serialize pixbuf')
    return Image.open(io.BytesIO(buf))


def pil_to_pixbuf(image) -> GdkPixbuf.Pixbuf:
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    loader = GdkPixbuf.PixbufLoader.new_with_type('png')
    loader.write(buf.getvalue())
    loader.close()
    return loader.get_pixbuf()


def user_pictures_dir() -> str:
    pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
    return pictures or GLib.get_home_dir()
