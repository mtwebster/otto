def crop(pixbuf, x, y, w, h):
    x = max(0, min(x, pixbuf.get_width()))
    y = max(0, min(y, pixbuf.get_height()))
    w = max(1, min(w, pixbuf.get_width() - x))
    h = max(1, min(h, pixbuf.get_height() - y))
    return pixbuf.new_subpixbuf(x, y, w, h).copy()
