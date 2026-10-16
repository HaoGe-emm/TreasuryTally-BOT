"""Secret-safe failures crossing the headless or MCP boundary."""


class HeadlessError(RuntimeError):
    def __init__(self, status: str, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.safe_message = message


def blocked(code: str, message: str) -> HeadlessError:
    return HeadlessError("BLOCKED", code, message)


def rejected(code: str, message: str) -> HeadlessError:
    return HeadlessError("REJECTED", code, message)


def authorization_required(message: str = "Local user approval is required.") -> HeadlessError:
    return HeadlessError("AUTHORIZATION_REQUIRED", "LOCAL_APPROVAL_REQUIRED", message)
