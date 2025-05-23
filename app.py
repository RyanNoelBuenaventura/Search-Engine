import streamlit as st
import os
from P3M2 import Gui_search

words ="Uci ICS Search Engine"
st.title(words.capitalize())
st.divider()

search = st.text_input("Enter search term")
if search:
    result = Gui_search(search)[0].split('\n')[1:]
    print(result)
    for i in result:
        st.write(str(i))



