import logging
import uuid

from rag2f.core.dto.johnny5_dto import InsertResponse


logger = logging.getLogger(__name__)



class Johnny5:
    """Small input handler that manages different input types.
    Famous quote from Johnny 5 in Short Circuit:
    "Input. More input!"
   
    """

    def __init__(self, rag2f_instance = None):
        self.rag2f = rag2f_instance 
        logger.debug("Johnny5 created ")

    def handle_text_foreground(self, text: str) -> InsertResponse:
        """
        Process the text and return True if the text was taken in charge (non-empty after strip), False otherwise.
        """
        if text is None or not str(text).strip():
            logger.debug("handle_text_foreground input empty")
            return InsertResponse(
                status="failure",
                message="Input text is empty"
            )
        id = None
        if self.rag2f:
            id = self.rag2f.morpheus.execute_hook(
                "get_id_input_text", id, text, rag2f=self.rag2f
            )   # TODO: missing a test that guarantees the hook pass-through and id return.
        if id is None:
            # TODO: missing a test to check it uses the GUID.
            id = uuid.uuid4().hex
        duplicated = False 
        if self.rag2f:
            duplicated = self.rag2f.morpheus.execute_hook(
                "check_duplicated_input_text", duplicated, id, text, rag2f=self.rag2f
            )   # TODO: missing a test that guarantees the hook pass-through and duplicated return
        if duplicated:
            logger.debug("handle_text_foreground input duplicated")
            return InsertResponse(
                status="duplicated",
                message="Input text is duplicated"
            )
        done = False 
        if self.rag2f:
            done = self.rag2f.morpheus.execute_hook(
                "handle_text_foreground", done, id, text, rag2f=self.rag2f
            )   # TODO: missing a test that guarantees the hook pass-through and done return
        if not done:
            logger.debug("handle_text_foreground input not handled by any hook")
            return InsertResponse(
                status="failure",
                message="Input text not handled"
            )
        return InsertResponse(
            status="success"
        )


InputManager = Johnny5
