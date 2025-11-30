import streamlit as st
import os
import logging
import sys

print("DEBUG: HELLO FROM DEBUG APP")

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
log_dir = os.path.join(project_root, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "debug_app.log")

with open(log_file, "w") as f:
    f.write("Log file created\n")

logging.basicConfig(filename=log_file, level=logging.DEBUG)
logging.info("Logging started")

st.title("Debug App")
st.write("If you see this, it works.")
