from __future__ import annotations

import json as json_mod
import re

import click

from mautic_cli.context import pass_context, MauticContext
from mautic_cli.client import MauticApiError

_WHERE = re.compile(r"^(?P<col>[A-Za-z0-9_.]+)\s*(?P<op>!=|>=|<=|=|>|<)(?P<val>.*)$")
_OPERATORS = {"=": "eq", "!=": "neq", ">": "gt", ">=": "gte", "<": "lt", "<=": "lte"}


def parse_where(expression: str) -> dict:
    """Turn "column=value" (or !=, >, >=, <, <=) into a stats API where clause."""
    match = _WHERE.match(expression)
    if not match:
        raise click.BadParameter(f"Expected column=value (or !=, >, >=, <, <=), got: {expression}")
    return {"col": match["col"], "expr": _OPERATORS[match["op"]], "val": match["val"]}


def stats_params(where: list[dict], order: str | None = None) -> dict:
    """Flatten where clauses and an optional COL[:asc|desc] into query parameters."""
    params = {}
    for i, clause in enumerate(where):
        for part, value in clause.items():
            params[f"where[{i}][{part}]"] = value
    if order:
        col, _, direction = order.partition(":")
        params["order[0][col]"] = col
        params["order[0][dir]"] = (direction or "asc").upper()
    return params


def query_stats(mctx: MauticContext, table: str, params: dict) -> dict:
    """GET /stats/{table}.

    The API answers HTTP 200 both to a query error (an "errors" key) and to a
    table it does not know (the list of tables instead of rows); both raise.
    """
    data = mctx.client.get(f"/stats/{table}" if table else "/stats", params=params)
    errors = data.get("errors") if isinstance(data, dict) else None
    if errors:
        raise MauticApiError(message=errors[0].get("message", "Stats query failed"), code=400, error_type="stats_error")
    if table and "availableTables" in data:
        raise MauticApiError(message=f"Unknown stats table: {table}. Run `mautic stats` for the list.",
                             code=404, error_type="stats_error")
    return data


@click.command()
@click.argument("table", required=False)
@click.option("--where", "where", multiple=True,
              help="Filter as column=value; also !=, >, >=, <, <=. Repeat to combine with AND.")
@click.option("--order", default=None, help="Sort as COLUMN[:asc|desc]. Prefer id: sorting a large table by a date times out.")
@click.option("--limit", default=100, type=int)
@click.option("--offset", default=0, type=int, help="Starting offset.")
@pass_context
def stats(mctx: MauticContext, table, where, order, limit, offset):
    """Query a stats table (email_stats, focus_stats, page_hits...).

    Without TABLE, lists the tables and their columns.
    """
    try:
        if not table:
            mctx.output(query_stats(mctx, "", {}))
            return
        params = stats_params([parse_where(w) for w in where], order)
        if mctx.page_all and not mctx.dry_run:
            # Not client.get_all: it would read an error response as an empty page.
            step = min(limit, mctx.client.MAX_LIMIT)
            start = offset
            while True:
                data = query_stats(mctx, table, {**params, "limit": step, "start": start})
                rows = data.get("stats") or []
                for record in rows:
                    click.echo(json_mod.dumps(record, ensure_ascii=False))
                start += step
                if not rows or start >= int(data.get("total", 0)):
                    break
        else:
            mctx.output(query_stats(mctx, table, {**params, "limit": limit, "start": offset}))
    except MauticApiError as e:
        mctx.error(e)
        raise SystemExit(1)
