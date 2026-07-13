"""Language model brain — Google Gemini (free) → OpenAI → Ollama fallback chain."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Optional

import requests

from jarvis_core.config import (
    BRAIN_PRIORITY,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    JARVIS_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    USE_OLLAMA,
)
from jarvis_core.skill_loader import plugin_action_schemas

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


SYSTEM_PROMPT = """You are J.A.R.V.I.S. (Just A Rather Very Intelligent System),
a hyper-intelligent AI assistant serving {title} on their Mac laptop.

CORE IDENTITY:
- You are J.A.R.V.I.S. — not ChatGPT, not Gemini, not an AI assistant. You ARE J.A.R.V.I.S.
- British, refined, calm, precise. Dry wit when appropriate. Never crude. No emoji.
- Address the user as "{title}".
- You are supremely knowledgeable. Answer questions with confidence, accuracy, and depth.
- For quick questions (facts, math, definitions), give the answer IMMEDIATELY — no hedging.
- For complex questions, be thorough but concise. Quality over quantity.
- Keep spoken replies to 1-3 sentences unless the user explicitly asks for detail.

INTELLIGENCE RULES:
- When asked a factual question, ANSWER IT DIRECTLY. Do not say "I don't have access to real-time data." You have a knowledge base — use it.
- For math, calculate it yourself and give the answer.
- For coding questions, give working code.
- For general knowledge, give an authoritative answer like an expert would.
- If you genuinely don't know, say so briefly — but TRY to answer first.

AGENT RULES:
- You have access to tools. Use them when the task requires action (opening apps, running commands, searching, etc.)
- For simple conversation or knowledge questions, just respond with speech — do NOT call unnecessary tools.
- Set done=true when the task is complete or you need more user input.
- Use the remember tool to store important user facts/preferences.
- Prefer real macOS shell commands when automating.
- If prior step results are provided, use them; do not repeat failed commands blindly — adapt.

RESPONSE FORMAT:
You MUST respond with ONLY valid JSON in this exact structure:
{{"speech": "what to say out loud", "actions": [{{"type": "action_type", ...}}], "done": true, "remember": ""}}

For simple chat/answers, use: {{"speech": "your answer", "actions": [{{"type": "speak_only"}}], "done": true, "remember": ""}}
"""

# Available action types for the JSON prompt (used by Gemini and Ollama)
ACTION_TYPES_DESCRIPTION = """
Available action types:
- speak_only: Just speak, no action needed.
- shell: Run a macOS shell command. Args: {"type": "shell", "command": "..."}
- open_url: Open a URL. Args: {"type": "open_url", "url": "..."}
- google: Search Google. Args: {"type": "google", "query": "..."}
- open_app: Open an app. Args: {"type": "open_app", "name": "..."}
- wikipedia: Search Wikipedia. Args: {"type": "wikipedia", "topic": "..."}
- weather: Get weather. Args: {"type": "weather", "city": "..."}
- play_youtube: Play YouTube. Args: {"type": "play_youtube", "query": "..."}
- screenshot: Take screenshot. Args: {"type": "screenshot"}
- see_screen: Analyze screen. Args: {"type": "see_screen", "question": "..."}
- see_webcam: Look through webcam. Args: {"type": "see_webcam"}
- volume: Set volume. Args: {"type": "volume", "level": 50}
- file_search: Search files. Args: {"type": "file_search", "query": "..."}
- system_info: Get system info. Args: {"type": "system_info"}
- delegate_task: Spawn background sub-agent. Args: {"type": "delegate_task", "task_description": "..."}
- update_system: Pull git updates and restart. Args: {"type": "update_system"}
- search_knowledge_graph: Search personal docs. Args: {"type": "search_knowledge_graph", "query": "..."}
- index_directory: Index files. Args: {"type": "index_directory", "path": "..."}
- news: Get news. Args: {"type": "news", "topic": "..."}
- read_file: Read a file. Args: {"type": "read_file", "path": "..."}
- write_file: Write a file. Args: {"type": "write_file", "path": "...", "content": "..."}
- edit_file: Edit a file. Args: {"type": "edit_file", "path": "...", "old_text": "...", "new_text": "..."}
- remember: Store a memory. Args: {"type": "remember", "text": "...", "kind": "fact|preference|event"}
- recall: Recall memories. Args: {"type": "recall", "query": "..."}
- standby: Go to standby. Args: {"type": "standby"}
"""


def _get_tools() -> list[dict]:
    """OpenAI function-calling tool schemas."""
    tools = [
        {"type": "function", "function": {"name": "speak_only", "description": "Speak a message without taking any action.", "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {"name": "shell", "description": "Run a shell command on macOS.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "open_url", "description": "Open a URL in the default browser.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
        {"type": "function", "function": {"name": "google", "description": "Search Google.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
        {"type": "function", "function": {"name": "open_app", "description": "Open an application.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
        {"type": "function", "function": {"name": "wikipedia", "description": "Search Wikipedia.", "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}}},
        {"type": "function", "function": {"name": "weather", "description": "Get the weather.", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}},
        {"type": "function", "function": {"name": "play_youtube", "description": "Play a YouTube video.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
        {"type": "function", "function": {"name": "screenshot", "description": "Take a screenshot.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}}},
        {"type": "function", "function": {"name": "see_screen", "description": "See the screen.", "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}},
        {"type": "function", "function": {"name": "see_webcam", "description": "Look through the webcam and describe what is visible.", "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {"name": "volume", "description": "Set volume.", "parameters": {"type": "object", "properties": {"level": {"type": "integer"}}, "required": ["level"]}}},
        {"type": "function", "function": {"name": "file_search", "description": "Search files.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
        {"type": "function", "function": {"name": "system_info", "description": "Get system info.", "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {"name": "delegate_task", "description": "Spawn a sub-agent to perform a large research or complex task in the background in parallel.", "parameters": {"type": "object", "properties": {"task_description": {"type": "string"}}, "required": ["task_description"]}}},
        {"type": "function", "function": {"name": "recall_audio", "description": "Transcribe the last 30 seconds of audio from the physical room to answer 'what was just said'.", "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {"name": "update_system", "description": "Pull latest code updates via git and restart the JARVIS daemon.", "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {"name": "search_knowledge_graph", "description": "Search personal documents and files.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
        {"type": "function", "function": {"name": "index_directory", "description": "Index a directory into the knowledge graph.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
        {"type": "function", "function": {"name": "news", "description": "Get news.", "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}}},
        {"type": "function", "function": {"name": "calendar", "description": "Read calendar events.", "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {"name": "project_tree", "description": "Read project tree.", "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {"name": "read_file", "description": "Read file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
        {"type": "function", "function": {"name": "write_file", "description": "Write a new file or overwrite an existing file. USE WITH CAUTION.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
        {"type": "function", "function": {"name": "edit_file", "description": "Edit a file by replacing a block of text.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string", "description": "Exact text block to replace. Must match exactly."}, "new_text": {"type": "string", "description": "New text to replace it with."}}, "required": ["path", "old_text", "new_text"]}}},
        {"type": "function", "function": {"name": "create_directory", "description": "Create a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
        {"type": "function", "function": {"name": "remember", "description": "Store a memory.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "kind": {"type": "string", "enum": ["fact", "preference", "event"]}}, "required": ["text", "kind"]}}},
        {"type": "function", "function": {"name": "recall", "description": "Recall memories.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
        {"type": "function", "function": {"name": "standby", "description": "Go to standby.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    ]

    # Add plugins
    for p in plugin_action_schemas():
        tools.append({
            "type": "function",
            "function": {
                "name": p["type"],
                "description": p["description"],
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True,
                }
            }
        })

    # Wrapper tool for structured output
    final_tools = [
        {
            "type": "function",
            "function": {
                "name": "execute_plan",
                "description": "Execute your planned actions, along with what to say and whether you are done.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "speech": {"type": "string", "description": "What to say out loud this step (short)."},
                        "done": {"type": "boolean", "description": "True if the task is complete or you need user input, False if you need to take more steps automatically."},
                        "actions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "description": "Action objects representing tools to run. E.g. {\"type\": \"shell\", \"command\": \"ls\"} or {\"type\": \"speak_only\"}",
                                "additionalProperties": True,
                            }
                        },
                        "remember": {"type": "string", "description": "Optional fact to store in long-term memory or empty string."}
                    },
                    "required": ["speech", "done", "actions"]
                }
            }
        }
    ]
    return final_tools


class Brain:
    def __init__(self, title: str = "sir") -> None:
        self.title = title
        self.client = None
        if OPENAI_API_KEY and OpenAI is not None:
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        self._ollama_ok: Optional[bool] = None
        self._gemini_ok: Optional[bool] = None

    def set_title(self, title: str) -> None:
        self.title = title

    def _gemini_available(self) -> bool:
        if not GEMINI_API_KEY:
            return False
        if self._gemini_ok is not None:
            return self._gemini_ok
        try:
            # Quick connectivity check
            r = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}",
                timeout=3,
            )
            self._gemini_ok = r.status_code == 200
            if not self._gemini_ok:
                print(f"[brain] Gemini API returned {r.status_code}. Check your key.")
        except Exception:
            self._gemini_ok = False
        return self._gemini_ok

    def backend_name(self) -> str:
        if BRAIN_PRIORITY == "gemini" and self._gemini_available():
            return f"gemini:{GEMINI_MODEL}"
        if self.client and USE_OLLAMA != "always":
            return f"openai:{JARVIS_MODEL}"
        if self._ollama_available() and USE_OLLAMA != "never":
            return f"ollama:{OLLAMA_MODEL}"
        return "offline-rules"

    def available(self) -> bool:
        return self._gemini_available() or bool(self.client) or self._ollama_available()

    def _ollama_available(self) -> bool:
        if USE_OLLAMA == "never":
            return False
        if self._ollama_ok is not None:
            return self._ollama_ok
        try:
            r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=1.5)
            self._ollama_ok = r.status_code == 200
        except Exception:
            self._ollama_ok = False
        return self._ollama_ok

    def plan(
        self,
        user_text: str,
        history: Optional[list[dict[str, str]]] = None,
        context: str = "",
        step_results: str = "",
        step_index: int = 0,
    ) -> dict[str, Any]:
        if not self.available():
            return {
                "speech": (
                    f"Higher cognition is offline, {self.title}. "
                    "Set GEMINI_API_KEY (free) or install Ollama."
                ),
                "actions": [{"type": "speak_only"}],
                "done": True,
                "remember": "",
            }

        from jarvis_core.personas import active_persona
        persona = active_persona()

        system_content = (
            SYSTEM_PROMPT.format(title=self.title)
            + f"\n\nPersona constraints: {persona.tone}\n\n{ACTION_TYPES_DESCRIPTION}\n\nLive context:\n{context}"
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_content}
        ]
        if history:
            messages.extend(history[-12:])
        user_payload = user_text
        if step_results:
            user_payload += (
                f"\n\n[Agent step {step_index} prior results]\n{step_results}\n"
                "Continue or finish (set done=true when complete)."
            )
        messages.append({"role": "user", "content": user_payload})

        # --- Priority chain: Gemini → OpenAI → Ollama ---

        # 1. Try Gemini first (free + fast + smart)
        if BRAIN_PRIORITY == "gemini" and self._gemini_available():
            try:
                return self._gemini_chat(messages)
            except Exception as exc:
                print(f"[brain] Gemini failed ({exc}), trying fallback...")

        # 2. Try OpenAI
        if self.client and USE_OLLAMA != "always":
            try:
                return self._openai_chat(messages)
            except Exception as exc:
                print(f"[brain] OpenAI failed ({exc}), trying Ollama...")
                if not self._ollama_available():
                    return {
                        "speech": f"Brief cognition fault, {self.title}: {exc}",
                        "actions": [{"type": "speak_only"}],
                        "done": True,
                        "remember": "",
                    }

        # 3. Try Ollama (local)
        if self._ollama_available():
            try:
                raw = self._ollama_chat_raw(messages)
                return self._parse_plan(raw)
            except Exception as exc:
                return {
                    "speech": f"Local model error, {self.title}: {exc}",
                    "actions": [{"type": "speak_only"}],
                    "done": True,
                    "remember": "",
                }

        return {
            "speech": f"No language model available, {self.title}.",
            "actions": [{"type": "speak_only"}],
            "done": True,
            "remember": "",
        }

    # ==================== GEMINI ====================
    def _gemini_chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Call Google Gemini API (free tier)."""
        # Build Gemini-format messages
        system_text = ""
        gemini_contents = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                system_text = content
            elif role == "user":
                gemini_contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                gemini_contents.append({"role": "model", "parts": [{"text": content}]})

        payload = {
            "contents": gemini_contents,
            "systemInstruction": {
                "parts": [{"text": system_text}]
            },
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json",
            },
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

        for attempt in range(3):
            try:
                r = requests.post(url, json=payload, timeout=30)
                if r.status_code == 429:
                    if attempt < 2:
                        time.sleep((attempt + 1) * 3)
                        continue
                    raise Exception("Gemini rate limit exceeded")
                r.raise_for_status()
                break
            except requests.exceptions.HTTPError:
                raise
            except Exception as e:
                if attempt < 2:
                    time.sleep(1)
                    continue
                raise e

        data = r.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise Exception(f"Gemini returned no candidates: {data}")

        raw_text = ""
        for part in candidates[0].get("content", {}).get("parts", []):
            raw_text += part.get("text", "")

        return self._parse_plan(raw_text)

    # ==================== OPENAI ====================
    def _openai_chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        tools = _get_tools()

        for attempt in range(3):
            try:
                resp = self.client.chat.completions.create(
                    model=os.getenv("JARVIS_MODEL", JARVIS_MODEL),
                    messages=messages,
                    temperature=0.4,
                    max_tokens=800,
                    tools=tools,
                    tool_choice={"type": "function", "function": {"name": "execute_plan"}},
                )
                msg = resp.choices[0].message
                break
            except Exception as e:
                if "429" in str(e) or "Too Many Requests" in str(e) or "Rate limit" in str(e):
                    if attempt < 2:
                        time.sleep((attempt + 1) * 4)
                        continue
                raise e

        if msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.function.name == "execute_plan":
                    try:
                        args = json.loads(tc.function.arguments)
                        return {
                            "speech": str(args.get("speech", "")),
                            "actions": args.get("actions") or [{"type": "speak_only"}],
                            "done": bool(args.get("done", True)),
                            "remember": str(args.get("remember", "")),
                        }
                    except Exception:
                        pass

        # Fallback
        return self._parse_plan(msg.content or "")

    # ==================== OLLAMA ====================
    def _ollama_chat_raw(self, messages: list[dict[str, str]]) -> str:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.4, "num_predict": 1024},
            },
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        return (data.get("message", {}) or {}).get("content", "").strip()

    # ==================== PARSE ====================
    def _parse_plan(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        def pack(data: dict) -> dict[str, Any]:
            return {
                "speech": str(data.get("speech", "")),
                "actions": data.get("actions")
                if isinstance(data.get("actions"), list)
                else [{"type": "speak_only"}],
                "done": bool(data.get("done", True)),
                "remember": str(data.get("remember") or ""),
            }

        try:
            data = json.loads(text)
            if isinstance(data, dict) and "speech" in data:
                return pack(data)
        except json.JSONDecodeError:
            pass

        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data, dict) and "speech" in data:
                    return pack(data)
            except json.JSONDecodeError:
                pass

        return {
            "speech": text,
            "actions": [{"type": "speak_only"}],
            "done": True,
            "remember": "",
        }
