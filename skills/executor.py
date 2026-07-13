"""Execute planned actions from the brain / agent."""

from __future__ import annotations

from typing import Any, Callable, Optional

from jarvis_core import calendar_mac
from jarvis_core import project_context
from jarvis_core import screen as screen_mod
from jarvis_core.long_memory import LongTermMemory
from skills import browser
from skills import shell as shell_mod
from skills import system_info
from skills import system_info
from skills import web
from pathlib import Path


class ActionExecutor:
    def __init__(
        self,
        speak: Callable[[str], None],
        ask_confirm: Optional[Callable[[str], bool]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        long_memory: Optional[LongTermMemory] = None,
    ) -> None:
        self.speak = speak
        self.ask_confirm = ask_confirm
        self.on_log = on_log or (lambda m: None)
        self.long_memory = long_memory or LongTermMemory()

    def run_actions(self, actions: list[dict[str, Any]]) -> tuple[list[str], bool]:
        results: list[str] = []
        standby = False

        for action in actions or []:
            if not isinstance(action, dict):
                continue
            atype = (action.get("type") or "").lower().strip()
            self.on_log(f"Action: {atype}")

            if atype in ("speak_only", "", "none"):
                continue

            if atype == "shell":
                cmd = action.get("command") or action.get("cmd") or ""
                if shell_mod.is_destructive(cmd):
                    self.speak(
                        "That command is potentially destructive. "
                        "Say 'force run' with the command if you insist."
                    )
                    results.append("blocked destructive command")
                    continue
                self.on_log(f"$ {cmd}")
                out = shell_mod.run_shell(cmd)
                results.append(out)
                continue

            if atype == "force_shell":
                cmd = action.get("command") or ""
                out = shell_mod.run_shell(cmd, confirm_destructive=False)
                results.append(out)
                continue

            if atype == "google":
                out = web.google_search(action.get("query", ""))
                results.append(out)
                continue

            if atype in ("open_url", "browser_open"):
                out = browser.open_url(action.get("url", ""))
                results.append(out)
                continue

            if atype == "fetch_url":
                out = browser.fetch_page_text(action.get("url", ""))
                results.append(out)
                continue

            if atype == "open_app":
                out = system_info.open_app(action.get("name", ""))
                results.append(out)
                continue

            if atype == "wikipedia":
                out = web.wikipedia_summary(action.get("topic", ""))
                results.append(out)
                continue

            if atype == "weather":
                out = web.weather(action.get("city", ""))
                results.append(out)
                continue

            if atype == "play_youtube":
                out = web.play_youtube(action.get("query", ""))
                results.append(out)
                continue

            if atype == "screenshot":
                out = system_info.take_screenshot(action.get("path", ""))
                results.append(out)
                continue

            if atype == "see_screen":
                q = action.get("question") or "What is on the screen?"
                out = screen_mod.describe_screen(q)
                results.append(out)
                continue

            if atype == "see_webcam":
                try:
                    from jarvis_core.webcam import describe_webcam
                    out = describe_webcam()
                    results.append(out)
                except Exception as e:
                    results.append(f"Failed to use webcam: {e}")
                continue
                
            if atype == "delegate_task":
                try:
                    task = action.get("task_description", "")
                    def _run_subagent():
                        from jarvis_core.agent import Agent
                        from jarvis_core.brain import Brain
                        from jarvis_core.memory import Memory
                        b = Brain(title="sir")
                        a = Agent(brain=b, executor=self, memory=Memory(), long_memory=self.long_memory, speak=lambda x: None, on_log=self.on_log)
                        out = a.run(task)
                        if self.speak:
                            self.speak(f"Sir, the background task '{task[:40]}' is complete.")
                    import threading
                    t = threading.Thread(target=_run_subagent, daemon=True, name="jarvis-subagent")
                    t.start()
                    results.append(f"Subagent dispatched for: {task}. I will continue to work while it runs.")
                except Exception as e:
                    results.append(f"Failed to delegate: {e}")
                continue

            if atype == "recall_audio":
                try:
                    from jarvis_core.audio_buffer import get_audio_buffer
                    out = get_audio_buffer().get_recent_transcription()
                    results.append(out)
                except Exception as e:
                    results.append(f"Failed to recall audio: {e}")
                continue

            if atype == "update_system":
                try:
                    from jarvis_core.config import ROOT
                    import subprocess
                    self.on_log("Updating JARVIS system...")
                    out = subprocess.run(["git", "pull"], cwd=str(ROOT), capture_output=True, text=True)
                    if out.returncode == 0:
                        results.append("I have pulled the latest updates. Restarting the daemon now.")
                        subprocess.Popen(["./jarvis_control.sh", "restart"], cwd=str(ROOT))
                        go_standby = True
                    else:
                        results.append(f"Failed to update code: {out.stderr}")
                except Exception as e:
                    results.append(f"Failed to run update: {e}")
                continue

            if atype == "search_knowledge_graph":
                try:
                    from jarvis_core.indexer import get_kg
                    q = action.get("query", "")
                    out = get_kg().search(q)
                    results.append(out)
                except Exception as e:
                    results.append(f"Failed to search KG: {e}")
                continue
                
            if atype == "index_directory":
                try:
                    from jarvis_core.indexer import get_kg
                    p = action.get("path", "")
                    out = get_kg().index_directory(p)
                    results.append(out)
                except Exception as e:
                    results.append(f"Failed to index {p}: {e}")
                continue

            if atype == "volume":
                out = system_info.set_volume(int(action.get("level", 50)))
                results.append(out)
                continue

            if atype == "brightness":
                out = system_info.set_brightness(int(action.get("level", 50)))
                results.append(out)
                continue

            if atype == "file_search":
                out = shell_mod.file_search(action.get("query", ""))
                results.append(out)
                continue

            if atype == "system_info":
                out = system_info.system_report()
                results.append(out)
                continue

            if atype == "news":
                out = web.latest_news(action.get("topic", "world news"))
                results.append(out)
                continue

            if atype == "calendar":
                out = calendar_mac.todays_events()
                results.append(out)
                continue

            if atype == "project_tree":
                out = project_context.tree_summary()
                results.append(out)
                continue

            if atype == "read_file":
                out = project_context.read_project_file(action.get("path", ""))
                results.append(out)
                continue

            if atype == "remember":
                text = action.get("text") or action.get("fact") or ""
                kind = action.get("kind") or "fact"
                if text:
                    self.long_memory.add(text, kind=kind)
                    results.append(f"Stored memory ({kind}): {text}")
                else:
                    results.append("Nothing to remember.")
                continue

            if atype == "recall":
                q = action.get("query") or ""
                block = self.long_memory.context_block(q or "preferences facts", k=6)
                results.append(block or "No matching memories.")
                continue

            if atype == "standby":
                standby = True
                results.append("standing by")
                continue

            if atype == "shutdown_pc":
                out = system_info.shutdown_pc()
                results.append(out)
                continue

            if atype == "restart_pc":
                out = system_info.restart_pc()
                results.append(out)
                continue

            if atype.startswith("plugin_"):
                plugin_name = atype.replace("plugin_", "", 1)
                from jarvis_core.skill_loader import get_plugins
                for p in get_plugins():
                    if p.name == plugin_name:
                        out = p.execute(**action)
                        results.append(out)
                        break
                else:
                    results.append(f"Plugin not found: {plugin_name}")
                continue

            if atype == "write_file":
                path = action.get("path")
                content = action.get("content")
                if not path or not content:
                    results.append("Missing path or content for write_file.")
                    continue
                if self.ask_confirm and not self.ask_confirm(f"Write to {path}?"):
                    results.append("File write aborted by user.")
                    continue
                try:
                    Path(path).write_text(content)
                    results.append(f"Wrote file {path}")
                except Exception as e:
                    results.append(f"Failed to write {path}: {e}")
                continue

            if atype == "edit_file":
                path = action.get("path")
                old = action.get("old_text")
                new = action.get("new_text")
                if not path or not old or new is None:
                    results.append("Missing args for edit_file.")
                    continue
                if self.ask_confirm and not self.ask_confirm(f"Edit {path}?"):
                    results.append("File edit aborted by user.")
                    continue
                try:
                    p = Path(path)
                    if not p.exists():
                        results.append(f"File {path} does not exist.")
                        continue
                    text = p.read_text()
                    if old not in text:
                        results.append(f"Target text not found in {path}.")
                        continue
                    p.write_text(text.replace(old, new, 1))
                    results.append(f"Edited file {path}")
                except Exception as e:
                    results.append(f"Failed to edit {path}: {e}")
                continue

            if atype == "create_directory":
                path = action.get("path")
                if not path:
                    results.append("Missing path for create_directory.")
                    continue
                try:
                    Path(path).mkdir(parents=True, exist_ok=True)
                    results.append(f"Created directory {path}")
                except Exception as e:
                    results.append(f"Failed to create directory {path}: {e}")
                continue

            results.append(f"Unknown action type: {atype}")

        return results, standby
