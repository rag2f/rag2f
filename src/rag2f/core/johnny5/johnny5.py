"""Johnny5 input manager.

Johnny5 handles user input and delegates parts of the processing pipeline to
Morpheus hooks.
"""

import logging
import uuid

from rag2f.core.dto.johnny5_dto import InsertResult
from rag2f.core.johnny5.exceptions import DuplicateInputError, InsertError

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

    def handle_text_foreground(self, text: str) -> InsertResult:
        """Process text input through the foreground pipeline.

        Args:
            text: Input text.

        Returns:
            An InsertResult describing the processing result.

        Raises:
            InsertError: If input is empty or not handled by any hook.
            DuplicateInputError: If input is detected as duplicate.
        """
        if text is None or not str(text).strip():
            logger.debug("handle_text_foreground input empty")
            raise InsertError("Input text is empty")
        id = None
        if self.rag2f:
            id = self.rag2f.morpheus.execute_hook(
                "get_id_input_text", id, text, rag2f=self.rag2f
            )  # TODO: missing a test that guarantees the hook pass-through and id return.
        if id is None:
            # TODO: missing a test to check it uses the GUID.
            id = uuid.uuid4().hex
        duplicated = False
        if self.rag2f:
            duplicated = self.rag2f.morpheus.execute_hook(
                "check_duplicated_input_text", duplicated, id, text, rag2f=self.rag2f
            )  # TODO: missing a test that guarantees the hook pass-through and duplicated return
        if duplicated:
            logger.debug("handle_text_foreground input duplicated")
            raise DuplicateInputError(
                "Input text is duplicated", context={"id": id, "text": text[:20]}
            )
        done = False
        if self.rag2f:
            done = self.rag2f.morpheus.execute_hook(
                "handle_text_foreground", done, id, text, rag2f=self.rag2f
            )  # TODO: missing a test that guarantees the hook pass-through and done return
        if not done:
            logger.debug("handle_text_foreground input not handled by any hook")
            raise InsertError("Input text not handled by any hook")
        return InsertResult(status="success", track_id=id)


InputManager = Johnny5
