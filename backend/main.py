import os
import io
import tempfile
import whisper
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from dotenv import load_dotenv
from typing import Optional

# Import the refactored helper functions
from utils import analyze_with_groq, read_pdf, read_docx, list_to_str

# Load environment variables from .env
load_dotenv()

# --------------------------
# Initialize FastAPI
# --------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------
# Load Whisper Model
# --------------------------
model = whisper.load_model("base")

# --------------------------
# Serve Frontend
# --------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

@app.get("/", response_class=HTMLResponse)
async def read_index():
    return FileResponse(os.path.join(PROJECT_ROOT, "index.html"))

@app.get("/style.css")
async def style():
    return FileResponse(os.path.join(PROJECT_ROOT, "style.css"))

@app.get("/script.js")
async def script():
    return FileResponse(os.path.join(PROJECT_ROOT, "script.js"))

# --------------------------
# API Endpoint
# --------------------------
@app.post("/analyze-interview/")
async def analyze_interview(
    file: UploadFile = File(...), 
    resume_file: Optional[UploadFile] = File(None)
):
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload audio.")

    temp_audio_file = None
    resume_text = None
    
    try:
        # --- 1. Process Resume File (using utils) ---
        if resume_file:
            resume_content = await resume_file.read()
            file_stream = io.BytesIO(resume_content)
            if resume_file.content_type == "application/pdf":
                resume_text = read_pdf(file_stream)
            elif resume_file.content_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
                resume_text = read_docx(file_stream)
            else:
                raise HTTPException(status_code=400, detail="Unsupported resume file type. Please upload a PDF or DOCX file.")

        # --- 2. Process Audio File ---
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            temp_audio_file = tmp.name
            audio_content = await file.read()
            tmp.write(audio_content)

        result = model.transcribe(temp_audio_file)
        transcript = result["text"]

        if not transcript.strip():
             raise HTTPException(status_code=400, detail="Could not transcribe audio. The file may be empty or silent.")

        # --- 3. Get AI Analysis (using utils) ---
        analysis_data = analyze_with_groq(transcript, resume_text)

        # --- 4. Format and Return Response (using utils) ---
        return {
            "transcript": transcript,
            "strengths": list_to_str(analysis_data.get("strengths", [])),
            "weaknesses": list_to_str(analysis_data.get("weaknesses", [])),
            "recommendations": list_to_str(analysis_data.get("recommendations", [])),
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

    finally:
        if temp_audio_file and os.path.exists(temp_audio_file):
            os.remove(temp_audio_file)