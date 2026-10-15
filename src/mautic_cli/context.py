from __future__ import annotations

import click

from mautic_cli.client import MauticApiError
from mautic_cli.output import format_output, print_table, get_err_console


class MauticContext:
    """Shared context passed to all commands."""

    def __init__(self):
        self.client = None  # MauticClient, set by cli.py
        self.fmt: str = "json"
        self.pretty: bool = False
        self.dry_run: bool = False
        self.page_all: bool = False
        self.published_only: bool = False
        self.verify_ssl: bool = True

    def output(self, data) -> None:
        result = format_output(data, fmt=self.fmt, pretty=self.pretty)
        click.echo(result)

    def output_list(self, data: dict, resource_key: str) -> None:
        """Output a Mautic list response, extracting records for table/csv."""
        if self.fmt in ("table", "csv"):
            items = data.get(resource_key, {})
            if isinstance(items, dict):
                records = list(items.values())
            else:
                records = list(items)
            flat = [_flatten_record(r, resource_key) for r in records]

            if self.fmt == "table":
                total = data.get("total")
                title = None
                if total is not None:
                    total = int(total)
                    shown = len(records)
                    if total > shown:
                        title = f"Showing {shown:,} of {total:,}"
                print_table(flat, title=title)
            else:
                click.echo(format_output(flat, fmt=self.fmt, pretty=self.pretty))
        else:
            self.output(data)

    def output_single(self, data: dict, resource_key: str) -> None:
        """Output a single Mautic record, flattening for table/csv."""
        if self.fmt in ("table", "csv"):
            record = data.get(resource_key, data)
            flat = _flatten_record(record, _SINGULAR_TO_PLURAL.get(resource_key, resource_key))
            if self.fmt == "table":
                print_table(flat)
            else:
                click.echo(format_output(flat, fmt=self.fmt, pretty=self.pretty))
        else:
            self.output(data)

    def error(self, err: MauticApiError) -> None:
        click.echo(format_output(err.to_dict(), fmt="json", pretty=self.pretty), err=True)


# Field sets for table/csv display per resource type (plural keys)
_TABLE_FIELDS = {
    "contacts": ["id", "firstname", "lastname", "email", "points", "dateAdded"],
    "lists": ["id", "name", "alias", "isPublished", "isGlobal"],
    "emails": ["id", "name", "subject", "emailType", "isPublished", "readCount"],
    "campaigns": ["id", "name", "isPublished", "dateAdded"],
    "forms": ["id", "name", "alias", "isPublished", "dateAdded"],
    "companies": ["id", "companyname", "companyemail", "companycity", "companywebsite"],
    "notes": ["id", "text", "type", "dateTime"],
    "stages": ["id", "name", "weight", "isPublished"],
    "assets": ["id", "title", "alias", "downloadCount", "isPublished"],
    "tags": ["id", "tag"],
    "categories": ["id", "title", "alias", "bundle", "color"],
    "pages": ["id", "title", "alias", "isPublished", "hits"],
    "hooks": ["id", "name", "webhookUrl", "isPublished"],
    "fields": ["id", "label", "alias", "type", "group"],
    "reports": ["id", "name", "system", "source"],
    "points": ["id", "name", "type", "delta", "isPublished"],
    "triggers": ["id", "name", "points", "isPublished"],
    "focus": ["id", "name", "type", "style", "isPublished"],
}

# Map singular API response keys to plural resource keys
_SINGULAR_TO_PLURAL = {
    "contact": "contacts",
    "list": "lists",
    "email": "emails",
    "campaign": "campaigns",
    "form": "forms",
    "company": "companies",
    "note": "notes",
    "stage": "stages",
    "asset": "assets",
    "tag": "tags",
    "category": "categories",
    "page": "pages",
    "hook": "hooks",
    "field": "fields",
    "report": "reports",
    "point": "points",
    "trigger": "triggers",
    "focus": "focus",
}


def _flatten_record(record: dict, resource_key: str) -> dict:
    """Extract key fields from a Mautic record for table/csv display."""
    fields = _TABLE_FIELDS.get(resource_key)
    if not fields:
        return record

    flat = {}
    for f in fields:
        if f in record:
            flat[f] = record[f]
        # Contacts and companies store most fields nested under fields.all
        elif resource_key in ("contacts", "companies") and "fields" in record:
            all_fields = record["fields"].get("all", {})
            flat[f] = all_fields.get(f, "")
        else:
            flat[f] = ""
    return flat


pass_context = click.make_pass_decorator(MauticContext, ensure=True)
