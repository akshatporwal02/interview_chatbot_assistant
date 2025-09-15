from pathlib import Path
from glob import glob
from openai import OpenAI
from utils.env_utils import load_dotenv, get_openai_api_key
import os
import re

# Set OpenAI API key
load_dotenv()  # Load .env if present
OPENAI_API_KEY = get_openai_api_key()
client = OpenAI(api_key=OPENAI_API_KEY)

# Updated Prompt Template (matches screenshot style)
EVAL_PROMPT_TEMPLATE = """
You are an interview evaluator. Analyze the candidate's interview using the provided transcript and logs.

Transcript:
{transcript}

System Logs:
{logs}

---
Your response must strictly follow this format (choose exactly one option from the choices and then add a short description after it):

Candidate Evaluation
Overall Remark      : Excellent / Good / Average / Below Average / Poor / N/A
                      (⚠️ Only judge based on communication + technical skills. Do NOT use suspicious activity here.)

Communication Skills: Proficient / Good / Average / Below Average / Poor / N/A
                      Short description of communication (⚠️ Do NOT mention suspicious activity here.)

Technical Skills    : Excellent / Good / Average / Below Average / Poor / N/A
                    
                     List domains with skill level and short summary (⚠️ Do NOT mention suspicious activity here.)
                     Example: JavaScript - Good | Strong understanding of basics
                              CSS - Good | Clear understanding of styling

Attitude            : Positive / Neutral / Negative
                      [primary tone from communication + technical discussion] + Suspicious Indicators (if any)  [⚠️ log suspicious behavior separately but do NOT override tone]

                      Example outputs:
                      - Positive
                        Polite, professional, confident. No suspicious behavior.
                      - Neutral
                        Calm and steady, but slightly hesitant. Suspicious: eye movement off-screen.
                      - Negative 
                        Rude tone, dismissive answers. With/without suspicious activity.
                      - Positive
                        Engaged and cooperative. Suspicious: face disappeared briefly.

                      (⚠️ Even if suspicious activity is detected, the main tone must still be reflected.
                       Suspicious activity is logged here only and does NOT affect Overall Remark or Status.)


Interviewer Evaluation
Questions Asked (i) : HR / Relevant / SR / Irrelevant / Generic / N/A
                      Short description
Difficulty Level (i): Basic / Intermediate / Difficult / Challenging / N/A
                      Short description
Attitude (i)        : Polite / Harsh / Rude / N/A
                      Short description

Result
Status  : Go Ahead / Rejected / On Hold / Re-Evaluation / No Show
          (⚠️ Status must be decided only from Overall Remark, not from suspicious activity.)
Summary : <Short concise summary>
AI Remarks: <Provide 4-5 words only capturing the essence of the summary>
"""


def parse_llm_response(llm_response: str):
    """
    Parse LLM response into structured data for the report template (word-based).
    Keeps 'score' key for backward compatibility and ensures 'Overall Remark' is last.
    """
    candidate_analysis = []
    interviewer_analysis = []
    decision = None
    overall_remark = None  # store separately to move it to the end

    try:
        if not llm_response:
            print("⚠️ Empty or None LLM response")
            return (
                [{"criteria": "Parsing Error", "value": "N/A", "score": None, "explanation": ""}],
                [{"aspect": "Parsing Error", "value": "N/A", "description": ""}],
                {"recommendation": "Manual Review Required", "summary": "Parsing failed"}
            )
        
        lines = [line.strip() for line in llm_response.splitlines() if line.strip()]

        for i, line in enumerate(lines):
            # Candidate
            if line.startswith("Overall Remark"):
                value = line.split(":", 1)[1].strip()
                overall_remark = {
                    "criteria": "Overall Remark",
                    "value": value,
                    "score": None,
                    "explanation": ""
                }
            elif line.startswith("Communication Skills"):
                value = line.split(":", 1)[1].strip()
                desc = lines[i+1] if (i+1 < len(lines) and not lines[i+1].startswith(("Technical","Attitude"))) else ""
                candidate_analysis.append({
                    "criteria": "Communication Skills",
                    "value": value,
                    "score": None,
                    "explanation": desc
                })
            elif line.startswith("Technical Skills"):
                value = line.split(":", 1)[1].strip()
                descs = []
                j = i+1
                while j < len(lines) and not lines[j].startswith("Attitude"):
                    descs.append(lines[j])
                    j += 1
                candidate_analysis.append({
                    "criteria": "Technical Skills",
                    "value": value,
                    "score": None,
                    "explanation": "\n".join(descs)
                })
            # elif line.startswith("Attitude") and not line.startswith("Attitude (i)"):
            #     value = line.split(":", 1)[1].strip()
            #     desc = lines[i+1] if (i+1 < len(lines) and not lines[i+1].startswith("Overall Remark")) else ""
            #     candidate_analysis.append({
            #         "criteria": "Attitude",
            #         "value": value,
            #         "score": None,
            #         "explanation": desc
            #     })
            elif line.startswith("Attitude") and not line.startswith("Attitude (i)"):
                    value = line.split(":", 1)[1].strip()
                    descs = []
                    j = i+1
                    while j < len(lines) and not lines[j].startswith(("Overall Remark", "Interviewer Evaluation")):
                        descs.append(lines[j])
                        j += 1

                    candidate_analysis.append({
                        "criteria": "Attitude",
                        "value": value if value else "N/A",
                        "score": None,
                        "explanation": "\n".join(descs)
                        })

            # Interviewer
            elif line.startswith("Questions Asked"):
                value = line.split(":", 1)[1].strip()
                desc = lines[i+1] if (i+1 < len(lines) and not lines[i+1].startswith("Difficulty")) else ""
                interviewer_analysis.append({
                    "aspect": "Questions Asked",
                    "value": value,
                    "description": desc
                })
            elif line.startswith("Difficulty Level"):
                value = line.split(":", 1)[1].strip()
                desc = lines[i+1] if (i+1 < len(lines) and not lines[i+1].startswith("Attitude")) else ""
                interviewer_analysis.append({
                    "aspect": "Difficulty Level",
                    "value": value,
                    "description": desc
                })
            elif line.startswith("Attitude (i)"):
                value = line.split(":", 1)[1].strip()
                desc = lines[i+1] if (i+1 < len(lines) and not lines[i+1].startswith("Result")) else ""
                interviewer_analysis.append({
                    "aspect": "Attitude",
                    "value": value,
                    "description": desc
                })

            # Result
            elif line.startswith("Status"):
                status = line.split(":", 1)[1].strip()
                decision = {"recommendation": status}
            elif line.startswith("Summary"):
                if decision:
                    decision["summary"] = line.split(":", 1)[1].strip()
            elif line.startswith("AI Remarks"):
                if decision is None:
                    decision = {}
                decision["ai_remarks"] = line.split(":", 1)[1].strip()

        # 🔑 Append Overall Remark at the end of candidate_analysis
        if overall_remark:
            candidate_analysis.append(overall_remark)
            # Also expose the overall remark on decision for downstream use (e.g., email)
            if decision is None:
                decision = {}
            try:
                decision["overall_remark_value"] = overall_remark.get("value") if isinstance(overall_remark, dict) else str(overall_remark)
            except Exception:
                pass

    except Exception as e:
        print(f"⚠️ Error parsing LLM response: {e}")
        candidate_analysis = [{"criteria": "Parsing Error", "value": "N/A", "score": None, "explanation": ""}]
        interviewer_analysis = [{"aspect": "Parsing Error", "value": "N/A", "description": ""}]
        decision = {"recommendation": "Manual Review Required", "summary": "Parsing failed"}

    return candidate_analysis, interviewer_analysis, decision




def analyze_transcript(room_name: str) -> str:
    try:
        project_root = Path(__file__).resolve().parents[2]  # repo root
        transcripts_glob = str(project_root / "code" / "session_data" / "transcripts_doc" / f"transcript_{room_name}_*.txt")
        print("Project root:", project_root)
        logs_glob = str(project_root / "code" / "session_data" / "logs" / f"alerts_{room_name}_*.log")
        transcript_files = sorted(glob(transcripts_glob))
        logs_files = sorted(glob(logs_glob))


        if not transcript_files:
            print("❌ No transcript file found for room:", room_name)
            return "Transcript not found."
        
        transcript_path = Path(transcript_files[-1])
        transcript = transcript_path.read_text(encoding="utf-8")

        logs = ""
        if logs_files:
            logs_path = Path(logs_files[-1])
            logs = logs_path.read_text(encoding="utf-8")

        prompt = EVAL_PROMPT_TEMPLATE.format(
            transcript=transcript.strip(),
            logs=logs.strip()
        )

        print("🤖 Sending transcript and logs to LLM for evaluation...")

        response = client.chat.completions.create(
            model="gpt-4",  
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1500
        )

        content = response.choices[0].message.content
        if content is None:
            print("⚠️ OpenAI API returned None content")
            return "LLM evaluation returned empty response."
        
        return content

    except Exception as e:
        print(f"❌ Error during LLM evaluation: {e}")
        return "LLM evaluation failed."


# if __name__ == "__main__":
#     room_name = input("Enter room name: ").strip()
#     result = analyze_transcript(room_name)
#     print("\n📄 Evaluation Report:\n")
#     print(result)
    
#     # Parse into structured data
#     print("\n🔍 Parsed Data:\n")
#     candidate_analysis, interviewer_analysis, decision = parse_llm_response(result)
#     print("Candidate Analysis:", candidate_analysis)
#     print("Interviewer Analysis:", interviewer_analysis)
#     print("Decision:", decision)
