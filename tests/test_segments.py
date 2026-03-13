import json

import httpx
import respx
from click.testing import CliRunner

from mautic_cli.cli import cli

MOCK_ENV = {
    "MAUTIC_BASE_URL": "https://mautic.test",
    "MAUTIC_USERNAME": "admin",
    "MAUTIC_PASSWORD": "secret",
}


class TestSegments:
    @respx.mock
    def test_list_segments(self):
        respx.get("https://mautic.test/api/segments").mock(
            return_value=httpx.Response(200, json={
                "total": "1",
                "lists": {"1": {"id": 1, "name": "Newsletter"}},
            })
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["segments", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] == "1"

    @respx.mock
    def test_get_segment(self):
        respx.get("https://mautic.test/api/segments/1").mock(
            return_value=httpx.Response(200, json={
                "list": {"id": 1, "name": "Newsletter"},
            })
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["segments", "get", "1"])
        assert result.exit_code == 0

    @respx.mock
    def test_create_segment(self):
        respx.post("https://mautic.test/api/segments/new").mock(
            return_value=httpx.Response(200, json={
                "list": {"id": 5, "name": "New Segment"},
            })
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["segments", "create", "--json", '{"name":"New Segment"}'])
        assert result.exit_code == 0

    @respx.mock
    def test_segment_contacts(self):
        # First call: fetch segment to get alias
        respx.get("https://mautic.test/api/segments/1").mock(
            return_value=httpx.Response(200, json={
                "list": {"id": 1, "name": "Newsletter", "alias": "newsletter"},
            })
        )
        # Second call: search contacts by segment alias
        respx.get("https://mautic.test/api/contacts").mock(
            return_value=httpx.Response(200, json={
                "total": "1",
                "contacts": {"42": {"id": 42}},
            })
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["segments", "contacts", "1"])
        assert result.exit_code == 0

    @respx.mock
    def test_delete_segment(self):
        respx.delete("https://mautic.test/api/segments/1/delete").mock(
            return_value=httpx.Response(200, json={"list": {"id": 1}})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["segments", "delete", "1"])
        assert result.exit_code == 0

    @respx.mock
    def test_add_contact_to_segment(self):
        respx.post("https://mautic.test/api/segments/5/contact/42/add").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["segments", "add-contact", "5", "42"])
        assert result.exit_code == 0

    @respx.mock
    def test_remove_contact_from_segment(self):
        respx.post("https://mautic.test/api/segments/5/contact/42/remove").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["segments", "remove-contact", "5", "42"])
        assert result.exit_code == 0
