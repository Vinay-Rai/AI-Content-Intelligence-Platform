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


# YouTube transcript loading via yt-dlp's subtitle download (auto-generated
# captions), routed through the Webshare proxy. This avoids the
# youtube_transcript_api caption endpoint, which gets IP-blocked separately
# and more aggressively than yt-dlp's general video-info access.

def _get_secret(key):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key)


def _build_proxy_url():
    webshare_user = _get_secret("WEBSHARE_PROXY_USERNAME")
    webshare_pass = _get_secret("WEBSHARE_PROXY_PASSWORD")
    proxy_endpoint = _get_secret("WEBSHARE_PROXY_ENDPOINT") or "31.59.20.176:6754"

    if not (webshare_user and webshare_pass):
        return None

    from urllib.parse import quote

    encoded_user = quote(webshare_user, safe="")
    encoded_pass = quote(webshare_pass, safe="")
    return f"http://{encoded_user}:{encoded_pass}@{proxy_endpoint}"


def _vtt_to_text(vtt_path):
    """Strip VTT timing/formatting down to plain, deduplicated text."""
    with open(vtt_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    text_lines = []
    seen = set()

    for line in lines:
        line = line.strip()

        if not line:
            continue
        if line.startswith("WEBVTT"):
            continue
        if line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        if "-->" in line:
            continue
        if re.match(r"^\d+$", line):
            continue

        # Strip inline timestamp tags like <00:00:01.234> and formatting tags
        line = re.sub(r"<[^>]+>", "", line).strip()

        if not line:
            continue

        # Auto-generated captions repeat the same line across overlapping
        # windows; skip consecutive duplicates.
        if line not in seen:
            text_lines.append(line)
            seen.add(line)

    return " ".join(text_lines)


def load_youtube_transcript(url, api_key=None):
    with tempfile.TemporaryDirectory() as workdir:
        output_template = os.path.join(workdir, "subs.%(ext)s")

        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en"],
            "subtitlesformat": "vtt",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web"],
                }
            },
        }

        proxy_url = _build_proxy_url()
        if proxy_url:
            ydl_opts["proxy"] = proxy_url
        else:
            st.warning(
                "No Webshare proxy credentials found (WEBSHARE_PROXY_USERNAME / "
                "WEBSHARE_PROXY_PASSWORD). YouTube requests from cloud hosting "
                "will likely be blocked without a proxy."
            )

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        vtt_files = [
            f for f in os.listdir(workdir) if f.endswith(".vtt")
        ]

        if not vtt_files:
            raise RuntimeError(
                "No subtitles/captions were found for this video "
                "(it may not have English captions available)."
            )

        vtt_path = os.path.join(workdir, vtt_files[0])
        text = _vtt_to_text(vtt_path)

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
                    with st.spinner("Fetching transcript..."):
                        docs = load_youtube_transcript(generic_url)

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