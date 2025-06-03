import streamlit as st
import time
from P3M2 import gui_search

words = "Uci ICS Search Engine"
st.title(words.capitalize())
st.divider()

search = st.text_input("Enter search term")
if search:
    # times the search
    start_time = time.time()
    result = gui_search(search)[0].split('\n')[1:]
    end_time = time.time()
    
    # calculates and displays retrieval time
    retrieval_time = (end_time - start_time) * 1000  # ms conversion
    st.success(f"Search completed in {retrieval_time:.1f}ms")
    
    print(result)
    for i in result:
        st.write(str(i))