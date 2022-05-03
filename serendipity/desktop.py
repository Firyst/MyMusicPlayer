import time
import random
from PyQt5 import uic, QtGui, QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QLabel, QPushButton, QVBoxLayout, \
    QSizePolicy, QToolButton, QStyle, QSlider, QMenu, QTabBar, QAction
from PyQt5.QtGui import QIcon, QPixmap, QFontMetrics, QFont, QPalette, QColor
from main import duration_to_string, MusicTrack, Playlist, bytes_to_string
from widgets.QJumpSlider import QJumpSlider
from widgets.QMyMenu import QMyMenu
from widgets.MyQuestionDialog import MyQuestionDialog
from datetime import datetime
from pygame import mixer
import threading
import requests
from database_operator import MusicDatabase
from style_manager import StyleManager
import importlib
import sys
import json
import os
from ui_setup import SetupWindow

test_data = []
# global queues
# I know this is bad...
result_queue = dict()  # scrapper_name: [[result_list], is_finished]
result_count = 0
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
                    'genre': 'Genre', 'bitrate': "Bitrate", 'data': "Custom data",
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
    pd("Queue_manager: new task:", track, task_type)
    if (track not in map(lambda x: x[0], download_queue)) or (task_type == 'play'):
        if prior:
            pd("Queue_manager: inserting", track, "into download queue")
            download_queue.insert(0, (track, task_type, folder))
        else:
            pd("Queue_manager: adding", track, "to download queue")
            download_queue.append((track, task_type, folder))
    else:
        pd("Queue_manager:", track, "already is awaiting caching")


def downloader(message_func=None):
    # too bad to exist but works
    while downloader_on:
        if download_queue:
            task, task_type, folder = download_queue.pop(0)
            pd("Download_manager: starting", task, task_type)
            if os.path.exists(os.path.join(folder, str(task.id) + '.mp3')) and task.id > 0:
                pd("Download_manager: task is already completed, going next")
                if message_func:
                    message_func(task, task_type, folder)
                    time.sleep(0.01)
                continue
            try:
                file = requests.get(task.file_link)
                with open(os.path.join(folder, str(task.id) + '.mp3'), 'wb') as new_file:
                    new_file.write(file.content)
                pd("Download_manager:", task, task_type, 'ok')
                if message_func:
                    message_func(task, task_type, folder)
                    time.sleep(0.01)
            except ConnectionError:
                time.sleep(1)
                pd("Download_manager:", task, task_type, 'connection error. Waiting for 1 sec...')
        else:
            time.sleep(0.25)


def updater(target, delay):
    while running:
        time.sleep(delay)
        target()


def run_scrapper(req, source_name, scrapper_func, signal):
    pd('Scarapper: running', scrapper_func)
    global result_queue
    result_queue[source_name] = [[], False]
    for r in scrapper_func(req):
        if r is not None:
            result_queue[source_name][0].append(r)
            signal.emit()
    result_queue[source_name][1] = True
    signal.emit()


def get_saved_tracks(folder):
    """
    Get all mp3 file ids in specific folder.
    """
    for file in os.listdir(folder):
        if file.split('.')[-1] == 'mp3':
            try:
                fid = int(file.split('.')[0])
                yield fid
            except ValueError:
                pass


class Communication(QtCore.QObject):
    """
    Collection of everywhere used signals.
    """
    add_result = QtCore.pyqtSignal()
    update = QtCore.pyqtSignal()

    # track widget signals
    track_add = QtCore.pyqtSignal()
    track_update = QtCore.pyqtSignal()



# noinspection PyUnresolvedReferences
class TrackWidget:
    def __init__(self, parent, track, properties_func=None):
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

        self.author_label = QLabel(track.get_param('author'))
        self.author_label.setWordWrap(False)

        label_layout.addWidget(self.author_label, 0, 3, 1, 3)

        self.name_label = QLabel(track.get_param('name'))
        self.name_label.setWordWrap(False)
        label_layout.addWidget(self.name_label, 0, 6, 1, 4)

        self.duration_label = QLabel(duration_to_string(track.get_param('duration')))
        self.duration_label.setWordWrap(False)
        label_layout.addWidget(self.duration_label, 0, 10, 1, 1)

        my_widget.setLayout(label_layout)
        my_widget.setAutoFillBackground(True)
        my_widget.setAttribute(QtCore.Qt.WA_Hover)

        self.button_play = QToolButton()
        self.button_play.setIcon(styles.get_icon('play'))
        self.button_play.setIconSize(QtCore.QSize(16, 16))
        self.button_play.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.button_play.setMinimumSize(32, 32)
        self.button_play.setObjectName("play_button")
        self.button_play.clicked.connect(self.test_play)

        self.button_download = QToolButton()
        self.button_download.setIconSize(QtCore.QSize(16, 16))
        self.button_download.setLayoutDirection(QtCore.Qt.LayoutDirectionAuto)
        self.button_download.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.button_download.setMinimumSize(32, 32)
        self.button_download.setObjectName("add_button")
        self.button_download.clicked.connect(self.track_manage)
        self.button_download.enterEvent = self.enter
        self.button_download.leaveEvent = self.leave

        self.button_more = QToolButton()
        self.button_more.setIcon(styles.get_icon('more'))
        self.button_more.setIconSize(QtCore.QSize(16, 16))
        self.button_more.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.button_more.setMinimumSize(32, 32)
        self.button_more.setObjectName("more_button")

        label_layout.addWidget(self.button_download, 0, 0, 1, 1)
        label_layout.addWidget(self.button_play, 0, 1, 1, 1)
        label_layout.addWidget(self.button_more, 0, 11, 1, 1)

        self.my_widget = my_widget

        track.upd_func = self.update_icons
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
                self.button_play.setIcon(styles.get_icon("pause"))
                return 2
        # otherwise set update icon
        self.button_play.setIcon(styles.get_icon("update"))

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
            self.button_add.setIcon(styles.get_icon("update"))

    def add_to_library(self):
        # update track
        new_id = db.add_track(self.track)
        self.track = db.get_track(new_id)
        self.track.upd_func = self.update_icons  # enable icon reset.

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
        self.parent.update_all_playlists()

    def update_icons(self):
        try:
            # add icon
            if self.in_library:
                self.button_download.setIcon(styles.get_icon("done"))
            else:
                self.button_download.setIcon(styles.get_icon("download"))
            # play icon
            if self.parent.player.playing_track and self.parent.playing:
                if self.parent.player.playing_track.get_param("file_hash", 'NO') == self.track.get_param('file_hash', "XD"):
                    # track is playing
                    self.button_play.setIcon(styles.get_icon("pause"))
                    return 1
            self.button_play.setIcon(styles.get_icon("play"))
        except RuntimeError:
            # if widget was deleted/closed
            pass

    def view_track_data(self):
        self.parent.search_properties_track = self.track
        self.properties_func()

    def enter(self, *args, **kwargs):
        # add button event
        if self.in_library:
            self.button_download.setIcon(styles.get_icon("remove"))

    def leave(self, event, **kwargs):
        # add button event
        if self.in_library:
            self.button_download.setIcon(styles.get_icon("done"))

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
        self.button_play.setIcon(styles.get_icon('play'))
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
        self.parent.open_playlist(PlaylistView(self.parent, self.playlist))

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
            self.button_add.setIcon(styles.get_icon("update"))

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
            self.button_play.setIcon(styles.get_icon("pause"))
        else:
            self.button_play.setIcon(styles.get_icon("play"))

    def enter(self, *args, **kwargs):
        # add button event
        if self.in_library:
            self.button_add.setIcon(styles.get_icon("close"))

    def leave(self, event, **kwargs):
        # add button event
        if self.in_library:
            self.button_add.setIcon(styles.get_icon("done"))

    def get_widget(self):
        return self.my_widget

    def truncate(self, max_width, metrics=None):
        # resize labels for the given proportions
        global pl_width
        props = [0.2, 0.35]
        labels = [self.name_label, self.desc_label]
        texts = ["        " + self.playlist.name, self.playlist.get_param('description', "No description")]

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
    def __init__(self, parent, track, font, properties_func, target_playlist=None):
        self.properties_func = properties_func  # open properties
        self.parent = parent
        self.in_library = False
        self.playlist = target_playlist
        self.com = Communication()

        # check if added
        track_id = db.find_track(True, file_link=track.file_link)
        if track_id:
            self.in_library = True
            track = db.get_track(track_id[0])
        if target_playlist:
            self.in_library = track.id in [tr.id for tr in target_playlist.tracks]

        # UI init
        my_widget = QWidget()
        my_widget.setObjectName("Result-background")
        label_layout = QGridLayout()

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
        self.button_play.setIcon(styles.get_icon('play'))
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
        self.button_more.setIcon(styles.get_icon('more'))
        self.button_more.setIconSize(QtCore.QSize(16, 16))
        self.button_more.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.button_more.setMinimumSize(32, 32)
        self.button_more.setObjectName("more_button")
        self.button_more.clicked.connect(self.view_track_data)

        label_layout.addWidget(self.button_add, 0, 0, 1, 1)
        label_layout.addWidget(self.button_play, 0, 1, 1, 1)
        label_layout.addWidget(self.button_more, 0, 11, 1, 1)

        self.my_widget = my_widget

        # bind signals
        self.com.track_add = self.add_to_library
        self.com.track_update = self.update_icons
        track.com = self.com

        self.track = track
        self.update_icons()


    def test_play(self):
        if self.parent.player.playing_track:
            if self.parent.player.playing_track.get_param("file_hash", 'NO') == self.track.get_param('file_hash', "XD"):
                # track is playing
                self.parent.player.pause()
                return 1

        self.parent.player.reset_queue(self.track, None)
        if self.parent.player.playing_track and self.parent.playing:
            if self.parent.player.playing_track.get_param("file_hash", 'NO') == self.track.get_param('file_hash', "XD"):
                # if track already started playing
                self.button_play.setIcon(styles.get_icon("pause"))
                return 2
        # otherwise set update icon
        self.button_play.setIcon(styles.get_icon("update"))

    def track_manage(self):
        if self.in_library:
            # remove
            if self.playlist:
                # if playlist edit active, just remove from playlist
                edit_pl = db.get_playlist(self.playlist.id)  # get current version of playlist
                edit_pl.remove_track(self.track)
                edit_pl.data_update()
                db.update_playlist(edit_pl.id, edit_pl)
            else:
                db.remove_track(self.track.id)
            self.in_library = False
            self.update_icons()
            self.parent.update_all_playlists()
        else:
            # add
            if self.parent.playing_track:
                if self.parent.playing_track.file_link == self.track.file_link:
                    # is playing now and is ready to be added
                    self.track.id = 0
                    self.add_to_library()
                    return 0
            if self.playlist and self.track.id > 0:
                # track is in library and should be just added to playlist.
                self.add_to_library()
                return 0
            self.track.id = 0
            self.track.temp = self.add_now
            add_to_download_queue(self.track, 'add', os.path.join(self.parent.config['storage'], 'cache'))
            self.parent.next_download_message(True)
            self.button_add.setIcon(styles.get_icon("update"))

    def add_to_library(self):
        # update track
        new_id = db.add_track(self.track)
        self.track = db.get_track(new_id)
        self.track.upd_func = self.update_icons

        # add it to main playlist
        lib = db.get_playlist(1)
        if self.track not in lib.tracks:
            lib.add_track(self.track)
            lib.data_update()
            db.update_playlist(1, lib)

        if self.playlist:
            edit_pl = db.get_playlist(self.playlist.id)  # get current version of playlist
            edit_pl.add_track(self.track)
            edit_pl.data_update()
            db.update_playlist(edit_pl.id, edit_pl)
            self.parent.update_all_playlists()

        # update properties
        if self.parent.search_properties_track:
            if self.track.file_link == self.parent.search_properties_track.file_link:
                self.parent.search_properties_track = self.track
                self.parent.show_search_properties()
        self.in_library = True
        self.update_icons()
        self.parent.update_all_playlists()

    def update_icons(self):
        try:
            # add icon
            if self.in_library:
                self.button_add.setIcon(styles.get_icon("done"))
            else:
                self.button_add.setIcon(styles.get_icon("add"))

            # play icon
            if self.parent.player.playing_track and not self.parent.player.paused:
                if self.parent.playing_track.get_param("file_hash", 'NO') == self.track.get_param('file_hash', "XD"):
                    # track is playing
                    self.button_play.setIcon(styles.get_icon("pause"))
                    return 1
            self.button_play.setIcon(styles.get_icon("play"))
        except RuntimeError:
            # widget is deleted or hidden
            pass

    def view_track_data(self):
        self.parent.search_properties_track = self.track
        self.properties_func()

    def enter(self, *args, **kwargs):
        # add button event
        if self.in_library:
            self.button_add.setIcon(styles.get_icon("close"))

    def leave(self, event, **kwargs):
        # add button event
        if self.in_library:
            self.button_add.setIcon(styles.get_icon("done"))

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


class Config:
    def __init__(self):
        pass

    def __getattr__(self, item):
        with open('../config.json', 'r') as f:
            data = json.loads(f.read())
        return data[item]

    def __setattr__(self, key, value):
        with open('../config.json', 'r') as f:
            data = json.loads(f.read())
        data[key] = value
        with open("../config.json", 'w') as f:
            f.write(json.dumps(data))


class SerendipityPlayer:
    """
    All player queue management.
    """
    def __init__(self, parent, player_widget, cache_path):
        mixer.init()
        self.parent = parent
        self.widget = player_widget

        self.cache_path = cache_path

        self.queue_pos = -1
        self.queue = None
        self.history = []

        self.paused = True  # track is paused
        self.loaded = False  # track is loaded and ready to play
        self.playing_track = None
        self.playing_list = None
        self.play_start = 0  # where to start play, used for rewinding

        self.repeat = False
        self.shuffle = False

        # self.update_widget()

    def update_config(self):
        self.repeat = config.repeat
        self.shuffle = config.shuffle

    @property
    def current_pos(self):
        return mixer.music.get_pos()

    def update_pos(self):
        if self.playing_track:
            if mixer.music.get_pos() == -1:
                self.next()
                pd("Player: finished, next!")
                return 0
            pos = mixer.music.get_pos() + self.play_start
            self.widget.time_slider.set_value(int(pos / self.playing_track['duration']))
            self.widget.label_current_time.setText(duration_to_string(pos // 1000))

    def download_finish_event(self, downloaded_track, task_type, folder):
        """
        Is called when download of track finishes.
        """
        global download_queue

        # check if no new "play" tasks appeared
        for i, queue_elem in enumerate(download_queue):
            if i > 0 and queue_elem[1] == 'play':
                download_queue.remove(queue_elem)

        if downloaded_track.id == 0:
            # if track is going to be added
            downloaded_track.file_path = os.path.join(folder, '0.mp3')  # set file
            downloaded_track.metadata_from_file()  # read metadata
            downloaded_track.file_path = ''

            self.parent.update_search_properties()

            if task_type == 'add':
                downloaded_track.com.track_add.emit()

        elif downloaded_track.id == -1:
            # if track is temporary (play without queue)
            downloaded_track.file_path = os.path.join(folder, '-1.mp3')  # set file
            downloaded_track.metadata_from_file()  # read metadata
            downloaded_track.file_path = ''

            self.parent.update_search_properties()

        if 'play' not in [t[1] for t in download_queue] and task_type == 'play':
            # play now
            self.play_track(downloaded_track)

        if downloaded_track.upd_func is not None:
            downloaded_track.com.track_update.emit()

    def reset_queue(self, track: MusicTrack, playlist: Playlist):
        self.stop()
        if playlist is None:
            self.queue = [track]
        else:
            self.queue = playlist.tracks
            while self.queue[0] != track:
                self.queue.append(self.queue.pop(0))
        self.next()

    def play_track(self, track: MusicTrack):
        cached_ids = set(get_saved_tracks(self.cache_path))
        if track.id in cached_ids:
            mixer.music.stop()
            mixer.music.unload()
            if track.file_path:
                # track is downloaded
                mixer.music.load(track.file_path)
            else:
                # play cached
                try:
                    mixer.music.load(os.path.join(self.cache_path, f"{track.id}.mp3"))
                    pd("Player: playing", track)
                except FileNotFoundError:
                    pd("Player: CRITICAL ERROR:", track, " is not cached for some reason")
                    return -1

        self.loaded = True
        self.paused = False
        self.playing_track = track
        self.update_widget()

    def next(self):
        if self.queue:
            self.queue_pos += 1
            if self.queue_pos >= len(self.queue):
                self.queue_pos = 0

            # clean "play" tasks from queue
            if len(download_queue) > 1:
                while download_queue[1][1] == 'play':
                    download_queue.pop(1)


            # get cached ids
            cached_ids = set(get_saved_tracks(self.cache_path))
            next_track = self.queue[self.queue_pos]

            self.playing_track = next_track

            if next_track.file_path:
                self.loaded = True
                self.play_track(next_track)
            if next_track.id not in cached_ids:
                # track isn't loaded
                add_to_download_queue(next_track, 'play', self.cache_path, True)
                self.paused = True
                self.loaded = False
            self.update_widget()

    def stop(self):
        mixer.music.stop()
        mixer.music.unload()
        self.playing_track = None
        self.loaded = False

    def rewind(self, secs):
        if self.playing_track:
            mixer.music.stop()
            mixer.music.play(0, (secs * self.playing_track['duration']) // 1000)
            if self.paused:
                mixer.music.pause()
            self.play_start = secs * self.playing_track['duration']
            self.widget.update_pos()

    def pause(self):
        if self.playing_track and self.loaded:
            if self.paused:
                mixer.music.unpause()
                self.paused = False
            else:
                mixer.music.pause()
                self.paused = True
            self.update_widget()

    def update_widget(self):
        self.parent.truncate_all()
        if config.shuffle:
            self.parent.player_button_shuffle.setIcon(styles.get_icon("shuffle"))
        else:
            self.parent.player_button_shuffle.setIcon(styles.get_icon("no-shuffle"))

        if self.loaded:
            if self.paused:
                self.parent.player_button_play.setIcon(styles.get_icon('play'))
            else:
                self.parent.player_button_play.setIcon(styles.get_icon('pause'))
        else:
            if self.playing_track:
                self.parent.player_button_play.setIcon(styles.get_icon('update'))
            else:
                self.parent.player_button_play.setIcon(styles.get_icon('play'))

        if config.repeat:
            self.parent.player_button_repeat.setIcon(styles.get_icon("repeat"))
        else:
            self.parent.player_button_repeat.setIcon(styles.get_icon("no-repeat"))

        if self.playing_track:
            if self.playing_track.com:
                self.playing_track.com.track_update.emit()


class PlaylistView(QWidget):
    def __init__(self, parent, playlist, new_playlist=False):
        super().__init__()
        self.track_widget_list = list()
        self.playlist = playlist
        self.playlist.data_update()
        self.parent = parent
        uic.loadUi(os.path.join('ui', 'playlist_view.ui'), self)
        self.tracks_scroll_area.setWidget(QLabel("???"))
        self.set_icons()
        self.buttons_init()
        self.load_playlist()
        self.new = new_playlist

        self.tab = None  # playlist tab (will be set automatically)
        self.playlist_desc.key_press_event = self.playlist_desc.keyPressEvent
        self.playlist_desc.focus_out_event = self.playlist_desc.focusOutEvent
        self.playlist_desc.keyPressEvent = self.key_press_handler
        self.playlist_desc.focusOutEvent = self.desc_change

        self.new_slider_pos = -1  # special variable to keep slider position after reloading (cos)

    def reset_slider(self, event):
        if self.new_slider_pos != -1:
            if self.tracks_scroll_area.verticalScrollBar().value() != self.new_slider_pos:
                self.tracks_scroll_area.verticalScrollBar().setValue(self.new_slider_pos)
            else:
                self.new_slider_pos = -1
                for tr in self.track_widget_list:
                    tr.my_widget.hide()
                    tr.my_widget.show()

    def desc_change(self, event):
        self.update_playlist()
        self.playlist_desc.focus_out_event(event)

    def key_press_handler(self, event):
        # override qplaintextedit events.
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.update_playlist()
            return
        self.playlist_desc.key_press_event(event)

    def buttons_init(self):
        self.button_play.clicked.connect(self.play_playlist)

        self.playlist_title.editingFinished.connect(self.update_playlist)
        self.playlist_title.returnPressed.connect(self.update_playlist)
        self.button_edit.clicked.connect(self.edit_playlist)
        self.button_delete.clicked.connect(self.delete_playlist)

    def set_return_function(self, function):
        self.button_return.clicked.connect(lambda: function(self))

    def set_icons(self):
        self.button_play.setIcon(styles.get_icon("play"))
        self.button_edit.setIcon(styles.get_icon("edit"))
        self.button_download.setIcon(styles.get_icon("download"))
        self.button_export.setIcon(styles.get_icon("export"))
        self.button_delete.setIcon(styles.get_icon("remove"))
        self.button_back.setIcon(styles.get_icon("back"))
        self.button_return.setIcon(styles.get_icon("back-right"))

        self.props.setObjectName("scroll_area_content")

    def reload_playlist(self):
        self.new_slider_pos = self.tracks_scroll_area.verticalScrollBar().value()
        self.playlist = db.get_playlist(self.playlist.id)
        self.load_playlist()

    def load_playlist(self):
        self.playlist.data_update()
        self.tracks_scroll_area.setWidget(QLabel("Loading..."))
        widget = self.tracks_scroll_area.widget()
        self.track_widget_list = list()
        if self.playlist.tracks:
            if isinstance(widget, QLabel) or widget is None:
                # if layout inside scroll widget
                new_widget = QWidget()
                new_widget.setAutoFillBackground(True)
                new_layout = QVBoxLayout()
                new_layout.setAlignment(QtCore.Qt.AlignTop)
                new_widget.setLayout(new_layout)
                new_widget.setObjectName("scroll_area_content")
                new_widget.paintEvent = self.reset_slider
                self.tracks_scroll_area.setWidget(new_widget)
            widget = self.tracks_scroll_area.widget()

            for i, track in enumerate(self.playlist.tracks):
                # generate track widget
                add_widget = TrackWidget(self.parent, track, self.show_track_properties)

                self.track_widget_list.append(add_widget)
                widget.layout().addWidget(add_widget.get_widget())
                add_widget.truncate(self.tracks_scroll_area.width())
                # get updated track with hooked function
                self.playlist.tracks[i] = add_widget.track
        else:
            self.tracks_scroll_area.setWidget(QLabel("No tracks here.\n"
                                                     "Click plus button in the right menu to add some."))
        self.label_tracks.setText(str(self.playlist['track_count']))
        self.label_length.setText(duration_to_string(self.playlist['duration']))
        self.label_created.setText(str(datetime.fromtimestamp(self.playlist['created']).strftime("%d.%m.%y %H:%M")))

        self.playlist_title.setText(self.playlist.name)
        self.playlist_desc.document().setPlainText(self.playlist.get_param('description', ''))

    def update_playlist(self):
        # stop input
        self.playlist_title.setEnabled(False)
        self.playlist_title.setEnabled(True)
        self.playlist_desc.setEnabled(False)
        self.playlist_desc.setEnabled(True)

        # update data
        if self.playlist.name != self.playlist_title.text() or \
                self.playlist.get_param("description") != self.playlist_desc.toPlainText():
            self.playlist.data_update()
            self.playlist.name = self.playlist_title.text()
            self.playlist.data["description"] = self.playlist_desc.toPlainText()
            if self.new:
                new_id = db.add_playlist(self.playlist)
                self.new = False
                self.playlist = db.get_playlist(new_id)
            else:
                db.update_playlist(self.playlist.id, self.playlist)
            self.update_playlist_label()
            self.parent.update_all_playlists()

    def edit_playlist(self):
        if self.new:
            self.update_playlist()
        self.parent.activate_playlist_edit(self)

    def delete_playlist(self):
        dialog = MyQuestionDialog(self,
                                  f"Do you really want to delete {self.playlist.name}?\nThis action cannot be undone.",
                                  "Confirm delete", styles)
        dialog.exec_()
        if dialog.ok:
            self.parent.close_playlist(self)
            db.remove_playlist(self.playlist.id)
            self.parent.update_all_playlists()

    def update_playlist_label(self):
        if self in self.parent.tabs:
            label = self.playlist_title.text()
            if len(label) > 16:
                label = label[:16] + '...'
            self.parent.tab_widget.setTabText(self.parent.tabs.index(self), label)

    def truncate_all(self):
        global track_width
        if self.track_widget_list:
            track_width = [0, 0]
            for track_widget in self.track_widget_list:
                track_widget.truncate(self.tracks_scroll_area.width())

    def paintEvent(self, a0: QtGui.QPaintEvent) -> None:
        self.truncate_all()

    def show_track_properties(self, *args):
        pass

    def play_playlist(self):
        self.parent.set_player_queue(self.playlist)


class MainWindow(QMainWindow):
    def __init__(self):
        global downloader_on
        super().__init__()

        # init music player
        mixer.init()

        # setup configs
        self.config = self.update_config()
        pd("Config:", self.config)

        # init system variables
        self.current_results = []
        self.current_playlists = []

        self.window_width = self.width()
        self.com = Communication()
        self.com.add_result.connect(self.update_results)

        self.library_properties_track = None  # track shown in properties
        self.search_properties_track = None  # same

        self.editor_playlist = None  # editing playlist. If is not none means that edit mode is active

        # setup UI
        uic.loadUi(os.path.join('ui', 'desktop.ui'), self)
        self.player = SerendipityPlayer(self, self.player_widget, os.path.join(config.storage, 'cache'))
        self.tabs = [self.tab_playing, self.tab_library, self.tab_playing, self.tab_search, self.tab_settings]
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
        self.label_current_time = QLabel()
        self.label_duration = QLabel()
        self.hide_search_properties()
        self.player_init()
        self.tab_widget.currentChanged.connect(self.tab_update)
        self.playlist_viewer = PlaylistView(self, db.get_playlist(1))
        self.tab_playlists.layout().addWidget(self.playlist_viewer)
        self.playlist_search_set()
        self.create_search_filter_menu()
        self.finish_playlist_edit()
        self.setWindowTitle("Serendipity")

        # setup services
        self.dl_thread = threading.Thread(target=downloader, args=[self.download_finish])
        downloader_on = True
        self.dl_thread.start()
        self.upd_thread = threading.Thread(target=updater, args=(self.player.update_pos, 0.25))
        self.upd_thread.start()

        # create context menu for sort button
        self.playlists_sort_menu = self.create_playlists_sort_menu()
        self.playlists_sort_button.setMenu(self.playlists_sort_menu)
        self.reload_playlists(None)

        self.used_font_family = self.label.font().family()
        # temp
        self.debug_button1.clicked.connect(self.test)
        self.tab_widget.tabBar().setTabButton(0, QTabBar.RightSide, None)

    def test(self, some):
        self.label_current_time.hide()
        self.label_current_time.show()

    def on_context_menu(self, point):
        # show context menu
        self.popMenu.exec_(self.playlists_sort_button.mapToGlobal(point))

    def create_playlists_sort_menu(self):
        font = QFont(self.playlists_sort_button.font().family(), self.playlists_sort_button.font().pixelSize())
        menu = QMenu()
        menu.setObjectName("sort_menu")
        act1 = menu.addAction("Default")
        act1.setIcon(styles.get_icon("no-sort"))
        menu.addSeparator()

        act1 = menu.addAction("Alphabet")
        act1.setIcon(styles.get_icon("sort1"))

        act1 = menu.addAction("Alphabet")
        act1.setIcon(styles.get_icon("sort2"))

        menu.addSeparator()

        act1 = menu.addAction("Created")
        act1.setIcon(styles.get_icon("sort1"))

        act1 = menu.addAction("Created")
        act1.setIcon(styles.get_icon("sort2"))

        menu.addSeparator()

        act1 = menu.addAction("Tracks")
        act1.setIcon(styles.get_icon("sort1"))

        act1 = menu.addAction("Tracks")
        act1.setIcon(styles.get_icon("sort2"))

        menu.addSeparator()

        act1 = menu.addAction("Duration")
        act1.setIcon(styles.get_icon("sort1"))

        act1 = menu.addAction("Duration")
        act1.setIcon(styles.get_icon("sort2"))
        menu.setStyleSheet(styles.style)
        return menu

    def create_search_filter_menu(self):
        menu = QMyMenu()

        menu.setObjectName("sort_menu")
        act1 = menu.addAction("Search saved")
        act1.setCheckable(True)
        act1.setChecked(config.local_search)

        def temp1():
            config.local_search = act1.isChecked()
        act1.changed.connect(temp1)

        act2 = menu.addAction("Search online")
        act2.setCheckable(True)
        act2.setChecked(config.online_search)

        def temp2():
            config.online_search = act2.isChecked()
        act2.changed.connect(temp2)

        # act1.setIcon(styles.get_icon("no-sort"))
        menu.setStyleSheet(styles.style)
        self.search_filter_button.setMenu(menu)

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

        if downloaded_track.upd_func is not None:
            downloaded_track.upd_func()

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
            # play cached
            try:
                mixer.music.load(os.path.join(self.config['storage'], 'cache', f"{track.id}.mp3"))
                pd("Player: playing", track)
            except FileNotFoundError:
                pd("Player: CRITICAL ERROR:", track, " is not cached for some reason")

        # update icons
        update_function = None
        if self.playing_track:
            if self.playing_track.upd_func:
                update_function = self.playing_track.upd_func

        self.playing = True
        self.time_slider.setEnabled(True)
        mixer.music.play()
        self.play_start = 0
        self.label_duration.setText(duration_to_string(track['duration']))
        self.label_player_title.setText(track.get_param('title', 'Unnamed'))
        self.label_player_artist.setText(track.get_param('artist', 'Unknown artist'))
        self.playing_track = track
        self.update_player()

        if update_function:
            update_function()

    def player_init(self):
        """
        Init main player widget.
        """
        self.volume_slider.setFocusPolicy(QtCore.Qt.NoFocus)
        self.time_slider.setFocusPolicy(QtCore.Qt.NoFocus)
        self.player_volume.layout().addWidget(self.volume_slider)
        self.player_time.addWidget(self.label_current_time)
        self.player_time.addWidget(self.time_slider)
        self.player_time.addWidget(self.label_duration)
        self.player_time.setStretch(0, 1)
        self.player_time.setStretch(1, 7)
        self.player_time.setStretch(2, 1)

        self.player_button_prev.setIcon(styles.get_icon("prev"))
        self.player_button_next.setIcon(styles.get_icon("next"))

        self.player_button_play.clicked.connect(self.player.pause)
        self.player_button_next.clicked.connect(self.player.next)
        self.player_button_shuffle.clicked.connect(self.player_shuffle)
        self.player_button_repeat.clicked.connect(self.player_repeat)

        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(int(self.config['volume'] * 100))
        self.change_volume()
        self.time_slider.setMaximum(1000)
        # self.time_slider.release_func = self.player_rewind
        self.volume_slider.valueChanged.connect(self.change_volume)

        self.update_player()
        # self.play_next()
        self.truncate_all()
        self.label_player_title.setText("No Track")

        self.player.update_widget()

    def update_player(self):
        self.truncate_all()
        # if self.config['shuffle']:
        #     self.player_button_shuffle.setIcon(styles.get_icon("shuffle"))
        # else:
        #     self.player_button_shuffle.setIcon(styles.get_icon("no-shuffle"))
#
        # if self.playing:
        #     self.player_button_play.setIcon(styles.get_icon("pause"))
        # else:
        #     self.player_button_play.setIcon(styles.get_icon("play"))
#
        # if self.config['repeat']:
        #     self.player_button_repeat.setIcon(styles.get_icon("repeat"))
        # else:
        #     self.player_button_repeat.setIcon(styles.get_icon("no-repeat"))
#
        # if self.playing_track:
        #     if self.playing_track.upd_func:
        #         self.playing_track.upd_func()

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
        config.repeat = not config.repeat
        self.update_player()
        self.save_config()

    def player_shuffle(self):
        config.shuffle = not config.shuffle
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
        # reset buttons
        f = None
        if self.playing_track:
            if self.playing_track.upd_func:
                f = self.playing_track.upd_func
        self.playing_track = None
        self.playing = False
        if f:
            f()

        mixer.music.stop()
        mixer.music.unload()

        self.update_player()
        print(type(playable))
        if isinstance(playable, MusicTrack):
            pd('Queue_manager: Adding:', playable, 'to queue')
            self.play_queue = [playable]
        elif isinstance(playable, Playlist):
            pd('Queue_manager: Adding:', playable.name, len(playable.tracks), 'to queue')
            self.play_queue = playable.tracks.copy()
        else:
            pd("Queue_manager: ERROR incorrect input")
            return -1
        self.queue_pos = -1

        # get currently cached tracks
        cached_ids = set(get_saved_tracks(os.path.join(self.config['storage'], 'cache')))

        print(self.play_queue)
        new_ids = [i.id for i in self.play_queue]
        for cached in tuple(cached_ids):
            if cached not in new_ids or cached < 1:
                cached_ids.remove(cached)
                pd('Cache_handler: removing', cached, 'from cache.')
                try:
                    os.remove(os.path.join(self.config['storage'], 'cache', str(cached) + ".mp3"))
                except FileNotFoundError:
                    pd("Cache_handler: file not found?.. ok skip")
                    pass
        self.play_next()

    def play_next(self):
        global download_queue
        update_function = None
        if self.playing_track:
            if self.playing_track.upd_func:
                update_function = self.playing_track.upd_func

        mixer.music.stop()
        mixer.music.unload()
        self.time_slider.setEnabled(False)
        self.playing_track = None
        self.playing = False

        if not self.play_queue:
            pd("Queue_manager: queue end")
            self.label_current_time.setText("--:--")
            self.label_duration.setText("--:--")
            self.time_slider.setValue(0)
            self.label_player_title.setText("No track")
            self.label_player_artist.setText('')
            self.update_player()
            if update_function:
                print("update_function")
                update_function()
            return 0
        else:
            pd('Queue_manager: next track')
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

            pd("Queue_manager: next track is", cur_track)
            # get currently cached tracks
            cached_ids = set(get_saved_tracks(os.path.join(self.config['storage'], 'cache')))
            if cur_track.file_path or cur_track.id in cached_ids:
                # if ready to play
                self.play_track(cur_track)
                self.awaiting_download = False

            # caching
            for i in range(self.queue_pos, min(len(self.play_queue), 1 + self.config["queue_cache"] + self.queue_pos)):
                cached_ids = set(get_saved_tracks(os.path.join(self.config['storage'], 'cache')))
                elem = self.play_queue[i]  # get track
                if not elem.file_path:
                    # if file is not stored
                    if elem.id not in cached_ids:
                        # if not cached yet
                        if elem not in [task[0] for task in download_queue]:
                            # if not awaiting download
                            if i != self.queue_pos:
                                add_to_download_queue(elem, 'cache', os.path.join(self.config['storage'], 'cache'))
                            else:
                                # add play task for current track if it needs to be downloaded
                                self.awaiting_download = True
                                add_to_download_queue(elem, 'play', os.path.join(self.config['storage'], 'cache'), True)
                                self.next_download_message(True)
                                self.label_player_title.setText("Downloading...")
                                self.label_player_artist.setText('')
            self.truncate_all()
            if update_function:
                update_function()

    # Playlists

    def reload_playlists(self, sorting_key=None):
        all_pl = [db.get_playlist(i) for i in db.find_playlist(True)]
        if sorting_key:
            all_pl.sort(key=sorting_key)
        pd("Playlists: found", len(all_pl))
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

    # noinspection PyUnresolvedReferences
    def open_playlist(self, playlist_view):
        """
        Open playlist in new tab.
        """
        # setup return function
        playlist_view.set_return_function(self.close_playlist)

        # create tab
        self.tab_widget.insertTab(3, playlist_view, playlist_view.playlist.name)
        close_button = QToolButton()
        close_button.setIcon(styles.get_icon("close"))
        close_button.setMaximumSize(16, 16)
        close_button.clicked.connect(lambda: self.close_playlist(playlist_view))
        close_button.setObjectName("small_button")
        self.tab_widget.tabBar().setTabButton(3, QTabBar.RightSide, close_button)
        self.tabs.insert(3, playlist_view)
        self.tab_widget.setCurrentIndex(3)
        # update_label
        playlist_view.update_playlist_label()

    def close_playlist(self, tab):
        if 2 < self.tab_widget.currentIndex() < len(self.tabs) - 2:
            self.tab_widget.setCurrentIndex(2)
        self.tab_widget.removeTab(self.tabs.index(tab))
        self.tabs.remove(tab)
        if tab == self.editor_playlist:
            self.editor_playlist = None
            self.finish_playlist_edit()

    def update_all_playlists(self):
        # reload all playlists
        for tab in self.tabs:
            if isinstance(tab, PlaylistView):
                tab.reload_playlist()
        self.reload_playlists()

    def playlist_search_set(self):
        self.update_all_playlists()
        self.playlist_menu.show()
        self.playlist_viewer.hide()

    def playlist_view_set(self):
        self.playlist_menu.hide()
        self.playlist_viewer.show()

    def new_playlist(self):
        self.open_playlist(PlaylistView(self, Playlist(0, "New playlist"), True))

    def activate_playlist_edit(self, playlist):
        self.tab_widget.setTabText(len(self.tabs) - 2, "Editor")
        self.tab_widget.setCurrentIndex(len(self.tabs) - 2)
        self.warning_widget_frame.show()
        self.search_request.setText('')
        self.label_editing_playlist.setText('Editing playlist: ' + playlist.playlist.name)
        self.set_search_label('You are currently editing playlist.\nSearch something in your library or in the web.\n'
                              'Use "+" button to add track to your playlist.\nWhen ready, click "Done" button.')
        self.editor_playlist = playlist

    def finish_playlist_edit(self):
        self.tab_widget.setTabText(len(self.tabs) - 2, "Search")
        self.warning_widget_frame.hide()
        self.set_search_label('Nothing here yet...')
        self.search_request.setText('')
        if self.editor_playlist:
            self.tab_widget.setCurrentIndex(self.tabs.index(self.editor_playlist))
            self.editor_playlist = None

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
        self.button_edit_finish.clicked.connect(self.finish_playlist_edit)
        self.playlists_new_button.clicked.connect(self.new_playlist)

    def load_styles(self, style):
        """
        Load and apply a new style.
        """
        # styles = StyleManager("default-dark")
        # styles.load_style("style.qss")
        # # styles.load_palette("palette.json")
        # styles.load_colors("palette.json")
        # self.setStyleSheet(styles.style)
        # # self.setPalette(styles.palette)

        styles.load_style('style.qss')
        styles.load_colors("palette.json")
        self.setStyleSheet(styles.style)
        self.search_button.setIcon(styles.get_icon("search"))
        self.properties_button.setIcon(styles.get_icon("close"))
        self.playlists_new_button.setIcon(styles.get_icon("add"))
        self.playlists_sort_button.setIcon(styles.get_icon("sort"))

    def debug(self, *args, **kwargs):
        print('debug')

    def player_truncate(self, metrics):
        # truncate player labels
        return 0
        labels = [self.label_player_title, self.label_player_artist]
        if self.player.playing_track:
            texts = [self.playing_track.get_param('title', 'Unnamed'),
                     self.playing_track.get_param('artist', 'Unknown artist')]
        else:
            if not self.player.loaded:
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
                try:
                    result.truncate(self.search_scroll_area.width(), metrics)
                except RuntimeError:
                    pass
        # truncate playlist text
        if self.current_playlists:
            pl_width = [0, 0]
            for playlist in self.current_playlists:
                try:
                    playlist.truncate(self.playlists_scroll_area.width(), metrics)
                except RuntimeError:
                    pass

    def hide_search_properties(self):
        self.search_properties.hide()
        self.search_properties_track = None
        self.truncate_all()

    def update_search_properties(self, new_track):
        """
        Update track on the right-side properties menu.
        """
        # check if something is already viewed
        if self.search_properties_track:
            if new_track.file_link == self.search_properties_track.file_link:
                # if new data gained, replace now
                self.search_properties_track = new_track
                self.show_properties_button.click()

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
                # print(t.file_link, list([res.track.file_link for res in self.current_results]))
                if t.file_link not in [res.track.file_link for res in self.current_results]:
                    self.add_search_result(t, scr_name == 'local_db')
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
        if self.config["local_search"]:
            self.set_search_label('Searching...')
            result_queue["local_db"] = [[], False]
            any_results = False

            for track in (db.find_track(False, artist=search_text) + db.find_track(False, title=search_text) +
                          db.find_track(False, data=search_text)):
                any_results = True
                result_queue["local_db"][0].append(db.get_track(track))
                self.com.add_result.emit()

            search_text = search_text.title()

            for track in (db.find_track(False, artist=search_text) + db.find_track(False, title=search_text) +
                          db.find_track(False, data=search_text)):
                any_results = True
                result_queue["local_db"][0].append(db.get_track(track))
                self.com.add_result.emit()

            if not any_results:
                self.set_search_label('Nothing found.\nCheck search keywords or change filters.')

        if search_text:
            if self.config["online_search"]:
                if not self.config['local_search']:
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

    def add_search_result(self, track, is_local):
        if not db.find_track(True, file_link=track.file_link) or is_local:
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
            playlist = None  # specify playlist to add (required for editor mode)
            if self.editor_playlist:
                playlist = self.editor_playlist.playlist
            add_widget = ResultWidget(self, track, self.label.font(), self.show_search_properties, playlist)

            self.current_results.append(add_widget)
            widget.layout().addWidget(add_widget.get_widget())
            add_widget.truncate(self.search_scroll_area.width())


def load_fonts_from_dir(directory):
    families = set()
    for fi in QtCore.QDir(directory).entryInfoList(["*.ttf"]):
        _id = QtGui.QFontDatabase.addApplicationFont(fi.absoluteFilePath())
        families |= set(QtGui.QFontDatabase.applicationFontFamilies(_id))
    return families


app = QApplication(sys.argv)
# check if setup is required
config = Config()

QtGui.QFontDatabase.addApplicationFont(os.path.join('..', 'styles', config.theme, 'font0.ttf'))
styles = StyleManager(config.theme)

if config.first_run:
    ex = SetupWindow()
    ex.show()
    app.exec_()
if not config.first_run:
    db = MusicDatabase(os.path.join(config.storage, 'local.db'))
    ex = MainWindow()
    ex.show()
    app.exec_()
    db.close()

