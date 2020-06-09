import requests

def count_words_at_url(url):
    resp = requests.get(url)
    value = len(resp.text.split())
    print(value)
    return value

def print_stuff(to_print):
    for item in to_print:
        print(str(item))
