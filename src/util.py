import datetime
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


def format_for_path(path):
    ext = os.path.splitext(path)[1].lower()
    return _PIXBUF_FORMAT_FOR_EXT.get(ext, _PIXBUF_FORMAT_FOR_EXT['.png'])


def save_pixbuf(pixbuf, path):
    fmt, options = format_for_path(path)
    keys = [k for k, _ in options]
    values = [v for _, v in options]
    pixbuf.savev(path, fmt, keys, values)


def copy_pixbuf_to_clipboard(pixbuf):
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_image(pixbuf)
    clipboard.store()


def pixbuf_to_pil(pixbuf):
    from PIL import Image
    success, buf = pixbuf.save_to_bufferv('png', [], [])
    if not success:
        raise RuntimeError('failed to serialize pixbuf')
    return Image.open(io.BytesIO(buf))


def pil_to_pixbuf(image):
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    loader = GdkPixbuf.PixbufLoader.new_with_type('png')
    loader.write(buf.getvalue())
    loader.close()
    return loader.get_pixbuf()


def user_pictures_dir():
    pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
    return pictures or GLib.get_home_dir()


def _candidate_dirs(preferred):
    dirs = []
    if preferred:
        dirs.append(os.path.expanduser(preferred))
    pictures = user_pictures_dir()
    if pictures and pictures not in dirs:
        dirs.append(pictures)
    home = os.path.expanduser('~')
    if home not in dirs:
        dirs.append(home)
    return [d for d in dirs if d]


def build_filename(preferred_dir=None, file_type='png', origin=None):
    if origin is None:
        origin = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')

    for base in _candidate_dirs(preferred_dir):
        if not os.path.isdir(base):
            continue
        for i in range(0, 1000):
            if i == 0:
                name = f'Screenshot from {origin}.{file_type}'
            else:
                name = f'Screenshot from {origin} - {i}.{file_type}'
            path = os.path.join(base, name)
            if not os.path.exists(path):
                return path
    return os.path.join(os.path.expanduser('~'),
                        f'Screenshot from {origin}.{file_type}')
