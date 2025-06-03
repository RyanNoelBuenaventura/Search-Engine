import json
import math
import time
import os
from nltk.stem import PorterStemmer
from collections import defaultdict
import re

def split_large_index():
    """splits the index into smaller files by first two letters for better retrieval performance"""
    
    print("OPTIMIZING INDEX FOR FAST QUERIES")
    print()
    
    print("Loading large index file...")
    with open("final_index/inverted_index.json", 'r') as f:
        full_index = json.load(f)
    
    print(f"Loaded {len(full_index)} terms from index")
    
    # creates split indexes directory
    os.makedirs("final_index/split_indexes", exist_ok=True)
    print("Created split_indexes directory")
    
    # groups terms by first TWO letters for smaller files (a-z only)
    print("Grouping terms by first two letters...")
    letter_indexes = {}
    skipped_count = 0
    
    for term, postings in full_index.items():
        # skips non-ASCII or non-alphabetic terms
        if not term or not term[0].isascii() or not term[0].isalpha():
            skipped_count += 1
            continue
            
        # uses first two letters for more granular splitting
        if len(term) >= 2 and term[1].isascii() and term[1].isalpha():
            prefix = term[:2].lower()
        else:
            prefix = term[0].lower() + 'a'  # single letter or special terms get 'a' suffix
        
        # only processes a-z prefixes
        if all(c.isascii() and c.isalpha() for c in prefix):
            if prefix not in letter_indexes:
                letter_indexes[prefix] = {}
            letter_indexes[prefix][term] = postings
        else:
            skipped_count += 1
    
    print(f"Processing {len(full_index) - skipped_count} terms, skipped {skipped_count} non-ASCII terms")
    
    # writes each prefix to separate file
    print(f"Writing {len(letter_indexes)} split index files...")
    for prefix, terms in letter_indexes.items():
        filename = f"final_index/split_indexes/index_{prefix}.json"
        with open(filename, 'w') as f:
            json.dump(terms, f, separators=(',', ':'))
        
        file_size = os.path.getsize(filename) / (1024 * 1024)  # MB
        print(f"   Created {filename}: {len(terms)} terms, {file_size:.1f}MB")
    
    print("SETUP COMPLETE")
    print()

class FastDiskBasedSearchEngine:
    """
    fast search using split index files
    """
    def __init__(self, mapping_path="final_index/file_mappings.json"):
        self.split_index_dir = "final_index/split_indexes"
        self.mapping_path = mapping_path
        self.stemmer = PorterStemmer()
        self.url_cache = {}
        self.punctuation_regex = re.compile(r'[^\w\s]')
        
        # term cache for frequently accessed terms
        self.term_cache = {}
        
        print("Initializing search engine...")
        
        # checks if split indexes exist, creates them before any searches
        if not os.path.exists(self.split_index_dir):
            print("Split indexes not found - running initial setup...")
            split_large_index()
            print("Initial setup complete. Search engine ready.")
        else:
            print("Split indexes found - search engine ready for fast queries")
        
        # loads file mappings
        self._load_file_mappings()
        
        # indexes metadata without loading full index
        self.total_documents = len(self.url_cache)
        
        print(f"Fast Search Engine: {self.total_documents} documents, split-index queries")
    
    def _load_file_mappings(self):
        """loads URL mappings into memory"""
        try:
            with open(self.mapping_path, 'r') as f:
                mappings = json.load(f)
                for file_id, data in mappings.items():
                    self.url_cache[file_id] = data['url']
            print(f"Loaded {len(self.url_cache)} URL mappings")
        except Exception as e:
            print(f"Error loading file mappings: {e}")
    
    def process_query(self, query):
        """processes query terms using same stemming as indexer"""
        words = query.lower().split()
        processed_terms = []
        
        for word in words:
            # same cleaning method as indexer
            word_clean = self.punctuation_regex.sub('', word.lower())
            if word_clean and word_clean.isalpha() and len(word_clean) > 1:
                stem = self.stemmer.stem(word_clean)
                processed_terms.append(stem)
        
        return processed_terms
    
    def get_index_file_for_term(self, term):
        """determines which split index file contains this term (using first two letters, a-z only)"""
        # skips non-ASCII or non-alphabetic terms
        if not term or not term[0].isascii() or not term[0].isalpha():
            return None  # no file for non-ASCII terms
            
        if len(term) >= 2 and term[1].isascii() and term[1].isalpha():
            prefix = term[:2].lower()
        else:
            prefix = term[0].lower() + 'a'  # single letter terms get 'a' suffix
            
        return f"{self.split_index_dir}/index_{prefix}.json"
    
    def fetch_term_postings_fast(self, term):
        """
        fast term lookup using split indexes
        """
        try:
            # checks memory cache first
            if term in self.term_cache:
                return self.term_cache[term]
            
            # determines which small index file to read
            index_file = self.get_index_file_for_term(term)
            
            if not index_file or not os.path.exists(index_file):
                return {}
            
            # reads only the relevant small index file
            with open(index_file, 'r') as f:
                index_data = json.load(f)
            
            # gets postings for this specific term
            postings = index_data.get(term, {})
            
            # caches in memory for future queries
            self.term_cache[term] = postings
            
            return postings
                    
        except Exception as e:
            print(f"Error fetching postings for '{term}': {e}")
            return {}
    
    def search_with_ranking(self, query):
        """
        fast search with TF-IDF ranking
        """
        start_time = time.time()
        
        query_terms = self.process_query(query)
        if not query_terms:
            return {}
        
        print(f"Fast Search for: {query_terms}")
        
        # fetches postings for each term
        all_postings = {}
        for term in query_terms:
            postings = self.fetch_term_postings_fast(term)
            if not postings:
                print(f"No documents found for term: {term}")
                return {}  # boolean AND - no results if any term missing
            all_postings[term] = postings
        
        # finds intersection of documents
        result_docs = set(all_postings[query_terms[0]].keys())
        for term in query_terms[1:]:
            result_docs &= set(all_postings[term].keys())
        
        if not result_docs:
            return {}
        
        # enhanced ranking with TF-IDF scores
        ranked_results = {}
        for doc_id in result_docs:
            combined_score = 0
            term_count = 0
            
            for term in query_terms:
                if doc_id in all_postings[term]:
                    tf_idf_score = all_postings[term][doc_id]
                    combined_score += tf_idf_score
                    term_count += 1
            
            # boosts score for documents containing more query terms
            if term_count > 1:
                combined_score *= (1 + 0.1 * (term_count - 1))
            
            ranked_results[doc_id] = combined_score
        
        # sorts by combined score
        ranked_results = dict(sorted(ranked_results.items(), 
                                   key=lambda x: x[1], reverse=True))
        
        elapsed_time = time.time() - start_time
        print(f"Fast Search completed in {elapsed_time*1000:.1f}ms with {len(ranked_results)} results")
        
        # compliance check
        if elapsed_time > 0.3:
            print("WARNING: Query time exceeded 300ms requirement")
        else:
            print("COMPLIANT: under 300ms")
        
        return ranked_results
    
    def get_url_for_doc(self, doc_id):
        """gets URL for document ID"""
        return self.url_cache.get(str(doc_id), f"Document {doc_id}")
    
    def format_results(self, search_results, query, max_results=5):
        """formats search results"""
        if not search_results:
            return f"Query: {query}\nNo results found."
        
        output_lines = [f"Query: {query}"]
        output_lines.append(f"Found {len(search_results)} results")
        output_lines.append(f"Top {min(len(search_results), max_results)} URLs:")
        
        count = 0
        for doc_id, score in search_results.items():
            if count >= max_results:
                break
            
            url = self.get_url_for_doc(doc_id)
            output_lines.append(f"{count + 1}. {url} (Score: {score:.3f})")
            count += 1
        
        return "\n".join(output_lines)

class M3TestSuite:
    """test suite for evaluation with 20+ queries"""
    
    def __init__(self):
        self.engine = FastDiskBasedSearchEngine()
        
        # test queries
        self.test_queries = [
            # good performing queries (should find relevant results quickly)
            "cristina lopes",
            "machine learning", 
            "computer class",
            "artificial intelligence",
            "software engineering",
            "data structures",
            "algorithms",
            "programming",
            "database",
            "networks",
            
            # challenging queries (may perform poorly initially)
            "quantum computing", 
            "blockchain technology",  
            "mobile app development", 
            "user experience design",  
            "cloud computing security",  
            "virtual reality applications", 
            "internet of things", 
            "big data analytics", 
            "cybersecurity frameworks", 
            "edge computing platforms", 
            
            # additional test queries
            "ACM",
            "master of software engineering",
            "research",
            "faculty"
        ]
    
    def evaluate_query_performance(self, query):
        """evaluates single query performance"""
        start_time = time.time()
        results = self.engine.search_with_ranking(query)
        elapsed_time = time.time() - start_time
        
        # performance criteria
        result_count = len(results)
        time_under_limit = elapsed_time < 0.3
        has_good_results = result_count >= 3
        
        performance_score = 0
        if time_under_limit:
            performance_score += 1
        if has_good_results:
            performance_score += 1
        if result_count >= 5:
            performance_score += 1
            
        return {
            'query': query,
            'results': results,
            'count': result_count,
            'time': elapsed_time,
            'performance_score': performance_score,
            'formatted': self.engine.format_results(results, query, 5)
        }
    
    def run_full_evaluation(self):
        """runs complete test suite"""
        print("="*60)
        print("SEARCH ENGINE EVALUATION")
        print("="*60)
        
        all_results = []
        total_time = 0
        
        for query in self.test_queries:
            print(f"\nEvaluating: '{query}'")
            eval_result = self.evaluate_query_performance(query)
            all_results.append(eval_result)
            total_time += eval_result['time']
            
            print(f"{eval_result['count']} results in {eval_result['time']*1000:.1f}ms")
        
        # generates comprehensive report
        self.generate_m3_report(all_results, total_time)
        
        return all_results
    
    def generate_m3_report(self, all_results, total_time):
        """generates evaluation report"""
        report_lines = []
        report_lines.append("SEARCH ENGINE EVALUATION REPORT")
        report_lines.append("="*50)
        report_lines.append(f"Total queries tested: {len(self.test_queries)}")
        report_lines.append(f"Average query time: {(total_time/len(self.test_queries))*1000:.1f}ms")
        report_lines.append(f"Queries under 300ms: {sum(1 for r in all_results if r['time'] < 0.3)}")
        report_lines.append("")
        
        report_lines.append("DETAILED RESULTS:")
        report_lines.append("="*30)
        
        for result in all_results:
            report_lines.append(f"\n{result['formatted']}")
            report_lines.append(f"Response time: {result['time']*1000:.1f}ms")
            report_lines.append("-"*20)
        
        # saves report
        with open("M3_Evaluation_Report.txt", 'w') as f:
            f.write("\n".join(report_lines))
        
        print(f"\nEvaluation Complete")
        print(f"Report saved to: M3_Evaluation_Report.txt")

def gui_search(query):
    """GUI search function for streamlit app"""
    try:
        engine = FastDiskBasedSearchEngine()
        results = engine.search_with_ranking(query)
        formatted_result = engine.format_results(results, query, 5)
        return [formatted_result]
    except Exception as e:
        return [f"Search error: {e}"]

def test_m2_queries():
    """tests the required M2 queries"""
    engine = FastDiskBasedSearchEngine()
    
    # M2 required test queries
    m2_queries = [
        "cristina lopes",
        "machine learning", 
        "ACM",
        "master of software engineering"
    ]
    
    print("M2 Required Query Testing")
    print("="*40)
    
    all_results = []
    
    for query in m2_queries:
        print(f"\nQuery: '{query}'")
        print("-" * 20)
        
        results = engine.search_with_ranking(query)
        formatted_result = engine.format_results(results, query, 5)
        print(formatted_result)
        all_results.append(formatted_result)
    
    # saves M2 report
    with open("M2_Required_Results.txt", 'w') as f:
        f.write("M2 Required Query Results\n")
        f.write("="*30 + "\n\n")
        for result in all_results:
            f.write(result)
            f.write("\n\n")
    
    print(f"\nM2 results saved to: M2_Required_Results.txt")

def main():
    print("Fast Search Engine")
    print("="*50)
    
    choice = input("Run (1) M2 required queries, (2) M3 full evaluation, or (3) interactive mode? ")
    
    if choice == "1":
        test_m2_queries()
    elif choice == "2":
        test_suite = M3TestSuite()
        test_suite.run_full_evaluation()
    else:
        # interactive mode
        engine = FastDiskBasedSearchEngine()
        print(f"\nInteractive search mode (Enter 'quit' to exit):")
        
        while True:
            query = input("\nSearch> ").strip()
            if query.lower() in ['quit', 'exit', 'q']:
                break
            elif query:
                results = engine.search_with_ranking(query)
                formatted = engine.format_results(results, query, 5)
                print(formatted)

if __name__ == "__main__":
    main()