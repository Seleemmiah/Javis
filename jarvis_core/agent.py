"""Multi-step agent loop — plan → act → observe → repeat."""

from __future__ import annotations

from typing import Any, Callable, Optional

from jarvis_core.brain import Brain
from jarvis_core.config import AGENT_MAX_STEPS
from jarvis_core.long_memory import LongTermMemory
from jarvis_core.memory import Memory
from jarvis_core import project_context
from skills.executor import ActionExecutor
from skills import system_info


class Agent:
    def __init__(
        self,
        brain: Brain,
        executor: ActionExecutor,
        memory: Memory,
        long_memory: LongTermMemory,
        speak: Callable[[str], None],
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.brain = brain
        self.executor = executor
        self.memory = memory
        self.long_memory = long_memory
        self.speak = speak
        self.on_log = on_log or (lambda m: None)

    def _stream_speak(self, text: str) -> None:
        """Speak text sentence-by-sentence for faster perceived response."""
        import re as _re
        # Split on sentence boundaries
        sentences = _re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                self.speak(sentence)

    def _context(self, user_text: str) -> str:
        parts = [
            system_info.system_report(),
            self.long_memory.context_block(user_text, k=6),
            f"Short memory title: {self.memory.title()}",
            project_context.context_block(),
        ]
        return "\n\n".join(p for p in parts if p)

    def run(self, user_text: str) -> dict[str, Any]:
        """
        Execute multi-step reasoning.
        Returns {final_speech, steps, standby}.
        """
        step_results = ""
        final_speech = ""
        standby = False
        steps_log: list[str] = []

        for step in range(AGENT_MAX_STEPS):
            self.on_log(f"Agent step {step + 1}/{AGENT_MAX_STEPS}")
            plan = self.brain.plan(
                user_text,
                history=self.memory.history(),
                context=self._context(user_text),
                step_results=step_results,
                step_index=step,
            )
            speech = (plan.get("speech") or "").strip()
            actions = plan.get("actions") or [{"type": "speak_only"}]
            done = bool(plan.get("done", True))
            remember = (plan.get("remember") or "").strip()

            if speech:
                # Stream speech sentence-by-sentence in background
                # so JARVIS starts talking immediately while actions execute
                if step == 0 or not done or len(actions) > 1:
                    self._stream_speak(speech)
                final_speech = speech

            if remember:
                self.long_memory.remember_fact(remember)
                self.on_log(f"Remembered: {remember[:80]}")

            results, go_standby = self.executor.run_actions(actions)
            if go_standby:
                standby = True
                done = True

            # Speak non-empty tool results (summarized)
            for res in results:
                if not res or res in ("standing by",):
                    continue
                summary = res if len(res) < 420 else res[:400] + "…"
                if summary.strip() and summary.strip() != speech.strip():
                    self.speak(summary)
                    final_speech = summary

            blob = "\n".join(results) if results else "(no tool output)"
            steps_log.append(f"step{step+1}: {speech} | {blob[:300]}")
            step_results = (step_results + f"\n--- step {step+1} ---\n" + blob)[-4000:]

            if done or not results:
                # if only speak_only and done, stop
                if done:
                    break
            # continue if not done

        self.memory.history_add("user", user_text)
        self.memory.history_add("assistant", final_speech or "Done.")
        # store interaction crumb
        self.long_memory.add(
            f"User asked: {user_text[:200]} → Jarvis: {(final_speech or '')[:200]}",
            kind="event",
        )
        return {
            "final_speech": final_speech,
            "steps": steps_log,
            "standby": standby,
        }
