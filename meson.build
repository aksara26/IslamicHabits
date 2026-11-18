project(
  'IslamicHabits',
  'c',
  version: '0.3.0',
  license: 'GPL-3.0-or-later',
  meson_version: '>= 0.63.0',
)

python = import('python')
python3 = python.find_installation('python3')
if not python3.found()
  error('Python 3 tidak ditemukan')
endif

prefix = get_option('prefix')
bindir = join_paths(prefix, get_option('bindir'))
datadir = join_paths(prefix, get_option('datadir'))
app_id = 'io.github.kurakura.IslamicHabits'

# Paket Python dipasang sebagai "islamichabits" agar import relatif di
# src/main.py bekerja baik dari sumber maupun setelah terpasang.
python3.install_sources(
  'src/__init__.py',
  'src/main.py',
  subdir: 'islamichabits',
)
python3.install_sources(
  'src/logic/__init__.py',
  'src/logic/constants.py',
  'src/logic/defaults.py',
  'src/logic/statistics.py',
  'src/logic/database.py',
  'src/logic/repository.py',
  'src/logic/transfer.py',
  subdir: 'islamichabits/logic',
)
python3.install_sources(
  'src/ui/__init__.py',
  'src/ui/main_window.py',
  'src/ui/today_page.py',
  'src/ui/worship_row.py',
  'src/ui/worship_dialog.py',
  'src/ui/manage_page.py',
  'src/ui/history_page.py',
  'src/ui/history_common.py',
  'src/ui/calendar_page.py',
  'src/ui/note_history_page.py',
  'src/ui/memo_page.py',
  'src/ui/muhasabah_page.py',
  'src/ui/settings_page.py',
  'src/ui/a11y.py',
  'src/ui/theme.py',
  'src/ui/trend_line.py',
  subdir: 'islamichabits/ui',
)

install_data(
  'src/islamichabits',
  install_dir: bindir,
  install_mode: 'rwxr-xr-x',
)

install_data(
  'data/' + app_id + '.desktop',
  install_dir: join_paths(datadir, 'applications'),
)
install_data(
  'data/' + app_id + '.metainfo.xml',
  install_dir: join_paths(datadir, 'metainfo'),
)
install_data(
  'data/icons/hicolor/scalable/apps/' + app_id + '.svg',
  install_dir: join_paths(datadir, 'icons', 'hicolor', 'scalable', 'apps'),
)
install_data(
  'data/style.css',
  'data/style-dark.css',
  install_dir: join_paths(datadir, app_id),
)

test(
  'logika statistik',
  python3,
  args: [
    '-m',
    'unittest',
    'discover',
    '-s',
    join_paths(meson.current_source_dir(), 'tests'),
    '-q',
  ],
  env: ['PYTHONPATH=' + meson.current_source_dir()],
)
