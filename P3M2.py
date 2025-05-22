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

def test_search():
    """
    test search logic with the M2 required queries
    """
    search = SearchLogic()
    
    # test queries
    test_queries = [
        "cristina lopes",
        "machine learning", 
        "ACM",
        "master of software engineering"
    ]
    
    print("M2 Search Testing")
    print("="*40)
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        print("-" * 20)
        
        results = search.boolean_and_search(query)
        
        if results:
            # show top three results sorted by freq
            sorted_results = sorted(results.items(), key = lambda x: x[1], reverse = True)
            for i, (file_id, freq) in enumerate(sorted_results[:3]):
                print(f" {i + 1}. File {file_id}: {freq}")
        else:
            print(" No results found")

if __name__ == "__main__":
    test_search()