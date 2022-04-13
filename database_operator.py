# local database operator

import sqlite3
import time
from main import MusicTrack, Playlist, md5
import json
import os

TRACK_KEYWORDS = ['title', 'album', 'artist', 'composer', 'date', 'discnumber', 'tracknumber', 'genre',
                  'duration', 'bitrate', 'data', 'added']

PL_KEYWORDS = ['description', 'track_count', 'genre', 'created']


def read_config():
    with open("sql_config.json") as j:
        return json.loads(j.read())


def write_config(d):
    with open("sql_config.json", 'w') as j:
        j.write(json.dumps(d))


class MusicDatabase:
    # sql operator
    def __init__(self, database, create_new=False):
        self.cfg = read_config()
        self.con = sqlite3.connect(database)
        self.cur = self.con.cursor()
        if create_new:
            self.create_db_structure()

    def exec_w(self, req):
        """
        Execute an SQL query with commit.
        """
        self.cur.execute(req).fetchall()
        self.con.commit()

    def exec_r(self, req):
        """
        Fetch all results.
        """
        return self.cur.execute(req).fetchall()

    def create_db_structure(self):
        for query in self.cfg['create']:
            self.exec_w(query)

    def get_track(self, track_id):
        """
        Returns MusicTrack object by ID.
        """

        try:
            track_data = self.exec_r(f'SELECT * FROM tracks WHERE id = {track_id}')[0]
        except IndexError:
            return None
        print(track_data)
        if track_data[2]:
            # if file_name is used (local)
            new_track = MusicTrack(track_id, track_data[2], True)
        else:
            new_track = MusicTrack(track_id, track_data[1], False)
        metadata = {"file_hash": track_data[3]}
        for i in range(len(TRACK_KEYWORDS)):
            if track_data[5 + i]:
                metadata[TRACK_KEYWORDS[i]] = track_data[5 + i]

        new_track.metadata = metadata
        new_track.metadata_check()
        return new_track

    def find_track(self, exact_search, **kwargs):
        """
        Select tracks with given properties.
        Exact search uses "=", non-exact uses "like"
        """

        req = "SELECT id FROM tracks WHERE "
        if exact_search:
            req = req + ' AND '.join(map(lambda x: f'{x}="{kwargs[x]}"', kwargs.keys()))
        else:
            req = req + ' AND '.join(map(lambda x: f'{x} LIKE "%{kwargs[x]}%"', kwargs.keys()))
        print(req)
        return list(map(lambda x: x[0], self.exec_r(req)))

    def add_track(self, track, override_id='NULL', add_time=int(time.time())):
        """
        Add track for the first time.
        Returns ID.
        """

        if track.is_local:
            req = f'INSERT INTO tracks VALUES({override_id}, "", "{track.file}",' \
                  f'"{md5(track.file)}", {os.path.getsize(track.file)}, '
        else:
            req = f'INSERT INTO tracks VALUES({override_id}, "{track.file}", "",' \
                  f'"{md5(track.file)}", {os.path.getsize(track.file)}, '

        # append main data of track
        all_args = dict()
        for kw in TRACK_KEYWORDS[:-1]:
            req = req + f'"{track.get_param(kw, "")}", '
            if track.get_param(kw, None):
                all_args[kw] = track.get_param(kw)
        # append timestamp
        req = req + f'"{add_time}")'

        self.exec_w(req)
        return self.find_track(True, **all_args)[0]

    def update_track(self, update_id, updated_track):
        """
        Update track with specific ID with new MusicTrack.
        """
        add_time = int(self.exec_r(f"SELECT added FROM tracks WHERE id = {update_id}")[0][0])
        self.remove_track(update_id)
        self.add_track(updated_track, override_id=update_id, add_time=add_time)

    def remove_track(self, track_id):
        """
        Remove track by ID.
        """
        self.exec_w(f"DELETE FROM tracks WHERE id={track_id}")

    def add_playlist(self, playlist, override_id='NULL', create_time=int(time.time())):
        """
        Add playlist to database and make links for each track.
        Returns ID.
        """

        req = f'INSERT INTO playlists VALUES({override_id}, "{playlist.name}", ' \
              f'"{playlist.get_param("description", "")}",' \
              f'{playlist["track_count"]}, "{playlist.get_param("genre", "")}", {create_time})'
        self.exec_w(req)

        # prepare data to get generated playlist id
        search_data = playlist.data
        search_data.pop('duration')
        search_data.pop('created')
        search_data['name'] = playlist.name
        print(search_data)
        new_id = self.find_playlist(True, **search_data)[0]

        # add tracks into playlist
        for pos, track in enumerate(playlist.tracks):
            self.exec_w(f"INSERT INTO playlist_tracks VALUES({new_id}, {track.id}, {pos})")
        return new_id

    def get_playlist(self, playlist_id):
        """
        Get playlist by ID.
        """
        try:
            playlist_data = self.exec_r(f'SELECT * FROM playlists WHERE id = {playlist_id}')[0]
            res_playlist = Playlist(playlist_id, playlist_data[1])

            # parse playlist data
            data = dict()
            for i in range(len(PL_KEYWORDS)):
                if playlist_data[i + 2]:
                    data[PL_KEYWORDS[i]] = playlist_data[i + 2]
            res_playlist.data = data

            # add all tracks
            tracks = self.exec_r(
                f"SELECT id FROM tracks INNER JOIN playlist_tracks ON playlist_id = {playlist_id} AND "
                f"track_id = id ORDER BY position")
            print(tracks)
            for track_id in tracks:
                res_playlist.add_track(self.get_track(track_id[0]))
            res_playlist.data_update()
            return res_playlist

        except IndexError:
            return None

    def find_playlist(self, exact_search, **kwargs):
        """
        Select tracks with given properties.
        Exact search uses "=", non-exact uses "like"
        """
        req = "SELECT id FROM playlists WHERE "
        if exact_search:
            req = req + ' AND '.join(map(lambda x: f'{x}="{kwargs[x]}"', kwargs.keys()))
        else:
            req = req + ' AND '.join(map(lambda x: f'{x} LIKE "%{kwargs[x]}%"', kwargs.keys()))
        print(req)
        return list(map(lambda x: x[0], self.exec_r(req)))

    def update_playlist(self, update_id, updated_playlist):
        """
        Rewrite existing playlist and make all links.
        """
        add_time = int(self.exec_r(f"SELECT created FROM playlists WHERE id = {update_id}")[0][0])
        self.remove_playlist(update_id)
        self.add_playlist(updated_playlist, override_id=update_id, create_time=add_time)

    def remove_playlist(self, playlist_id):
        """
        Remove playlist and all its links.
        """
        self.exec_w(f"DELETE FROM playlists WHERE id={playlist_id}")
        self.exec_w(f"DELETE FROM playlist_tracks WHERE playlist_id={playlist_id}")


a1 = """CREATE TABLE tracks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_link   STRING,
    file_path   STRING,
    file_hash   STRING  UNIQUE ON CONFLICT IGNORE,
    file_size   INT,
    title       STRING,
    album       STRING,
    artist      STRING,
    composer    STRING,
    date        STRING,
    discnumber  STRING,
    tracknumber STRING,
    genre       STRING,
    duration    INT,
    bitrate     INT,
    data        TEXT,
    added       INT
);
"""

a2 = """CREATE TABLE playlists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        STRING,
    description TEXT,
    track_count INT,
    genre       STRING,
    created     INT
);
"""

a3 = """CREATE TABLE playlist_tracks (
    playlist_id INT REFERENCES playlists (id) ON DELETE CASCADE,
    track_id    INT REFERENCES tracks (id) ON DELETE CASCADE,
    position    INT
);
"""

write_config({'create': [a1, a2, a3]})

my_db = MusicDatabase("test.db", False)
# tt = MusicTrack(0, "testfile", True, title="track4", artist="me", duration=123, album="first")
# print(my_db.add_track(tt))
# my_db.update_track(1, tt)
# print(my_db.find_track(False, album="grey "))
# print(my_db.get_track(1))
my_pl = Playlist(0, "My-Playlist", description="Мой плейлист 1", genre="дрянь")
my_pl.add_track(my_db.get_track(3))
my_pl.add_track(my_db.get_track(1))

my_pl.data_update()
# print(my_db.add_playlist(my_pl))
print(my_db.update_playlist(9, my_pl))

print(my_db.get_playlist(9))
print(my_db.find_playlist(False, description="лист"))
