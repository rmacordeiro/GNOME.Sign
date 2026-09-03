project(
  'gnome-sign',
  version: '1.0.0',
  meson_version: '>= 0.61.0'
)

app_id = 'io.github.ppgllrd.GNOME-Sign'
pkgdatadir = join_paths(get_option('datadir'), app_id)

launcher = configure_file(
  input: 'gnomesign-launcher.sh.in',
  output: 'gnomesign',
  configuration: {
    'pkgdatadir': join_paths(get_option('prefix'), pkgdatadir),
  }
)

install_data(
  launcher,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

install_subdir(
  'src',
  install_dir: pkgdatadir,
  strip_directory: true
)

install_data(
  'io.github.ppgllrd.GNOME-Sign.desktop',
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
