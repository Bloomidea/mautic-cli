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


class TestStats:
    @respx.mock
    def test_without_table_lists_tables(self):
        respx.get("https://mautic.test/api/stats").mock(
            return_value=httpx.Response(200, json={"availableTables": ["email_stats"], "tableColumns": {}})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert json.loads(result.output)["availableTables"] == ["email_stats"]

    @respx.mock
    def test_where_and_order(self):
        route = respx.get("https://mautic.test/api/stats/email_stats").mock(
            return_value=httpx.Response(200, json={"total": "1", "stats": [{"id": "9"}]})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, [
            "stats", "email_stats", "--where", "email_id=296", "--where", "date_sent>=2026-10-15",
            "--order", "id:desc", "--limit", "5",
        ])
        assert result.exit_code == 0, result.output
        params = dict(route.calls.last.request.url.params)
        assert params == {
            "where[0][col]": "email_id", "where[0][expr]": "eq", "where[0][val]": "296",
            "where[1][col]": "date_sent", "where[1][expr]": "gte", "where[1][val]": "2026-10-15",
            "order[0][col]": "id", "order[0][dir]": "DESC",
            "limit": "5", "start": "0",
        }

    @respx.mock
    def test_query_error_reported_with_http_200(self):
        respx.get("https://mautic.test/api/stats/focus_stats").mock(
            return_value=httpx.Response(200, json={"errors": [{"message": "Unknown column 'e.nope'", "code": 1054}]})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["stats", "focus_stats", "--where", "nope=1"])
        assert result.exit_code == 1
        assert "Unknown column" in result.output

    @respx.mock
    def test_unknown_table_is_an_error(self):
        # Mautic answers an unknown table with HTTP 200 and the list of tables.
        respx.get("https://mautic.test/api/stats/focus_stat").mock(
            return_value=httpx.Response(200, json={"availableTables": ["focus_stats"], "tableColumns": {}})
        )
        runner = CliRunner(env=MOCK_ENV)
        for args in (["stats", "focus_stat"], ["--page-all", "stats", "focus_stat"]):
            result = runner.invoke(cli, args)
            assert result.exit_code == 1
            assert "Unknown stats table: focus_stat" in result.output

    def test_page_all_dry_run_prints_the_request(self):
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["--dry-run", "--page-all", "stats", "focus_stats", "--where", "focus_id=2"])
        assert result.exit_code == 0
        out = json.loads(result.output)
        assert out["dry_run"] is True
        assert out["params"]["where[0][val]"] == "2"

    def test_bad_where(self):
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["stats", "focus_stats", "--where", "nope"])
        assert result.exit_code == 2
        assert "Expected column=value" in result.output

    @respx.mock
    def test_page_all_follows_total(self):
        route = respx.get("https://mautic.test/api/stats/focus_stats")
        route.side_effect = [
            httpx.Response(200, json={"total": "3", "stats": [{"id": "1"}, {"id": "2"}]}),
            httpx.Response(200, json={"total": "3", "stats": [{"id": "3"}]}),
        ]
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["--page-all", "stats", "focus_stats", "--limit", "2"])
        assert result.exit_code == 0, result.output
        assert [json.loads(line)["id"] for line in result.output.strip().split("\n")] == ["1", "2", "3"]
        assert route.calls[1].request.url.params["start"] == "2"
