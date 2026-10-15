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

NEWSLETTER = {
    "id": 5,
    "name": "Newsletter PT",
    "alias": "newsletter",
    "formType": "standalone",
    "postAction": "redirect",
    "postActionProperty": "https://example.test/thanks",
    "isPublished": True,
    "category": None,
    "dateModified": "2026-10-15T08:52:00+00:00",
    "cachedHtml": "<form></form>",
    "fields": [
        {"id": 4, "label": "Subscribe", "alias": "subscribe", "type": "button", "order": 3,
         "parent": None, "properties": [], "mappedObject": None, "mappedField": None},
        {"id": 3, "label": "Email", "alias": "email", "type": "email", "order": 1,
         "parent": None, "properties": [], "mappedObject": "contact", "mappedField": "email"},
        {"id": 7, "label": "Birthday", "alias": "birthday", "type": "date", "order": 2,
         "parent": None, "properties": [], "mappedObject": "contact", "mappedField": "birthday"},
    ],
    "actions": [
        {"id": 11, "name": "Points", "type": "lead.pointschange", "order": 1,
         "properties": {"operator": "plus", "points": 5}},
        {"id": 12, "name": "More points", "type": "lead.pointschange", "order": 2,
         "properties": {"operator": "plus", "points": 7}},
    ],
}


def _form_with(fields=None, **top):
    """NEWSLETTER with some field keys and top-level keys replaced."""
    form = copy.deepcopy(NEWSLETTER)
    form.update(top)
    for field in form["fields"]:
        field.update((fields or {}).get(field["id"], {}))
    return form


class TestForms:
    @respx.mock
    def test_list_forms(self):
        respx.get("https://mautic.test/api/forms").mock(
            return_value=httpx.Response(200, json={
                "total": "1",
                "forms": {"1": {"id": 1, "name": "Contact Form"}},
            })
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] == "1"

    @respx.mock
    def test_get_form(self):
        respx.get("https://mautic.test/api/forms/1").mock(
            return_value=httpx.Response(200, json={
                "form": {"id": 1, "name": "Contact Form"},
            })
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "get", "1"])
        assert result.exit_code == 0

    @respx.mock
    def test_form_submissions(self):
        respx.get("https://mautic.test/api/forms/1/submissions").mock(
            return_value=httpx.Response(200, json={
                "total": "2",
                "submissions": {"10": {"id": 10}, "11": {"id": 11}},
            })
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "submissions", "1"])
        assert result.exit_code == 0

    @respx.mock
    def test_create_form(self):
        respx.post("https://mautic.test/api/forms/new").mock(
            return_value=httpx.Response(200, json={
                "form": {"id": 5, "name": "New Form"},
            })
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, [
            "forms", "create",
            "--json", '{"name": "New Form", "formType": "standalone", "postAction": "message", "postActionProperty": "Thanks!"}'
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["form"]["name"] == "New Form"

    @respx.mock
    def test_edit_form(self):
        respx.get("https://mautic.test/api/forms/5").mock(side_effect=[
            httpx.Response(200, json={"form": NEWSLETTER}),
            httpx.Response(200, json={"form": {**NEWSLETTER, "name": "Updated Form"}}),
        ])
        patch = respx.patch("https://mautic.test/api/forms/5/edit").mock(
            return_value=httpx.Response(200, json={"form": NEWSLETTER})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, [
            "forms", "edit", "5",
            "--json", '{"name": "Updated Form"}'
        ])
        assert result.exit_code == 0
        body = json.loads(patch.calls.last.request.content)
        assert body["name"] == "Updated Form"
        assert body["postAction"] == "redirect"
        # Fields and actions the patch leaves out are not sent, so nothing renumbers them.
        assert "fields" not in body and "actions" not in body
        assert json.loads(result.output) == {"id": 5, "changes": [
            {"path": "name", "before": "Newsletter PT", "after": "Updated Form"},
        ]}

    @respx.mock
    def test_edit_field_label_keeps_post_action_order_and_mapping(self):
        after = _form_with(fields={3: {"label": "Your email"}})
        respx.get("https://mautic.test/api/forms/5").mock(side_effect=[
            httpx.Response(200, json={"form": NEWSLETTER}),
            httpx.Response(200, json={"form": after}),
        ])
        patch = respx.patch("https://mautic.test/api/forms/5/edit").mock(
            return_value=httpx.Response(200, json={"form": after})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, [
            "forms", "edit", "5", "--json", '{"fields": [{"id": 3, "label": "Your email"}]}'
        ])
        assert result.exit_code == 0, result.output
        body = json.loads(patch.calls.last.request.content)
        assert body["postAction"] == "redirect"
        assert body["postActionProperty"] == "https://example.test/thanks"
        # Every field by id, in the current order, with the mapping of the mapped ones.
        assert body["fields"] == [
            {"id": 3, "label": "Your email", "mappedObject": "contact", "mappedField": "email"},
            {"id": 7, "mappedObject": "contact", "mappedField": "birthday"},
            {"id": 4},
        ]
        assert json.loads(result.output)["changes"] == [
            {"path": "fields[id=3].label", "before": "Email", "after": "Your email"},
        ]

    @respx.mock
    def test_edit_reports_post_action_reset(self):
        after = _form_with(fields={3: {"label": "Your email"}}, postAction="return")
        respx.get("https://mautic.test/api/forms/5").mock(side_effect=[
            httpx.Response(200, json={"form": NEWSLETTER}),
            httpx.Response(200, json={"form": after}),
        ])
        respx.patch("https://mautic.test/api/forms/5/edit").mock(
            return_value=httpx.Response(200, json={"form": after})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, [
            "forms", "edit", "5", "--json", '{"fields": [{"id": 3, "label": "Your email"}]}'
        ])
        assert result.exit_code == 0
        out = json.loads(result.stdout)
        assert out["unexpected"] == [{"path": "postAction", "before": "redirect", "after": "return"}]

    @respx.mock
    def test_edit_moves_and_adds_fields(self):
        respx.get("https://mautic.test/api/forms/5").mock(
            return_value=httpx.Response(200, json={"form": NEWSLETTER})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, [
            "forms", "edit", "5", "--dry-run", "--json",
            '{"fields": [{"id": 7, "order": 1}, {"label": "Phone", "type": "tel", "order": 3}]}'
        ])
        assert result.exit_code == 0, result.output
        # Birthday first, Phone before the button: the server renumbers by position.
        paths = [(c["path"], c["after"] if "order" in c["path"] else None)
                 for c in json.loads(result.output)["changes"]]
        assert paths == [
            ("fields[id=4].order", 4),
            ("fields[id=3].order", 2),
            ("fields[id=7].order", 1),
            ("fields[id=new2]", None),
        ]

    @respx.mock
    def test_edit_moves_a_field_down_and_to_the_end(self):
        respx.get("https://mautic.test/api/forms/5").mock(
            return_value=httpx.Response(200, json={"form": NEWSLETTER})
        )
        runner = CliRunner(env=MOCK_ENV)
        # Current order: Email (3), Birthday (7), Subscribe (4).
        for order, expected in ((2, [7, 3, 4]), (3, [7, 4, 3])):
            result = runner.invoke(cli, [
                "forms", "edit", "5", "--dry-run", "--json", f'{{"fields": [{{"id": 3, "order": {order}}}]}}'
            ])
            assert result.exit_code == 0, result.output
            orders = {c["path"]: c["after"] for c in json.loads(result.output)["changes"]}
            new_orders = {3: orders.get("fields[id=3].order", 1), 7: orders.get("fields[id=7].order", 2),
                          4: orders.get("fields[id=4].order", 3)}
            assert sorted(new_orders, key=new_orders.get) == expected

    @respx.mock
    def test_edit_does_not_send_publish_dates_back(self):
        form = {**NEWSLETTER, "publishUp": "2026-10-20T09:00:00+00:00"}
        respx.get("https://mautic.test/api/forms/5").mock(side_effect=[
            httpx.Response(200, json={"form": form}),
            httpx.Response(200, json={"form": {**form, "name": "Renamed"}}),
        ])
        patch = respx.patch("https://mautic.test/api/forms/5/edit").mock(
            return_value=httpx.Response(200, json={"form": form})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "edit", "5", "--json", '{"name": "Renamed"}'])
        assert result.exit_code == 0, result.output
        assert "publishUp" not in json.loads(patch.calls.last.request.content)

    @respx.mock
    def test_edit_reports_a_key_the_server_ignored(self):
        respx.get("https://mautic.test/api/forms/5").mock(side_effect=[
            httpx.Response(200, json={"form": NEWSLETTER}),
            httpx.Response(200, json={"form": NEWSLETTER}),
        ])
        respx.patch("https://mautic.test/api/forms/5/edit").mock(
            return_value=httpx.Response(200, json={"form": NEWSLETTER})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "edit", "5", "--json", '{"fields": [{"id": 3, "lable": "Typo"}]}'])
        assert result.exit_code == 0
        out = json.loads(result.stdout)
        assert out["changes"] == []
        assert [c["path"] for c in out["not_applied"]] == ["fields[id=3].lable"]
        assert "did not change" in result.stderr

    @respx.mock
    def test_edit_sends_new_fields_in_place(self):
        respx.get("https://mautic.test/api/forms/5").mock(side_effect=[
            httpx.Response(200, json={"form": NEWSLETTER}),
            httpx.Response(200, json={"form": NEWSLETTER}),
        ])
        patch = respx.patch("https://mautic.test/api/forms/5/edit").mock(
            return_value=httpx.Response(200, json={"form": NEWSLETTER})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, [
            "forms", "edit", "5", "--json", '{"fields": [{"label": "Phone", "type": "tel", "order": 3}]}'
        ])
        assert result.exit_code == 0, result.output
        body = json.loads(patch.calls.last.request.content)
        assert [f.get("id", f.get("label")) for f in body["fields"]] == [3, 7, "Phone", 4]

    @respx.mock
    def test_edit_strips_derived_sync_list_options(self):
        derived = {"syncList": True, "optionlist": {"list": {"Portuguese": "pt_PT", "English": "en"}}}
        form = _form_with(fields={7: {"type": "radiogrp", "properties": derived}})
        respx.get("https://mautic.test/api/forms/5").mock(side_effect=[
            httpx.Response(200, json={"form": form}),
            httpx.Response(200, json={"form": form}),
        ])
        patch = respx.patch("https://mautic.test/api/forms/5/edit").mock(
            return_value=httpx.Response(200, json={"form": form})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, [
            "forms", "edit", "5", "--json", '{"fields": [{"id": 7, "properties": {"helpMessage": "x"}}]}'
        ])
        assert result.exit_code == 0, result.output
        sent = json.loads(patch.calls.last.request.content)["fields"][1]
        assert sent["properties"] == {"syncList": True, "helpMessage": "x"}

    @respx.mock
    def test_edit_actions_only_when_patched_all_by_id(self):
        respx.get("https://mautic.test/api/forms/5").mock(side_effect=[
            httpx.Response(200, json={"form": NEWSLETTER}),
            httpx.Response(200, json={"form": NEWSLETTER}),
        ])
        patch = respx.patch("https://mautic.test/api/forms/5/edit").mock(
            return_value=httpx.Response(200, json={"form": NEWSLETTER})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, [
            "forms", "edit", "5", "--json", '{"actions": [{"id": 12, "properties": {"points": 9}}]}'
        ])
        assert result.exit_code == 0, result.output
        body = json.loads(patch.calls.last.request.content)
        assert "fields" not in body
        assert body["actions"] == [
            {"id": 11},
            {"id": 12, "properties": {"operator": "plus", "points": 9}},
        ]

    @respx.mock
    def test_edit_unknown_field_id(self):
        respx.get("https://mautic.test/api/forms/5").mock(
            return_value=httpx.Response(200, json={"form": NEWSLETTER})
        )
        patch = respx.patch("https://mautic.test/api/forms/5/edit")
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "edit", "5", "--json", '{"fields": [{"id": 99, "label": "x"}]}'])
        assert result.exit_code == 2
        assert "No field with id 99" in result.output
        assert not patch.called

    @respx.mock
    def test_delete_fields(self):
        route = respx.delete("https://mautic.test/api/forms/5/fields/delete").mock(
            return_value=httpx.Response(200, json={"form": {"id": 5}})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "fields", "delete", "5", "7", "4"])
        assert result.exit_code == 0
        assert route.calls.last.request.url.query == b"fields%5B%5D=7&fields%5B%5D=4"

    def test_embed_default(self):
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "embed", "4"])
        assert result.exit_code == 0
        assert "Via Javascript (recommended)" in result.output
        assert "Via iframe" in result.output
        assert "generate.js?id=4" in result.output
        assert 'src="//mautic.test/form/4"' in result.output

    def test_embed_js(self):
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "embed", "4", "--type", "js"])
        assert result.exit_code == 0
        assert result.output.strip() == '<script type="text/javascript" src="//mautic.test/form/generate.js?id=4"></script>'

    def test_embed_iframe(self):
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "embed", "4", "--type", "iframe"])
        assert result.exit_code == 0
        assert 'src="//mautic.test/form/4"' in result.output

    @respx.mock
    def test_embed_html(self):
        respx.get("https://mautic.test/api/forms/4").mock(
            return_value=httpx.Response(200, json={
                "form": {"id": 4, "name": "Test", "cachedHtml": "<div>form html</div>"},
            })
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "embed", "4", "--type", "html"])
        assert result.exit_code == 0
        assert result.output.strip() == "<div>form html</div>"

    @respx.mock
    def test_form_submissions_with_offset(self):
        respx.get("https://mautic.test/api/forms/1/submissions").mock(
            return_value=httpx.Response(200, json={
                "total": "5",
                "submissions": {"12": {"id": 12}},
            })
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "submissions", "1", "--offset", "3", "--limit", "2"])
        assert result.exit_code == 0

    @respx.mock
    def test_form_submissions_page_all(self):
        route = respx.get("https://mautic.test/api/forms/1/submissions")
        route.side_effect = [
            httpx.Response(200, json={
                "total": "3",
                "submissions": {"10": {"id": 10}, "11": {"id": 11}},
            }),
            httpx.Response(200, json={
                "total": "3",
                "submissions": {"12": {"id": 12}},
            }),
        ]
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["--page-all", "forms", "submissions", "1", "--limit", "2"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0])["id"] == 10
        assert json.loads(lines[2])["id"] == 12

    @respx.mock
    def test_get_submission(self):
        respx.get("https://mautic.test/api/forms/1/submissions/10").mock(
            return_value=httpx.Response(200, json={
                "submission": {"id": 10, "form": {"id": 1}},
            })
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "submission", "1", "10"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["submission"]["id"] == 10

    @respx.mock
    def test_contact_submissions(self):
        respx.get("https://mautic.test/api/forms/1/submissions/contact/5").mock(
            return_value=httpx.Response(200, json={
                "total": "1",
                "submissions": {"10": {"id": 10, "lead": {"id": 5}}},
            })
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "contact-submissions", "1", "5"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] == "1"

    @respx.mock
    def test_delete_form(self):
        respx.delete("https://mautic.test/api/forms/1/delete").mock(
            return_value=httpx.Response(200, json={"form": {"id": 1}})
        )
        runner = CliRunner(env=MOCK_ENV)
        result = runner.invoke(cli, ["forms", "delete", "1"])
        assert result.exit_code == 0
