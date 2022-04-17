import requests
from bs4 import BeautifulSoup
import sys
sys.path.insert(0,'..')
from main import MusicTrack, string_to_duration


def get_music_list(search_request):
    # search by given name
    for page in range(1, 5):
        try:
            response = requests.get(f"https://page.ligaudio.ru/mp3/{search_request}/{page}")
        except requests.exceptions.ConnectionError:
            return
        if response:
            soup = BeautifulSoup(response.text, features="html.parser")
            found_links = soup.findAll('div', {'itemtype': "http://schema.org/MusicRecording"})

            for found_link in found_links:
                try:
                    dur = found_link.find_next('span', {'class': 'd'}).text
                    title = found_link.find_next('span', {'class': 'title'}).text
                    author = found_link.find_next('span', {'class': 'autor'}).text
                    href = found_link.find_next('a', {'class': 'down'})
                    yield MusicTrack(-1, 'https:' + href['href'] + '?play', '', False, duration=string_to_duration(dur),
                                     title=title, artist=author)

                except KeyError:
                    continue
    yield None
    return 0
