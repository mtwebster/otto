# otto

A screenshot tool for the Cinnamon desktop on Linux Mint. Replaces
`gnome-screenshot` and keeps its command-line interface compatible.

## Capture modes

- whole screen (default)
- active window (`-w`)
- selected area (`-a`)

## Output

- preview window with a small editor (crop, rotate, flip) — default and
  `--interactive` modes
- direct save to a path with `--file PATH`
- direct copy to clipboard with `--clipboard`

## Backends

- **DBus** (primary): talks to `org.gnome.Shell.Screenshot`, which Cinnamon
  exposes on the session bus
- **X11** (fallback): used when the DBus service is unavailable, or when
  `OTTO_FORCE_FALLBACK=1` is set in the environment

## Build

```
meson setup obj-x86_64-linux-gnu --prefix=/usr
ninja -C obj-x86_64-linux-gnu
sudo ninja -C obj-x86_64-linux-gnu install
```

Or build a `.deb`:

```
dpkg-buildpackage -us -uc -b
```

## Command-line options

| flag | meaning |
|---|---|
| `-c`, `--clipboard` | send the grab directly to the clipboard |
| `-w`, `--window` | grab the active window |
| `-a`, `--area` | grab a selected area |
| `-p`, `--include-pointer` | include the pointer |
| `-d N`, `--delay N` | wait N seconds before capturing |
| `-i`, `--interactive` | show the options dialog first |
| `-f PATH`, `--file PATH` | save directly to PATH |
| `--version` | print version |

`gnome-screenshot` is provided as an alias.
