# components/file_tools.py
import os
import re
import shutil
from langchain.tools import tool
from .retriever import Retriever
from .retriever import retriever_instance
from .events_log import log_event

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


# --- T011: collision-safe destination naming ---
# shutil.move silently overwrites an existing file at the destination path
# with no warning (see state.md §6). Rather than ever calling shutil.move
# against a path that already exists, we compute a non-colliding destination
# up front by auto-suffixing " (1)", " (2)", etc. before the extension, the
# same convention most OS file managers use for "copy" conflicts.
_MAX_COLLISION_ATTEMPTS = 1000


def _get_collision_safe_path(destination_path: str) -> str:
    """
    Given a desired destination path, return a path guaranteed not to exist
    on disk at the moment of the check: either the original path unchanged
    (if nothing is there yet), or the same path with a " (N)" suffix inserted
    before the file extension, incrementing N until a free name is found.

    This does not eliminate every theoretical TOCTOU race (another process
    could create the chosen name between this check and the actual
    shutil.move), but it closes the actual reported gap: a same-run
    mis-classification or naming collision silently clobbering an existing
    file. Raises RuntimeError in the extremely unlikely event no free name is
    found within _MAX_COLLISION_ATTEMPTS tries, rather than looping forever.
    """
    if not os.path.exists(destination_path):
        return destination_path

    folder, filename = os.path.split(destination_path)
    base, ext = os.path.splitext(filename)

    for n in range(1, _MAX_COLLISION_ATTEMPTS + 1):
        candidate = os.path.join(folder, f"{base} ({n}){ext}")
        if not os.path.exists(candidate):
            return candidate

    raise RuntimeError(
        f"Could not find a free filename for '{filename}' in '{folder}' "
        f"after {_MAX_COLLISION_ATTEMPTS} attempts."
    )


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

        # T011: never let shutil.move silently overwrite an existing file at
        # the destination. If destination_path is already taken, resolve to
        # a free " (N)" suffixed name instead of clobbering whatever is
        # there. The collision check happens only after the folder exists
        # above (so a freshly created destination folder is never mistaken
        # for a collision) and immediately before the move, to keep the
        # window between check and move as small as possible.
        try:
            final_destination_path = _get_collision_safe_path(destination_path)
        except RuntimeError as e:
            return f"Error: refused to move file due to a naming collision ({e})"

        shutil.move(source_path, final_destination_path)

        # T012: log every successful move/rename to the append-only events
        # table (architecture.md §2.1) so there is an audit trail of what
        # happened to a user's files, and so T013's undo has something to
        # reverse. Only successful moves are logged here - refusals (bad
        # sanitization, containment escape, exhausted collision attempts)
        # are surfaced to the caller as error strings above but intentionally
        # not logged as events, since no filesystem change occurred for them.
        log_event(
            event_type="moved",
            from_path=source_path,
            to_path=final_destination_path,
            actor="agent",
        )

        if final_destination_path != destination_path:
            return (
                f"Success: A file named '{new_filename}' already existed at the "
                f"destination, so this file was moved and renamed to "
                f"{final_destination_path} instead, to avoid overwriting the "
                f"existing file."
            )
        return f"Success: File moved and renamed to {final_destination_path}"
    except Exception as e:
        return f"Error moving file: {e}"
