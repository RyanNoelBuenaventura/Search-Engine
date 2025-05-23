import hashlib
import os
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from nltk.stem import PorterStemmer
import json

document_fingerprints = {}
document_checksums = set()
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
                page_content = file_content['content']
                if dup_check(page_content, url):
                    file_id = write_FileID_FilePath(file, url)
                    parse(file_id, page_content)
        write_index_to_file()


def createFingerprint(content, url):
    """
    creates text fingerprints for near duplicate deletion
    """
    soup = BeautifulSoup(content, 'html.parser')  # Gets all html data from page

    for element in soup(['script', 'style', 'header', 'footer',
                         'nav']):  # Removes any type of text specified here
        element.decompose()

    text = soup.get_text(
        separator = ' ').lower()  # Gets text from html and seperates by a space if not already there, making everything lowercase too

    text = re.sub(r'\s+', ' ', text).strip()  # Replaces sequences of whitespace with 1 space

    n_length = 5  # length per fingerprint
    words = text.split()  # makes text into individual words for fingerprinting

    # since we have extracted all the words and remvoed html flags it might be best to compare
    # length to any previous word page length and update if needed

    # this can be used later for word fequency and other things

    # set main url
    # if too small check
    if len(words) < n_length:
        return set()

    # makes a set of the ngrams that we will create
    ngrams = set()

    # creating ngrams, hashing them, and putting them into the set of ngrams for the page
    for i in range(len(words) - n_length + 1):
        ngram = ' '.join(words[i:i + n_length])
        ngram_hash = hashlib.md5(ngram.encode()).hexdigest()
        ngrams.add(ngram_hash)

    # maybe error checks here??

    return ngrams
# checks for exact duplicates to existing websites
def exactDupe(content):
    # creates hash of current site text
    current_hash = hashlib.md5(content.encode()).hexdigest()

    # checks doc against other hashes created and looks for a match, returning True if match found
    if current_hash in document_checksums:
        print(f"Exact dupe detected. Hash: {current_hash}")
        return True

    # if not found add to list of unique websites
    document_checksums.add(current_hash)

    return False


def nearDupe(content, url):
    similarity_limit = 0.7
    # using createFingerprint to get the fingerprint of the site of interest
    current_fingerprint = createFingerprint(content, url)

    if len(current_fingerprint) < 10:  # doc too small or fingerprint failed
        return False

    # compares documents and finds the words in common from the fingerprints
    for seenUrl, seenFingerprint in document_fingerprints.items():
        if len(seenFingerprint) > 0:
            intersection = len(current_fingerprint.intersection(seenFingerprint))
            union = len(current_fingerprint.union(seenFingerprint))

            # if union exists, calculate similarity level
            if union > 0:
                similarity = intersection / union
            else:
                similarity = 0

            # similarity checker, returns true if its similar enough
            if similarity >= similarity_limit:
                return True

    # if not similar enough store fingerprint for future comparisons and return false
    document_fingerprints[url] = current_fingerprint
    return False

def dup_check(content, url):
    if exactDupe(content):
        return False

    if nearDupe(content, url):
        return False

    return True

def parse(file_id, page_content):
    """
    this extracts paragraphs and strong html tags from the page content
    then using porter stemming we turn each work into it's root words hash it and set as the
    key in a dictionary
    :param file_content: the contents of the page from the analyst file
    :param url: the url of the page from the analyst file
    :return:
    """
    try:
        text = (BeautifulSoup(page_content, 'html.parser'))
        words_in_html = text.find_all(['p', 'strong'])
        for t in words_in_html:
            for word in t.text.split():
                stem = word_stem(word)
                if stem.isalpha():
                    indexer(stem, file_id)
    except Exception as e:
        return

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

def write_index_to_file():
    # sort the index alphabetically
    sorted_index = dict(sorted(inverted_index.items()))
    
    # load existing index if it exists
    existing_index = {}
    try:
        with open('inverted_index.json', 'r') as f:
            existing_index = json.load(f)
    except FileNotFoundError:
        pass
    
    # merge current index with existing index
    for term, postings in sorted_index.items():
        if term in existing_index:
            # merge postings
            for file_id, freq in postings.items():
                if str(file_id) in existing_index[term]:
                    existing_index[term][str(file_id)] += freq
                else:
                    existing_index[term][str(file_id)] = freq
            # Sort by frequency
            existing_index[term] = dict(sorted(existing_index[term].items(), 
                                             key=lambda x: x[1], reverse=True))
        else:
            existing_index[term] = {str(k): v for k, v in postings.items()}
    
    # write back to file
    with open('inverted_index.json', 'w') as f:
        json.dump(existing_index, f, indent=2)
    
    # clear memory
    inverted_index.clear()
    print(f"Index written to file. Memory cleared.")


def report():
    """this should make and write to the file i added a try and except in general"""

    try:
        with open('inverted_index.json', 'r') as f:
            final_index = json.load(f)
        
        total_unique_tokens = len(final_index.keys())
        
        with open('Report.txt', 'w') as f:
            # longest url and the number of words
            f.write(
                f"total unique tokens {total_unique_tokens}\n")
            f.write("-" * 20 + "\n")

            # top 50 words with their number
            f.write(f"Total indexed pages without intersections {indexed_doc_cnt[0]}\n")

            f.write("-" * 20 + "\n")

            import os
            index_size = os.path.getsize('inverted_index.json')
            f.write(f"Total size is {index_size} in bytes\n")

            f.write("-" * 20 + "\n")

    except Exception as e:
        print(f"Error writing to Report.txt: {e}")

if __name__ == "__main__":
    Get_Next_File()
    report()