project('otto',
    version: '0.0.1',
    meson_version: '>=0.59.0',
    license: 'GPL-3.0-or-later',
)

pymod = import('python')
python3 = pymod.find_installation('python3')

i18n = import('i18n')
gnome = import('gnome')

gettext_package = meson.project_name()

prefix = get_option('prefix')
bindir = prefix / get_option('bindir')
datadir = prefix / get_option('datadir')
localedir = prefix / get_option('localedir')
pkgdatadir = datadir / meson.project_name()

podir = meson.project_source_root() / 'po'

conf = configuration_data()
conf.set('PYTHON', python3.full_path())
conf.set('PACKAGE', meson.project_name())
conf.set('VERSION', meson.project_version())
conf.set('LOCALEDIR', localedir)
conf.set('PKGDATADIR', pkgdatadir)
conf.set('GETTEXT_PACKAGE', gettext_package)

subdir('data')
subdir('po')
subdir('src')

configure_file(
    input: 'src/otto.in',
    output: 'otto',
    configuration: conf,
    install: true,
    install_dir: bindir,
    install_mode: 'rwxr-xr-x',
)

gnome.post_install(
    glib_compile_schemas: true,
    gtk_update_icon_cache: false,
    update_desktop_database: true,
)
