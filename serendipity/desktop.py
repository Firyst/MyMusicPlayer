import time
from PyQt5 import uic, QtGui, QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QLabel, QPushButton, QVBoxLayout, \
    QSizePolicy, QToolButton, QStyle, QSlider, QMenu
from PyQt5.QtGui import QIcon, QPixmap, QFontMetrics, QFont, QPalette, QColor
from serendipity.main import duration_to_string, MusicTrack, Playlist, bytes_to_string
from datetime import datetime
from pygame import mixer
import threading
import requests
from serendipity.database_operator import MusicDatabase
from style_manager import StyleManager
import importlib
import sys
import json
import os
from serendipity.ui_setup import SetupWindow

test_data = []
# global queues
# I know this is bad...
result_queue = dict()  # scrapper_name: [[result_list], is_finished]
result_count = 0
cached_ids = set()  # which tracks are currently cached
download_queue = []  # queue(folder, task_type, MusicTrack), task_type in (export, cache, download, play, add)
downloader_on = False  # special variable to turn the downloader off
running = True  # cos

# globals
track_width = [0, 0]  # calculated optimal symbol width for tracks
pl_width = [0, 0]  # calculated optimal symbol width for playlists
last_width = 0
DEBUG_MODE = True
TRACK_PROPERTIES = {'title': "Title", 'artist': "Artist", 'album': "Album", 'duration': "Duration",
                    'date': 'Release date', 'discnumber': 'Disc number', 'tracknumber': 'Track number',
                    'genre': 'Genre',  'bitrate': "Bitrate", 'data': "Custom data",
                    'added': "Added to collection", 'file_size': 'File size', 'counter': "Played times"}
STATUSBAR_MESSAGES = {'cache': 'Caching', 'download': 'Downloading', 'export': 'Exporting', 'play': 'Loading',
                      'add': 'Adding'}


def pd(*args):
    """
    Print debug if debug mode is on.
    """
    if DEBUG_MODE:
        print(*args)


def get_scrappers():
    # import all available scrappers
    found = dict()
    for file in os.listdir('scrappers/'):
        # print(file)
        try:
            name, ext = file.rsplit('.', 1)
            if name == 'example':
                continue
            found[name] = getattr(importlib.import_module('scrappers.' + name), 'get_music_list')
        except ValueError or ImportError:
            continue
    return found


def add_to_download_queue(track, task_type, folder, prior=False):
    """
    Add track to global download queue. Task_types: export, download, cache. Prior=True means that track will
    be added to the beginning of the queue.
    """
    global download_queue
    if prior:
        download_queue.insert(0, (track, task_type, folder))
    else:
        download_queue.append((track, task_type, folder))


def downloader(message_func=None):
    # too bad to exist but works
    while downloader_on:
        if download_queue:
            task, task_type, folder = download_queue.pop(0)
            try:
                file = requests.get(task.file_link)
                with open(os.path.join(folder, str(task.id) + '.mp3'), 'wb') as new_file:
                    new_file.write(file.content)
                if message_func:
                    message_func(task, task_type, folder)
                    time.sleep(0.01)
            except ConnectionError:
                time.sleep(1)
        else:
            time.sleep(0.25)


def updater(target, delay):
    while running:
        time.sleep(delay)
        target()


def run_scrapper(req, source_name, scrapper_func, signal):
    print('running search with ', scrapper_func)
    global result_queue
    result_queue[source_name] = [[], False]
    for r in scrapper_func(req):
        if r is not None:
            result_queue[source_name][0].append(r)
            signal.emit()
    result_queue[source_name][1] = True
    signal.emit()

class Communication(QtCore.QObject):
    add_result = QtCore.pyqtSignal()

# noinspection PyUnresolvedReferences
class PlaylistWidget:
    def __init__(self, parent, playlist, font, properties_func=None):
        self.properties_func = properties_func  # open properties
        self.parent = parent
        self.in_library = False

        # UI init
        my_widget = QWidget()
        my_widget.setObjectName("Result-background")
        label_layout = QGridLayout()
        self.styles = parent.styles

        # name
        self.name_label = QLabel(playlist.name)
        self.name_label.setWordWrap(False)
        label_layout.addWidget(self.name_label, 0, 2, 1, 3)
        # self.name_label.setFont(font)

        # desc
        self.desc_label = QLabel(playlist.get_param('description', "No description."))
        self.desc_label.setWordWrap(False)
        label_layout.addWidget(self.desc_label, 0, 5, 1, 5)
        # self.desc_label.setFont(font)

        # track_count
        self.track_label = QLabel(str(playlist.get_param('track_count')))
        self.track_label.setWordWrap(False)
        self.track_label.setToolTip("Track count")
        label_layout.addWidget(self.track_label, 0, 10, 1, 1)
        # self.duration_label.setFont(font)

        # duration
        self.duration_label = QLabel(duration_to_string(playlist.get_param('duration')))
        self.duration_label.setWordWrap(False)
        label_layout.addWidget(self.duration_label, 0, 11, 1, 1)
        # self.duration_label.setFont(font)

        my_widget.setLayout(label_layout)
        my_widget.setAutoFillBackground(True)
        my_widget.setAttribute(QtCore.Qt.WA_Hover)

        self.button_play = QToolButton()
        self.button_play.setIcon(self.styles.get_icon('play'))
        self.button_play.setIconSize(QtCore.QSize(16, 16))
        self.button_play.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.button_play.setMinimumSize(32, 32)
        self.button_play.setObjectName("play_button")
        self.button_play.clicked.connect(self.test_play)

        label_layout.addWidget(self.button_play, 0, 0, 1, 1)

        self.my_widget = my_widget

        self.playlist = playlist
        self.is_playing = False

        # cos
        self.add_now = QPushButton()
        self.add_now.clicked.connect(self.add_to_library)

        self.update_icons()
        self.my_widget.mousePressEvent = self.cum

    def cum(self, *args):
        view = PlaylistView(self.parent)
        self.parent.tab_library.layout().addWidget(view)

    def test_play(self):
        pass

    def track_manage(self):
        if self.in_library:
            # remove
            db.remove_track(self.track.id)
            self.in_library = False
            self.update_icons()
        else:
            # add
            self.track.id = 0
            if self.parent.playing_track:
                if self.parent.playing_track.file_link == self.track.file_link:
                    # is playing now and is ready to be added
                    self.add_to_library()
                    return 0
            self.track.temp = self.add_now
            add_to_download_queue(self.track, 'add', os.path.join(self.parent.config['storage'], 'cache'))
            self.parent.next_download_message(True)
            self.button_add.setIcon(self.styles.get_icon("update"))

    def add_to_library(self):
        # update track
        new_id = db.add_track(self.track)
        self.track = db.get_track(new_id)

        # add it to main playlist
        lib = db.get_playlist(1)
        lib.add_track(self.track)
        lib.data_update()
        db.update_playlist(1, lib)

        # update properties
        if self.parent.search_properties_track:
            if self.track.file_link == self.parent.search_properties_track.file_link:
                self.parent.search_properties_track = self.track
                self.parent.show_search_properties()
        self.in_library = True
        self.update_icons()

    def update_icons(self):
        if self.is_playing:
            self.button_play.setIcon(self.styles.get_icon("pause"))
        else:
            self.button_play.setIcon(self.styles.get_icon("play"))

    def enter(self, *args, **kwargs):
        # add button event
        if self.in_library:
            self.button_add.setIcon(self.styles.get_icon("close"))

    def leave(self, event, **kwargs):
        # add button event
        if self.in_library:
            self.button_add.setIcon(self.styles.get_icon("done"))

    def get_widget(self):
        return self.my_widget

    def truncate(self, max_width, metrics=None):
        # resize labels for the given proportions
        global pl_width
        props = [0.2, 0.35]
        labels = [self.name_label, self.desc_label]
        texts = ["        " + self.playlist.name, self.playlist['description']]

        if metrics is None:
            metrics = QFontMetrics(self.name_label.font())
        for i in range(len(props)):
            if pl_width[i]:
                # if symbol width is already calculated
                if len(texts[i]) > pl_width[i]:
                    labels[i].setText(texts[i][:pl_width[i]] + '...')
                else:
                    labels[i].setText(texts[i][:pl_width[i]])
            else:
                size = int(props[i] * max_width)
                text = texts[i]
                if metrics.width(text) > size:
                    while metrics.width(text + '...') > size:
                        text = text[:-1]
                    labels[i].setText(text + '...')
                    pl_width[i] = len(text)
                else:
                    labels[i].setText(text)


# noinspection PyUnresolvedReferences
class ResultWidget:
    def __init__(self, parent, track, font, properties_func=None):
        self.properties_func = properties_func  # open properties
        self.parent = parent
        self.in_library = False

        # check if added
        track_id = db.find_track(True, file_link=track.file_link)
        if track_id:
            self.in_library = True
            track = db.get_track(track_id[0])

        # UI init
        my_widget = QWidget()
        my_widget.setObjectName("Result-background")
        label_layout = QGridLayout()
        self.styles = parent.styles
        # my_widget.setStyleSheet(self.styles.style)

        self.author_label = QLabel(track.get_param('author'))
        self.author_label.setWordWrap(False)

        label_layout.addWidget(self.author_label, 0, 3, 1, 3)
        # self.author_label.setFont(font)

        self.name_label = QLabel(track.get_param('name'))
        self.name_label.setWordWrap(False)
        label_layout.addWidget(self.name_label, 0, 6, 1, 4)
        self.name_label.setFont(font)

        self.duration_label = QLabel(duration_to_string(track.get_param('duration')))
        self.duration_label.setWordWrap(False)
        label_layout.addWidget(self.duration_label, 0, 10, 1, 1)
        self.duration_label.setFont(font)

        my_widget.setLayout(label_layout)
        my_widget.setAutoFillBackground(True)
        my_widget.setAttribute(QtCore.Qt.WA_Hover)

        self.button_play = QToolButton()
        self.button_play.setIcon(self.styles.get_icon('play'))
        self.button_play.setIconSize(QtCore.QSize(16, 16))
        self.button_play.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.button_play.setMinimumSize(32, 32)
        self.button_play.setObjectName("play_button")
        self.button_play.clicked.connect(self.test_play)

        self.button_add = QToolButton()
        self.button_add.setIconSize(QtCore.QSize(16, 16))
        self.button_add.setLayoutDirection(QtCore.Qt.LayoutDirectionAuto)
        self.button_add.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.button_add.setMinimumSize(32, 32)
        self.button_add.setObjectName("add_button")
        self.button_add.clicked.connect(self.track_manage)
        self.button_add.enterEvent = self.enter
        self.button_add.leaveEvent = self.leave

        self.button_more = QToolButton()
        self.button_more.setIcon(self.styles.get_icon('more'))
        self.button_more.setIconSize(QtCore.QSize(16, 16))
        self.button_more.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.button_more.setMinimumSize(32, 32)
        self.button_more.setObjectName("more_button")

        label_layout.addWidget(self.button_add, 0, 0, 1, 1)
        label_layout.addWidget(self.button_play, 0, 1, 1, 1)
        label_layout.addWidget(self.button_more, 0, 11, 1, 1)

        self.my_widget = my_widget

        self.track = track
        self.button_more.clicked.connect(self.view_track_data)

        self.add_now = QPushButton()
        self.add_now.clicked.connect(self.add_to_library)

        self.update_icons()

    def test_play(self):
        if self.parent.playing_track:
            if self.parent.playing_track.get_param("file_hash", 'NO') == self.track.get_param('file_hash', "XD"):
                # track is playing
                self.parent.player_pause()
                return 1

        self.parent.set_player_queue(self.track)
        if self.parent.playing_track and self.parent.playing:
            if self.parent.playing_track.get_param("file_hash", 'NO') == self.track.get_param('file_hash', "XD"):
                # if track already started playing
                self.button_play.setIcon(self.styles.get_icon("pause"))
                return 2
        # otherwise set update icon
        self.button_play.setIcon(self.styles.get_icon("update"))

    def track_manage(self):
        if self.in_library:
            # remove
            db.remove_track(self.track.id)
            self.in_library = False
            self.update_icons()
        else:
            # add
            self.track.id = 0
            if self.parent.playing_track:
                if self.parent.playing_track.file_link == self.track.file_link:
                    # is playing now and is ready to be added
                    self.add_to_library()
                    return 0
            self.track.temp = self.add_now
            add_to_download_queue(self.track, 'add', os.path.join(self.parent.config['storage'], 'cache'))
            self.parent.next_download_message(True)
            self.button_add.setIcon(self.styles.get_icon("update"))

    def add_to_library(self):
        # update track
        new_id = db.add_track(self.track)
        self.track = db.get_track(new_id)

        # add it to main playlist
        lib = db.get_playlist(1)
        lib.add_track(self.track)
        lib.data_update()
        db.update_playlist(1, lib)

        # update properties
        if self.parent.search_properties_track:
            if self.track.file_link == self.parent.search_properties_track.file_link:
                self.parent.search_properties_track = self.track
                self.parent.show_search_properties()
        self.in_library = True
        self.update_icons()

    def update_icons(self):
        # add icon
        if self.in_library:
            self.button_add.setIcon(self.styles.get_icon("done"))
        else:
            self.button_add.setIcon(self.styles.get_icon("add"))

        # play icon
        if self.parent.playing_track and self.parent.playing:
            if self.parent.playing_track.get_param("file_hash", 'NO') == self.track.get_param('file_hash', "XD"):
                # track is playing
                self.button_play.setIcon(self.styles.get_icon("pause"))
                return 1
        self.button_play.setIcon(self.styles.get_icon("play"))

    def view_track_data(self):
        self.parent.search_properties_track = self.track
        self.properties_func()

    def enter(self, *args, **kwargs):
        # add button event
        if self.in_library:
            self.button_add.setIcon(self.styles.get_icon("close"))

    def leave(self, event, **kwargs):
        # add button event
        if self.in_library:
            self.button_add.setIcon(self.styles.get_icon("done"))

    def get_widget(self):
        return self.my_widget

    def truncate(self, max_width, metrics=None):
        # resize labels for the given proportions
        global track_width
        self.duration_label = duration_to_string(self.track['duration'])

        props = [0.2, 0.3]
        labels = [self.author_label, self.name_label]
        texts = ["        " + self.track['artist'], self.track['title']]

        if metrics is None:
            metrics = QFontMetrics(self.name_label.font())
        for i in range(len(props)):
            if track_width[i]:
                # if symbol width is already calculated
                if len(texts[i]) > track_width[i]:
                    labels[i].setText(texts[i][:track_width[i]] + '...')
                else:
                    labels[i].setText(texts[i][:track_width[i]])
            else:
                size = int(props[i] * max_width)
                text = texts[i]
                if metrics.width(text) > size:
                    while metrics.width(text + '...') > size:
                        text = text[:-1]
                    labels[i].setText(text + '...')
                    track_width[i] = len(text)
                else:
                    labels[i].setText(text)


class QJumpSlider(QSlider):
    def __init__(self, parent=None):
        super(QJumpSlider, self).__init__(parent)
        self.pressed = False
        self.release_func = None  # function that is called when mouse button is released
        self.set_value(33)

    def set_value(self, value):
        if not self.pressed:
            self.setValue(value)

    def mousePressEvent(self, event):
        # Jump to click position
        self.pressed = True
        self.setValue(QStyle.sliderValueFromPosition(self.minimum() - 5, self.maximum() + 5, event.x(), self.width()))

    def mouseMoveEvent(self, event):
        # Jump to pointer position while moving
        self.setValue(QStyle.sliderValueFromPosition(self.minimum() - 5, self.maximum() + 5, event.x(), self.width()))

    def mouseReleaseEvent(self, event):
        self.pressed = False
        if self.release_func:
            self.release_func(self)


class PlaylistView(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        uic.loadUi(os.path.join('ui', 'playlist_view.ui'), self)
        self.set_icons()

    def set_icons(self):
        self.button_play.setIcon(self.parent.styles.get_icon("play"))
        self.button_add.setIcon(self.parent.styles.get_icon("add"))
        self.button_download.setIcon(self.parent.styles.get_icon("download"))
        self.button_export.setIcon(self.parent.styles.get_icon("export"))
        self.button_delete.setIcon(self.parent.styles.get_icon("close"))
        self.button_back.setIcon(self.parent.styles.get_icon("back"))

        self.label1.font().setBold(True)
        self.props.setObjectName("scroll_area_content")


class MainWindow(QMainWindow):
    def __init__(self):
        global downloader_on
        super().__init__()

        # init music player
        mixer.init()

        # setup configs
        self.styles = None
        self.config = self.update_config()
        pd(self.config)

        # init system variables
        self.current_results = []
        self.current_playlists = []

        self.window_width = self.width()
        self.com = Communication()
        self.com.add_result.connect(self.update_results)

        self.cached_ids = set()
        self.playing_track = None
        self.playing = False
        self.play_queue = []
        self.play_start = 0
        self.awaiting_download = False
        self.queue_pos = -1
        self.library_properties_track = None
        self.search_properties_track = None

        # setup UI
        uic.loadUi(os.path.join('ui', 'desktop.ui'), self)
        self.set_search_label('Nothing here yet...')
        self.buttons_init()
        self.load_styles("default-dark")
        if self.config["status_bar_enabled"]:
            self.status_bar.show()
            self.sb_msg("Ready.")
        else:
            self.status_bar.hide()
        self.volume_slider = QJumpSlider(QtCore.Qt.Horizontal)
        self.time_slider = QJumpSlider(QtCore.Qt.Horizontal)
        self.label_duration = QLabel()
        self.hide_search_properties()
        self.player_init()
        self.tab_widget.currentChanged.connect(self.tab_update)

        # setup services
        self.dl_thread = threading.Thread(target=downloader, args=[self.download_finish])
        downloader_on = True
        self.dl_thread.start()
        self.upd_thread = threading.Thread(target=updater, args=(self.update_pos, 0.25))
        self.upd_thread.start()

        # create context menu for sort button
        self.playlists_sort_menu = self.create_playlists_sort_menu()
        self.playlists_sort_button.setMenu(self.playlists_sort_menu)
        self.reload_playlists(None)

        print(self.label.font().family())
        self.used_font_family = self.label.font().family()

    def test(self, some):
        print(some)

    def on_context_menu(self, point):
        # show context menu
        self.popMenu.exec_(self.playlists_sort_button.mapToGlobal(point))

    def create_playlists_sort_menu(self):
        font = QFont(self.playlists_sort_button.font().family(), self.playlists_sort_button.font().pixelSize())
        menu = QMenu()
        menu.setObjectName("sort_menu")
        act1 = menu.addAction("Default")
        act1.setIcon(self.styles.get_icon("no-sort"))
        menu.addSeparator()

        act1 = menu.addAction("Alphabet")
        act1.setIcon(self.styles.get_icon("sort1"))

        act1 = menu.addAction("Alphabet")
        act1.setIcon(self.styles.get_icon("sort2"))

        menu.addSeparator()

        act1 = menu.addAction("Created")
        act1.setIcon(self.styles.get_icon("sort1"))

        act1 = menu.addAction("Created")
        act1.setIcon(self.styles.get_icon("sort2"))

        menu.addSeparator()

        act1 = menu.addAction("Tracks")
        act1.setIcon(self.styles.get_icon("sort1"))

        act1 = menu.addAction("Tracks")
        act1.setIcon(self.styles.get_icon("sort2"))

        menu.addSeparator()

        act1 = menu.addAction("Duration")
        act1.setIcon(self.styles.get_icon("sort1"))

        act1 = menu.addAction("Duration")
        act1.setIcon(self.styles.get_icon("sort2"))
        menu.setStyleSheet(self.styles.style)
        return menu

    def closeEvent(self, event):
        global downloader_on
        global running
        downloader_on = False
        running = False

    def reload(self):
        uic.loadUi('desktop.ui', self)
        self.set_search_label('Nothing here yet...')
        self.buttons_init()
        self.load_styles("default-dark")

    def tab_update(self):
        self.truncate_all()

    def next_download_message(self, new_task):
        if self.status_bar.currentMessage() == "Ready." or self.status_bar.currentMessage() == '' or not new_task:
            if download_queue:
                track, task_type, _ = download_queue[0]
                self.sb_msg(f"{STATUSBAR_MESSAGES[task_type]} {track['title']}...")
            else:
                self.sb_msg("Ready.")

    def download_finish(self, downloaded_track, task_type, folder):
        """
        Is called when download of track finishes.
        """
        global download_queue
        self.cached_ids.add(downloaded_track.id)

        # check if no new "play" tasks appeared
        for i, queue_elem in enumerate(download_queue):
            if i > 0 and queue_elem[1] == 'play':
                download_queue.remove(queue_elem)

        if downloaded_track.id == 0:
            # if track is going to be added
            downloaded_track.file_path = os.path.join(folder, '0.mp3')  # set file
            downloaded_track.metadata_from_file()  # read metadata
            downloaded_track.file_path = ''
            # if metadata needs to be updated now
            if self.search_properties_track:
                if downloaded_track.file_link == self.search_properties_track.file_link:
                    self.search_properties_track = downloaded_track
                    self.show_properties_button.click()
            if task_type == 'add':
                downloaded_track.temp.click()

        elif downloaded_track.id == -1:
            # if track is temporary
            downloaded_track.file_path = os.path.join(folder, '-1.mp3')  # set file
            downloaded_track.metadata_from_file()  # read metadata
            downloaded_track.file_path = ''
            # if metadata needs to be updated now
            if self.search_properties_track:
                if downloaded_track.file_link == self.search_properties_track.file_link:
                    self.search_properties_track = downloaded_track
                    self.show_properties_button.click()

        if 'play' not in [t[1] for t in download_queue] and task_type == 'play':
            # play now
            self.awaiting_download = False
            self.play_track(downloaded_track)

        self.next_download_message(False)

    def sb_msg(self, message):
        """
        Show a message in status bar (if it is enabled)
        """
        if self.config["status_bar_enabled"]:
            self.status_bar.showMessage(message)

    def update_config(self):
        """
        Update configs from config.json
        """
        with open("../config.json", 'r') as f:
            config = json.loads(f.read())
        self.config = config
        return config

    def save_config(self):
        with open("../config.json", 'w') as f:
            f.write(json.dumps(self.config))

    # Player

    def play_track(self, track):
        mixer.music.stop()
        mixer.music.unload()
        if track.file_path:
            # track is downloaded
            mixer.music.load(track.file_path)
        else:
            if track.id not in self.cached_ids:
                pd("ERROR: not cached for some reason")
                return -1
            # play cached
            mixer.music.load(os.path.join(self.config['storage'], 'cache', f"{track.id}.mp3"))
        self.playing = True
        self.time_slider.setEnabled(True)
        mixer.music.play()
        self.play_start = 0
        self.label_duration.setText(duration_to_string(track['duration']))
        self.label_player_title.setText(track.get_param('title', 'Unnamed'))
        self.label_player_artist.setText(track.get_param('artist', 'Unknown artist'))
        self.playing_track = track
        self.update_player()


    def player_init(self):
        """
        Init main player widget.
        """
        self.volume_slider.setFocusPolicy(QtCore.Qt.NoFocus)
        self.time_slider.setFocusPolicy(QtCore.Qt.NoFocus)
        self.player_volume.layout().addWidget(self.volume_slider)
        self.player_time.addWidget(self.time_slider)
        self.player_time.addWidget(self.label_duration)
        self.player_time.setStretch(0, 1)
        self.player_time.setStretch(1, 7)
        self.player_time.setStretch(2, 1)

        self.player_button_prev.setIcon(self.styles.get_icon("prev"))
        self.player_button_next.setIcon(self.styles.get_icon("next"))

        self.player_button_play.clicked.connect(self.player_pause)
        self.player_button_next.clicked.connect(self.play_next)
        self.player_button_shuffle.clicked.connect(self.player_shuffle)
        self.player_button_repeat.clicked.connect(self.player_repeat)

        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(int(self.config['volume'] * 100))
        self.change_volume()
        self.time_slider.setMaximum(1000)
        self.time_slider.release_func = self.player_rewind
        self.volume_slider.valueChanged.connect(self.change_volume)

        self.update_player()
        self.play_next()
        self.truncate_all()
        self.label_player_title.setText("No Track")

    def update_player(self):
        self.truncate_all()
        if self.config['shuffle']:
            self.player_button_shuffle.setIcon(self.styles.get_icon("shuffle"))
        else:
            self.player_button_shuffle.setIcon(self.styles.get_icon("no-shuffle"))

        if self.playing:
            self.player_button_play.setIcon(self.styles.get_icon("pause"))
        else:
            self.player_button_play.setIcon(self.styles.get_icon("play"))

        if self.config['repeat']:
            self.player_button_repeat.setIcon(self.styles.get_icon("repeat"))
        else:
            self.player_button_repeat.setIcon(self.styles.get_icon("no-repeat"))

        for res in self.current_results:
            res.update_icons()

    def player_pause(self):
        if self.playing_track:
            if self.playing:
                self.playing = False
                mixer.music.pause()
            else:
                self.playing = True
                mixer.music.unpause()
            self.update_player()

    def player_repeat(self):
        self.config['repeat'] = not self.config['repeat']
        self.update_player()
        self.save_config()

    def player_shuffle(self):
        self.config['shuffle'] = not self.config['shuffle']
        self.update_player()
        self.save_config()

    def player_rewind(self, slider):
        if self.playing_track:
            mixer.music.stop()
            mixer.music.play(0, (slider.value() * self.playing_track['duration']) // 1000)
            if not self.playing:
                mixer.music.pause()
            self.play_start = slider.value() * self.playing_track['duration']
            self.update_pos()

    def update_pos(self):
        """
        Tick function.
        """
        if self.playing_track:
            if mixer.music.get_pos() == -1:
                self.play_next()
                return 0
            pos = mixer.music.get_pos() + self.play_start
            self.time_slider.set_value(int(pos / self.playing_track['duration']))
            self.label_current_time.setText(duration_to_string(pos // 1000))

    def change_volume(self):
        """
        Change music volume and save it to config.
        """
        mixer.music.set_volume(self.volume_slider.value() / 200)
        self.config['volume'] = round(self.volume_slider.value() / 100, 2)
        self.save_config()

    def set_player_queue(self, playable):
        """
        Resets player queue and adds new objects.
        """
        self.playing_track = None
        self.playing = False
        mixer.music.stop()
        mixer.music.unload()

        self.update_player()
        print(type(playable), isinstance(playable, MusicTrack))

        if isinstance(playable, MusicTrack):
            pd('adding', MusicTrack, 'to queue')
            self.play_queue = [playable]
        elif isinstance(playable, Playlist):
            self.play_queue = playable
        self.queue_pos = -1

        # clean unused ids from cache
        if 0 in self.cached_ids:
            # clean cache for temp id
            self.cached_ids.remove(0)
        if -1 in self.cached_ids:
            # clean cache for temp id
            self.cached_ids.remove(-1)
        new_ids = [i.id for i in self.play_queue]
        print(os.path.join(self.config['storage'], 'cache'))
        for cached in tuple(self.cached_ids):
            if cached not in new_ids:
                self.cached_ids.remove(cached)
                pd('removing', cached, 'from cache.')
                try:
                    os.remove(os.path.join(self.config['storage'], 'cache', str(cached) + ".mp3"))
                except FileNotFoundError:
                    pd("cant remove")
                    pass
        self.play_next()

    def play_next(self):
        global download_queue
        if not self.play_queue:
            mixer.music.stop()
            mixer.music.unload()
            self.time_slider.setEnabled(False)
            self.label_current_time.setText("--:--")
            self.label_duration.setText("--:--")
            self.time_slider.setValue(0)
            self.playing_track = None
            self.playing = False
            self.label_player_title.setText("No track")
            self.label_player_artist.setText('')
            self.update_player()
            return 0
        else:
            pd('queue', self.play_queue)
            if self.config['repeat']:
                if self.queue_pos == len(self.play_queue) - 1:
                    # repeat on, return to begin
                    self.queue_pos = 0
                else:
                    # repeat on, next
                    self.queue_pos += 1
                cur_track = self.play_queue[self.queue_pos]
            else:
                # repeat off, pop first track
                if self.playing:
                    # if not new track
                    self.play_queue.pop(0)
                if not self.play_queue:
                    # if queue became empty
                    self.play_next()
                    return 0
                cur_track = self.play_queue[0]
                self.queue_pos = 0

            if cur_track.file_path or cur_track.id in self.cached_ids:
                # if ready to play
                self.play_track(cur_track)
                self.awaiting_download = False
                pd("ad", self.awaiting_download)

            # caching
            for i in range(self.queue_pos, min(len(self.play_queue), 1 + self.config["queue_cache"] + self.queue_pos)):
                elem = self.play_queue[i]  # get track
                if not elem.file_path:
                    # if file is not stored
                    if elem.id not in self.cached_ids:
                        # if not cached yet
                        if elem not in download_queue:
                            # if not awaiting download
                            pd(elem, 'needs to be downloaded')
                            if i != self.queue_pos:
                                add_to_download_queue(elem, 'cache', os.path.join(self.config['storage'], 'cache'))
                            else:
                                # add play task for current track if it needs to be downloaded
                                self.awaiting_download = True
                                pd("ad", self.awaiting_download)
                                add_to_download_queue(elem, 'play', os.path.join(self.config['storage'], 'cache'), True)
                                self.next_download_message(True)
                                self.label_player_title.setText("Downloading...")
                                self.label_player_artist.setText('')
            self.truncate_all()

    # Playlists

    def reload_playlists(self, sorting_key=None):
        all_pl = [db.get_playlist(i) for i in db.find_playlist(True)]
        if sorting_key:
            all_pl.sort(key=sorting_key)
        print(all_pl)
        self.current_playlists = []
        if all_pl:
            # generate new layout for scroll area
            new_widget = QWidget()
            new_widget.setObjectName("search_area_content")
            new_widget.setAutoFillBackground(True)
            new_layout = QVBoxLayout()
            new_layout.setAlignment(QtCore.Qt.AlignTop)
            new_widget.setLayout(new_layout)
            self.playlists_scroll_area.setWidget(new_widget)

            # add playlists
            for playlist in all_pl:
                font = self.label_current_time.font()
                font = QFont(font.family(), font.pointSize())

                # generate result widget
                add_widget = PlaylistWidget(self, playlist, font)

                self.current_playlists.append(add_widget)
                new_widget.layout().addWidget(add_widget.get_widget())
            self.truncate_all()
        else:
            res_label = QLabel("Nothing found...")
            self.playlists_scroll_area.setWidget(res_label)

    def buttons_init(self):
        """
        Connect all buttons.
        """
        self.search_button.clicked.connect(self.start_search)
        self.search_request.returnPressed.connect(self.start_search)
        self.update_button.clicked.connect(self.update_results)
        self.update_button.hide()
        self.show_properties_button.clicked.connect(self.show_search_properties)
        self.show_properties_button.hide()
        self.properties_button.clicked.connect(self.hide_search_properties)
        self.toolButton.clicked.connect(lambda: self.status_bar.showMessage('пошел нахуй'))


    def load_styles(self, style):
        """
        Load and apply a new style.
        """
        self.styles = StyleManager("default-dark")
        self.styles.load_style("style.qss")
        # self.styles.load_palette("palette.json")
        self.styles.load_colors("palette.json")
        self.setStyleSheet(self.styles.style)
        # self.setPalette(self.styles.palette)

        self.search_button.setIcon(self.styles.get_icon("search"))
        self.properties_button.setIcon(self.styles.get_icon("close"))
        self.playlists_new_button.setIcon(self.styles.get_icon("add"))
        self.playlists_sort_button.setIcon(self.styles.get_icon("sort"))

    def debug(self, *args, **kwargs):
        print('debug')

    def player_truncate(self, metrics):
        # truncate player labels

        labels = [self.label_player_title, self.label_player_artist]
        if self.playing_track:
            texts = [self.playing_track.get_param('title', 'Unnamed'),
                     self.playing_track.get_param('artist', 'Unknown artist')]
        else:
            if self.awaiting_download:
                texts = ["Loading...", "-"]
            else:
                texts = ["No track", '-']
        size = self.player_widget.width() // 5
        if size <= 40:
            # on create
            size = 100

        for i in range(2):
            text = texts[i]
            if metrics.width(text) > size:
                while metrics.width(text + '...') > size:
                    text = text[:-1]
                labels[i].setText(text + '...')
            else:
                labels[i].setText(text)

    def paintEvent(self, a0: QtGui.QPaintEvent) -> None:
        # if self.width() != self.window_width:
        # custom resize event
        self.window_width = self.width()
        self.truncate_all()

    def truncate_all(self):
        """
        Truncate text while resizing
        """
        global track_width
        global pl_width

        metrics = QFontMetrics(self.label_player_title.font())
        self.player_truncate(metrics)
        # width changed
        # truncate result text
        if self.current_results:
            track_width = [0, 0]
            for result in self.current_results:
                result.truncate(self.search_scroll_area.width(), metrics)
        # truncate playlist text
        if self.current_playlists:
            pl_width = [0, 0]
            for playlist in self.current_playlists:
                playlist.truncate(self.playlists_scroll_area.width(), metrics)

    def hide_search_properties(self):
        self.search_properties.hide()
        self.search_properties_track = None
        self.truncate_all()

    def show_search_properties(self):
        """
        Show track data in right-side menu
        """
        track = self.search_properties_track
        self.search_properties.show()
        data_layout = QVBoxLayout()
        for track_kw in TRACK_PROPERTIES:
            if track.get_param(track_kw):
                title = QLabel(TRACK_PROPERTIES[track_kw] + ":")
                font = title.font()
                font.setBold(True)
                title.setFont(font)
                data_layout.addWidget(title)

                if track_kw == "duration":
                    text = QLabel(duration_to_string(track.get_param(track_kw)))
                elif track_kw == "bitrate":
                    text = QLabel(str(track.get_param(track_kw)) + "Kbps")
                elif track_kw == 'file_size':
                    text = QLabel(bytes_to_string(track.get_param(track_kw)))
                elif track.get_param(track_kw, '') and track_kw == "added":
                    text = QLabel(str(datetime.fromtimestamp(track['added']).strftime("%d.%m.%y %H:%M")))
                else:
                    text = QLabel(str(track.get_param(track_kw)))
                text.setWordWrap(True)
                data_layout.addWidget(text)
        properties_widget = QWidget()
        properties_widget.setObjectName("search_area_content")
        data_layout.addStretch(0)
        properties_widget.setLayout(data_layout)
        self.properties_area.setWidget(properties_widget)
        self.truncate_all()

    def update_results(self):
        global result_count
        finished = True
        for scr_name in result_queue:
            scrapper_res = result_queue[scr_name]
            while len(scrapper_res[0]):
                t = scrapper_res[0].pop(0)
                self.add_search_result(t)
                self.truncate_all()
                result_count += 1
            if not scrapper_res[1]:
                finished = False
        if result_count == 0 and finished:
            self.set_search_label('Nothing found.\nCheck search keywords or your connection.')

    def start_search(self):
        global result_queue
        global result_count
        result_count = 0
        result_queue = dict()
        self.current_results = []
        search_text = self.search_request.text()
        if search_text:
            self.set_search_label('Searching...')
            scr = get_scrappers()
            for scrapper in scr:
                threading.Thread(target=run_scrapper,
                                 args=(search_text, scrapper, scr[scrapper], self.com.add_result)).start()

    def set_search_label(self, label_text):
        """
        Set a label in results field
        """
        lbl = QLabel(label_text)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setObjectName("search_area_content")
        self.search_scroll_area.setWidget(lbl)

    def add_search_result(self, track):
        widg = self.search_scroll_area.widget()

        if isinstance(widg, QLabel):
            # if layout inside scroll widget
            new_widget = QWidget()
            new_widget.setAutoFillBackground(True)
            new_layout = QVBoxLayout()
            new_layout.setAlignment(QtCore.Qt.AlignTop)
            new_widget.setLayout(new_layout)
            new_widget.setObjectName("search_area_content")
            self.search_scroll_area.setWidget(new_widget)
        widget = self.search_scroll_area.widget()

        # get new font probe
        font = self.label_current_time.font()
        font = QFont(font.family(), font.pointSize())

        # generate result widget
        add_widget = ResultWidget(self, track, self.label.font(), self.show_search_properties)

        self.current_results.append(add_widget)
        widget.layout().addWidget(add_widget.get_widget())
        add_widget.truncate(self.search_scroll_area.width())


app = QApplication(sys.argv)
# check if setup is required
with open("../config.json", 'r') as j:
    cfg = json.loads(j.read())
QtGui.QFontDatabase.addApplicationFont(os.path.join("../styles", cfg["theme"], "SFUIText-Light.ttf"))
print(QtGui.QFontDatabase.styleString)
if cfg["first_run"]:
    ex = SetupWindow()
    ex.show()
    app.exec_()
    with open("../config.json", 'r') as j:
        cfg = json.loads(j.read())
if not cfg["first_run"]:
    db = MusicDatabase(os.path.join(cfg['storage'], 'local.db'))
    ex = MainWindow()
    ex.show()
    app.exec_()
    db.close()
