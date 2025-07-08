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
        user_input = st.chat_input("Talk to InnerAlly...")
        if user_input:
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

    # --- Daily Mood Check-in ---
st.subheader("📋 Daily Mood Check-in")
with st.form("checkin_form"):
    mood = st.selectbox("How are you feeling today?", ["😊 Happy", "😐 Neutral", "😟 Sad", "😠 Angry", "😰 Anxious"])
    checkin_submit = st.form_submit_button("Submit Mood")
    if checkin_submit:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO checkins (mood) VALUES (?)", (mood,))
        st.success("Mood check-in saved!")

# --- Daily Journal Entry ---
st.subheader("📓 Daily Journal")
with st.form("journal_form"):
    journal_text = st.text_area("Write about your day...")
    journal_submit = st.form_submit_button("Save Journal Entry")
    if journal_submit:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO journal (entry) VALUES (?)", (journal_text,))
        st.success("Journal entry saved!")

# --- Healing Entry ---
st.subheader("🛠️ Healing Map Entry")
with st.form("healing_form"):
    emotional_intensity = st.slider("Emotional Intensity (1 = low, 10 = high)", 1, 10)
    triggers = st.text_input("What triggered the emotion?")
    tools = st.text_input("What tool did you use to regulate?")
    healing_submit = st.form_submit_button("Save Healing Entry")
    if healing_submit:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO healing_entries (emotional_intensity, triggers, tools) VALUES (?, ?, ?)",
                         (emotional_intensity, triggers, tools))
        st.success("Healing entry saved!")

# --- Mood Trends ---
st.subheader("📈 Mood Trends")
with sqlite3.connect(DB_PATH) as conn:
    df_mood = pd.read_sql_query("SELECT * FROM checkins", conn, parse_dates=["timestamp"])

if not df_mood.empty:
    df_mood["date"] = pd.to_datetime(df_mood["timestamp"]).dt.date
    chart_data = df_mood.groupby("date")["mood"].agg(lambda x: x.value_counts().idxmax()).reset_index()
    chart_data["mood"] = chart_data["mood"].str.extract(r"([a-zA-Z]+)")
    mood_chart = alt.Chart(chart_data).mark_line(point=True).encode(
        x="date:T",
        y=alt.Y("mood:N", sort=None),
        tooltip=["date", "mood"]
    ).properties(height=300)
    st.altair_chart(mood_chart, use_container_width=True)
else:
    st.info("No mood data to display yet.")

# --- Journal History ---
st.subheader("🕰️ Journal History")
with sqlite3.connect(DB_PATH) as conn:
    df_journal = pd.read_sql_query("SELECT * FROM journal ORDER BY timestamp DESC", conn)

if not df_journal.empty:
    for _, row in df_journal.iterrows():
        st.markdown(f"**{row['timestamp']}**\n\n{row['entry']}")
