import importlib
import os
import hashlib
from importlib import import_module


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
    def __init__(self, track_id, file, is_local, **kwargs):
        # is_local=True: file should be DIRECT link to web file
        # is_local=False: filepath + filename
        # metadata=dict()
        self.id = track_id
        self.file = file
        self.is_local = is_local
        self.metadata = dict()
        known_keywords = ['author', 'name', 'duration', 'sample_rate', 'year', ]
        for kwarg in kwargs:
            if kwarg in known_keywords:
                self.metadata[kwarg] = kwargs[kwarg]
            else:
                raise TypeError(f"No such keyword parameter. Available types are:\n{' '.join(known_keywords)}")

    def get_param(self, keyword):
        # returns parameter if present, else None
        return self.metadata.get(keyword, None)

    def add_param(self, **kwargs):
        # adds or re-writes metadata parameter
        for kwarg in kwargs:
            self.metadata[kwarg] = kwargs[kwarg]


# print(get_scrappers())
