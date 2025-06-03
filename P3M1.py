import hashlib
import os
import re
import sys
import json
import heapq
import math
from pathlib import Path
from bs4 import BeautifulSoup
from nltk.stem import PorterStemmer
from collections import defaultdict

class MemoryEfficientIndexer:
    def __init__(self, max_memory_tokens=50000, corpus_path="DEV"):  # increases memory limit
        self.max_memory_tokens = max_memory_tokens
        self.corpus_path = corpus_path
        self.inverted_index = defaultdict(lambda: defaultdict(int))
        self.document_frequencies = defaultdict(int)  # for IDF calculation
        self.file_id_mapping = {}
        self.indexed_doc_cnt = 0
        self.partial_index_counter = 0
        self.porter_stemmer = PorterStemmer()
        self.total_documents = 0
        
        # inits for dupe detection later
        self.document_checksums = set()
        self.document_fingerprints = {}
        
        # precompiles regex
        self.punctuation_regex = re.compile(r'[^\w\s]')
        self.whitespace_regex = re.compile(r'\s+')
        
        # creates directories
        os.makedirs("partial_indexes", exist_ok=True)
        os.makedirs("final_index", exist_ok=True)
    
        # recovery mechanism - checks for existing partial indexes
        self._check_for_existing_partials()
    
    def _check_for_existing_partials(self):
        """check for existing partial indexes from previous run"""
        existing_partials = []
        if os.path.exists("partial_indexes"):
            for file in os.listdir("partial_indexes"):
                if file.startswith("partial_") and file.endswith(".json"):
                    partial_num = int(file.split("_")[1].split(".")[0])
                    existing_partials.append(partial_num)
        
        if existing_partials:
            self.partial_index_counter = max(existing_partials)
            print(f"Found {len(existing_partials)} existing partial indexes, resuming from {self.partial_index_counter}")
        
        # merges existing partials if we have too many (prevents memory issues)
        if len(existing_partials) >= 50:
            print("Too many partial indexes found, performing intermediate merge...")
            self._intermediate_merge()
    
    def _intermediate_merge(self):
        """merge some partial indexes to reduce file count"""
        # merges first half of partials
        partials_to_merge = []
        for i in range(1, self.partial_index_counter // 2 + 1):
            filename = f"partial_indexes/partial_{i:03d}.json"
            if os.path.exists(filename):
                partials_to_merge.append(filename)
        
        if len(partials_to_merge) < 2:
            return
        
        print(f"Merging {len(partials_to_merge)} partial indexes into intermediate index...")
        
        # creates merged intermediate index
        merged_index = defaultdict(lambda: defaultdict(int))
        
        for filename in partials_to_merge:
            with open(filename, 'r') as f:
                partial_data = json.load(f)
                for term, postings in partial_data.items():
                    for doc_id, tf in postings.items():
                        merged_index[term][doc_id] += tf
        
        # writes merged index as new partial
        self.partial_index_counter += 1
        merged_filename = f"partial_indexes/partial_{self.partial_index_counter:03d}.json"
        
        with open(merged_filename, 'w') as f:
            json.dump(dict(merged_index), f, separators=(',', ':'))
        
        # removes old partials
        for filename in partials_to_merge:
            try:
                os.remove(filename)
                # alsos remove corresponding df file
                df_filename = filename.replace("partial_", "df_")
                if os.path.exists(df_filename):
                    os.remove(df_filename)
            except:
                pass
        
        print(f"Intermediate merge complete, reduced to {self.partial_index_counter} partials")
    
    def count_total_documents(self):
        """counts total documents for IDF calculation"""
        count = 0
        corpus_folder = str(Path.cwd()) + f"/{self.corpus_path}"
        
        for folder in os.listdir(corpus_folder):
            folder_path = os.path.join(corpus_folder, folder)
            if os.path.isdir(folder_path):
                count += len([f for f in os.listdir(folder_path) if f.endswith('.json')])
        
        self.total_documents = count
        print(f"Total documents to process: {self.total_documents}")
    
    def create_fingerprint(self, content):
        """creates fingerprint for near-duplicate detection"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            for element in soup(['script', 'style', 'header', 'footer', 'nav']):
                element.decompose()
            
            text = soup.get_text(separator=' ').lower()
            text = self.whitespace_regex.sub(' ', text).strip()
            words = text.split()
            
            if len(words) < 5:
                return set()
            
            ngrams = set()
            for i in range(len(words) - 4):
                ngram = ' '.join(words[i:i + 5])
                ngram_hash = hashlib.md5(ngram.encode()).hexdigest()
                ngrams.add(ngram_hash)
            
            return ngrams
        except:
            return set()
    
    def is_duplicate(self, content, url):
        """checks for exact and near duplicates"""
        # exact dupe
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        if content_hash in self.document_checksums:
            return True
        self.document_checksums.add(content_hash)
        
        # near dupe
        current_fingerprint = self.create_fingerprint(content)
        if len(current_fingerprint) < 10:
            return False
        
        for seen_url, seen_fingerprint in self.document_fingerprints.items():
            if len(seen_fingerprint) > 0:
                intersection = len(current_fingerprint & seen_fingerprint)
                union = len(current_fingerprint | seen_fingerprint)
                if union > 0 and (intersection / union) >= 0.7:
                    return True
        
        self.document_fingerprints[url] = current_fingerprint
        return False
    
    def word_stem(self, word):
        """clean and stem word"""
        if not word:
            return ""
        
        word_clean = self.punctuation_regex.sub('', word.lower())
        if not word_clean or len(word_clean) < 2:
            return ""
        
        return self.porter_stemmer.stem(word_clean)
    
    def parse_document(self, file_id, content):
        """parse document and extract terms with importance weights"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # important elements
            important_elements = soup.find_all(['h1', 'h2', 'h3', 'title', 'strong', 'b'])
            for element in important_elements:
                text = element.get_text()
                self.process_text(text, file_id, weight=3)
            
            # regular text
            regular_elements = soup.find_all(['p'])
            for element in regular_elements:
                text = element.get_text()
                self.process_text(text, file_id, weight=1)
            
            # other text
            all_text = soup.get_text()
            self.process_text(all_text, file_id, weight=1)
            
            return True
        except:
            return False
    
    def process_text(self, text, file_id, weight=1):
        """processes text and add terms to index"""
        words = text.split()
        for word in words:
            stem = self.word_stem(word)
            if stem and stem.isalpha() and len(stem) > 1:
                if file_id not in self.inverted_index[stem]:
                    self.document_frequencies[stem] += 1 # track DF
                self.inverted_index[stem][file_id] += weight # accumulate TF
    
    def write_partial_index(self):
        """writes current index to disk and clear memory"""
        if not self.inverted_index:
            return
        
        self.partial_index_counter += 1
        filename = f"partial_indexes/partial_{self.partial_index_counter:03d}.json"
        
        print(f"Writing partial index {self.partial_index_counter} to disk (memory limit reached)")
        
        # converts to regular dict and sort
        sorted_index = dict(sorted(self.inverted_index.items()))
        
        # stores document frequencies for this batch
        df_filename = f"partial_indexes/df_{self.partial_index_counter:03d}.json"
        current_df = {term: df for term, df in self.document_frequencies.items() 
                     if term in sorted_index}
        
        with open(df_filename, 'w') as f:
            json.dump(current_df, f, separators=(',', ':'))
        
        # calculates TF scores for partial index
        processed_index = {}
        for term, postings in sorted_index.items():
            processed_index[term] = {}
            for doc_id, tf in postings.items():
                # stores raw TF for now, will calculate TF-IDF during merge
                processed_index[term][str(doc_id)] = tf
        
        with open(filename, 'w') as f:
            json.dump(processed_index, f, separators=(',', ':'))
        
        print(f"Partial index {self.partial_index_counter}: {len(sorted_index)} terms, "
              f"memory freed: {sys.getsizeof(self.inverted_index)} bytes")
        
        # clears memory
        self.inverted_index.clear()
        # keeps running DF count but clear local batch
        for term in current_df:
            self.document_frequencies[term] = current_df[term]
    
    def process_documents(self):
        """processes all documents with memory management"""
        self.count_total_documents()
        
        corpus_folder = str(Path.cwd()) + f"/{self.corpus_path}"
        processed_count = 0
        
        for folder in os.listdir(corpus_folder):
            folder_path = os.path.join(corpus_folder, folder)
            if not os.path.isdir(folder_path):
                continue
            
            for file in os.listdir(folder_path):
                if not file.endswith('.json'):
                    continue
                
                try:
                    document_path = os.path.join(folder_path, file)
                    with open(document_path, 'r', encoding='utf-8') as json_file:
                        file_content = json.load(json_file)
                    
                    url = file_content.get('url', '')
                    content = file_content.get('content', '')
                    
                    if not self.is_duplicate(content, url):
                        file_id = self.indexed_doc_cnt
                        self.file_id_mapping[file_id] = {'file': file, 'url': url}
                        
                        if self.parse_document(file_id, content):
                            self.indexed_doc_cnt += 1
                    
                    processed_count += 1
                    
                    # writes partial index when memory limit reached
                    if len(self.inverted_index) >= self.max_memory_tokens:
                        self.write_partial_index()
                        # clears duplicate detection cache periodically
                        if self.partial_index_counter % 10 == 0:
                            print(f"Clearing duplicate detection cache at {self.partial_index_counter} partials")
                            self.document_fingerprints.clear()
                        
                        # performs intermediate merge if too many partials
                        if self.partial_index_counter >= 100:
                            print("Too many partials created, performing intermediate merge...")
                            self._intermediate_merge()
                    
                    if processed_count % 1000 == 0:
                        print(f"Processed {processed_count}/{self.total_documents} documents")
                
                except Exception as e:
                    print(f"Error processing {file}: {e}")
                    continue
        
        # writes final partial index
        if self.inverted_index:
            self.write_partial_index()
        
        # saves file mappings
        with open("final_index/file_mappings.json", 'w') as f:
            json.dump(self.file_id_mapping, f, separators=(',', ':'))
        
        print(f"Total documents indexed: {self.indexed_doc_cnt}")
        print(f"Created {self.partial_index_counter} partial indexes")
    
    def merge_partial_indexes(self):
        """merge all partial indexes into final index with TF-IDF calculation"""
        print("Merging partial indexes...")
        
        partial_files = []
        for i in range(1, self.partial_index_counter + 1):
            filename = f"partial_indexes/partial_{i:03d}.json"
            if os.path.exists(filename):
                partial_files.append(filename)
        
        if not partial_files:
            print("No partial indexes found")
            return
        
        # uses heap for efficient merging
        heap = []
        file_handles = []
        iterators = []
        
        # opens all partial index files
        for i, filename in enumerate(partial_files):
            f = open(filename, 'r')
            file_handles.append(f)
            index_data = json.load(f)
            f.close()
            
            # reopens for iteration
            f = open(filename, 'r')
            file_handles[i] = f
            index_data = json.load(f)
            f.close()
            
            iterator = iter(sorted(index_data.items()))
            try:
                term, postings = next(iterator)
                heapq.heappush(heap, (term, i, postings, iterator))
            except StopIteration:
                pass
        
        # merging process
        current_term = None
        merged_postings = defaultdict(int)
        final_index = {}
        terms_processed = 0
        
        while heap:
            term, file_idx, postings, iterator = heapq.heappop(heap)
            
            if current_term != term:
                # saves previous term
                if current_term is not None:
                    final_index[current_term] = self.calculate_tf_idf(current_term, merged_postings)
                    terms_processed += 1
                    
                    if terms_processed % 10000 == 0:
                        print(f"Processed {terms_processed} terms")
                
                current_term = term
                merged_postings = defaultdict(int)
            
            # merges postings for current term
            for doc_id, tf in postings.items():
                merged_postings[doc_id] += tf
            
            # gets next term from same file
            try:
                next_term, next_postings = next(iterator)
                heapq.heappush(heap, (next_term, file_idx, next_postings, iterator))
            except StopIteration:
                pass
        
        # saves last term
        if current_term is not None:
            final_index[current_term] = self.calculate_tf_idf(current_term, merged_postings)
        
        # writes final index
        with open("final_index/inverted_index.json", 'w') as f:
            json.dump(final_index, f, separators=(',', ':'))
        
        print(f"Final index created with {len(final_index)} terms")
        
        # cleans up partial indexes
        for filename in partial_files:
            try:
                os.remove(filename)
            except:
                pass
    
    def calculate_tf_idf(self, term, postings):
        """calculate TF-IDF scores for term postings"""
        df = self.document_frequencies.get(term, len(postings))
        idf = math.log(self.indexed_doc_cnt / df) if df > 0 else 0
        
        tf_idf_postings = {}
        for doc_id, tf in postings.items():
            tf_idf = tf * idf # final TF-IDF calculation
            tf_idf_postings[doc_id] = round(tf_idf, 4)
        
        # sort by TF-IDF score
        sorted_postings = dict(sorted(tf_idf_postings.items(), 
                                    key=lambda x: x[1], reverse=True))
        return sorted_postings
    
    def generate_report(self):
        """generate final report"""
        try:
            index_size = os.path.getsize("final_index/inverted_index.json")
            
            with open("final_index/inverted_index.json", 'r') as f:
                # counts terms without loading entire index
                term_count = 0
                for line in f:
                    if '"' in line and ':' in line:
                        term_count += line.count('":')
            
            with open('M3_Report.txt', 'w') as f:
                f.write("M3 Search Engine Report\n")
                f.write("=" * 40 + "\n")
                f.write(f"Number of indexed documents: {self.indexed_doc_cnt}\n")
                f.write(f"Number of unique tokens: {term_count}\n")
                f.write(f"Total index size: {index_size / 1024:.2f} KB\n")
                f.write(f"Memory-efficient processing: {self.partial_index_counter} partial indexes created\n")
                f.write("-" * 40 + "\n")
            
            print(f"Report generated: {self.indexed_doc_cnt} docs, {term_count} terms, {index_size/1024:.2f} KB")
            
        except Exception as e:
            print(f"Error generating report: {e}")

def main():
    indexer = MemoryEfficientIndexer(max_memory_tokens=50000, corpus_path="DEV")  # prevents excessive partial indexes
    
    print("Starting memory-efficient indexing...")
    indexer.process_documents()
    indexer.merge_partial_indexes()
    indexer.generate_report()
    print("indexing complete")

if __name__ == "__main__":
    main()