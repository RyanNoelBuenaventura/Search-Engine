import hashlib
import os
import sys

from bs4 import BeautifulSoup
from nltk.stem import PorterStemmer
import json


inverted_index = {} #key hashed stems value list with path, frequency count.
indexed_doc_cnt = [0]
def Get_Next_File():
    """
    given the path open, go through all the folders then inside those folders go through
    all the files and read them. Each file is in json formate and we can extract the
    url and the contents of the page from there they are sent to parser
    :return:
    """
    path = """C:\\Users\\Nicol Umanzor\\PythonProject\\analyst\\ANALYST"""
    for folder in os.listdir(path):
        for file in os.listdir(os.path.join(path, folder)):
            with open(os.path.join(path, folder, file), 'r') as json_file:
                for line in json_file:
                    file_content = json.loads(line)
                    url = file_content['url']
                    page_content = file_content['content']
                    parse(page_content, url)



def parse(page_content, url):
    """
    this extracts paragraphs and strong html tags from the page content
    then using porter stemming we turn each work into it's root words hash it and set as the
    key in a dictionary
    :param page_content: the contents of the page from the analyst file
    :param url: the url of the page from the analyst file
    :return:
    """
    text = (BeautifulSoup(page_content, 'html.parser'))
    words_in_html = text.find_all(['p', 'strong'])
    for t in words_in_html:
        for word in t.text.split():
            hashed_stem, Hashed_url = word_hasher(word, url)
            indexer(hashed_stem, Hashed_url)


def word_hasher(word, url):
    word_changes = word.lower().replace('.', '')
    # might need to remove more stuff from work like ', \u' and nums
    stem = PorterStemmer().stem(word_changes)
    hashed_stem = hashlib.md5(stem.encode('utf-8')).hexdigest()
    hashed_url = hashlib.md5(url.encode('utf-8')).hexdigest()

    print(stem, url)
    return hashed_stem, hashed_url


def indexer(hashed_stem, Hashed_url):
    if hashed_stem in inverted_index.keys():
        if Hashed_url in inverted_index[hashed_stem].keys():
            inverted_index[hashed_stem][Hashed_url] += 1
        else:
            inverted_index[hashed_stem][Hashed_url] = 1
            indexed_doc_cnt[0] += 1
    else:
        inverted_index[hashed_stem] = {Hashed_url: 1}

def report():
    """this should make and write to the file i added a try and except in general
        just incase to keep the crawel from crashing since this is untested"""

    total_unique_tokens = len(inverted_index.keys())
    try:
        with open('Report.txt', 'w') as f:
            # longest url and the number of words
            f.write(
                f"total unique tokens {total_unique_tokens}\n")
            f.write("-" * 20 + "\n")

            # top 50 words with their number
            f.write(f"Total indexed pages without intersections {indexed_doc_cnt[0]}\n")

            f.write("-" * 20 + "\n")

            f.write(f"Total size is {sys.getsizeof(inverted_index)} in bytes\n")

            f.write("-" * 20 + "\n")

    except Exception as e:
        print(f"Error writing to Report.txt: {e}")

Get_Next_File()
report()
