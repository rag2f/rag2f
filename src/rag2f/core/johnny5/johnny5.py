import logging

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
        Processa il testo e ritorna True se il testo è stato preso in carico (non vuoto dopo strip), False altrimenti.
        """
        if text is None or not str(text).strip():
            logger.debug("handle_text_foreground input empty")
            return InsertResponse(
                status="failure",
                message="Input text is empty"
            )
        duplicated = False 
        if self.rag2f:
            self.rag2f.morpheus.execute_hook(
                "check_duplicated_input_text", duplicated , rag2f=self.rag2f
            )   
        if duplicated:
            logger.debug("handle_text_foreground input duplicated")
            return InsertResponse(
                status="duplicated",
                message="Input text is duplicated"
            )
        if self.rag2f:
            self.rag2f.morpheus.execute_hook(
                "handle_text_foreground", text, rag2f=self.rag2f
            )
        return InsertResponse(
            status="success"
        )


InputManager = Johnny5