import httpx
import pytest
import respx

from mautic_cli.client import MauticClient, MauticApiError


@pytest.fixture
def basic_creds():
    return {
        "base_url": "https://mautic.test",
        "auth_method": "basic",
        "username": "admin",
        "password": "secret",
    }


class TestMauticClientBasicAuth:
    @respx.mock
    def test_get_contacts(self, basic_creds):
        route = respx.get("https://mautic.test/api/contacts").mock(
            return_value=httpx.Response(200, json={
                "total": "1",
                "contacts": {"1": {"id": 1, "fields": {"all": {"email": "a@b.com"}}}},
            })
        )
        client = MauticClient(basic_creds)
        result = client.get("/contacts")
        assert route.called
        assert result["total"] == "1"

    @respx.mock
    def test_post_contact(self, basic_creds):
        respx.post("https://mautic.test/api/contacts/new").mock(
            return_value=httpx.Response(200, json={
                "contact": {"id": 42, "fields": {"all": {"email": "new@b.com"}}},
            })
        )
        client = MauticClient(basic_creds)
        result = client.post("/contacts/new", json={"email": "new@b.com"})
        assert result["contact"]["id"] == 42

    @respx.mock
    def test_basic_auth_header_sent(self, basic_creds):
        route = respx.get("https://mautic.test/api/contacts").mock(
            return_value=httpx.Response(200, json={"total": "0", "contacts": {}})
        )
        client = MauticClient(basic_creds)
        client.get("/contacts")
        request = route.calls[0].request
        assert "authorization" in request.headers
        assert request.headers["authorization"].startswith("Basic ")

    @respx.mock
    def test_api_error_parsed_v1(self, basic_creds):
        respx.get("https://mautic.test/api/contacts/999").mock(
            return_value=httpx.Response(404, json={
                "errors": [{"message": "Item was not found.", "code": 404}],
            })
        )
        client = MauticClient(basic_creds)
        with pytest.raises(MauticApiError, match="Item was not found"):
            client.get("/contacts/999")

    @respx.mock
    def test_api_error_parsed_v2(self, basic_creds):
        respx.get("https://mautic.test/api/contacts/999").mock(
            return_value=httpx.Response(404, json={
                "hydra:description": "Resource not found.",
            })
        )
        client = MauticClient(basic_creds)
        with pytest.raises(MauticApiError, match="Resource not found"):
            client.get("/contacts/999")


class TestPagination:
    @respx.mock
    def test_limit_capped_at_200(self, basic_creds):
        route = respx.get("https://mautic.test/api/contacts").mock(
            return_value=httpx.Response(200, json={"total": "0", "contacts": {}})
        )
        client = MauticClient(basic_creds)
        client.get("/contacts", params={"limit": 500})
        request = route.calls[0].request
        assert "limit=200" in str(request.url)

    @respx.mock
    def test_page_all_fetches_multiple_pages(self, basic_creds):
        page1 = {"total": "3", "contacts": {
            "1": {"id": 1}, "2": {"id": 2},
        }}
        page2 = {"total": "3", "contacts": {
            "3": {"id": 3},
        }}
        route = respx.get("https://mautic.test/api/contacts")
        route.side_effect = [
            httpx.Response(200, json=page1),
            httpx.Response(200, json=page2),
        ]
        client = MauticClient(basic_creds)
        results = list(client.get_all("/contacts", resource_key="contacts", limit=2))
        assert len(results) == 3
        assert results[0]["id"] == 1
        assert results[2]["id"] == 3


class TestVersionDetection:
    @respx.mock
    def test_detects_mautic_version_from_header(self, basic_creds):
        respx.get("https://mautic.test/api/contacts").mock(
            return_value=httpx.Response(
                200,
                json={"total": "0", "contacts": {}},
                headers={"mautic-version": "5.4.2"},
            )
        )
        client = MauticClient(basic_creds)
        version = client.detect_version()
        assert version == (5, 4, 2)

    @respx.mock
    def test_version_cached_after_first_call(self, basic_creds):
        route = respx.get("https://mautic.test/api/contacts").mock(
            return_value=httpx.Response(
                200,
                json={"total": "0", "contacts": {}},
                headers={"mautic-version": "7.0.0"},
            )
        )
        client = MauticClient(basic_creds)
        client.detect_version()
        client.detect_version()
        assert route.call_count == 1

    @respx.mock
    def test_require_version_raises_on_old(self, basic_creds):
        respx.get("https://mautic.test/api/contacts").mock(
            return_value=httpx.Response(
                200,
                json={"total": "0", "contacts": {}},
                headers={"mautic-version": "5.4.2"},
            )
        )
        client = MauticClient(basic_creds)
        with pytest.raises(MauticApiError, match="requires Mautic 7"):
            client.require_version((7, 0, 0))

    @respx.mock
    def test_require_version_passes_on_new(self, basic_creds):
        respx.get("https://mautic.test/api/contacts").mock(
            return_value=httpx.Response(
                200,
                json={"total": "0", "contacts": {}},
                headers={"mautic-version": "7.0.0"},
            )
        )
        client = MauticClient(basic_creds)
        client.require_version((7, 0, 0))  # Should not raise


@pytest.fixture
def oauth2_creds():
    return {
        "base_url": "https://mautic.test",
        "auth_method": "oauth2",
        "client_id": "my_client",
        "client_secret": "my_secret",
        "token_endpoint": "https://mautic.test/oauth/v2/token",
    }


class TestOAuth2:
    @respx.mock
    def test_oauth2_fetches_token_and_authenticates(self, oauth2_creds):
        respx.post("https://mautic.test/oauth/v2/token").mock(
            return_value=httpx.Response(200, json={
                "access_token": "test_token_123",
                "token_type": "bearer",
                "expires_in": 3600,
            })
        )
        respx.get("https://mautic.test/api/contacts").mock(
            return_value=httpx.Response(200, json={"total": "0", "contacts": {}})
        )
        client = MauticClient(oauth2_creds)
        client.get("/contacts")
        request = respx.calls[1].request
        assert request.headers["authorization"] == "Bearer test_token_123"

    @respx.mock
    def test_oauth2_refreshes_token_on_401(self, oauth2_creds):
        # Initial token fetch
        respx.post("https://mautic.test/oauth/v2/token").mock(
            side_effect=[
                httpx.Response(200, json={"access_token": "old_token", "token_type": "bearer"}),
                httpx.Response(200, json={"access_token": "new_token", "token_type": "bearer"}),
            ]
        )
        contacts_route = respx.get("https://mautic.test/api/contacts")
        contacts_route.side_effect = [
            httpx.Response(401, json={"errors": [{"message": "Unauthorized", "code": 401}]}),
            httpx.Response(200, json={"total": "0", "contacts": {}}),
        ]
        client = MauticClient(oauth2_creds)
        data = client.get("/contacts")
        assert data["total"] == "0"
        # Should have called token endpoint twice (initial + refresh)
        token_calls = [c for c in respx.calls if "token" in str(c.request.url)]
        assert len(token_calls) == 2

    @respx.mock
    def test_oauth2_token_failure_raises(self, oauth2_creds):
        respx.post("https://mautic.test/oauth/v2/token").mock(
            return_value=httpx.Response(400, json={
                "error": "invalid_client",
                "error_description": "Client credentials are invalid",
            })
        )
        with pytest.raises(MauticApiError, match="Client credentials are invalid"):
            MauticClient(oauth2_creds)


class TestDryRunAndVerbose:
    @respx.mock
    def test_dry_run_does_not_send_request(self, basic_creds):
        route = respx.get("https://mautic.test/api/contacts").mock(
            return_value=httpx.Response(200, json={})
        )
        client = MauticClient(basic_creds, dry_run=True)
        result = client.get("/contacts", params={"limit": 10})
        assert not route.called
        assert result["dry_run"] is True
        assert result["method"] == "GET"
        assert "/contacts" in result["url"]

    @respx.mock
    def test_fetch_runs_under_dry_run(self, basic_creds):
        route = respx.get("https://mautic.test/api/focus/2").mock(
            return_value=httpx.Response(200, json={"focus": {"id": 2}})
        )
        client = MauticClient(basic_creds, dry_run=True)
        assert client.fetch("/focus/2") == {"focus": {"id": 2}}
        assert route.called
        assert client.patch("/focus/2/edit", json={})["dry_run"] is True

    @respx.mock
    def test_verbose_includes_request_info(self, basic_creds, capsys):
        respx.get("https://mautic.test/api/contacts").mock(
            return_value=httpx.Response(200, json={"total": "0", "contacts": {}})
        )
        client = MauticClient(basic_creds, verbose=True)
        client.get("/contacts")
        captured = capsys.readouterr()
        assert "GET" in captured.err
        assert "/contacts" in captured.err
