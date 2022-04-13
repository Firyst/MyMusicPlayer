from bs4 import BeautifulSoup
import requests
import audio_metadata
import urllib.request


def get_sources(requested_data):

    with open('sources', 'r') as file:
        data = list(file.read().split("\n"))
    for i, source in enumerate(data):
        data[i] = source.format(str(requested_data))
    return data


def get_files(request, file_format, protocol, args):
    for source in get_sources(request):
        response = requests.get(source)
        if response:
            print("success")
            soup = BeautifulSoup(response.text, features="html.parser")
            found_links = soup.findAll("a")
            print(len(found_links))
            found_files = []
            for found_link in found_links:
                try:
                    href = found_link['href']
                    name = found_link['title']
                except KeyError:
                    continue
                try:
                    if href[(len(file_format) * -1):] == file_format:  # check file format
                        href = protocol + ':' + href + args
                        print(name)
                        found_files.append((name[9:-1], href))
                except IndexError:
                    continue
            print(found_files)
            print(len(found_files))
            return found_files


def get_files_data(file_links, file_format):
    # gets all files data such as bitrate, length etc.
    for file_index, file_link in enumerate(file_links[:5]):
        filename = f"temp/track{file_index}.{file_format}"
        track = requests.get(file_link[1])
        with open(filename, 'wb') as f:
            f.write(track.content)

        # print(audioread.available_backends())
        # with audioread.audio_open(filename) as f:
        #     print(f.channels, f.samplerate, f.duration)
        # urllib.request.urlcleanup()

        metadata = audio_metadata.load(filename)

        print(metadata)



links = get_files("Slipknot Devil In I", 'mp3', 'https', '?play')
print(links)
get_files_data(links, 'mp3')
