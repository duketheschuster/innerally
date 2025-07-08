# innerally.py (Streamlit app with integrated backend + frontend)

import streamlit as st
import sqlite3
import os
import time
import pandas as pd
import altair as alt
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mood TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS onboarding (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT,
                core_values TEXT,
                emotional_triggers TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS healing_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                emotional_intensity INTEGER,
                triggers TEXT,
                tools TEXT
            )
        """)
init_db()

# Streamlit UI
st.set_page_config(page_title="InnerAlly Chatbot", layout="wide")
st.title("🧠 InnerAlly: Your Mental Wellness Companion")

# Onboarding
if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

if not st.session_state.onboarded:
    st.subheader("👋 Welcome to InnerAlly!")
    with st.form("onboarding_form"):
        name = st.text_input("What is your name?")
        core_values = st.text_area("What are your core values?")
        emotional_triggers = st.text_area("What emotional triggers should I be aware of?")
        submitted = st.form_submit_button("Save and Start")
        if submitted:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("REPLACE INTO onboarding (id, name, core_values, emotional_triggers) VALUES (1, ?, ?, ?)",
                                 (name, core_values, emotional_triggers))
                st.session_state.onboarded = True
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save onboarding data: {e}")

else:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "chat_key" not in st.session_state:
        st.session_state.chat_key = 0

    # --- Chat at top ---
    st.subheader("💬 Chat with InnerAlly")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    chat_container = st.container()
    with chat_container:
        user_input = st.text_input("Talk to InnerAlly...", key=f"chat_input_{st.session_state.chat_key}")
        if st.button("Send", key="send_button") and user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            st.session_state.chat_key += 1  # Causes text input to reset
            with st.chat_message("user"):
                st.markdown(user_input)

            with st.spinner("InnerAlly is responding..."):
                try:
                    if not st.session_state.thread_id:
                        thread = client.beta.threads.create()
                        st.session_state.thread_id = thread.id

                    if len(st.session_state.messages) == 1:
                        with sqlite3.connect(DB_PATH) as conn:
                            cur = conn.execute("SELECT name, core_values, emotional_triggers FROM onboarding WHERE id = 1")
                            row = cur.fetchone()
                            if row:
                                context = f"User Info:\nName: {row[0]}\nCore Values: {row[1]}\nEmotional Triggers: {row[2]}"
                                client.beta.threads.messages.create(
                                    thread_id=st.session_state.thread_id,
                                    role="user",
                                    content=context
                                )

                    client.beta.threads.messages.create(
                        thread_id=st.session_state.thread_id,
                        role="user",
                        content=user_input
                    )

                    run = client.beta.threads.runs.create(
                        thread_id=st.session_state.thread_id,
                        assistant_id=ASSISTANT_ID
                    )

                    while True:
                        run_status = client.beta.threads.runs.retrieve(
                            thread_id=st.session_state.thread_id,
                            run_id=run.id
                        )
                        if run_status.status == "completed":
                            break
                        elif run_status.status == "failed":
                            error_msg = run_status.last_error.get("message", "Unknown error")
                            st.error(f"Assistant run failed: {error_msg}")
                            st.stop()
                        time.sleep(0.5)

                    messages = client.beta.threads.messages.list(
                        thread_id=st.session_state.thread_id
                    )
                    reply = messages.data[0].content[0].text.value

                    st.session_state.messages.append({"role": "assistant", "content": reply})
                    with st.chat_message("assistant"):
                        st.markdown(reply)

                except Exception as e:
                    st.error(f"Failed to get response: {e}")

    # [Remaining unchanged code continues here for check-in, journal, data...]
