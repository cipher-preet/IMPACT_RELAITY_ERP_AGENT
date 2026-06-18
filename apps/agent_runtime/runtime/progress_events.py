from typing import Any, Dict, Optional


def emit_progress(
    state: Dict[str, Any],
    event_type: str,
    message: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    progress_callback = state.get("progress_callback")

    if not callable(progress_callback):
        return

    progress_callback(
        {
            "event_type": event_type,
            "message": message,
            "payload": payload or {},
        }
    )
