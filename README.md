# 🧠 AI-Content-Intelligence-Platform


An AI-powered content intelligence application that summarizes **YouTube
videos** and **web pages** into concise, easy-to-understand summaries
and can convert those summaries into **natural-sounding downloadable MP3
audio**.

Built with **LangChain**, **Groq Llama 3.3**, **Streamlit**, and
**Microsoft Edge Neural Text-to-Speech**, InsightAI helps users consume
long-form content in minutes.

------------------------------------------------------------------------

## ✨ Features

-   🎥 Summarize YouTube videos using transcripts
-   🌐 Summarize website content from URLs
-   🤖 AI-powered summarization with Groq Llama 3.3
-   🔊 Generate downloadable MP3 audio summaries
-   🎙️ Multiple neural voice options
-   ⚡ Adjustable speech speed
-   ▶️ In-app audio playback
-   ✅ URL validation and robust error handling
-   💻 Clean Streamlit interface

------------------------------------------------------------------------

## 🛠️ Tech Stack

Technologies
  ---------------- --------------------------------------------------
Python,
Streamlit,
LangChain (LCEL),
Groq Llama 3.3-70B, 
UnstructuredURLLoader,
YouTube Loader,    
Microsoft Edge TTS,
validators

------------------------------------------------------------------------

## 📌 Workflow

``` text
User URL
   │
   ▼
Detect Source
   │
   ├── YouTube Transcript
   └── Website Extraction
            │
            ▼
      LangChain Pipeline
            │
            ▼
     Groq Llama 3.3 Summary
            │
      ┌─────┴─────┐
      ▼           ▼
 Text Summary   MP3 Audio
      │           │
      └─────┬─────┘
            ▼
      Streamlit Interface
```

------------------------------------------------------------------------

## 🚀 Installation

### Clone the repository

``` bash
git clone https://github.com/Vinay-Rai/AI-Content-Intelligence-Platform
cd AI-Content-Intelligence-Platform
```

### Create a virtual environment

``` bash
python -m venv venv
```

Activate it:

**Windows**

``` bash
venv\Scripts\activate
```

**macOS/Linux**

``` bash
source venv/bin/activate
```

### Install dependencies

``` bash
pip install -r requirements.txt
```

### Run the application

``` bash
streamlit run app.py
```

------------------------------------------------------------------------

## 📖 How to Use

1.  Launch the Streamlit application.
2.  Enter your **Groq API Key**.
3.  Paste a YouTube or Website URL.
4.  Click **Generate Summary**.
5.  Read the AI-generated summary.
6.  Listen using the built-in audio player.
7.  Download the MP3 summary.

------------------------------------------------------------------------

## 📂 Project Structure

``` text
InsightAI/
│
├── app.py
├── requirements.txt
├── README.md
├── generated_audio/

```

------------------------------------------------------------------------

## 🌟 Future Enhancements

-   Chat with YouTube videos and websites (RAG)
-   Multi-language summaries
-   PDF & DOCX export
-   AI-generated quizzes and flashcards
-   Keyword extraction
-   Timestamp-aware video summaries
-   Summary history
-   Multiple LLM providers

------------------------------------------------------------------------

## 👨‍💻 Author

**Vinay Rai**

If you found this project useful, consider giving it a ⭐ on GitHub.
