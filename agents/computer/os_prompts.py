"""OS-specific prompt loader for ComputerUse agent.

Dynamically loads the appropriate OS shortcuts reference based on the current platform.
"""
from __future__ import annotations

import platform
from pathlib import Path
from typing import Optional


def get_os_shortcuts_content(base_dir: str | Path) -> str:
    """Load OS-specific shortcuts reference content.
    
    Args:
        base_dir: Base directory where prompt files are located
        
    Returns:
        Content of the appropriate OS shortcuts file, or empty string if not found
    """
    base_dir = Path(base_dir)
    
    # Determine current OS
    system = platform.system().lower()
    
    # Map to prompt file
    os_file_map = {
        "darwin": "agent.system.os.macos.md",
        "windows": "agent.system.os.windows.md",
        "linux": "agent.system.os.linux.md",
    }
    
    filename = os_file_map.get(system)
    if not filename:
        return ""  # Unknown OS, return empty
    
    filepath = base_dir / filename
    
    try:
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
    except Exception:
        pass
    
    return ""  # File not found or error reading


def get_os_identifier() -> str:
    """Get a simple OS identifier for prompts.
    
    Returns:
        'macos', 'windows', 'linux', or 'unknown'
    """
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    return "unknown"


def format_os_context(base_dir: str | Path) -> str:
    """Format the OS-specific context for injection into system prompt.
    
    Args:
        base_dir: Base directory where prompt files are located
        
    Returns:
        Formatted string with OS info and shortcuts, ready to inject
    """
    os_id = get_os_identifier()
    shortcuts_content = get_os_shortcuts_content(base_dir)
    
    if not shortcuts_content:
        return f"""### Operating System
Current OS: {os_id.upper()}
Use appropriate keyboard shortcuts for this operating system."""
    
    # Return with OS identifier header
    return f"""### Operating System
Current OS: {os_id.upper()}

{shortcuts_content}"""
