from __future__ import annotations

import sys

import httpx


class MauticApiError(Exception):
    """Raised when Mautic API returns an error response."""

    def __init__(self, message: str, code: int, error_type: str = "api_error"):
        self.message = message
        self.code = code
        self.error_type = error_type
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "type": self.error_type}}


class MauticClient:
    MAX_LIMIT = 200

    def __init__(self, credentials: dict, dry_run: bool = False, verbose: bool = False, verify_ssl: bool = True):
        self.base_url = credentials["base_url"].rstrip("/")
        self.api_url = f"{self.base_url}/api"
        self._credentials = credentials
        self.dry_run = dry_run
        self.verbose = verbose
        self.verify_ssl = verify_ssl
        self._http = self._build_http_client()
        self._mautic_version: tuple[int, ...] | None = None

    def _build_http_client(self) -> httpx.Client:
        headers = {"Accept": "application/json"}
        auth = None

        if self._credentials["auth_method"] == "basic":
            auth = httpx.BasicAuth(
                self._credentials["username"],
                self._credentials["password"],
            )
        elif self._credentials["auth_method"] == "oauth2":
            token = self._fetch_oauth2_token()
            headers["Authorization"] = f"Bearer {token}"

        return httpx.Client(
            base_url=self.api_url,
            auth=auth,
            headers=headers,
            timeout=30.0,
            verify=self.verify_ssl,
            follow_redirects=True,
        )

    def _fetch_oauth2_token(self) -> str:
        """Exchange client credentials for an access token."""
        token_url = self._credentials["token_endpoint"]
        response = httpx.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._credentials["client_id"],
                "client_secret": self._credentials["client_secret"],
            },
            verify=self.verify_ssl,
            timeout=30.0,
        )
        if response.status_code != 200:
            try:
                detail = response.json().get("error_description", response.text)
            except Exception:
                detail = response.text
            raise MauticApiError(
                message=f"OAuth2 token request failed: {detail}",
                code=response.status_code,
                error_type="oauth2_error",
            )
        data = response.json()
        return data["access_token"]

    def get(self, path: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        if "limit" in params:
            params["limit"] = min(int(params["limit"]), self.MAX_LIMIT)
        return self._request("GET", path, params=params)

    def get_all(
        self,
        path: str,
        resource_key: str,
        limit: int = 30,
        params: dict | None = None,
    ):
        """Auto-paginate and yield individual records."""
        limit = min(limit, self.MAX_LIMIT)
        offset = 0
        params = dict(params or {})
        while True:
            params.update({"limit": limit, "start": offset})
            data = self.get(path, params=params)
            items = data.get(resource_key, {})
            # v1 returns dict keyed by ID, convert to list
            if isinstance(items, dict):
                records = list(items.values())
            else:
                records = list(items)
            yield from records
            total = int(data.get("total", 0))
            offset += limit
            if offset >= total:
                break

    def post(self, path: str, json: dict | None = None) -> dict:
        return self._request("POST", path, json=json)

    def patch(self, path: str, json: dict | None = None) -> dict:
        return self._request("PATCH", path, json=json)

    def delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    def detect_version(self) -> tuple[int, ...]:
        """Detect Mautic version from the mautic-version response header.

        Available since Mautic 2.4.0. Makes a lightweight GET to /contacts
        with limit=1 and reads the header from the response.
        """
        if self._mautic_version is not None:
            return self._mautic_version
        response = self._http.request("GET", "/contacts", params={"limit": 1})
        version_str = response.headers.get("mautic-version", "0.0.0")
        parts = []
        for part in version_str.split("."):
            # Handle versions like "6.0.6-dev" by stripping non-numeric suffixes
            digits = ""
            for ch in part:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            parts.append(int(digits) if digits else 0)
        self._mautic_version = tuple(parts)
        return self._mautic_version

    def require_version(self, minimum: tuple[int, ...]) -> None:
        """Raise if connected Mautic is older than minimum."""
        detected = self.detect_version()
        if detected < minimum:
            min_str = ".".join(str(x) for x in minimum)
            det_str = ".".join(str(x) for x in detected)
            raise MauticApiError(
                message=f"This command requires Mautic {min_str}+. Detected version: {det_str}.",
                code=0,
                error_type="version_required",
            )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.api_url}{path}"
        if self.dry_run:
            return {
                "dry_run": True,
                "method": method,
                "url": url,
                "params": kwargs.get("params"),
                "body": kwargs.get("json"),
            }
        if self.verbose:
            params = kwargs.get("params", {})
            print(f">> {method} {url}", file=sys.stderr)
            if params:
                print(f">> Params: {params}", file=sys.stderr)
        response = self._http.request(method, path, **kwargs)
        if self.verbose:
            print(f"<< {response.status_code}", file=sys.stderr)

        # OAuth2 token expired - refresh and retry once
        if response.status_code == 401 and self._credentials["auth_method"] == "oauth2":
            token = self._fetch_oauth2_token()
            self._http.headers["Authorization"] = f"Bearer {token}"
            response = self._http.request(method, path, **kwargs)
            if self.verbose:
                print(f"<< {response.status_code} (after token refresh)", file=sys.stderr)

        if not response.content:
            content_type = response.headers.get("content-type", "")
            raise MauticApiError(
                message=f"Empty response body (HTTP {response.status_code}). Content-Type: {content_type}",
                code=response.status_code,
                error_type="empty_response",
            )
        try:
            data = response.json()
        except Exception:
            raise MauticApiError(
                message=f"Response is not valid JSON (HTTP {response.status_code})",
                code=response.status_code,
                error_type="invalid_response",
            )
        if response.status_code >= 400:
            self._raise_api_error(data, response.status_code)
        return data

    def _raise_api_error(self, data: dict, status_code: int) -> None:
        """Parse error from v1 or v2 response format."""
        message = "Unknown API error"
        error_type = "api_error"
        # v1 format: {"errors": [{"message": "...", "code": 404, "type": "..."}]}
        errors = data.get("errors")
        if isinstance(errors, list) and errors:
            err = errors[0]
            message = err.get("message", message)
            error_type = err.get("type", error_type)
        # v1 alt format: {"error": {"message": "..."}}
        elif isinstance(data.get("error"), dict):
            message = data["error"].get("message", message)
            error_type = data["error"].get("type", error_type)
        # v2 format: {"hydra:description": "...", "detail": "..."}
        elif "hydra:description" in data:
            message = data["hydra:description"]
        elif "detail" in data:
            message = data["detail"]
        raise MauticApiError(message=message, code=status_code, error_type=error_type)

    def close(self) -> None:
        self._http.close()
