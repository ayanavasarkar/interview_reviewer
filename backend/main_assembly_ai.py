import os
import requests
import time
import json
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

# ----------------- Setup -----------------
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Keys
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not ASSEMBLYAI_API_KEY or not GROQ_API_KEY:
    raise RuntimeError("API keys for AssemblyAI or Groq not found in .env file")

groq_client = Groq(api_key=GROQ_API_KEY)

# ----------------- Pydantic Models -----------------
class AnalysisResponse(BaseModel):
    strengths: str
    weaknesses: str
    recommendations: str

class TranscriptRequest(BaseModel):
    transcript: str

# ----------------- AssemblyAI Helpers -----------------
def upload_to_assemblyai(audio_data: bytes, headers: dict) -> str:
    """Upload audio file to AssemblyAI in chunks."""
    upload_endpoint = "https://api.assemblyai.com/v2/upload"
    chunk_size = 5_242_880  # 5MB

    def read_chunks(data, size):
        for i in range(0, len(data), size):
            yield data[i:i+size]

    response = None
    for chunk in read_chunks(audio_data, chunk_size):
        response = requests.post(upload_endpoint, headers=headers, data=chunk)
        if response.status_code != 200:
            logger.error("AssemblyAI upload failed: %s", response.text)
            raise HTTPException(status_code=500, detail="Failed to upload audio to AssemblyAI.")
    return response.json()['upload_url']

def request_transcription(audio_url: str, headers: dict) -> str:
    transcript_endpoint = "https://api.assemblyai.com/v2/transcript"
    response = requests.post(transcript_endpoint, json={"audio_url": audio_url}, headers=headers)
    if response.status_code != 200 and response.status_code != 202:
        logger.error("AssemblyAI transcription start failed: %s", response.text)
        raise HTTPException(status_code=500, detail="Failed to start transcription.")
    return response.json()['id']

def poll_transcription(transcript_id: str, headers: dict, timeout: int = 300) -> str:
    transcript_endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
    start_time = time.time()

    while time.time() - start_time < timeout:
        response = requests.get(transcript_endpoint, headers=headers)
        result = response.json()
        status = result.get("status")

        if status == "completed":
            return result["text"]
        elif status == "error":
            logger.error("Transcription error: %s", result.get("error"))
            raise HTTPException(status_code=500, detail=f"Transcription failed: {result['error']}")

        time.sleep(3)

    raise HTTPException(status_code=500, detail="Transcription timed out.")

def transcribe_audio(audio_file: bytes) -> str:
    """Full transcription pipeline with AssemblyAI."""
    headers = {"authorization": ASSEMBLYAI_API_KEY}
    audio_url = upload_to_assemblyai(audio_file, headers)
    transcript_id = request_transcription(audio_url, headers)
    return poll_transcription(transcript_id, headers)

# ----------------- Groq Analysis Helper -----------------
def analyze_transcript_with_groq(transcript: str) -> dict:
    """Analyzes transcript with Groq API."""
    system_prompt = (
        "You are an expert interview coach. Analyze the following interview transcript. "
        "Identify the candidate's strengths, weaknesses, and provide actionable recommendations. "
        "Respond in JSON format with keys: strengths, weaknesses, recommendations."
    )

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ],
            model="llama3-8b-8192",
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        content = chat_completion.choices[0].message.content
        parsed = json.loads(content)

        # Normalize lists into strings
        def normalize(value):
            if isinstance(value, list):
                return "\n- " + "\n- ".join(value)
            return str(value)

        return {
            "strengths": normalize(parsed.get("strengths", "")),
            "weaknesses": normalize(parsed.get("weaknesses", "")),
            "recommendations": normalize(parsed.get("recommendations", "")),
        }
    except Exception as e:
        logger.error("Groq analysis failed: %s", str(e))
        raise HTTPException(status_code=500, detail="AI analysis failed.")


# ----------------- API Endpoints -----------------
@app.post("/analyze-interview/", response_model=AnalysisResponse)
async def analyze_interview(file: UploadFile = File(...)):
    """Upload an audio file, transcribe, and analyze it."""
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an audio file.")

    audio_data = await file.read()
    if len(audio_data) > 25 * 1024 * 1024:  # 25 MB limit
        raise HTTPException(status_code=400, detail="File too large. Max size is 25 MB.")

    transcript = transcribe_audio(audio_data)
    analysis = analyze_transcript_with_groq(transcript)
    return AnalysisResponse(**analysis)

@app.post("/transcribe/")
async def transcribe_endpoint(file: UploadFile = File(...)):
    """Upload audio and get only the transcript."""
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an audio file.")
    audio_data = await file.read()
    transcript = transcribe_audio(audio_data)
    return {"transcript": transcript}

@app.post("/analyze-text/", response_model=AnalysisResponse)
async def analyze_text(request: TranscriptRequest):
    """Analyze a raw transcript (without uploading audio)."""
    analysis = analyze_transcript_with_groq(request.transcript)
    return AnalysisResponse(**analysis)

@app.get("/")
def read_root():
    return {"status": "Interview Feedback API is running!"}
