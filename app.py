from io import BytesIO
from uuid import uuid4
from hashlib import md5
import streamlit as st
from audiorecorder import audiorecorder

from openai import OpenAI
from dotenv import dotenv_values

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams

#
# INIT
#

if "note_audio_bytes_md5" not in st.session_state:
    st.session_state["note_audio_bytes_md5"] = None

if "note_audio_bytes" not in st.session_state:
    st.session_state["note_audio_bytes"] = None

if "note_audio_text" not in st.session_state:
    st.session_state["note_audio_text"] = ""

if "note_text" not in st.session_state:
    st.session_state["note_text"] = ""

if "audio_key" not in st.session_state:
    st.session_state["audio_key"] = 0

if "text_key" not in st.session_state:
    st.session_state["text_key"] = 0

#
# ENVS, CLIENTS
#

env = dotenv_values(".env")


def get_openai_client():
    return OpenAI(api_key=st.session_state["openai_api_key"])


@st.cache_resource()
def get_qdrant_client():
    # return QdrantClient(path=":memory:")
    return QdrantClient(
        url=env["QDRANT_URL"],
        api_key=env["QDRANT_API_KEY"],
    )


#
# AUDIO TRANSCRIBE
#

AUDIO_TRANSCRIBE_MODEL = "whisper-1"


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
# QDRANT, GET EMBEDDING
#

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 3072
QDRANT_COLLECTION_NAME = "notes-ai"


def ensure_qdrant_collection_exists():
    qdrant_client = get_qdrant_client()

    if not qdrant_client.collection_exists(QDRANT_COLLECTION_NAME):
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
            ),
        )


def get_embedding(text):
    openai_client = get_openai_client()
    result = openai_client.embeddings.create(
        input=[text],
        model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIM,
    )

    return result.data[0].embedding


def upsert_note_to_qdrant(note_text):
    qdrant_client = get_qdrant_client()
    qdrant_client.upsert(
        collection_name=QDRANT_COLLECTION_NAME,
        points=[
            PointStruct(
                id=str(uuid4()),
                vector=get_embedding(text=note_text),
                payload={"text": note_text},
            )
        ],
    )

    st.session_state["note_audio_bytes_md5"] = None
    st.session_state["note_audio_bytes"] = None
    st.session_state["note_audio_text"] = ""
    st.session_state["note_text"] = ""
    st.session_state["audio_key"] += 1
    st.session_state["text_key"] += 1
    st.rerun()


def retrieve_notes_from_qdrant(query=None):
    qdrant_client = get_qdrant_client()
    if not query:
        notes = qdrant_client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=5,
        )[0]

        return [{"text": note.payload["text"], "score": None} for note in notes]

    notes = qdrant_client.search(
        collection_name=QDRANT_COLLECTION_NAME,
        query_vector=get_embedding(text=query),
        limit=5,
    )

    return [{"text": note.payload["text"], "score": note.score} for note in notes]


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

ensure_qdrant_collection_exists()

# OpenAI API key protection
if not st.session_state.get("openai_api_key"):
    if "OPENAI_API_KEY" in env:
        st.session_state["openai_api_key"] = env["OPENAI_API_KEY"]
    else:
        st.info("Add your OpenAI API key to use the application")
        st.session_state["openai_api_key"] = st.text_input(
            "API key",
            type="password",
        )
        if st.session_state["openai_api_key"]:
            st.rerun()

if not st.session_state.get("openai_api_key"):
    st.stop()

col1, col2 = st.tabs(["New note", "Search notes"])

with col1:
    input_mode = st.radio(
        "Select your note input method:",
        [":microphone: Audio Recording", ":pencil: Manual Typing"],
        horizontal=True,
    )

    if input_mode == ":microphone: Audio Recording":
        note_audio = audiorecorder(
            start_prompt="▶️ Start recording",
            stop_prompt="⏹️ Stop Recording",
            key=f"audio_recorder_{st.session_state.get('audio_key', 0)}",
        )

        if note_audio:
            audio = BytesIO()
            note_audio.export(
                audio,
                format="mp3",
            )
            st.session_state["note_audio_bytes"] = audio.getvalue()

            current_md5 = md5(st.session_state["note_audio_bytes"]).hexdigest()

            if st.session_state["note_audio_bytes_md5"] != current_md5:
                st.session_state["note_audio_text"] = ""
                st.session_state["note_audio_bytes_md5"] = current_md5

            st.audio(
                st.session_state["note_audio_bytes"],
                format="audio/mp3",
            )

            if st.button(
                "Transcribe audio",
                use_container_width=True,
            ):
                st.session_state["note_audio_text"] = transcribe_audio(
                    st.session_state["note_audio_bytes"],
                )

            if st.session_state["note_audio_text"]:
                st.session_state["note_audio_text"] = st.text_area(
                    "Audio transcription (you can edit):",
                    value=st.session_state["note_audio_text"],
                )

            if st.session_state["note_audio_text"] and st.button(
                "Save note",
                disabled=not st.session_state["note_audio_text"].strip(),
                use_container_width=True,
            ):
                upsert_note_to_qdrant(note_text=st.session_state["note_audio_text"])
                st.toast("Note saved!", icon="🎉")

    else:
        st.session_state["note_text"] = st.text_area(
            "Type your note:",
            value=st.session_state["note_text"],
            height=200,
            placeholder="Start typing your note here...",
            key=f"text_note_{st.session_state.get('text_key', 0)}",
        )

        if st.session_state["note_text"] and st.button(
            "Save note",
            disabled=not st.session_state["note_text"].strip(),
            use_container_width=True,
        ):
            st.toast("Note saved!", icon="🎉")
            upsert_note_to_qdrant(note_text=st.session_state["note_text"])

with col2:
    query = st.text_input("Search Notes")

    if st.button("Search", use_container_width=True):
        for note in retrieve_notes_from_qdrant(query):
            with st.container(border=True):
                st.markdown(note["text"])
                if note["score"] is not None:
                    st.markdown(f':violet[{note["score"]}]')
