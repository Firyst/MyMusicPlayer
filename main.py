import importlib
import os
import hashlib
import time
from importlib import import_module


# this file contains some basic functions and classes used everywhere


def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def string_to_duration(string):
    times = list(map(int, string.split(':')))[::-1]
    dur = 0
    for t in range(len(times)):
        dur += times[t] * (60 ** t)
    return dur


def duration_to_string(seconds):
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    if minutes:
        if hours:
            return str(hours) + ':' + str(minutes).rjust(2, '0') + ':' + str(seconds).rjust(2, '0')
        return str(minutes) + ':' + str(seconds).rjust(2, '0')
    return '0:' + str(seconds).rjust(2, '0')


def generate_unique_key(name):
    hash = hashlib.md5(name.encode())
    print(int(hash.hexdigest(), 16))


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


class MusicTrack:
    def __init__(self, track_id, file_link, is_local, **kwargs):
        """file_link should be a complete url if if_local=True, otherwise a path to local file"""
        self.id = track_id
        self.is_local = is_local
        self.file = file_link
        self.file_hash = ''
        self.metadata = dict()
        known_keywords = ['title', 'album', 'artist', 'composer', 'date', 'discnumber', 'tracknumber', 'genre',
                          'duration', 'bitrate', 'data', 'added']
        for kwarg in kwargs:
            if kwarg in known_keywords:
                self.metadata[kwarg] = kwargs[kwarg]
            else:
                if kwarg == "file_hash":
                    self.file_hash = kwargs["file_hash"]
                raise TypeError(f' "{kwarg}" no such keyword parameter.'
                                f' Available types are:\n{", ".join(known_keywords)}')

    def __getitem__(self, item):
        return self.metadata[item]

    def get_param(self, keyword, empty_value=None):
        """returns parameter if present, else empty_value"""
        return self.metadata.get(keyword, empty_value)

    def add_param(self, **kwargs):
        """adds or re-writes metadata parameter"""
        for kwarg in kwargs:
            self.metadata[kwarg] = kwargs[kwarg]

    def metadata_check(self):
        """Ints all int-like data"""
        int_keywords = ["discnumber", "tracknumber", "duration", "bitrate", "added"]
        if 'added' not in self.metadata:
            # actually useless
            self.metadata['added'] = int(time.time())
        for kw in int_keywords:
            if kw in self.metadata:
                self.metadata[kw] = int(self.metadata[kw])

    def __repr__(self):
        return f"MusicTrack({self.id}, {self.file}, {self.file_hash}, {self.is_local}, {self.metadata})"


class Playlist:
    def __init__(self, playlist_id, name, **kwargs):
        """
        Playlist object.
        KW_parameters: description, track_count, duration, genre
        """
        self.id = playlist_id
        self.name = name
        self.data = dict()
        self.tracks = []
        known_keywords = ["description", "track_count", "duration", "genre", "created"]
        for kwarg in kwargs:
            if kwarg in known_keywords:
                self.data[kwarg] = kwargs[kwarg]
            else:
                raise TypeError(f' "{kwarg}" no such keyword parameter.'
                                f' Available types are:\n{", ".join(known_keywords)}')

    def __repr__(self):
        return f"Playlist({self.id}, {self.name}, Tracks: {self.data['track_count']}, Len: {self.data['duration']})"

    def __getitem__(self, item):
        return self.data[item]

    def get_param(self, keyword, empty_value=None):
        """returns parameter if present, else empty_value"""
        return self.data.get(keyword, empty_value)

    def add_param(self, **kwargs):
        """adds or re-writes metadata parameter"""
        for kwarg in kwargs:
            self.data[kwarg] = kwargs[kwarg]

    def add_track(self, track):
        """adds track to playlist"""
        if isinstance(track, MusicTrack):
            self.tracks.append(track)
        else:
            raise ValueError("Attempt to add something but not a MusicTrack")

    def data_update(self):
        """recounts duration"""
        self.data['duration'] = sum(map(lambda x: x.get_param("duration", 0), self.tracks))
        self.data['track_count'] = len(self.tracks)
        if 'created' not in self.data:
            # actually useless
            self.data['created'] = int(time.time())
        else:
            self.data['created'] = int(self.data['created'])
