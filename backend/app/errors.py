"""Domain errors -> human-readable HTTP errors."""


class DomainError(Exception):
    status_code = 400
    code = "error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ClassNotActiveError(ConflictError):
    code = "class_not_active"

    def __init__(self, message: str = "No class is currently active. Start a class first."):
        super().__init__(message)
