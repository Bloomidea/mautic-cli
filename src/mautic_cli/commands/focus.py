from __future__ import annotations

import click

from mautic_cli.context import pass_context, MauticContext
from mautic_cli.client import MauticApiError
from mautic_cli.commands.stats import query_stats, stats_params
from mautic_cli.edit import merge_edit
from mautic_cli.json_input import parse_json_input, read_text_input
from mautic_cli.merge import deep_merge, editable

# focus_stats.type values (MauticFocusBundle Stat::TYPE_*), in the order they are reported.
_STAT_TYPES = (("views", "view"), ("clicks", "click"), ("submissions", "submission"))


def to_api(payload: dict) -> dict:
    """GET returns htmlMode, but the API form field is html_mode; htmlMode is silently ignored."""
    payload = dict(payload)
    mode = payload.pop("htmlMode", None)
    if mode is not None:
        payload["html_mode"] = mode
    return payload


@click.group()
def focus():
    """Manage Mautic Focus items (popups, bars, notifications)."""


@focus.command("list")
@click.option("--search", default=None, help="Mautic search string.")
@click.option("--limit", default=30, type=int)
@click.option("--offset", default=0, type=int)
@pass_context
def list_focus(mctx: MauticContext, search, limit, offset):
    """List Focus items."""
    params = {"limit": limit, "start": offset}
    if search:
        params["search"] = search
    if mctx.published_only:
        params["search"] = ((params.get("search") or "") + " is:published").strip()
    try:
        data = mctx.client.get("/focus", params=params)
        mctx.output_list(data, "focus")
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@focus.command()
@click.argument("id", type=int)
@pass_context
def get(mctx: MauticContext, id):
    """Get a Focus item by ID."""
    try:
        data = mctx.client.get(f"/focus/{id}")
        mctx.output_single(data, "focus")
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@focus.command()
@click.option("--json", "json_str", required=True, help="JSON data or @file.")
@pass_context
def create(mctx: MauticContext, json_str):
    """Create a Focus item."""
    try:
        payload = to_api(parse_json_input(json_str))
        data = mctx.client.post("/focus/new", json=payload)
        mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@focus.command()
@click.argument("id", type=int)
@click.option("--json", "json_str", default=None,
              help="JSON patch or @file, merged into the current item, also inside properties.")
@click.option("--html", default=None, help="HTML or @file. Sets html and switches htmlMode to html.")
@click.option("--css", default=None, help="CSS or @file. Sets properties.content.css.")
@click.option("--publish/--unpublish", "publish", default=None, help="Publish or unpublish the item.")
@click.option("--dry-run", "dry_run", is_flag=True, default=False,
              help="Print the changes without sending them.")
@pass_context
def edit(mctx: MauticContext, id, json_str, html, css, publish, dry_run):
    """Edit a Focus item without losing what the patch leaves out.

    Reads the item, merges the patch into it, sends the whole item and prints
    the keys that changed, from a GET before and a GET after.
    """
    patch = parse_json_input(json_str) if json_str else {}
    if not isinstance(patch, dict):
        raise click.BadParameter("The JSON patch must be an object.", param_hint="--json")
    if "html_mode" in patch:
        patch["htmlMode"] = patch.pop("html_mode")
    # Stripped like the server does, so an unchanged file sends nothing.
    if html is not None:
        patch = deep_merge(patch, {"html": read_text_input(html).strip(), "htmlMode": "html"})
    if css is not None:
        patch = deep_merge(patch, {"properties": {"content": {"css": read_text_input(css).strip()}}})
    if publish is not None:
        patch["isPublished"] = publish
    if not patch:
        raise click.UsageError("Nothing to change: pass --json, --html, --css, --publish or --unpublish.")

    def build(before: dict) -> tuple[dict, dict]:
        expected = deep_merge(before, patch)
        return expected, to_api(editable(expected, patch))

    try:
        merge_edit(mctx, f"/focus/{id}", "focus", build, dry_run)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@focus.command()
@click.argument("id", type=int)
@pass_context
def js(mctx: MauticContext, id):
    """Print the JavaScript a visitor receives, without recording a view."""
    try:
        data = mctx.client.post(f"/focus/{id}/js")
        if mctx.dry_run:
            mctx.output(data)
        else:
            click.echo(data.get("js", ""))
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@focus.command("stats")
@click.argument("id", type=int)
@click.option("--since", default=None, help="From this date, inclusive (YYYY-MM-DD or 'YYYY-MM-DD HH:MM:SS', UTC).")
@click.option("--until", default=None, help="Up to this date, exclusive.")
@pass_context
def focus_stats(mctx: MauticContext, id, since, until):
    """Count views, clicks and form submissions of a Focus item."""
    where = [{"col": "focus_id", "expr": "eq", "val": id}]
    if since:
        where.append({"col": "date_added", "expr": "gte", "val": since})
    if until:
        where.append({"col": "date_added", "expr": "lt", "val": until})
    try:
        result = {"focus_id": id, "since": since, "until": until}
        requests = []
        for label, stat_type in _STAT_TYPES:
            params = stats_params(where + [{"col": "type", "expr": "eq", "val": stat_type}])
            # limit=1: only the total is needed, and it is a count(*) on the server.
            data = query_stats(mctx, "focus_stats", {**params, "limit": 1})
            requests.append(data)
            result[label] = int(data.get("total", 0))
        mctx.output(requests if mctx.dry_run else result)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@focus.command()
@click.argument("id", type=int)
@pass_context
def delete(mctx: MauticContext, id):
    """Delete a Focus item."""
    try:
        data = mctx.client.delete(f"/focus/{id}/delete")
        mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)
