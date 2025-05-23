import json
from nltk.stem import PorterStemmer

class SearchLogic:
    """
    search logic using M1 database
    """
    
    def __init__(self, index_path="inverted_index.json"):
        self.index_path = index_path
        self.stemmer = PorterStemmer()
        self.inverted_index = self._load_index()
    
    def _load_index(self):
        try:
            with open(self.index_path, 'r') as f:
                index = json.load(f)
            print(f"Loaded index with {len(index)} terms")
            return index
        except FileNotFoundError:
            print(f"Index file {self.index_path} not found!")
            return {}
        except Exception as e:
            print(f"Error loading index: {e}")
            return {}
    
    def process_query_terms(self, query):
        """
        process query using same logic as M1 word_stem
        """
        words = query.lower().split()
        processed_terms = []
        
        for word in words:
            # same cleaning as word_stem
            word_changes = word.lower()
            for elem in [',', '.', "'", '"', ']', '[', '?', '|', '(', ')']:
                word_changes = word_changes.replace(elem, "")
            
            # only process alphabetic words
            if word_changes.isalpha():
                stem = self.stemmer.stem(word_changes)
                processed_terms.append(stem)
        
        return processed_terms
    
    def fetch_term_postings(self, term):
        """
        get postings for a term from existing database
        """
        return self.inverted_index.get(term, {})
    
    def boolean_and_search(self, query):
        """
        boolean and operation find documents with all query terms
        """
        # process the query
        query_terms = self.process_query_terms(query)
        
        if not query_terms:
            return {}
        
        print(f"Searching for terms: {query_terms}")
        
        # get postings for the first term
        results = self.fetch_term_postings(query_terms[0])
        
        if not results:
            return {}
        
        # intersect with each additional term
        for term in query_terms[1:]:
            term_postings = self.fetch_term_postings(term)
            # if term has no matches then no results
            if not term_postings:
                return {}
            
            # keep documents that appear in both current results and this term
            results = {
                file_id: frequency 
                for file_id, frequency in results.items() 
                if file_id in term_postings
            }
        
        print(f"Found {len(results)} documents")
        return results

class ResultFormatter:
    # initialize file mapping
    def __init__(self, file_map = "FileID_FilePath.txt"):
        self.file_mapping_path = file_map
        self.url_cache = {}
        self._load_all_mappings()
        print(f"ResultFormatter initialized w/: {file_map}")
    
    def _load_all_mappings(self):
        try:
            print("Loading file mappings...")
            
            # read file exactly as the original indexer would have
            with open(self.file_mapping_path, 'r') as f:
                while True:
                    current_pos = f.tell()  # get position before reading
                    line = f.readline()
                    
                    if not line:  # End of file
                        break
                        
                    line = line.strip()
                    if ' ==> ' in line:
                        file_path, url = line.split(' ==> ', 1)
                        self.url_cache[str(current_pos)] = url
            
            print(f"Loaded {len(self.url_cache)} URL mappings")
            sample_keys = sorted([int(k) for k in self.url_cache.keys()])[:10]
            print(f"Sample file IDs: {sample_keys}")
                    
        except FileNotFoundError:
            print(f"Warning: {self.file_mapping_path} not found")
        except Exception as e:
            print(f"Error loading URL mapping: {e}")
    
    def get_url_for_file_id(self, file_id):
        # reads existing FileID_FilePath.txt to get URL for file_id
        return self.url_cache.get(str(file_id))
    
    def sort_results_by_relevance(self, search_results):

        if not search_results:
            return []
        
        # sort by term frequency descending
        sorted_results = sorted(search_results.items(), 
                              key=lambda item: item[1], reverse=True)
        
        return sorted_results
    
    def get_valid_results(self, search_results, max_results=5):
        if not search_results:
            return []
        
        # show what file IDs we're looking for
        file_ids = list(search_results.keys())
        print(f"Search found file IDs: {file_ids[:10]}...")  # Show first 10
        
        # sort by relevance first
        sorted_results = sorted(search_results.items(), 
                              key=lambda item: item[1], reverse=True)
        
        valid_results = []
        found_count = 0
        
        for file_id, frequency in sorted_results:
            url = self.get_url_for_file_id(file_id)
            if url:  # only add if URL was found
                valid_results.append((file_id, frequency, url))
                found_count += 1
                if len(valid_results) >= max_results:
                    break
        
        print(f"Found {found_count} valid results out of {len(search_results)} total")
        return valid_results
    
    def formatted_results(self, search_results, query, max_results=5):
    
        # formats search results, returning formatted string with top URLs
        output_lines = []
        output_lines.append(f"Query: {query}")
        
        if not search_results:
            output_lines.append("No results found.")
            return "\n".join(output_lines)
        
        # get valid results only
        valid_results = self.get_valid_results(search_results, max_results)
        
        if not valid_results:
            output_lines.append("No valid results found.")
            return "\n".join(output_lines)
        
        # adding top URLs
        output_lines.append(f"Top {len(valid_results)} URLs:")
        
        for i, (file_id, frequency, url) in enumerate(valid_results, 1):
            output_lines.append(f"{i}. {url}")
        
        return "\n".join(output_lines)
    
    def create_report_file(self, all_query_results):
        # creates report file
        try:
            with open("M2_Report.txt", 'w') as f:
                f.write("Search Results Report\n")
                f.write("="*50 + "\n\n")
                
                for result_text in all_query_results:
                    f.write(result_text)
                    f.write("\n\n")
                
                f.write("End of Report\n")
            
            print("M2 report saved to: M2_Report.txt")
            return True
            
        except Exception as e:
            print(f"Error creating report file: {e}")
            return False
    

    def search_demo(self, search_function=None):
        
        # testing search implementation
        print("\n" + "="*50)
        print("SEARCH DEMO")
        print("="*50)
        
        if search_function is None:
            print("Search function was not succcessfully connected. Try again.")
            return
        else:
            # connection successful
            print("Enter queries (q to quit):")
            
            while True:
                query = input("Search> ").strip()
                if query.lower() in ['quit', 'exit', 'q']:
                    break
                elif query:
                    # utilizes search to display results
                    results = search_function(query)
                    formatted = self.formatted_results(results, query, max_results=10)
                    print(formatted)
                else:
                    print("Not in indexed queries. Try another term: ")

def Gui_search(query):
    all_results = []

    search = SearchLogic()
    formatter = ResultFormatter()
    results = search.boolean_and_search(query)

    formatted_result = formatter.formatted_results(results, query)
    all_results.append(formatted_result)
    return all_results

def test_search():
    """
    test search logic with the M2 required queries
    """
    search = SearchLogic()
    formatter = ResultFormatter()
    
    # test queries
    test_queries = [
        "cristina lopes",
        "machine learning", 
        "ACM",
        "master of software engineering"
    ]
    
    print("M2 Search Testing")
    print("="*40)
    
    all_results = []
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        print("-" * 20)
        
        results = search.boolean_and_search(query)
        formatted_result = formatter.formatted_results(results, query)
        print(formatted_result)
        all_results.append(formatted_result)
    
    formatter.create_report_file(all_results)
    
    # run search demo
    formatter.search_demo(search.boolean_and_search)

if __name__ == "__main__":
    test_search()