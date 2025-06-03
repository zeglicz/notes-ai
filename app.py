from io import BytesIO
import streamlit as st
from audiorecorder import audiorecorder

from openai import OpenAI
from dotenv import dotenv_values

#
# INIT
#

if "note_audio_bytes" not in st.session_state:
    st.session_state["note_audio_bytes"] = None

if "note_audio_text" not in st.session_state:
    st.session_state["note_audio_text"] = ""

if "note_text" not in st.session_state:
    st.session_state["note_text"] = ""

#
# AUDIO TRANSCRIBE
#

AUDIO_TRANSCRIBE_MODEL = "whisper-1"

env = dotenv_values(".env")


@st.cache_resource
def get_openai_client():
    return OpenAI(api_key=env["OPENAI_API_KEY"])


def transcribe_audio(audio_bytes):
    openai_client = get_openai_client()
    audio_file = BytesIO(audio_bytes)
    audio_file.name = "audio.mp3"
    transcript = openai_client.audio.transcriptions.create(
        file=audio_file,
        model=AUDIO_TRANSCRIBE_MODEL,
        response_format="verbose_json",
    )

    return transcript.text


#
# MAIN
#

st.set_page_config(
    page_title="Notes AI",
    page_icon=":memo:",
    layout="centered",
)
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
        start_prompt="Start recording",
        stop_prompt="Stop Recording",
    )

    if note_audio:
        audio = BytesIO()
        note_audio.export(
            audio,
            format="mp3",
        )
        st.session_state["note_audio_bytes"] = audio.getvalue()
        st.audio(
            st.session_state["note_audio_bytes"],
            format="audio/mp3",
        )

        if st.button("Transcribe audio"):
            st.session_state["note_audio_text"] = transcribe_audio(
                st.session_state["note_audio_bytes"],
            )

        if st.session_state["note_audio_bytes"]:
            st.text_area(
                "Transcribed audio",
                value=st.session_state["note_audio_text"],
                # disabled=True,
            )

else:
    st.session_state["note_text"] = st.text_area(
        "Type your note:",
        height=200,
        placeholder="Start typing your note here...",
    )
