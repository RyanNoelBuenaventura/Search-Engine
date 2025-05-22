import sqlite3
import json
from nltk.stem import PorterStemmer

class SearchLogic:
    """
    search logic using M1 database
    """
    
    def __init__(self, db_path="text.db"):
        self.db_path = db_path
        self.stemmer = PorterStemmer()
    
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
        get postings for a term from existing SQLite database
        """
        try:
            # connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # query using table structure
            cursor.execute("select data from entries where id = ?", (term,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # parse the JSON data stored in M1
                return json.loads(result[0])
            # term not found
            else:
                return {}
                
        except Exception as e:
            print(f"Error for term '{term}': {e}")
            return {}
    
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
    #initialize file mapping
    def __init__(self, file_map = "FileID_FilePath.txt"):
        self.file_mapping_path = file_map
        print(f"ResultFormatter initialized w/: {file_map}")
    
    def get_url_for_file_id(self, file_id):
        # reads existing FileID_FilePath.txt to get URL for file_id
        try:
            with open(self.file_mapping_path, 'r') as f:
                # seek to the byte position
                f.seek(file_id)
                line = f.readline().strip()
                
                if ' ==> ' in line:
                    file_path, url = line.split(' ==> ', 1)
                    return url
                else:
                    return f"URL not found for file_id: {file_id}"
                    
        except FileNotFoundError:
            return f"File mapping not found: {self.file_mapping_path}"
        except Exception as e:
            return f"Error reading file_id {file_id}: {str(e)}"
    
    def sort_results_by_relevance(self, search_results):

        if not search_results:
            return []
        
        # sort by term frequency descending
        sorted_results = sorted(search_results.items(), 
                              key=lambda item: item[1], reverse=True)
        
        return sorted_results
    
    def formatted_results(self, search_results, query, max_results=5):
    
        # formats search results, returning formatted string with top URLs
        output_lines = []
        output_lines.append(f"Query: {query}")
        
        if not search_results:
            output_lines.append("No results found.")
            return "\n".join(output_lines)
        
        # sorting results by relevance
        sorted_results = self.sort_results_by_relevance(search_results)
        
        # adding top URLs
        output_lines.append(f"Top {min(max_results, len(sorted_results))} URLs:")
        
        for i, (file_id, frequency) in enumerate(sorted_results[:max_results], 1):
            url = self.get_url_for_file_id(file_id)
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