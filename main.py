import importlib
import os
import hashlib
from importlib import import_module

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
    def __init__(self, track_id, file, is_local, metadata=None):
        # is_local=True: file should be DIRECT link to web file
        # is_local=False: filepath + filename
        # metadata=dict()
        self.id = track_id
        if metadata is None:
            self.metadata = dict()
        else:
            if type(metadata) == dict:
                self.metadata = metadata
            else:
                raise TypeError('Track metadata should be dict')

    def get_param(self, keyword):
        # returns parameter if present, else None
        return self.metadata.get(keyword, None)

    def add_param(self, **kwargs):
        # adds or re-writes metadata parameter
        for kwarg in kwargs:
            self.metadata[kwarg] = kwargs[kwarg]



# print(get_scrappers())
generate_unique_key("heou")
print('474882478560272308151711149012156580409737478144.')