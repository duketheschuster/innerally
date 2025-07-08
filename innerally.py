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
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("REPLACE INTO onboarding (id, name, core_values, emotional_triggers) VALUES (1, ?, ?, ?)",
                             (name, core_values, emotional_triggers))
            st.session_state.onboarded = True
            st.rerun()
else:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Layout with sidebar for tools
    left_col, right_col = st.columns([1, 2])

    # ----------------------
    # Sidebar Tools: Daily Check-In, Journal, Healing Map
    # ----------------------
    with left_col:
        st.subheader("📅 Daily Check-In")
        mood = st.radio("How are you feeling today?", ["😊 Good", "😐 Okay", "😞 Not great"])
        if st.button("Submit Check-In"):
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("INSERT INTO checkins (mood) VALUES (?)", (mood,))
                st.success(f"Your check-in for today is recorded: {mood}")
            except Exception as e:
                st.error(f"Error saving check-in: {e}")

        # Mood trend chart
        st.subheader("📈 Mood Trends")
        try:
            with sqlite3.connect(DB_PATH) as conn:
                df = pd.read_sql_query("SELECT mood, timestamp FROM checkins ORDER BY timestamp", conn)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                chart = alt.Chart(df).mark_line(point=True).encode(
                    x='timestamp:T',
                    y=alt.Y('mood:N', sort=["😞 Not great", "😐 Okay", "😊 Good"]),
                    tooltip=['timestamp:T', 'mood:N']
                ).properties(height=200)
                st.altair_chart(chart, use_container_width=True)
        except Exception as e:
            st.error(f"Error loading mood trends: {e}")

        # --- Journal + Healing Entry Form ---
        st.subheader("📓 Daily Journal & Healing Entry")

        # Load triggers from onboarding DB
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT emotional_triggers FROM onboarding WHERE id = 1").fetchone()
            triggers_list = []
            if row and row[0]:
                triggers_list = [t.strip() for t in row[0].replace('\n', ',').split(',') if t.strip()]

        healing_tools = [
            "Journaling",
            "Deep Breathing",
            "Meditation",
            "Exercise",
            "Talking with Friend",
            "Creative Expression",
            "Nature Walk",
            "Mindfulness",
        ]

        with st.form("journal_healing_form"):
            journal_text = st.text_area("Write your thoughts:", height=150)
            emotional_intensity = st.slider("Rate your emotional intensity (1 = low, 5 = high)", 1, 5, 3)
            selected_triggers = st.multiselect("Select emotional triggers you experienced", options=triggers_list)
            selected_tools = st.multiselect("Which healing tools did you use?", options=healing_tools)
            submitted = st.form_submit_button("Save Journal & Healing Entry")

            if submitted and journal_text:
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute("INSERT INTO journal (entry) VALUES (?)", (journal_text,))
                        conn.execute(
                            "INSERT INTO healing_entries (emotional_intensity, triggers, tools) VALUES (?, ?, ?)",
                            (
                                emotional_intensity,
                                ",".join(selected_triggers),
                                ",".join(selected_tools),
                            ),
                        )
                    st.success("Journal entry and healing data saved.")
                except Exception as e:
                    st.error(f"Error saving entries: {e}")

        # Journal History
        st.subheader("📚 Journal History")
        try:
            with sqlite3.connect(DB_PATH) as conn:
                journal_entries = conn.execute("SELECT timestamp, entry FROM journal ORDER BY timestamp DESC").fetchall()
            for timestamp, entry in journal_entries:
                st.markdown(f"**{timestamp}**\n\n{entry}")
        except Exception as e:
            st.error(f"Error loading journal entries: {e}")

        # Healing Map Radial Chart
        st.subheader("🗺️ Healing Map Radial Chart")

        try:
            with sqlite3.connect(DB_PATH) as conn:
                df = pd.read_sql_query("SELECT emotional_intensity, triggers, tools FROM healing_entries ORDER BY timestamp DESC LIMIT 30", conn)

            if not df.empty:
                df['triggers_list'] = df['triggers'].apply(lambda x: x.split(',') if x else [])
                df['tools_list'] = df['tools'].apply(lambda x: x.split(',') if x else [])

                unique_triggers = sorted(set(t for sublist in df['triggers_list'] for t in sublist if t))
                unique_tools = sorted(set(t for sublist in df['tools_list'] for t in sublist if t))

                data = []

                avg_intensity = df['emotional_intensity'].mean()
                data.append({"category": "Emotional Intensity", "value": avg_intensity})

                for trig in unique_triggers:
                    freq = df['triggers_list'].apply(lambda lst: trig in lst).mean() * 5
                    data.append({"category": f"Trigger: {trig}", "value": freq})

                for tool in unique_tools:
                    freq = df['tools_list'].apply(lambda lst: tool in lst).mean() * 5
                    data.append({"category": f"Tool: {tool}", "value": freq})

                chart_df = pd.DataFrame(data)

                chart = (
                    alt.Chart(chart_df)
                    .mark_line(point=True)
                    .encode(
                        theta=alt.Theta("category:N", sort=chart_df["category"].tolist()),
                        radius=alt.Radius("value:Q", scale=alt.Scale(type="linear", domain=[0, 5])),
                        tooltip=["category", alt.Tooltip("value", format=".2f")],
                    )
                    .properties(width=400, height=400)
                )
                st.altair_chart(chart)
            else:
                st.info("Add some healing entries to see your Healing Map here.")

        except Exception as e:
            st.error(f"Error loading Healing Map: {e}")

    # ----------------------
    # Right Column: Chat Interface
    # ----------------------
    with right_col:
        st.subheader("💬 Chat with InnerAlly")

    # Display messages inside an expandable container
    with st.container():
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Custom input field at bottom of right column
    with st.form("chat_form"):
        user_input = st.text_input("Talk to InnerAlly...", key="chat_input")
        submit = st.form_submit_button("Send")

    if submit and user_input:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.spinner("InnerAlly is responding..."):
            try:
                if not st.session_state.thread_id:
                    thread = client.beta.threads.create()
                    st.session_state.thread_id = thread.id

                # Add onboarding context at start
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

# ----------------------
# .env.example (put in project root, NOT .env!)
# ----------------------
# OPENAI_API_KEY=your_openai_key_here
# ASSISTANT_ID=your_assistant_id_here
