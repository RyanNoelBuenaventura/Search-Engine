import hashlib
import os
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from nltk.stem import PorterStemmer
import json
import ast
import sqlite3


# in postings we might put the tf-idf of that term in that doc
    # we can hard code the num of docs for tf-idf
    # or do one pass and then go through everything again and update tf-idf ounce we know it
# the file names are already in hex value
# when keeping an index file have it sorted from alphabetically then make sure any new elements are also sorted that way
# writing to new index data to the file only moves forward
#  index like {"key word": [hex filename, url, [byte place of word], ]
inverted_index = {} #key hashed stems value list with path, frequency count.
indexed_doc_cnt = [0]
helper_files = ["FileID_FilePath.txt"]
file_index_alphabet = {}
sql_cursor = None

def Get_Next_File():
    """
    given the path open, go through all the folders then inside those folders go through
    all the files and read them. Each file is in json formate and we can extract the
    url and the contents of the page from there they are sent to parser
    :return:
    """

    ANALYST_FOLDER = str(Path.cwd()) + """/analyst/ANALYST"""

    for folder in os.listdir(ANALYST_FOLDER):
        for file in os.listdir(os.path.join(ANALYST_FOLDER, folder)):
            document_path = os.path.join(ANALYST_FOLDER, folder, file)
            with open(document_path, 'r') as json_file:
                print(document_path)
                file_content = json.load(json_file)
                url = file_content['url']
                file_id = write_FileID_FilePath(document_path, url)
                parse(file_id, file_content)
            sql_add()
        break

def parse(file_id, file_content):
    """
    this extracts paragraphs and strong html tags from the page content
    then using porter stemming we turn each work into it's root words hash it and set as the
    key in a dictionary
    :param file_content: the contents of the page from the analyst file
    :param url: the url of the page from the analyst file
    :return:
    """

    page_content = file_content['content']
    text = (BeautifulSoup(page_content, 'html.parser'))
    words_in_html = text.find_all(['p', 'strong'])
    for t in words_in_html:
        for word in t.text.split():
            stem = word_stem(word)
            if stem.isalpha():
                print(stem, file_id)
                indexer(stem, file_id)

def word_stem(word):
    """
    hashing the word made it difficult to order it from a-z
    maybe well just get the stem and use that as the key then writing it to file
    while keeping a local dict that stores the cursor location for each letter
    :param word:
    :return:
    """

    word_changes = word.lower()
    for elem in [',', '.', "'", '"', ']', '[', '?', '|', '(', ')']:
        word_changes = word_changes.replace(elem, "")
    # might need to remove more stuff from work like ', \u' and nums
    stem = PorterStemmer().stem(word_changes)
    #hashed_stem = hashlib.md5(stem.encode('utf-8')).hexdigest()

    return stem

def indexer(stem, file_id):
    if stem in inverted_index.keys():
        if file_id in inverted_index[stem].keys():
            inverted_index[stem][file_id] += 1
        else:
            inverted_index[stem][file_id] = 1
            indexed_doc_cnt[0] += 1
    else:
        inverted_index[stem] = {file_id: 1}

    inverted_index[stem] = dict(sorted(inverted_index[stem].items(), key=lambda x: x[1], reverse=True))

def write_FileID_FilePath(FilePath, url):
    """
    enter file path then use tell to get a unique byte address in file
    :param FilePath:
    :return: A unique placement of file path and url in this helper file
    """

    with open('FileID_FilePath.txt', 'a+') as f:
        Seek_Pos = f.tell()
        f.write(FilePath + " ==> " + url + '\n')
    return Seek_Pos


def connect_sql():
    """
    call at start and delete before re-run
    :return:
    """
    sql_file = sqlite3.connect("text.db")
    cursor = sql_file.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entries(
        id TEXT PRIMARY KEY,
        data TEXT
        )
    """)

    sql_file.commit()
    sql_file.close()

def sql_add():
    sql_file = sqlite3.connect("text.db")
    cursor = sql_file.cursor()

    inverted_index1 = dict(sorted(inverted_index.items()))
    for key, value in inverted_index1.items():
        cursor.execute("SELECT * FROM entries WHERE id = ?", (key,))
        result_tuple = cursor.fetchone()
        if result_tuple:
            dict_data = json.loads(result_tuple[1])
            dict_data.update(value)
            value = dict(sorted(dict_data.items(), key = lambda x: x[1], reverse = True))
            cursor.execute("UPDATE entries SET data = ? WHERE id = ?", (json.dumps(value), key,))
        else:
            cursor.execute("INSERT INTO entries VALUES(?,?)", (key, json.dumps(value),))
        sql_file.commit()
    sql_file.close()

    inverted_index.clear()
    inverted_index1.clear()


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

    def write_to_disk(update_elem):
        with open('inverted index.json', 'w') as file:
            for elem in update_elem:
                file.write(elem)

connect_sql()
Get_Next_File()
report()