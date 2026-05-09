from gi.repository import GdkPixbuf


def rotate_cw(pixbuf: GdkPixbuf.Pixbuf) -> GdkPixbuf.Pixbuf:
    return pixbuf.rotate_simple(GdkPixbuf.PixbufRotation.CLOCKWISE)


def rotate_ccw(pixbuf: GdkPixbuf.Pixbuf) -> GdkPixbuf.Pixbuf:
    return pixbuf.rotate_simple(GdkPixbuf.PixbufRotation.COUNTERCLOCKWISE)


def flip_horizontal(pixbuf: GdkPixbuf.Pixbuf) -> GdkPixbuf.Pixbuf:
    return pixbuf.flip(True)


def flip_vertical(pixbuf: GdkPixbuf.Pixbuf) -> GdkPixbuf.Pixbuf:
    return pixbuf.flip(False)


def crop(pixbuf: GdkPixbuf.Pixbuf, x: int, y: int, w: int, h: int) -> GdkPixbuf.Pixbuf:
    x = max(0, min(x, pixbuf.get_width()))
    y = max(0, min(y, pixbuf.get_height()))
    w = max(1, min(w, pixbuf.get_width() - x))
    h = max(1, min(h, pixbuf.get_height() - y))
    return pixbuf.new_subpixbuf(x, y, w, h).copy()
