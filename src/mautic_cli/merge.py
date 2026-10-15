"""Read-merge-write helpers for edits that must not lose fields.

A Mautic PATCH is not partial for every field: some controllers reset what the
request leaves out (FormApiController sets postAction to "return", FormModel
renumbers the order of the fields it receives). Commands built on these helpers
read the entity, merge the user's patch into it, send a complete payload and
report what changed by diffing a GET taken before against one taken after.
"""
from __future__ import annotations

import copy
import json
import re

# Keys the server rewrites on every save; never reported as a change.
VOLATILE_KEYS = {
    "dateModified", "modifiedBy", "modifiedByUser", "cachedHtml",
    "checkedOut", "checkedOutBy", "checkedOutByUser",
}

# Keys a GET returns that an edit must not send back.
READ_ONLY_KEYS = VOLATILE_KEYS | {"id", "dateAdded", "createdBy", "createdByUser"}

_DATE_KEYS = {"publishUp", "publishDown"}
_LONG_TEXT = 120
_LARGE_OBJECT = 2000
_ITEM_PATH = re.compile(r"^(?P<list>.*)\[id=(?P<id>[^\]]+)\]")


def deep_merge(base, patch):
    """Return base with patch merged in: dicts recursively, anything else replaced."""
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = copy.deepcopy(base)
        for key, value in patch.items():
            merged[key] = deep_merge(base[key], value) if key in base else copy.deepcopy(value)
        return merged
    return copy.deepcopy(patch)


def merge_items_by_id(current: list, patch: list, what: str = "item") -> tuple[list, list, set]:
    """Merge a patch list into a list of objects keyed by "id".

    Returns the merged list in the current order, the patch items without an id
    (new items), and the ids of the items the patch touched. An id that is not
    in the current list raises ValueError.
    """
    index = {str(item["id"]): i for i, item in enumerate(current)}
    merged = copy.deepcopy(current)
    added = []
    touched = set()
    for item in patch:
        item_id = item.get("id")
        if item_id is None:
            added.append(copy.deepcopy(item))
            continue
        if str(item_id) not in index:
            raise ValueError(f"No {what} with id {item_id}.")
        position = index[str(item_id)]
        # Keep the server's id, which may be an int where the patch has "3".
        merged[position] = {**deep_merge(merged[position], item), "id": merged[position]["id"]}
        touched.add(str(item_id))
    return merged, added, touched


def editable(entity: dict, patch: dict | None = None) -> dict:
    """Turn a GET representation into something the edit endpoint accepts back.

    The publish dates go only when the patch sets them: GET returns them as
    ISO 8601, which the form rejects ("Please enter a valid date and time";
    it expects YYYY-MM-DD HH:MM), and a PATCH keeps what it is not sent.
    """
    patch = patch or {}
    payload = {
        k: copy.deepcopy(v) for k, v in entity.items()
        if k not in READ_ONLY_KEYS and (k not in _DATE_KEYS or k in patch)
    }
    # GET returns the category as an object; the API casts what it receives to int.
    if isinstance(payload.get("category"), dict):
        payload["category"] = payload["category"].get("id")
    if isinstance(payload.get("projects"), list):
        payload["projects"] = [p["id"] if isinstance(p, dict) else p for p in payload["projects"]]
    return payload


def diff(before, after, path: str = "") -> list[dict]:
    """List the paths whose values differ, as {"path", "before", "after"}.

    Lists of objects with an "id" are compared item by item, with paths like
    fields[id=3].label. Server-maintained keys at the top level are skipped,
    and an empty list equals an empty object (PHP serialises both as []).
    """
    if isinstance(before, dict) and isinstance(after, dict):
        changes = []
        for key in list(before) + [k for k in after if k not in before]:
            if not path and key in VOLATILE_KEYS:
                continue
            changes += diff(before.get(key), after.get(key), f"{path}.{key}" if path else key)
        return changes
    if _is_item_list(before) and _is_item_list(after):
        old = {_item_key(item, i): item for i, item in enumerate(before or [])}
        new = {_item_key(item, i): item for i, item in enumerate(after or [])}
        changes = []
        for key in list(old) + [k for k in new if k not in old]:
            changes += diff(old.get(key), new.get(key), f"{path}[id={key}]")
        return changes
    if _same(before, after):
        return []
    return [{"path": path, "before": shorten(before), "after": shorten(after)}]


def unexpected_changes(changes: list[dict], intended: list[dict], before: dict) -> list[dict]:
    """Return the changes that no intended change accounts for.

    An intended path covers itself and anything below it, never what is above
    it: an edit to properties.content.css does not account for properties
    being emptied. An item the server created (an id the GET before did not
    have) is covered when the patch added items to that list.
    """
    intended_paths = [c["path"] for c in intended]
    unexpected = []
    for change in changes:
        path = change["path"]
        if any(_below(p, path) for p in intended_paths):
            continue
        match = _ITEM_PATH.match(path)
        if match and _is_new_item(before, match["list"], match["id"]) and any(
            p.startswith(f"{match['list']}[id=new") for p in intended_paths
        ):
            continue
        unexpected.append(change)
    return unexpected


def not_applied(intended: list[dict], changes: list[dict], before: dict) -> list[dict]:
    """Return the intended changes the server did not make.

    An intended path counts as applied when anything changed at it, below it
    or above it, so a value the server normalises (a trimmed string, "6" for 6)
    is not reported. A new item counts as applied when the server created an
    item in that list.
    """
    changed = [c["path"] for c in changes]
    missing = []
    for change in intended:
        path = change["path"]
        if any(_below(path, c) or _below(c, path) for c in changed):
            continue
        match = _ITEM_PATH.match(path)
        if match and match["id"].startswith("new") and any(
            (m := _ITEM_PATH.match(c)) and m["list"] == match["list"] and _is_new_item(before, m["list"], m["id"])
            for c in changed
        ):
            continue
        missing.append(change)
    return missing


def shorten(value):
    """Shorten long strings and large objects so a diff of HTML, CSS or an
    option list stays readable."""
    if isinstance(value, str) and len(value) > _LONG_TEXT:
        return f"{value[:60]}... ({len(value)} chars)"
    if isinstance(value, (dict, list)) and len(json.dumps(value, ensure_ascii=False)) > _LARGE_OBJECT:
        kind = "object with" if isinstance(value, dict) else "list of"
        return f"<{kind} {len(value)} entries>"
    if isinstance(value, dict):
        return {k: shorten(v) for k, v in value.items()}
    if isinstance(value, list):
        return [shorten(v) for v in value]
    return value


def _is_item_list(value) -> bool:
    if value is None or value == []:
        return True
    return isinstance(value, list) and all(isinstance(v, dict) and "id" in v for v in value)


def _item_key(item: dict, position: int) -> str:
    item_id = item.get("id")
    return f"new{position}" if item_id is None else str(item_id)


def _same(before, after) -> bool:
    if isinstance(before, (list, dict)) and isinstance(after, (list, dict)) and not before and not after:
        return True
    return before == after


def _below(parent: str, path: str) -> bool:
    """True when path is parent itself or lies under it."""
    return path == parent or path.startswith(parent + ".") or path.startswith(parent + "[")


def _is_new_item(before: dict, list_path: str, item_id: str) -> bool:
    node = before
    for part in list_path.split("."):
        if not isinstance(node, dict):
            return False
        node = node.get(part)
    if not isinstance(node, list):
        return True
    return item_id not in {str(item.get("id")) for item in node if isinstance(item, dict)}
