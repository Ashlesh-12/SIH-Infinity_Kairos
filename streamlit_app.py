import streamlit as st

st.title("My First Streamlit App")

user_name = st.text_input("What's your name?")
if user_name:
    st.write("Hello,", user_name)   
