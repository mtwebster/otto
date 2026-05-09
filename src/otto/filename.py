import datetime
import os

from .util import user_pictures_dir


def _expand(path: str) -> str:
    if not path:
        return ''
    return os.path.expanduser(path)


def _candidate_dirs(preferred: str | None) -> list[str]:
    dirs: list[str] = []
    if preferred:
        dirs.append(_expand(preferred))
    pictures = user_pictures_dir()
    if pictures and pictures not in dirs:
        dirs.append(pictures)
    home = os.path.expanduser('~')
    if home not in dirs:
        dirs.append(home)
    return [d for d in dirs if d]


def build_filename(preferred_dir: str | None = None,
                   file_type: str = 'png',
                   origin: str | None = None) -> str:
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
