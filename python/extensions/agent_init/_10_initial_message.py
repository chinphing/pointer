import json
import re
from agent import LoopData
from python.helpers.extension import Extension
from python.helpers import extract_tools


class InitialMessage(Extension):

    async def execute(self, **kwargs):
        """
        Add an initial greeting message when first user message is processed.
        Called only once per session via _process_chain method.
        """

        # Only add initial message for main agent (A0), not subordinate agents
        if self.agent.number != 0:
            return

        # If the context already contains log messages, do not add another initial message
        if self.agent.context.log.logs:
            return

        # Construct the initial message from prompt template
        initial_message = self.agent.read_prompt("fw.initial_message.md")

        # add initial loop data to agent (for hist_add_ai_response)
        self.agent.loop_data = LoopData(user_message=None)

        # Add the message to history as an AI response
        self.agent.hist_add_ai_response(initial_message)

        # Parse message (XML or JSON) to get tool_args.text for the log
        initial_message_text = "Hello! How can I help you?"
        stripped = initial_message.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```\w*\n?", "", stripped)
            stripped = re.sub(r"\n?```\s*$", "", stripped)
        try:
            parsed = extract_tools.xml_parse_dirty(stripped)
            if parsed and isinstance(parsed.get("tool_args"), dict):
                initial_message_text = parsed["tool_args"].get("text") or initial_message_text
            else:
                raise ValueError("XML parse returned no tool_args")
        except (ValueError, TypeError):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed.get("tool_args"), dict):
                    initial_message_text = parsed["tool_args"].get("text") or initial_message_text
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # Add to log (green bubble) for immediate UI display
        self.agent.context.log.log(
            type="response",
            content=initial_message_text,
            finished=True,
            update_progress="none",
        )
