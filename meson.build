project(
  'gnome-sign',
  version: '1.0.1',
  meson_version: '>= 0.61.0'
)

app_id = 'io.github.ppgllrd.GNOME-Sign'
pkgdatadir = join_paths(get_option('datadir'), app_id)

launcher_conf = configuration_data()
launcher_conf.set('pkgdatadir', join_paths(get_option('prefix'), pkgdatadir))

launcher = configure_file(
  input: 'gnomesign-launcher.sh.in',
  output: 'gnomesign',
  configuration: launcher_conf
)

cli_wrapper = configure_file(
  input: 'gnome-sign-wrapper.sh.in',
  output: 'gnome-sign',
  copy: true
)

desktop_alias = configure_file(
  input: 'gnome-sign.desktop',
  output: 'gnome-sign.desktop',
  copy: true
)

root_sources = files(
  'src/certificate_manager.py',
  'src/config_manager.py',
  'src/i18n.py',
  'src/main.py',
  'src/runtime.py',
  'src/stamp_creator.py'
)

ui_sources = files(
  'src/ui/app_window.py',
  'src/ui/dialogs.py',
  'src/ui/preferences_window.py',
  'src/ui/stamp_editor_dialog.py'
)

ui_component_sources = files(
  'src/ui/components/sidebar.py',
  'src/ui/components/welcome.py'
)

install_data(
  launcher,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

install_data(
  cli_wrapper,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

install_data(root_sources, install_dir: pkgdatadir)
install_data(ui_sources, install_dir: join_paths(pkgdatadir, 'ui'))
install_data(ui_component_sources, install_dir: join_paths(pkgdatadir, 'ui', 'components'))

install_data(
  'io.github.ppgllrd.GNOME-Sign.desktop',
  install_dir: join_paths(get_option('datadir'), 'applications')
)

install_data(
  desktop_alias,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

install_data(
  'io.github.ppgllrd.GNOME-Sign.metainfo.xml',
  install_dir: join_paths(get_option('datadir'), 'metainfo')
)

install_data(
  'svg/io.github.ppgllrd.GNOME-Sign.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps')
)
