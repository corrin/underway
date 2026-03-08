from google.auth.transport.requests import Request

def verify_oauth2_token(
    id_token: str,
    request: Request,
    audience: str | None = None,
) -> dict[str, object]: ...
