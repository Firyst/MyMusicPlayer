# This is an example of music scrapper
# to use a new scrapper in MyMusicPlayer just create a new file with wanted name
# program scans those files automatically
# there should be a "get_music_list(search_name)" function to call
# example is given below

# import MusicTrack type
from serendipity.main import MusicTrack


# file should be named as you want it to be shown in the app

def get_music_list(search_request):
    # return results by given request
    # you can do whatever you want (get results from web, your own db or even local storage)

    # create track with id=0 (it will be assigned later automatically)

    for i in range(0):
        my_track = MusicTrack(0, "file_link", False, author='author', name='name', duration=112, sample_rate=320,
                              year=1999)
        yield my_track

    return  # let the program now search is now finished
