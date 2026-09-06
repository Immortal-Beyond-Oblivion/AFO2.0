# components/file_tools.py
import os
import re
import shutil
from langchain.tools import tool
from .retriever import Retriever
from .retriever import retriever_instance

# --- T010: path/filename sanitization ---
# destination_category and new_filename below come straight from LLM tool-call
# output (see state.md §6). They must be treated as untrusted input: a
# mis-classification, a malformed model response, or a prompt-injection
# attempt embedded in a file's own content could otherwise smuggle path
# separators, '..', or illegal characters into a path we're about to write to.

# Characters that are illegal in filenames on Windows (and generally unwise
# elsewhere) plus all ASCII control characters, including NUL.
_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')

_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _sanitize_path_component(value: str, field_name: str) -> str:
    """
    Validate a single path *component* (a category name or filename) that came
    from LLM tool-call output. Returns the sanitized value, or raises
    ValueError with a human-readable reason. Callers must catch ValueError and
    turn it into a tool error string rather than letting it propagate, so a
    bad LLM response surfaces as a normal "Error: ..." tool result instead of
    crashing the agent run.

    This deliberately rejects rather than silently strips: a value that needed
    "fixing" to become safe is exactly the kind of value we don't want to
    guess about and proceed with anyway.
    """
    if value is None:
        raise ValueError(f"{field_name} is missing.")

    original = value
    value = value.strip()

    if not value:
        raise ValueError(f"{field_name} is empty after stripping whitespace.")

    if any(ord(ch) < 0x20 for ch in value):
        raise ValueError(f"{field_name} contains control characters: {original!r}")

    # Reject both OS-native and the other OS's path separators, since LLM
    # output isn't guaranteed to match the host OS. This also implicitly
    # blocks absolute paths like '/etc/passwd' or 'C:\\Windows' from ever
    # being treated as a single component.
    if "/" in value or "\\" in value:
        raise ValueError(
            f"{field_name} contains a path separator, which is not allowed: {original!r}"
        )

    # Reject '..' anywhere in the value (not just as the whole value) to block
    # directory-traversal tricks like '..hidden' as well as a bare '..'.
    if ".." in value:
        raise ValueError(f"{field_name} contains '..', which is not allowed: {original!r}")

    if _ILLEGAL_FILENAME_CHARS.search(value):
        raise ValueError(
            f"{field_name} contains characters that are not allowed in filenames "
            f'(< > : " | ? * or control characters): {original!r}'
        )

    if value in (".", ".."):
        raise ValueError(f"{field_name} cannot be '.' or '..': {original!r}")

    if value.upper() in _WINDOWS_RESERVED_NAMES:
        raise ValueError(f"{field_name} is a reserved device name on Windows: {original!r}")

    return value


@tool
def move_and_rename_file(source_path: str, destination_category: str, new_filename: str):
    """
    Moves a file to a specified destination folder and renames it.
    It will create the destination folder if it does not exist.
    The destination_folder should be a simple category like 'Invoices' or 'Resumes', not a full path.
    """
    if not os.path.exists(source_path):
        return f"Error: Source file not found at {source_path}"

    # Sanitize LLM-provided values before they touch any path construction.
    try:
        destination_category = _sanitize_path_component(destination_category, "destination_category")
        new_filename = _sanitize_path_component(new_filename, "new_filename")
    except ValueError as e:
        return f"Error: refused to move file due to an unsafe destination/filename ({e})"

    try:
        monitored_folder = os.path.dirname(source_path)
        # realpath resolves symlinks too, not just '..' segments, so the
        # containment check below can't be fooled by a symlinked monitored
        # folder either.
        monitored_root = os.path.realpath(monitored_folder)

        current_subfolder = os.path.basename(monitored_folder)
        if current_subfolder.lower() == destination_category.lower():
            return f"Success: File is already in the correct category folder '{destination_category}'. No action taken."

        full_destination_folder = os.path.join(monitored_folder, destination_category)
        destination_path = os.path.join(full_destination_folder, new_filename)

        # Hard-enforce the resolved destination cannot escape the monitored
        # root, regardless of what the component-level checks above might
        # have missed. This is the last line of defense, not the only one.
        resolved_destination = os.path.realpath(destination_path)
        try:
            common = os.path.commonpath([resolved_destination, monitored_root])
        except ValueError:
            # Raised on Windows when the two paths are on different drives -
            # that's an escape too, just report it via the same branch below.
            common = None

        if common != monitored_root:
            return (
                f"Error: refused to move file — resolved destination "
                f"'{resolved_destination}' would land outside the monitored "
                f"folder '{monitored_root}'."
            )

        if not os.path.exists(full_destination_folder):
            retriever_instance.add_folder_to_memory(destination_category)

        os.makedirs(full_destination_folder, exist_ok=True)
        shutil.move(source_path, destination_path)
        return f"Success: File moved and renamed to {destination_path}"
    except Exception as e:
        return f"Error moving file: {e}"
