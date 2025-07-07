# innerally.py (Streamlit app with integrated backend + frontend)

import streamlit as st
import sqlite3
import requests
import os
import time
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize database
DB_PATH = "journal.db"
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
init_db()

# Streamlit UI
st.set_page_config(page_title="InnerAlly Chatbot", layout="centered")
st.title("🧠 InnerAlly: Your Mental Wellness Companion")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

# ----------------------
# Chat Interface
# ----------------------
st.subheader("💬 Chat")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("How are you feeling today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("InnerAlly is responding..."):
        try:
            # Start new thread if needed
            if not st.session_state.thread_id:
                thread = client.beta.threads.create()
                st.session_state.thread_id = thread.id

            # Add message
            client.beta.threads.messages.create(
                thread_id=st.session_state.thread_id,
                role="user",
                content=prompt
            )

            # Run assistant
            run = client.beta.threads.runs.create(
                thread_id=st.session_state.thread_id,
                assistant_id=ASSISTANT_ID
            )

            # Poll until completion
            while True:
                run_status = client.beta.threads.runs.retrieve(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id
                )
                if run_status.status == "completed":
                    break
                elif run_status.status == "failed":
                    st.error("Assistant run failed")
                    st.stop()
                time.sleep(0.5)

            # Fetch latest message
            messages = client.beta.threads.messages.list(
                thread_id=st.session_state.thread_id
            )
            reply = messages.data[0].content[0].text.value

            st.session_state.messages.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant"):
                st.markdown(reply)

        except Exception as e:
            st.error(f"Failed to get response: {e}")

# ----------------------
# Journaling Interface
# ----------------------
st.subheader("📓 Daily Journal")
with st.form("journal_form"):
    journal_text = st.text_area("Write your thoughts:", height=150)
    submitted = st.form_submit_button("Save Journal Entry")
    if submitted and journal_text:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("INSERT INTO journal (entry) VALUES (?)", (journal_text,))
            st.success("Journal entry saved.")
        except Exception as e:
            st.error(f"Error saving journal entry: {e}")

# ----------------------
# .env.example (put in project root, NOT .env!)
# ----------------------
# OPENAI_API_KEY=your_openai_key_here
# ASSISTANT_ID=your_assistant_id_here
