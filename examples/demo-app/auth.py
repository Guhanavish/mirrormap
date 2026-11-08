"""Tiny intentionally incomplete demo for audit examples (not production auth)."""

def login(username: str, password: str) -> bool:
    return bool(username and password)  # Demo defect: no credential verification.


def logout() -> bool:
    return True  # Demo defect: does not invalidate a session.
