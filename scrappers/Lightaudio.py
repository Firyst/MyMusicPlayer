import requests
from bs4 import BeautifulSoup


def get_music_list(search_request):
    # search by given name
    file_format = 'mp3'
    response = requests.get(f"https://page.ligaudio.ru/mp3/{search_request}")
    if response:
        soup = BeautifulSoup(response.text, features="html.parser")
        found_links = soup.findAll("a")
        # print(len(found_links))
        found_files = []
        for found_link in found_links:
            try:
                href = found_link['href']
                name = found_link['title']
            except KeyError:
                continue
            try:
                if href[(len(file_format) * -1):] == file_format:  # check file format
                    href = 'https:' + href + '?play'
                    # print(name)
                    found_files.append((name[9:-1], href))
            except IndexError:
                continue
        print(found_files)
        # print(len(found_files))
        return found_files

# print(get_music_list("Мельница Снег"))