from enum import Enum


class AssistantEventType(str, Enum):

    THINKING = "thinking"

    ANALYZING = "analyzing"

    TOOL_START = "tool_start"

    TOOL_RESULT = "tool_result"

    TOOL_ERROR = "tool_error"

    FOLLOW_UP_QUESTION = "follow_up_question"

    PARTIAL_MESSAGE = "partial_message"

    FINAL_MESSAGE = "final_message"

    PERMISSION_DENIED = "permission_denied"

    CONFIRMATION_REQUIRED = "confirmation_required"

    WAITING_FOR_USER = "waiting_for_user"

    RUN_STARTED = "run_started"

    RUN_COMPLETED = "run_completed"

    RUN_FAILED = "run_failed"

    RUN_CANCELLED = "run_cancelled"
