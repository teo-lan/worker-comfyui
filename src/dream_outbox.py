"""Durable, temporary delivery outbox for DREAM media.

RunPod only retains asynchronous job responses briefly.  The worker therefore
copies every completed output to the attached network volume before returning
it.  DREAM can request the bytes again by original job ID, then acknowledge
delivery on a later worker request.  Old entries are pruned automatically.
"""

import base64
import os
import re
import shutil
import time
import uuid


DEFAULT_ROOT = "/runpod-volume/dream-outbox"
DEFAULT_TTL_SECONDS = 72 * 60 * 60
MAX_ACKNOWLEDGEMENTS = 100
_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,160}$")


def configured_root(root=None):
    """Return the configured outbox directory."""
    return root or os.environ.get("DREAM_OUTBOX_PATH", DEFAULT_ROOT)


def ttl_seconds():
    """Return the configured retention period, with a safe 72-hour fallback."""
    try:
        value = int(os.environ.get("DREAM_OUTBOX_TTL_SECONDS", DEFAULT_TTL_SECONDS))
    except ValueError:
        return DEFAULT_TTL_SECONDS
    return max(60 * 60, value)


def is_available(root=None):
    """Whether the target is backed by the expected persistent volume.

    An explicit path is accepted for local tests and custom deployments.  For
    the default path we require /runpod-volume to exist; otherwise writing there
    would silently create ephemeral container storage and provide false safety.
    """
    target = configured_root(root)
    if root is None and "DREAM_OUTBOX_PATH" not in os.environ:
        if not os.path.isdir("/runpod-volume"):
            return False
    try:
        os.makedirs(target, exist_ok=True)
        return os.access(target, os.W_OK)
    except OSError:
        return False


def validate_job_id(job_id):
    """Reject path traversal and malformed external identifiers."""
    if not isinstance(job_id, str) or not _SAFE_JOB_ID.fullmatch(job_id):
        raise ValueError("invalid outbox job id")
    return job_id


def _job_directory(job_id, root=None):
    validated = validate_job_id(job_id)
    return os.path.join(configured_root(root), validated)


def _safe_filename(filename):
    name = os.path.basename(filename or "output.bin")
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return cleaned[:180] or "output.bin"


def persist(job_id, filename, data, output_index=0, root=None):
    """Atomically persist one generated file, returning True on success."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        return False
    if not is_available(root):
        return False

    directory = _job_directory(job_id, root)
    os.makedirs(directory, exist_ok=True)
    destination = os.path.join(
        directory,
        f"{max(0, int(output_index)):03d}-{_safe_filename(filename)}",
    )
    temporary = os.path.join(directory, f".{uuid.uuid4().hex}.tmp")
    try:
        with open(temporary, "wb") as output_file:
            output_file.write(data)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary, destination)
        os.utime(directory, None)
        return True
    except OSError:
        try:
            os.remove(temporary)
        except OSError:
            pass
        return False


def recover(job_id, root=None):
    """Return worker-compatible base64 output descriptors for a saved job."""
    if not is_available(root):
        return []
    directory = _job_directory(job_id, root)
    try:
        names = sorted(
            name
            for name in os.listdir(directory)
            if not name.startswith(".")
            and os.path.isfile(os.path.join(directory, name))
        )
    except OSError:
        return []

    outputs = []
    for name in names:
        path = os.path.join(directory, name)
        try:
            with open(path, "rb") as input_file:
                data = input_file.read()
        except OSError:
            continue
        if not data:
            continue
        display_name = name.split("-", 1)[1] if "-" in name else name
        outputs.append(
            {
                "filename": display_name,
                "type": "base64",
                "data": base64.b64encode(data).decode("utf-8"),
            }
        )
    return outputs


def delete(job_ids, root=None):
    """Delete acknowledged job directories and return the IDs actually removed."""
    if not is_available(root):
        return []
    if not isinstance(job_ids, list):
        raise ValueError("outbox job_ids must be a list")

    removed = []
    for raw_id in job_ids[:MAX_ACKNOWLEDGEMENTS]:
        job_id = validate_job_id(raw_id)
        directory = _job_directory(job_id, root)
        if not os.path.isdir(directory):
            continue
        try:
            shutil.rmtree(directory)
            removed.append(job_id)
        except OSError:
            continue
    return removed


def prune(root=None, now=None, retention_seconds=None):
    """Remove outbox directories older than the configured retention period."""
    if not is_available(root):
        return []
    target = configured_root(root)
    cutoff = (time.time() if now is None else now) - (
        ttl_seconds() if retention_seconds is None else retention_seconds
    )
    removed = []
    try:
        entries = list(os.scandir(target))
    except OSError:
        return removed

    for entry in entries:
        if not entry.is_dir(follow_symlinks=False):
            continue
        try:
            if entry.stat(follow_symlinks=False).st_mtime >= cutoff:
                continue
            shutil.rmtree(entry.path)
            removed.append(entry.name)
        except OSError:
            continue
    return removed
