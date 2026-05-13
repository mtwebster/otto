config_py = configure_file(
    input: '_config.py.in',
    output: '_config.py',
    configuration: conf,
)

install_data(
    [
        'application.py',
        'backend.py',
        'prefs.py',
        'util.py',
        config_py,
    ],
    install_dir: pkgdatadir,
)

subdir('backends')
subdir('ui')

gnome.compile_resources(
    'otto',
    'otto.gresource.xml',
    source_dir: '.',
    gresource_bundle: true,
    install: true,
    install_dir: pkgdatadir,
)
