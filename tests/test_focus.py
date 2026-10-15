import copy
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

FOCUS = {
    "id": 2,
    "name": "Newsletter PT",
    "isPublished": True,
    "dateAdded": "2026-10-01T10:00:00+00:00",
    "dateModified": "2026-10-15T09:00:00+00:00",
    "createdBy": 1,
    "createdByUser": "Admin",
    "modifiedBy": 1,
    "modifiedByUser": "Admin",
    "category": {"id": 4, "title": "Popups"},
    "type": "form",
    "style": "modal",
    "form": 5,
    "htmlMode": "html",
    "html": "<div>Old</div>",
    "properties": {
        "when": "immediately",
        "timeout": "4",
        "frequency": "everypage",
        "min_page_views": 2,
        "content": {"headline": "H", "css": ".a{color:red}"},
        "modal": {"placement": "middle"},
    },
    "projects": [],
}


def _after(**changes):
    focus = copy.deepcopy(FOCUS)
    focus["dateModified"] = "2026-10-15T10:00:00+00:00"
    for path, value in changes.items():
        node = focus
        *parents, last = path.split("__")
        for part in parents:
            node = node[part]
        node[last] = value
    return focus


class TestFocus:
    @respx.mock
    def test_list(self):
        respx.get("https://mautic.test/api/focus").mock(
            return_value=httpx.Response(200, json={"total": 1, "focus": [FOCUS]})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["--format", "table", "focus", "list"])
        assert result.exit_code == 0
        assert "Newsletter PT" in result.output
        assert "modal" in result.output

    @respx.mock
    def test_get(self):
        respx.get("https://mautic.test/api/focus/2").mock(
            return_value=httpx.Response(200, json={"focus": FOCUS})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["focus", "get", "2"])
        assert result.exit_code == 0
        assert json.loads(result.output)["focus"]["id"] == 2

    @respx.mock
    def test_create_sends_html_mode_under_its_api_name(self):
        route = respx.post("https://mautic.test/api/focus/new").mock(
            return_value=httpx.Response(201, json={"focus": {"id": 3}})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["focus", "create", "--json", '{"name": "Bar", "htmlMode": "html"}'])
        assert result.exit_code == 0
        body = json.loads(route.calls.last.request.content)
        assert body == {"name": "Bar", "html_mode": "html"}

    @respx.mock
    def test_edit_css_sends_whole_item(self, tmp_path):
        css = tmp_path / "focus.css"
        css.write_text(".a{color:blue}\n")
        respx.get("https://mautic.test/api/focus/2").mock(side_effect=[
            httpx.Response(200, json={"focus": FOCUS}),
            httpx.Response(200, json={"focus": _after(properties__content__css=".a{color:blue}")}),
        ])
        patch = respx.patch("https://mautic.test/api/focus/2/edit").mock(
            return_value=httpx.Response(200, json={"focus": FOCUS})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["focus", "edit", "2", "--css", f"@{css}"])
        assert result.exit_code == 0, result.output

        body = json.loads(patch.calls.last.request.content)
        assert body["properties"]["content"] == {"headline": "H", "css": ".a{color:blue}"}
        # Properties the code does not know about travel back untouched.
        assert body["properties"]["min_page_views"] == 2
        assert body["html_mode"] == "html" and "htmlMode" not in body
        assert body["category"] == 4
        assert "id" not in body and "dateModified" not in body

        out = json.loads(result.output)
        assert out == {"id": 2, "changes": [
            {"path": "properties.content.css", "before": ".a{color:red}", "after": ".a{color:blue}"},
        ]}

    @respx.mock
    def test_edit_html_switches_html_mode_and_publish(self):
        before = {**FOCUS, "htmlMode": "basic"}
        respx.get("https://mautic.test/api/focus/2").mock(side_effect=[
            httpx.Response(200, json={"focus": before}),
            httpx.Response(200, json={"focus": _after(html="<p>New</p>", isPublished=False)}),
        ])
        patch = respx.patch("https://mautic.test/api/focus/2/edit").mock(
            return_value=httpx.Response(200, json={"focus": FOCUS})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["focus", "edit", "2", "--html", "<p>New</p>", "--unpublish"])
        assert result.exit_code == 0, result.output
        body = json.loads(patch.calls.last.request.content)
        assert body["html"] == "<p>New</p>"
        assert body["html_mode"] == "html"
        assert body["isPublished"] is False

    @respx.mock
    def test_edit_json_merges_inside_properties(self):
        respx.get("https://mautic.test/api/focus/2").mock(side_effect=[
            httpx.Response(200, json={"focus": FOCUS}),
            httpx.Response(200, json={"focus": _after(properties__timeout="6")}),
        ])
        patch = respx.patch("https://mautic.test/api/focus/2/edit").mock(
            return_value=httpx.Response(200, json={"focus": FOCUS})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["focus", "edit", "2", "--json", '{"properties": {"timeout": "6"}}'])
        assert result.exit_code == 0, result.output
        body = json.loads(patch.calls.last.request.content)
        assert body["properties"]["timeout"] == "6"
        assert body["properties"]["when"] == "immediately"
        assert body["properties"]["modal"] == {"placement": "middle"}

    @respx.mock
    def test_edit_reports_unexpected_change(self):
        respx.get("https://mautic.test/api/focus/2").mock(side_effect=[
            httpx.Response(200, json={"focus": FOCUS}),
            httpx.Response(200, json={"focus": _after(html="<div>New</div>", properties__when="leave")}),
        ])
        respx.patch("https://mautic.test/api/focus/2/edit").mock(
            return_value=httpx.Response(200, json={"focus": FOCUS})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["focus", "edit", "2", "--html", "<div>New</div>"])
        assert result.exit_code == 0
        out = json.loads(result.stdout)
        assert [c["path"] for c in out["unexpected"]] == ["properties.when"]
        assert "properties.when" in result.stderr

    @respx.mock
    def test_edit_dry_run_sends_nothing(self):
        respx.get("https://mautic.test/api/focus/2").mock(
            return_value=httpx.Response(200, json={"focus": FOCUS})
        )
        patch = respx.patch("https://mautic.test/api/focus/2/edit")
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["focus", "edit", "2", "--css", ".b{}", "--dry-run"])
        assert result.exit_code == 0
        assert not patch.called
        out = json.loads(result.output)
        assert out["dry_run"] is True
        assert out["changes"] == [{"path": "properties.content.css", "before": ".a{color:red}", "after": ".b{}"}]

    @respx.mock
    def test_edit_global_dry_run_still_reads(self):
        respx.get("https://mautic.test/api/focus/2").mock(
            return_value=httpx.Response(200, json={"focus": FOCUS})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["--dry-run", "focus", "edit", "2", "--publish"])
        assert result.exit_code == 0
        out = json.loads(result.output)
        assert out["dry_run"] is True
        assert out["changes"] == []

    @respx.mock
    def test_edit_without_changes_sends_nothing(self):
        respx.get("https://mautic.test/api/focus/2").mock(
            return_value=httpx.Response(200, json={"focus": FOCUS})
        )
        patch = respx.patch("https://mautic.test/api/focus/2/edit")
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["focus", "edit", "2", "--css", ".a{color:red}\n"])
        assert result.exit_code == 0
        assert not patch.called
        assert json.loads(result.output)["changes"] == []

    def test_edit_needs_something_to_change(self):
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["focus", "edit", "2"])
        assert result.exit_code == 2
        assert "Nothing to change" in result.output

    @respx.mock
    def test_js(self):
        respx.post("https://mautic.test/api/focus/2/js").mock(
            return_value=httpx.Response(200, json={"js": "(function(window){})(window);"})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["focus", "js", "2"])
        assert result.exit_code == 0
        assert result.output.strip() == "(function(window){})(window);"

    @respx.mock
    def test_stats_counts_each_type(self):
        totals = {"view": "120", "click": "7", "submission": "3"}

        def respond(request):
            params = dict(request.url.params)
            assert params["where[0][col]"] == "focus_id"
            assert params["where[1][col]"] == "date_added"
            assert params["where[1][expr]"] == "gte"
            assert params["limit"] == "1"
            return httpx.Response(200, json={"total": totals[params["where[2][val]"]], "stats": []})

        respx.get("https://mautic.test/api/stats/focus_stats").mock(side_effect=respond)
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["focus", "stats", "2", "--since", "2026-10-15"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {
            "focus_id": 2, "since": "2026-10-15", "until": None,
            "views": 120, "clicks": 7, "submissions": 3,
        }

    @respx.mock
    def test_delete(self):
        respx.delete("https://mautic.test/api/focus/2/delete").mock(
            return_value=httpx.Response(200, json={"focus": {"id": 2}})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["focus", "delete", "2"])
        assert result.exit_code == 0
