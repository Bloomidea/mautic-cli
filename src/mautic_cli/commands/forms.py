from __future__ import annotations

import json as json_mod
from urllib.parse import urlparse

import click

from mautic_cli.context import pass_context, MauticContext
from mautic_cli.client import MauticApiError
from mautic_cli.edit import merge_edit
from mautic_cli.json_input import parse_json_input
from mautic_cli.merge import deep_merge, editable, merge_items_by_id


@click.group()
def forms():
    """Manage Mautic forms."""


@forms.command("list")
@click.option("--search", default=None, help="Mautic search string.")
@click.option("--limit", default=30, type=int)
@click.option("--offset", default=0, type=int)
@pass_context
def list_forms(mctx: MauticContext, search, limit, offset):
    """List forms."""
    params = {"limit": limit, "start": offset}
    if search:
        params["search"] = search
    if mctx.published_only:
        params["search"] = ((params.get("search") or "") + " is:published").strip()
    try:
        data = mctx.client.get("/forms", params=params)
        mctx.output_list(data, "forms")
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@forms.command()
@click.argument("id", type=int)
@pass_context
def get(mctx: MauticContext, id):
    """Get a form by ID."""
    try:
        data = mctx.client.get(f"/forms/{id}")
        mctx.output_single(data, "form")
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@forms.command()
@click.argument("id", type=int)
@click.option("--limit", default=30, type=int)
@click.option("--offset", default=0, type=int, help="Starting offset.")
@pass_context
def submissions(mctx: MauticContext, id, limit, offset):
    """List form submissions."""
    try:
        if mctx.page_all:
            for record in mctx.client.get_all(
                f"/forms/{id}/submissions",
                resource_key="submissions",
                limit=limit,
                params={"start": offset},
            ):
                click.echo(json_mod.dumps(record, ensure_ascii=False))
        else:
            data = mctx.client.get(
                f"/forms/{id}/submissions",
                params={"limit": limit, "start": offset},
            )
            mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@forms.command("submission")
@click.argument("form_id", type=int)
@click.argument("submission_id", type=int)
@pass_context
def get_submission(mctx: MauticContext, form_id, submission_id):
    """Get a specific form submission by ID."""
    try:
        data = mctx.client.get(f"/forms/{form_id}/submissions/{submission_id}")
        mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@forms.command("contact-submissions")
@click.argument("form_id", type=int)
@click.argument("contact_id", type=int)
@pass_context
def contact_submissions(mctx: MauticContext, form_id, contact_id):
    """Get submissions for a specific contact on a form."""
    try:
        data = mctx.client.get(f"/forms/{form_id}/submissions/contact/{contact_id}")
        mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@forms.command()
@click.option("--json", "json_str", required=True, help="JSON data or @file.")
@pass_context
def create(mctx: MauticContext, json_str):
    """Create a new form."""
    try:
        payload = parse_json_input(json_str)
        data = mctx.client.post("/forms/new", json=payload)
        mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


def _ordered(staying: list, moved: list) -> list:
    """Put each moved item at the position its order asks for (1 = first),
    the others keeping their sequence around them."""
    result = list(staying)
    for item in sorted(moved, key=lambda m: int(m["order"])):
        result.insert(min(max(int(item["order"]) - 1, 0), len(result)), item)
    return result


def _strip_derived(properties, sent):
    """With syncList on, GET returns the option list derived from the contact field,
    keyed by label; sent back, it fails with a 500. Drop it unless the patch set it:
    the form still renders every option, from the contact field."""
    if not isinstance(properties, dict) or not properties.get("syncList"):
        return properties
    return {k: v for k, v in properties.items() if k not in ("list", "optionlist") or k in sent}


def _merge_items(current: list, patch: list, what: str, mapped: bool) -> tuple[list, list]:
    """Merge patched fields or actions into the current ones.

    Returns the expected list, in the shape a GET returns, and the list to send:
    every item by id in the new order (the server renumbers the order of the
    items it receives by their position), only the patched keys of a patched
    item, and the contact mapping of every mapped field, which the server
    otherwise drops.
    """
    current = sorted(current, key=lambda item: (item.get("order") or 0, item["id"]))
    merged, added, _ = merge_items_by_id(current, patch, what)
    patch_by_id = {str(p["id"]): p for p in patch if p.get("id") is not None}
    new_items = [{**item, "id": None} for item in added]
    # An item moves when the patch gives it an order; a new item without one goes last.
    moves = [m for m in merged if "order" in patch_by_id.get(str(m["id"]), {})]
    moves += [n for n in new_items if n.get("order") is not None]
    staying = [item for item in merged + new_items if not any(item is m for m in moves)]
    expected = _ordered(staying, moves)

    payload = []
    counter = 1
    for item in expected:
        if item["id"] is None:
            entry = {k: v for k, v in item.items() if k not in ("id", "order")}
        else:
            sent = patch_by_id.get(str(item["id"]), {})
            entry = {"id": item["id"]}
            for key in sent:
                if key not in ("id", "order"):
                    entry[key] = item[key]
            if "properties" in entry:
                item["properties"] = _strip_derived(item["properties"], sent.get("properties") or {})
                entry["properties"] = item["properties"]
            if mapped and item.get("mappedField"):
                entry["mappedObject"] = item.get("mappedObject")
                entry["mappedField"] = item.get("mappedField")
        payload.append(entry)
        # Mirror FormModel::setFields(): a child field takes the counter without advancing it.
        item["order"] = counter
        if not item.get("parent"):
            counter += 1
    return expected, payload


def build_form_edit(before: dict, patch: dict) -> tuple[dict, dict]:
    """Expected form and PATCH body for a merging forms edit.

    Fields and actions the request leaves out stay as they are, so they are
    sent only when the patch has them, and then all of them.
    """
    top = {k: v for k, v in patch.items() if k not in ("fields", "actions")}
    expected = deep_merge(before, top)
    payload = editable(expected, top)
    payload.pop("fields", None)
    payload.pop("actions", None)
    if patch.get("fields"):
        expected["fields"], payload["fields"] = _merge_items(
            before.get("fields") or [], patch["fields"], "field", mapped=True
        )
    if patch.get("actions"):
        expected["actions"], payload["actions"] = _merge_items(
            before.get("actions") or [], patch["actions"], "action", mapped=False
        )
    return expected, payload


@forms.command()
@click.argument("id", type=int)
@click.option("--json", "json_str", required=True,
              help="JSON patch or @file, merged into the current form. Fields and actions match by id; "
                   "one without an id is added.")
@click.option("--dry-run", "dry_run", is_flag=True, default=False,
              help="Print the changes without sending them.")
@pass_context
def edit(mctx: MauticContext, id, json_str, dry_run):
    """Edit a form without losing what the patch leaves out.

    Keeps postAction and postActionProperty, the field order and the contact
    mapping of every field, which a plain PATCH resets. Prints the keys that
    changed, from a GET before and a GET after.
    """
    patch = parse_json_input(json_str)
    if not isinstance(patch, dict):
        raise click.BadParameter("The JSON patch must be an object.", param_hint="--json")

    def build(before: dict) -> tuple[dict, dict]:
        try:
            return build_form_edit(before, patch)
        except ValueError as e:
            raise click.BadParameter(str(e), param_hint="--json")

    try:
        merge_edit(mctx, f"/forms/{id}", "form", build, dry_run)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@forms.group("fields")
def form_fields():
    """Manage the fields of a form."""


@form_fields.command("delete")
@click.argument("form_id", type=int)
@click.argument("field_ids", nargs=-1, required=True, type=int)
@pass_context
def delete_fields(mctx: MauticContext, form_id, field_ids):
    """Delete fields from a form by field ID."""
    try:
        data = mctx.client.delete(f"/forms/{form_id}/fields/delete", params={"fields[]": list(field_ids)})
        mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@forms.command()
@click.argument("id", type=int)
@click.option("--type", "embed_type", default=None, type=click.Choice(["js", "iframe", "html"]),
              help="Embed type: js (script tag), iframe, or html (raw cachedHtml). Omit to show all.")
@pass_context
def embed(mctx: MauticContext, id, embed_type):
    """Get form embed code."""
    base = mctx.client.base_url.rstrip("/")
    parsed = urlparse(base)
    host = parsed.hostname
    if parsed.port and parsed.port not in (80, 443):
        host = f"{host}:{parsed.port}"

    js_code = f'<script type="text/javascript" src="//{host}/form/generate.js?id={id}"></script>'
    iframe_code = (f'<iframe src="//{host}/form/{id}" width="300" height="300">'
                   f"<p>Your browser does not support iframes.</p></iframe>")

    if embed_type == "js":
        click.echo(js_code)
    elif embed_type == "iframe":
        click.echo(iframe_code)
    elif embed_type == "html":
        try:
            data = mctx.client.get(f"/forms/{id}")
            form = data.get("form", data)
            click.echo(form.get("cachedHtml", ""))
        except MauticApiError as e:
            mctx.error(e)
            raise SystemExit(1)
    else:
        click.echo("Via Javascript (recommended)")
        click.echo(js_code)
        click.echo()
        click.echo("Via iframe")
        click.echo(iframe_code)


@forms.command()
@click.argument("id", type=int)
@pass_context
def delete(mctx: MauticContext, id):
    """Delete a form."""
    try:
        data = mctx.client.delete(f"/forms/{id}/delete")
        mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)
