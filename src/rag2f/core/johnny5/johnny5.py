"""Johnny5 input manager.

Johnny5 handles user input and delegates parts of the processing pipeline to
Morpheus hooks. Expected states (empty, duplicate, not_handled) return
InsertResult with status="error". System errors raise exceptions.
"""

import logging
import uuid

from rag2f.core.dto.johnny5_dto import InsertResult
from rag2f.core.dto.result_dto import StatusCode, StatusDetail

logger = logging.getLogger(__name__)


class Johnny5:
    """Small input handler that manages different input types.

    Famous quote from Johnny 5 in Short Circuit:
    "Input. More input!"
    """

    def __init__(self, rag2f_instance=None):
        """Create a Johnny5 instance.

        Args:
            rag2f_instance: Optional RAG2F instance used to invoke hooks.
        """
        self.rag2f = rag2f_instance
        logger.debug("Johnny5 created ")

    def execute_handle_text_foreground(self, text: str) -> InsertResult:
        """Process text input through the foreground pipeline.

        [Result Pattern] Check result.is_ok() before using fields.

        Args:
            text: Input text.

        Returns:
            InsertResult with status="success" and track_id if processed,
            or status="error" with detail for expected failures:
            - StatusCode.EMPTY: Input is empty or whitespace-only
            - StatusCode.DUPLICATE: Input was already processed
            - StatusCode.NOT_HANDLED: No hook handled the input

        Note:
            This method does NOT raise exceptions for expected states.
            System errors (rare) may still raise RuntimeError.
        """
        if text is None or not str(text).strip():
            logger.debug("execute_handle_text_foreground input empty")
            return InsertResult.fail(
                StatusDetail(code=StatusCode.EMPTY, message="Input text is empty")
            )

        track_id = None
        if self.rag2f:
            track_id = self.rag2f.morpheus.execute_hook(
                "get_id_input_text", track_id, text, rag2f=self.rag2f
            )
        if track_id is None:
            track_id = uuid.uuid4().hex

        duplicated = False
        if self.rag2f:
            duplicated = self.rag2f.morpheus.execute_hook(
                "check_duplicated_input_text", duplicated, track_id, text, rag2f=self.rag2f
            )
        if duplicated:
            logger.debug("execute_handle_text_foreground input duplicated")
            return InsertResult.fail(
                StatusDetail(
                    code=StatusCode.DUPLICATE,
                    message="Input text is duplicated",
                    context={"id": track_id, "text": text[:20]},
                )
            )

        done = False
        if self.rag2f:
            done = self.rag2f.morpheus.execute_hook(
                "handle_text_foreground", done, track_id, text, rag2f=self.rag2f
            )
        if not done:
            logger.debug("execute_handle_text_foreground input not handled by any hook")
            return InsertResult.fail(
                StatusDetail(
                    code=StatusCode.NOT_HANDLED, message="Input text not handled by any hook"
                )
            )

        return InsertResult.success(track_id=track_id)


InputManager = Johnny5
