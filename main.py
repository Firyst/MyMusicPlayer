import importlib
import os
from importlib import import_module


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


# print(get_scrappers())