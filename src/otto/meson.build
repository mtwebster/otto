otto_install_dir = pkgdatadir / 'otto'

config_py = configure_file(
    input: '_config.py.in',
    output: '_config.py',
    configuration: conf,
)

install_data(
    [
        '__init__.py',
        'application.py',
        'config.py',
        'filename.py',
        'util.py',
        'backend.py',
        'backend_dbus.py',
        'backend_x11.py',
        'area_select.py',
        config_py,
    ],
    install_dir: otto_install_dir,
)

install_data(
    [
        'ui/__init__.py',
        'ui/options_dialog.py',
        'ui/preview_window.py',
        'ui/editor.py',
    ],
    install_dir: otto_install_dir / 'ui',
)
