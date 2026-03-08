import os
from typing import Any
from python.helpers.files import VariablesPlugin
from python.helpers import files
from python.helpers.print_style import PrintStyle


class BuidToolsPrompt(VariablesPlugin):
    def get_variables(self, file: str, backup_dirs: list[str] | None = None, **kwargs) -> dict[str, Any]:

        # Default: collect from dir of the template file (or root)
        folder = files.get_abs_path(os.path.dirname(file) or ".")
        folders = [folder]
        if backup_dirs:
            for backup_dir in backup_dirs:
                folders.append(files.get_abs_path(backup_dir))

        # Only when profile is "computer": add agents/computer/prompts so computer-specific
        # tools (partially_done, vision_actions, extract_data, etc.) are loaded for this
        # profile only; agent0 and other profiles are unchanged.
        agent = kwargs.get("_agent")
        if agent and getattr(getattr(agent, "config", None), "profile", None) == "computer":
            computer_prompts = files.get_abs_path("agents", "computer", "prompts")
            folders = [computer_prompts] + folders

        # collect all tool instruction files
        prompt_files = files.get_unique_filenames_in_dirs(folders, "agent.system.tool.*.md")
        
        # load tool instructions
        tools = []
        for prompt_file in prompt_files:
            try:
                tool = files.read_prompt_file(prompt_file, **kwargs)
                tools.append(tool)
            except Exception as e:
                PrintStyle().error(f"Error loading tool '{prompt_file}': {e}")

        return {"tools": "\n\n".join(tools)}
