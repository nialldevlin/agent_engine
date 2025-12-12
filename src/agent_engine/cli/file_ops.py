"""
File operations for Phase 18 CLI Framework.

Handles file viewing, editing, diffing, and patching with workspace safety.
"""

import os
from pathlib import Path
from typing import Optional
import difflib
import shutil
import tempfile

from .exceptions import CliError


def validate_path(path: str, workspace_root: str) -> str:
    """
    Validate and resolve a file path within workspace.

    Args:
        path: File path (absolute or relative to workspace)
        workspace_root: Workspace root directory

    Returns:
        Validated absolute path

    Raises:
        CliError: If path is outside workspace or contains traversal
    """
    # Resolve path
    if os.path.isabs(path):
        resolved = Path(path).resolve()
    else:
        resolved = (Path(workspace_root) / path).resolve()

    # Ensure within workspace
    workspace_path = Path(workspace_root).resolve()
    try:
        resolved.relative_to(workspace_path)
    except ValueError:
        raise CliError(f"Path is outside workspace: {path}")

    # Check for traversal attempts
    if ".." in path or path.startswith("/"):
        if not str(resolved).startswith(str(workspace_path)):
            raise CliError(f"Path traversal detected: {path}")

    return str(resolved)


def view_file(path: str, workspace_root: str) -> None:
    """
    Display file contents with line numbers and simple paging.

    Args:
        path: File path (relative to workspace)
        workspace_root: Workspace root directory

    Raises:
        CliError: If file cannot be read
    """
    validated_path = validate_path(path, workspace_root)

    try:
        with open(validated_path, "r") as f:
            lines = f.readlines()
    except IOError as e:
        raise CliError(f"Failed to read file: {str(e)}")

    # Display with line numbers
    terminal_height = 20  # Simple hardcoded height
    current_page = 0

    while True:
        start_idx = current_page * terminal_height
        end_idx = start_idx + terminal_height

        if start_idx >= len(lines):
            break

        for i, line in enumerate(lines[start_idx:end_idx], start=start_idx + 1):
            print(f"{i:4d}: {line}", end="")

        if end_idx >= len(lines):
            break

        # Simple paging prompt
        print("-- (space for next page, q to quit) --", end=" ")
        try:
            response = input()
            if response.lower() == "q":
                break
            elif response == " ":
                current_page += 1
            else:
                current_page += 1
        except EOFError:
            break


def edit_buffer(initial_text: str) -> str:
    """
    Simple line-based text editing.

    Args:
        initial_text: Initial text to edit

    Returns:
        Edited text
    """
    if initial_text:
        lines = initial_text.split("\n")
        for i, line in enumerate(lines, start=1):
            print(f"{i:3d}: {line}")

    print("--- Edit text below (blank line to finish) ---")
    edited_lines = []
    try:
        while True:
            line = input()
            if not line:
                break
            edited_lines.append(line)
    except EOFError:
        pass

    return "\n".join(edited_lines)


def compute_diff(file_path: str, artifact_content: str, workspace_root: str) -> str:
    """
    Compute unified diff between file and artifact content.

    Args:
        file_path: File path (relative to workspace)
        artifact_content: Content to compare against
        workspace_root: Workspace root directory

    Returns:
        Unified diff string

    Raises:
        CliError: If file cannot be read
    """
    validated_path = validate_path(file_path, workspace_root)

    try:
        with open(validated_path, "r") as f:
            file_content = f.read()
    except IOError as e:
        raise CliError(f"Failed to read file: {str(e)}")

    # Generate unified diff
    file_lines = file_content.splitlines(keepends=True)
    artifact_lines = artifact_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        file_lines,
        artifact_lines,
        fromfile=file_path,
        tofile=f"{file_path} (artifact)",
    )

    return "".join(diff)


def apply_patch_safe(file_path: str, patch_content: str, workspace_root: str) -> None:
    """
    Apply patch to file with backup and rollback on error.

    Args:
        file_path: File path (relative to workspace)
        patch_content: Patch content in unified diff format
        workspace_root: Workspace root directory

    Raises:
        CliError: If patch cannot be applied
    """
    validated_path = validate_path(file_path, workspace_root)

    # Create backup
    backup_path = validated_path + ".backup"
    try:
        if os.path.exists(validated_path):
            shutil.copy2(validated_path, backup_path)

        # Simple patch parsing (basic unified diff)
        # For v1, we do a simple text replacement approach
        # A more robust implementation would use patch parsing library

        with open(validated_path, "r") as f:
            original_content = f.read()

        # Apply patch (simplified - extract "new" version from diff)
        new_content = _parse_patch(patch_content, original_content)

        with open(validated_path, "w") as f:
            f.write(new_content)

        # Clean up backup on success
        if os.path.exists(backup_path):
            os.remove(backup_path)

    except Exception as e:
        # Rollback on error
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, validated_path)
                os.remove(backup_path)
            except:
                pass
        raise CliError(f"Failed to apply patch: {str(e)}")


def _parse_patch(patch_content: str, original_content: str) -> str:
    """
    Parse unified diff and apply to content.

    Args:
        patch_content: Patch in unified diff format
        original_content: Original file content

    Returns:
        Patched content
    """
    # Simplified patch parsing - extract new content from diff
    # For v1, this is a basic implementation
    lines = patch_content.split("\n")
    new_lines = []
    in_new_section = False

    for line in lines:
        if line.startswith("-"):
            # Removed line
            continue
        elif line.startswith("+"):
            # Added line
            new_lines.append(line[1:])
        elif line.startswith(" "):
            # Context line
            new_lines.append(line[1:])
        elif line.startswith("@@"):
            # Hunk header - skip
            continue

    if new_lines:
        return "\n".join(new_lines)
    return original_content
