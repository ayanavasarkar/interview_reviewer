import os
import whisper
import json
import tempfile
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Force Whisper and Torch to use /app/.cache
os.environ["XDG_CACHE_HOME"] = "/app/.cache"
os.environ["TORCH_HOME"] = "/app/.cache/torch"
os.environ["TRANSFORMERS_CACHE"] = "/app/.cache/huggingface"

# --------------------------
# Initialize FastAPI
# --------------------------
app = FastAPI()

# Allow CORS
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
model = whisper.load_model("base")  # choose "small", "medium", etc. for speed vs accuracy

# --------------------------
# Initialize Groq Client
# --------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in environment variables")

groq_client = Groq(api_key=GROQ_API_KEY)

# --------------------------
# Frontend file paths
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
# Helper: Analyze transcript with Groq + LLaMA
# --------------------------

def list_to_str(lst):
    """Ensure all items in a list are strings and join with newlines."""
    return "\n".join([str(item) for item in lst])

def analyze_with_groq(transcript: str) -> dict:
    """
    Sends the transcript to Groq LLaMA model and returns analysis JSON.
    """
    system_prompt = (
        "You are an expert interview coach. Analyze the following interview transcript. "
        "Identify the candidate's strengths, weaknesses, and provide actionable recommendations. "
        "Format your response as a JSON object with three keys: 'strengths', 'weaknesses', 'recommendations'."
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

        analysis_json = chat_completion.choices[0].message.content
        return json.loads(analysis_json)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Groq analysis failed: {str(e)}")

# --------------------------
# Analyze Interview Endpoint
# --------------------------
@app.post("/analyze-interview/")
async def analyze_interview(file: UploadFile = File(...)):
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload audio.")

    try:
        # Create a temporary file in a safe directory
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            temp_file = tmp.name
            tmp.write(await file.read())

        # Transcribe audio
        result = model.transcribe(temp_file)
        transcript = result["text"]

        # Analyze transcript
        analysis_data = analyze_with_groq(transcript)

        # Convert lists to strings for frontend display
        strengths = list_to_str(analysis_data.get("strengths", []))
        weaknesses = list_to_str(analysis_data.get("weaknesses", []))
        recommendations = list_to_str(analysis_data.get("recommendations", []))

        print("Processing complete")
        return {
            "transcript": transcript,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

    finally:
        if 'temp_file' in locals() and os.path.exists(temp_file):
            os.remove(temp_file)
