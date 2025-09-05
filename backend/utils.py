import io
import json
import os
from typing import Optional, List

import docx
import PyPDF2
from fastapi import HTTPException
from groq import Groq

# --------------------------
# Initialize Groq Client
# --------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in environment variables")
groq_client = Groq(api_key=GROQ_API_KEY)


# --------------------------
# Text Extraction Helpers
# --------------------------
def read_pdf(file_stream: io.BytesIO) -> str:
    """Extracts text from a PDF file stream."""
    try:
        pdf_reader = PyPDF2.PdfReader(file_stream)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read PDF file: {e}")

def read_docx(file_stream: io.BytesIO) -> str:
    """Extracts text from a DOCX file stream."""
    try:
        doc = docx.Document(file_stream)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read DOCX file: {e}")


# --------------------------
# AI Analysis Helper
# --------------------------
def analyze_with_groq(transcript: str, resume_text: Optional[str] = None) -> dict:
    """
    Sends the transcript (and optional resume) to Groq LLaMA and returns analysis.
    """
    system_prompt_template = """
        You are an expert interview coach. Analyze the following interview transcript.
        {resume_context}
        Identify the candidate's strengths, weaknesses, and provide actionable recommendations.
        Your feedback should be insightful and directly related to the content of the interview.
        
        Format your response as a single JSON object with three keys: 'strengths', 'weaknesses', 'recommendations'.
    """
    
    if resume_text:
        resume_context = (
            "The candidate's resume is provided below. Use it to cross-reference their spoken experience. "
            "Tailor your feedback based on both the interview and the resume.\n\n"
            f"--- RESUME ---\n{resume_text}\n--- END RESUME ---"
        )
    else:
        resume_context = ""

    system_prompt = system_prompt_template.format(resume_context=resume_context)

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ],
            model="llama-3.1-8b-instant",
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        analysis_json = chat_completion.choices[0].message.content
        return json.loads(analysis_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Groq analysis failed: {str(e)}")


# --------------------------
# Formatting Helper
# --------------------------
def list_to_str(lst: List[str]) -> str:
    """Ensure all items in a list are strings and join with newlines."""
    return "\n".join([str(item) for item in lst])
