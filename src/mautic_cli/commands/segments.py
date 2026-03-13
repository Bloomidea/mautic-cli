from __future__ import annotations

import click

from mautic_cli.context import pass_context, MauticContext
from mautic_cli.client import MauticApiError
from mautic_cli.json_input import parse_json_input


@click.group()
def segments():
    """Manage Mautic segments."""


@segments.command("list")
@click.option("--search", default=None, help="Mautic search string.")
@click.option("--limit", default=30, type=int)
@click.option("--offset", default=0, type=int)
@pass_context
def list_segments(mctx: MauticContext, search, limit, offset):
    """List segments."""
    params = {"limit": limit, "start": offset}
    if search:
        params["search"] = search
    if mctx.published_only:
        params["search"] = ((params.get("search") or "") + " is:published").strip()
    try:
        data = mctx.client.get("/segments", params=params)
        mctx.output_list(data, "lists")
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@segments.command()
@click.argument("id", type=int)
@pass_context
def get(mctx: MauticContext, id):
    """Get a segment by ID."""
    try:
        data = mctx.client.get(f"/segments/{id}")
        mctx.output_single(data, "list")
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@segments.command()
@click.argument("id", type=int)
@click.option("--limit", default=30, type=int)
@pass_context
def contacts(mctx: MauticContext, id, limit):
    """List contacts in a segment."""
    try:
        # Fetch segment to get its alias for search
        segment_data = mctx.client.get(f"/segments/{id}")
        segment = segment_data.get("list", {})
        alias = segment.get("alias", "")
        if not alias:
            mctx.output({"total": 0, "contacts": {}})
            return
        data = mctx.client.get("/contacts", params={
            "search": f"segment:{alias}",
            "limit": limit,
        })
        mctx.output_list(data, "contacts")
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@segments.command()
@click.option("--json", "json_str", required=True, help="JSON data or @file.")
@pass_context
def create(mctx: MauticContext, json_str):
    """Create a new segment."""
    try:
        payload = parse_json_input(json_str)
        data = mctx.client.post("/segments/new", json=payload)
        mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@segments.command()
@click.argument("id", type=int)
@click.option("--json", "json_str", required=True, help="JSON data or @file.")
@pass_context
def edit(mctx: MauticContext, id, json_str):
    """Edit a segment."""
    try:
        payload = parse_json_input(json_str)
        data = mctx.client.patch(f"/segments/{id}/edit", json=payload)
        mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@segments.command()
@click.argument("id", type=int)
@pass_context
def delete(mctx: MauticContext, id):
    """Delete a segment."""
    try:
        data = mctx.client.delete(f"/segments/{id}/delete")
        mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@segments.command("add-contact")
@click.argument("segment_id", type=int)
@click.argument("contact_id", type=int)
@pass_context
def add_contact(mctx: MauticContext, segment_id, contact_id):
    """Add a contact to a segment."""
    try:
        data = mctx.client.post(f"/segments/{segment_id}/contact/{contact_id}/add")
        mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)


@segments.command("remove-contact")
@click.argument("segment_id", type=int)
@click.argument("contact_id", type=int)
@pass_context
def remove_contact(mctx: MauticContext, segment_id, contact_id):
    """Remove a contact from a segment."""
    try:
        data = mctx.client.post(f"/segments/{segment_id}/contact/{contact_id}/remove")
        mctx.output(data)
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)
