from io import BytesIO

import streamlit as st
from audiorecorder import audiorecorder

st.set_page_config(page_title="Notes AI", layout="centered")
st.title(":memo: Notes AI")
st.markdown("*Capture your thoughts with voice or text*")
st.divider()

input_mode = st.radio(
    "Select your note input method:",
    [":microphone: Audio Recording", ":pencil: Manual Typing"],
    horizontal=True,
)

if input_mode == ":microphone: Audio Recording":
    note_audio = audiorecorder(
        start_prompt="Start recording", stop_prompt="Stop Recording"
    )

    if note_audio:
        audio = BytesIO()
        note_audio.export(audio, format="mp3")
        note_audio_bytes = audio.getvalue()
        st.audio(note_audio_bytes, format="audio/mp3")

else:
    manual_note = st.text_area(
        "Type your note:", height=200, placeholder="Start typing your note here..."
    )
