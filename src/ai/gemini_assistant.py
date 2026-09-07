"""
Google Gemini AI Health & Longevity Assistant.
Provides automated executive briefings, biomarker interpretations, and interactive
multi-turn coaching grounded in your Apple Health, MyFitnessPal, and Quest Diagnostics data.
Uses official google-genai SDK.
"""

import os
from typing import Dict, List, Optional, Any, Generator
from google import genai
from google.genai import types

DEFAULT_SYSTEM_INSTRUCTION = """
You are the JB-Health Intelligence AI Coach — an elite sports medicine, clinical longevity, and preventive health consultant.
You synthesize physiological data from Apple Health (sleep architecture, HRV, resting HR, activity), MyFitnessPal (nutrition and macronutrients), and Quest Diagnostics (clinical blood work & biomarkers) into clear, evidence-based, actionable guidance.

YOUR PRINCIPLES:
1. Longevity & Optimal Ranges: Standard laboratory reference ranges identify active disease/pathology. Where relevant, contrast standard ranges with optimal longevity benchmarks (e.g. ApoB < 60-70 mg/dL, hs-CRP < 0.5 mg/L, deep sleep >= 15-20%, REM >= 20-25%).
2. Interconnected Systems: Connect inputs (nutrition, training load, lifestyle) to outputs (HRV, resting HR, deep sleep, inflammatory biomarkers).
3. Actionable Prescription: Always provide clear, high-priority, realistic next steps (e.g., specific timing of fueling, sleep hygiene habits, workout intensity modulation based on TSB/ATL).
4. Tone: Professional, scientifically grounded, encouraging, analytical, and structured with clean markdown headers and bullet points.
5. Medical Responsibility: Provide valuable health education and optimization insights, with a clear note that your analysis is for informational/optimization purposes and not a substitute for formal diagnosis or medical treatment.
"""

AVAILABLE_MODELS = [
    "gemini-3.7-flash",
    "gemini-2.5-pro",
    "gemini-3.5-flash-lite"
]


class GeminiHealthAssistant:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-3.7-flash",
        temperature: float = 0.4,
        system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name if model_name in AVAILABLE_MODELS else "gemini-3.7-flash"
        self.temperature = temperature
        self.system_instruction = system_instruction
        self.client = None

        if self.api_key and self.api_key.strip():
            try:
                self.client = genai.Client(api_key=self.api_key.strip())
            except Exception:
                self.client = None

    def is_available(self) -> bool:
        """Returns True if the Gemini client is initialized with an API key."""
        return self.client is not None

    def generate_executive_briefing(self, health_context: str, focus_area: Optional[str] = None) -> str:
        """Generates an end-to-end executive health and longevity report."""
        if not self.is_available():
            return (
                "⚠️ **Gemini API Key Required**\n\n"
                "Please enter your Google Gemini API key in the left sidebar under **🤖 Gemini AI Settings** "
                "or set the `GEMINI_API_KEY` environment variable. You can get a free API key at "
                "[Google AI Studio](https://aistudio.google.com/app/apikey)."
            )

        prompt = f"""
{health_context}

---

TASK:
Generate an executive-level Health & Performance Intelligence Briefing based on the above personal health data.
{"Special focus requested: " + focus_area if focus_area else ""}

Structure your briefing into the following sections:
1. ⚡ Executive Summary & Readiness State (Autonomic balance, HRV, RHR, readiness score)
2. 🧪 Clinical Biomarker & Blood Work Review (Highlight any flagged or suboptimal Quest lab markers and explain their systemic implications)
3. 🌙 Sleep Architecture Diagnostic (Duration, Deep & REM distribution, cumulative debt, and bedtime consistency)
4. 🏋️ Athletic Performance & Training Load Prescription (ATL fatigue vs CTL fitness, TSB balance, ACWR injury risk, and today's workout recommendation)
5. 🎯 Top 3 High-Impact Action Protocols for This Week (Specific, prioritized adjustments to nutrition, recovery, or training)

Format with clean Markdown, bold metrics, and structured bullet points.
"""
        try:
            config = types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=self.temperature
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return response.text or "No response generated."
        except Exception as e:
            return f"❌ **Error generating briefing from Gemini**: {str(e)}"

    def chat_turn(self, user_message: str, chat_history: List[Dict[str, str]], health_context: str) -> str:
        """Processes a single conversational turn with full health context memory."""
        if not self.is_available():
            return (
                "⚠️ **Gemini API Key Required**\n\n"
                "Please provide a valid Gemini API key in the sidebar to chat with your health data."
            )

        # Assemble prompt with conversation history
        messages_text = []
        messages_text.append("HEALTH DATA CONTEXT:\n" + health_context + "\n---\n")
        messages_text.append("CONVERSATION HISTORY:")
        for msg in chat_history[-6:]:  # Keep recent turns for context efficiency
            role = "User" if msg["role"] == "user" else "AI Coach"
            messages_text.append(f"{role}: {msg['content']}")

        messages_text.append(f"\nUser: {user_message}\nAI Coach:")
        prompt = "\n".join(messages_text)

        try:
            config = types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=self.temperature
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return response.text or "I was unable to generate a response."
        except Exception as e:
            return f"❌ **Error chatting with Gemini**: {str(e)}"

    def stream_chat_turn(self, user_message: str, chat_history: List[Dict[str, str]], health_context: str) -> Generator[str, None, None]:
        """Streams response tokens in real time for Streamlit chat."""
        if not self.is_available():
            yield "⚠️ **Gemini API Key Required**: Please enter your API key in the sidebar to chat with your health data."
            return

        messages_text = []
        messages_text.append("HEALTH DATA CONTEXT:\n" + health_context + "\n---\n")
        messages_text.append("CONVERSATION HISTORY:")
        for msg in chat_history[-6:]:
            role = "User" if msg["role"] == "user" else "AI Coach"
            messages_text.append(f"{role}: {msg['content']}")

        messages_text.append(f"\nUser: {user_message}\nAI Coach:")
        prompt = "\n".join(messages_text)

        try:
            config = types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=self.temperature
            )
            for chunk in self.client.models.generate_content_stream(
                model=self.model_name,
                contents=prompt,
                config=config
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            yield f"\n\n❌ **Error streaming response from Gemini**: {str(e)}"