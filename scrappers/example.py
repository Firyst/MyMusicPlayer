# This is an example of music scrapper
# to use a new scrapper in MyMusicPlayer just create a new file with wanted name
# program scans those files automatically
# there should be a "get_music_list(search_name)" function to call
# example is given below

# import MusicTrack type
from main import MusicTrack


# file should be named as you want it to be shown in the app

def get_music_list(search_request):
    result = []
    # search by given name
    # you can do whatever you want (get results from web, your own db or even local storage)
    # write result
    new_metadata = {'author': 'Track author', 'name': 'Track name', 'duration': 112, 'year': 1999, 'sample_rate': 320}
    # create track with id=0 (it will be assigned later automatically)
    my_track = MusicTrack(0, "file_link", False, new_metadata)
    result.append(my_track)
    # list list of MusicTrack objects
    return result
