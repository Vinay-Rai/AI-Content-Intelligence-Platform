# 🦜 AI Website & YouTube Summarizer

Paste in any website URL or YouTube link and get back a clean, bullet-pointed summary — plus a natural-sounding audio version you can play or download. Built with Streamlit, LangChain, and Groq's LLaMA 3.3.

---

## ✨ Features

- 🌐 **Website summarization** — paste any article/blog URL and get a concise, structured summary
- 📺 **YouTube summarization** — paste a video link and get a summary of its spoken content, no manual transcript needed
- 🔊 **Audio summaries** — every summary is converted into natural-sounding speech (multiple voice/accent options) that you can play in-browser or download as an MP3
- ⚡ Powered by **Groq's LLaMA 3.3 70B** for fast, high-quality summarization
- 🎙️ Text-to-speech via **edge-tts**, speech-to-text via **Groq Whisper**

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| UI / App framework | [Streamlit](https://streamlit.io) |
| LLM orchestration | [LangChain](https://www.langchain.com) |
| Summarization model | Groq — LLaMA 3.3 70B Versatile |
| YouTube audio extraction | [yt-dlp](https://github.com/yt-dlp/yt-dlp) |
| Speech-to-text | Groq Whisper (`whisper-large-v3-turbo`) |
| Text-to-speech | [edge-tts](https://github.com/rany2/edge-tts) |
| Website content extraction | `unstructured` (via LangChain), with a `requests` + `BeautifulSoup` fallback |
| Proxy (cloud deployment) | Webshare residential proxy |

---

## 🧠 How It Works

```
User pastes URL
      │
      ├── YouTube link? ──► yt-dlp downloads audio ──► Groq Whisper transcribes it
      │
      └── Website link?  ──► UnstructuredURLLoader extracts text
                              (falls back to requests + BeautifulSoup if empty)
      │
      ▼
LangChain prompt ──► Groq LLaMA 3.3 ──► Bullet-point summary
      │
      ▼
edge-tts converts summary to speech ──► Playable / downloadable MP3
```

### Why audio download instead of YouTube's transcript API?

YouTube aggressively rate-limits and IP-blocks its caption/transcript endpoint, especially from cloud-hosted apps (AWS, GCP, Azure, and by extension most PaaS platforms like Streamlit Cloud). After testing multiple approaches — the official transcript API, `yt-dlp`'s subtitle downloader, and various proxy configurations — the most reliable path turned out to be downloading the audio track (a far less aggressively policed endpoint) and transcribing it directly with Whisper. This trades a bit of speed for significantly better reliability in production.

---

## 📦 Setup

### 1. Clone the repo

```bash
git clone https://github.com/Vinay-Rai/AI-Content-Intelligence-Platform
cd AI-Content-Intelligence-Platform
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install `ffmpeg` (required for audio extraction)

- **Windows**: [Download from ffmpeg.org](https://ffmpeg.org/download.html), or `choco install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Linux (Debian/Ubuntu)**: `sudo apt install ffmpeg`

Verify with:
```bash
ffmpeg -version
```

### 4. Get a Groq API key

Sign up at [console.groq.com](https://console.groq.com) and generate an API key. You'll paste this into the app's sidebar at runtime — it's not stored anywhere.

### 5. Run locally

```bash
streamlit run app.py
```

---

## ☁️ Deploying to Streamlit Cloud

Cloud-hosted apps run on data center IPs, which YouTube blocks more aggressively than residential IPs. To keep YouTube summarization working in production, this app routes those specific requests through a residential proxy.

### Required files

- **`requirements.txt`** — Python dependencies
- **`packages.txt`** — system-level dependencies (must contain `ffmpeg`)

### Required secrets

In your Streamlit Cloud app → **Settings → Secrets**, add:

```toml
WEBSHARE_PROXY_USERNAME = "your-webshare-proxy-username"
WEBSHARE_PROXY_PASSWORD = "your-webshare-proxy-password"
WEBSHARE_PROXY_ENDPOINT = "your-proxy-ip:port"   # optional, has a fallback default
```

Get these from your [Webshare](https://www.webshare.io) dashboard under **Proxy → List** (use a specific allocated IP:port, and make sure your account's authentication mode is set to **Username/Password**, not IP whitelisting).

> ⚠️ Without proxy credentials, the app will still run, but YouTube link summarization will likely fail on cloud hosting due to IP blocking. It works fine locally without a proxy.

---

## 📁 Project Structure

```
.
├── fixed_app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── packages.txt         # System dependencies (ffmpeg) for Streamlit Cloud
└── README.md
```

---

## ⚠️ Known Limitations

- **25 MB audio cap** for YouTube transcription (Groq's free-tier Whisper limit — roughly a 30–40 minute video at the bitrate used here). Longer videos return a clear error rather than failing silently.
- **JavaScript-heavy websites**: some sites render their content client-side, which a server-side fetch can't see. The app falls back from `unstructured` to a direct HTML fetch, but genuinely JS-only content will still fail with a clear error message.
- **Proxy dependency**: YouTube summarization on cloud deployments depends on a working residential proxy. If your proxy IP gets rotated/deallocated by your provider, update the `WEBSHARE_PROXY_ENDPOINT` secret with a fresh one from your dashboard.

---

## 🗺️ Possible Future Improvements

- Support for additional languages (currently defaults to English captions/audio)
- Headless-browser fallback (e.g. Playwright) for fully JS-rendered websites
- Rotating across multiple proxy IPs automatically instead of relying on one static endpoint
- Summary length/tone customization (e.g. executive summary vs. detailed notes)

---



## 🙋 Author

**Vinay Rai**

If you found this project useful, consider giving it a ⭐ on GitHub.
