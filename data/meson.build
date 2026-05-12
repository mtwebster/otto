i18n.merge_file(
    input: 'org.x.Otto.desktop.in',
    output: 'org.x.Otto.desktop',
    type: 'desktop',
    po_dir: podir,
    install: true,
    install_dir: datadir / 'applications',
)

i18n.merge_file(
    input: 'org.x.Otto.metainfo.xml.in',
    output: 'org.x.Otto.metainfo.xml',
    type: 'xml',
    po_dir: podir,
    install: true,
    install_dir: datadir / 'metainfo',
)

install_data('org.x.Otto.gschema.xml',
    install_dir: datadir / 'glib-2.0' / 'schemas',
)

install_data(
    [
        'icons/otto-display-symbolic.svg',
        'icons/otto-window-symbolic.svg',
        'icons/otto-selection-symbolic.svg',
    ],
    install_dir: datadir / 'icons' / 'hicolor' / 'symbolic' / 'apps',
)
