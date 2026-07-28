import asyncio
import os
import re
import traceback

import edge_tts
import streamlit as st
import validators

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_groq import ChatGroq
from langchain_community.document_loaders import UnstructuredURLLoader

import tempfile
import yt_dlp
from groq import Groq


# Cache LLM

@st.cache_resource
def get_llm(api_key):
    return ChatGroq(
        groq_api_key=api_key,
        model="llama-3.3-70b-versatile"
    )

# Streamlit Config

st.set_page_config(
    page_title="AI Website & YouTube Summarizer",
    page_icon="🦜",
    layout="wide",
)

st.title("🦜 AI Website & YouTube Summarizer")
st.subheader("Summarize any YouTube Video or Website")


# Sidebar

with st.sidebar:

    st.header("Settings")

    groq_api_key = st.text_input(
        "Groq API Key",
        type="password"
    )

    voice = st.selectbox(
        "Voice",
        [
            "en-IN-NeerjaNeural",
            "en-IN-PrabhatNeural",
            "en-US-JennyNeural",
            "en-US-GuyNeural",
            "en-GB-SoniaNeural",
            "en-GB-RyanNeural",
        ]
    )

    rate = st.selectbox(
        "Speech Speed",
        [
            "+0%",
            "+10%",
            "+20%",
            "-10%",
            "-20%",
        ]
    )

generic_url = st.text_input(
    "Enter YouTube or Website URL"
)


# Prompt

prompt = ChatPromptTemplate.from_template(
    """
You are an expert summarizer.

Summarize the following content.

Requirements:

- Give a concise summary.
- Mention important points.
- Keep it easy to understand.
- Use bullet points wherever appropriate.

Content:

{text}
"""
)


# Text to Speech

async def generate_audio(
    text,
    voice_name,
    speech_rate,
    output_file,
):
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice_name,
        rate=speech_rate,
    )

    await communicate.save(output_file)


# Clean the summary before converting to speech

def clean_text_for_tts(text):
    # Remove bold (**text**)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)

    # Remove italic (*text*)
    text = re.sub(r"\*(.*?)\*", r"\1", text)

    # Remove markdown headings
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)

    # Remove bullet symbols
    text = re.sub(r"^\s*[-*•]\s*", "", text, flags=re.MULTILINE)

    # Remove numbered lists like "1."
    text = re.sub(r"^\s*\d+\.\s*", "", text, flags=re.MULTILINE)

    # Remove backticks
    text = text.replace("`", "")

    # Collapse multiple blank lines
    text = re.sub(r"\n\s*\n", "\n", text)

    return text.strip()


# YouTube transcript loading via audio download + Groq Whisper transcription.
# This avoids YouTube's transcript/caption endpoint entirely (the thing that
# was getting IP-blocked / 429'd), by downloading the audio track and
# transcribing it ourselves.

# Groq's free-tier audio endpoint caps uploaded files at 25 MB, which is
# roughly 30-40 minutes of compressed mono audio. Adjust if you're on a
# paid Groq tier with a higher limit.
MAX_AUDIO_MB = 25


def _get_secret(key):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key)


def download_youtube_audio(url, workdir):
    output_template = os.path.join(workdir, "audio.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "64",  # smaller file, plenty for speech
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # The default "web" client increasingly triggers 403s due to
        # YouTube's signature/PO-token checks. The android/ios clients
        # use a simpler API that avoids most of that.
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web"],
            }
        },
    }

    # On cloud hosting, YouTube blocks datacenter IPs from downloading
    # video/audio too (not just the transcript endpoint). Route through a
    # Webshare residential proxy if credentials are configured.
    webshare_user = _get_secret("WEBSHARE_PROXY_USERNAME")
    webshare_pass = _get_secret("WEBSHARE_PROXY_PASSWORD")

    if webshare_user and webshare_pass:
        from urllib.parse import quote

        encoded_user = quote(webshare_user, safe="")
        encoded_pass = quote(webshare_pass, safe="")
        # Use the specific proxy endpoint shown in your Webshare dashboard
        # (Proxy -> List), not the general rotating gateway, since that
        # wasn't matching your currently allocated proxy list.
        proxy_endpoint = _get_secret("WEBSHARE_PROXY_ENDPOINT") or "31.59.20.176:6754"
        ydl_opts["proxy"] = (
            f"http://{encoded_user}:{encoded_pass}@{proxy_endpoint}"
        )
    else:
        st.warning(
            "No Webshare proxy credentials found. YouTube audio downloads "
            "from cloud hosting will likely be blocked (403) without a proxy."
        )

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    audio_path = os.path.join(workdir, "audio.mp3")
    if not os.path.exists(audio_path):
        raise RuntimeError("Audio download did not produce an output file.")

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if size_mb > MAX_AUDIO_MB:
        raise RuntimeError(
            f"Downloaded audio is {size_mb:.1f} MB, which exceeds the "
            f"{MAX_AUDIO_MB} MB limit for transcription. Try a shorter video."
        )

    return audio_path


def transcribe_audio_with_groq(audio_path, api_key):
    client = Groq(api_key=api_key)

    with open(audio_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), f.read()),
            model="whisper-large-v3-turbo",
            response_format="text",
        )

    # response_format="text" returns a plain string in recent groq SDK
    # versions; fall back to .text if a structured object is returned.
    if isinstance(transcription, str):
        return transcription
    return getattr(transcription, "text", str(transcription))


def load_youtube_transcript(url, api_key):
    with tempfile.TemporaryDirectory() as workdir:
        audio_path = download_youtube_audio(url, workdir)
        text = transcribe_audio_with_groq(audio_path, api_key)

    return [Document(page_content=text, metadata={"source": url})]


# Button

if st.button("Generate Summary"):

    if not groq_api_key.strip():
        st.error("Please enter your Groq API Key.")

    elif not generic_url.strip():
        st.error("Please enter a URL.")

    elif not validators.url(generic_url):
        st.error("Invalid URL.")

    else:
        llm = get_llm(groq_api_key)
        try:

            with st.spinner("Loading content..."):

                if (
                    "youtube.com" in generic_url
                    or "youtu.be" in generic_url
                ):
                    with st.spinner("Downloading audio and transcribing..."):
                        docs = load_youtube_transcript(generic_url, groq_api_key)

                else:
                    loader = UnstructuredURLLoader(
                        urls=[generic_url],
                        ssl_verify=False,
                        headers={
                            "User-Agent":
                            "Mozilla/5.0"
                        },
                    )
                    docs = loader.load()

                if len(docs) == 0:
                    st.error("No content found.")
                    st.stop()

                # Extract text
                text = "\n\n".join(
                    doc.page_content
                    for doc in docs
                )

            with st.spinner("Generating summary..."):

                chain = (
                    prompt
                    | llm
                    | StrOutputParser()
                )

                summary = chain.invoke(
                    {
                        "text": text
                    }
                )

            st.success("Summary Generated!")

            st.markdown("## 📄 Summary")

            st.write(summary)

            # Generate Audio

            with st.spinner("Generating Audio..."):

                audio_file = "summary.mp3"

                clean_summary = clean_text_for_tts(summary)
                asyncio.run(
                    generate_audio(
                        clean_summary,
                        voice,
                        rate,
                        audio_file,
                    )
                )

            st.markdown("## 🔊 Audio Summary")

            st.audio(audio_file)

            with open(audio_file, "rb") as audio:

                st.download_button(
                    label="⬇ Download MP3",
                    data=audio,
                    file_name="summary.mp3",
                    mime="audio/mpeg",
                )

        except Exception as e:

            st.error(type(e).__name__)
            st.error(str(e))
            st.code(traceback.format_exc())