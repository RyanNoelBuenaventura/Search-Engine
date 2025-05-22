import streamlit as st
import os
from P3M2 import Gui_search

words ="Search stuff "
st.title(words.capitalize())
st.divider()

search = st.text_input("Enter search term")
if search:
    for i in Gui_search(search):
        st.write(str(i))



