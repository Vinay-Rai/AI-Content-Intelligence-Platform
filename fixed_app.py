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

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig


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


# YouTube transcript loading (proxy-enabled, to survive cloud-provider IP blocks)

def extract_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None


def load_youtube_transcript(url):
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Could not extract a video ID from that URL.")

    # If Webshare proxy credentials are set (as Streamlit secrets or env vars),
    # route the request through them. This is required on most cloud hosts
    # (Streamlit Cloud, AWS, GCP, etc.) since YouTube blocks those IP ranges
    # outright. Locally, it usually works fine without a proxy.
    def _get_secret(key):
        try:
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            pass
        return os.environ.get(key)

    webshare_user = _get_secret("WEBSHARE_PROXY_USERNAME")
    webshare_pass = _get_secret("WEBSHARE_PROXY_PASSWORD")

    if webshare_user and webshare_pass:
        ytt_api = YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=webshare_user,
                proxy_password=webshare_pass,
            )
        )
    else:
        st.warning(
            "No Webshare proxy credentials found (WEBSHARE_PROXY_USERNAME / "
            "WEBSHARE_PROXY_PASSWORD). YouTube transcript requests from cloud "
            "hosting will likely be rate-limited (429) without a proxy."
        )
        ytt_api = YouTubeTranscriptApi()

    transcript = ytt_api.fetch(video_id)
    text = " ".join(snippet.text for snippet in transcript)

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