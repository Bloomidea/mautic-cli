"""The read-merge-write flow shared by the edit commands that must not lose fields."""
from __future__ import annotations

from typing import Callable

from rich.markup import escape

from mautic_cli.context import MauticContext
from mautic_cli.merge import diff, not_applied, unexpected_changes
from mautic_cli.output import get_err_console


def merge_edit(
    mctx: MauticContext,
    entity_path: str,
    key: str,
    build: Callable[[dict], tuple[dict, dict]],
    dry_run: bool = False,
) -> None:
    """Edit an entity without letting the server reset what the patch leaves out.

    build(before) returns (expected, payload): the entity as it should read
    after the edit, in the shape a GET returns, and the complete body to PATCH.

    Prints {"id", "changes"} from a GET before and a GET after the PATCH, plus
    "unexpected" when a key changed that the patch did not ask for, and
    "not_applied" when a key the patch asked for did not change. With
    dry_run (or the global --dry-run), prints the changes it would make and
    sends nothing; the GET still runs, because the diff needs it.
    """
    client = mctx.client
    before = client.fetch(entity_path)[key]
    expected, payload = build(before)
    intended = diff(before, expected)
    edit_path = f"{entity_path}/edit"

    if dry_run or mctx.dry_run:
        mctx.output({
            "dry_run": True,
            "id": before.get("id"),
            "method": "PATCH",
            "url": f"{client.api_url}{edit_path}",
            "changes": intended,
        })
        return

    if not intended:
        mctx.output({"id": before.get("id"), "changes": [], "message": "Nothing to change; no request sent."})
        return

    client.patch(edit_path, json=payload)
    after = client.get(entity_path)[key]
    changes = diff(before, after)
    result = {"id": before.get("id"), "changes": changes}
    err = get_err_console()
    unexpected = unexpected_changes(changes, intended, before)
    if unexpected:
        result["unexpected"] = unexpected
        paths = escape(", ".join(c["path"] for c in unexpected))
        err.print(f"[warning]Warning:[/warning] the server also changed {paths}, which the patch did not ask for.")
    missing = not_applied(intended, changes, before)
    if missing:
        result["not_applied"] = missing
        paths = escape(", ".join(c["path"] for c in missing))
        err.print(f"[warning]Warning:[/warning] the server did not change {paths}; check the key names.")
    mctx.output(result)
