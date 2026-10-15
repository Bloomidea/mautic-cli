import pytest

from mautic_cli.merge import (
    deep_merge,
    diff,
    editable,
    merge_items_by_id,
    not_applied,
    shorten,
    unexpected_changes,
)


class TestDeepMerge:
    def test_merges_nested_objects(self):
        base = {"name": "A", "properties": {"content": {"css": "a", "headline": "H"}, "when": "leave"}}
        merged = deep_merge(base, {"properties": {"content": {"css": "b"}}})
        assert merged == {"name": "A", "properties": {"content": {"css": "b", "headline": "H"}, "when": "leave"}}

    def test_does_not_mutate_inputs(self):
        base = {"properties": {"content": {"css": "a"}}}
        patch = {"properties": {"content": {"css": "b"}}}
        deep_merge(base, patch)
        assert base["properties"]["content"]["css"] == "a"

    def test_replaces_lists_and_empty_php_arrays(self):
        # PHP serialises an empty object as [], so a patch object must replace it.
        merged = deep_merge({"page": [], "tags": [1, 2]}, {"page": {"placement": "top"}, "tags": [3]})
        assert merged == {"page": {"placement": "top"}, "tags": [3]}


class TestMergeItemsById:
    def test_merges_by_id_and_keeps_order(self):
        current = [{"id": 1, "label": "Email"}, {"id": 2, "label": "Name"}]
        merged, added, touched = merge_items_by_id(current, [{"id": "2", "label": "Your name"}])
        assert merged == [{"id": 1, "label": "Email"}, {"id": 2, "label": "Your name"}]
        assert added == []
        assert touched == {"2"}

    def test_items_without_id_are_new(self):
        merged, added, _ = merge_items_by_id([{"id": 1}], [{"label": "Phone"}])
        assert merged == [{"id": 1}]
        assert added == [{"label": "Phone"}]

    def test_unknown_id_raises(self):
        with pytest.raises(ValueError, match="No field with id 9"):
            merge_items_by_id([{"id": 1}], [{"id": 9}], "field")


class TestEditable:
    def test_drops_read_only_keys(self):
        payload = editable({"id": 3, "name": "F", "dateAdded": "x", "dateModified": "y",
                            "createdBy": 1, "modifiedByUser": "Admin", "cachedHtml": "<form>"})
        assert payload == {"name": "F"}

    def test_category_and_projects_become_ids(self):
        payload = editable({"category": {"id": 7, "title": "Popups"}, "projects": [{"id": 2, "name": "P"}]})
        assert payload == {"category": 7, "projects": [2]}

    def test_null_category_stays_null(self):
        assert editable({"category": None}) == {"category": None}

    def test_publish_dates_only_when_patched(self):
        # GET returns ISO 8601, which the edit form rejects with a 400.
        entity = {"name": "F", "publishUp": "2026-10-20T09:00:00+00:00", "publishDown": None}
        assert editable(entity) == {"name": "F"}
        patch = {"publishUp": "2026-10-21 09:00"}
        assert editable({**entity, **patch}, patch) == {"name": "F", "publishUp": "2026-10-21 09:00"}


class TestDiff:
    def test_nested_paths(self):
        before = {"properties": {"content": {"css": "a"}}, "name": "A"}
        after = {"properties": {"content": {"css": "b"}}, "name": "A"}
        assert diff(before, after) == [{"path": "properties.content.css", "before": "a", "after": "b"}]

    def test_skips_server_maintained_keys(self):
        assert diff({"dateModified": "1", "cachedHtml": "a"}, {"dateModified": "2", "cachedHtml": "b"}) == []

    def test_items_compared_by_id(self):
        before = {"fields": [{"id": 1, "label": "A", "order": 1}, {"id": 2, "label": "B", "order": 2}]}
        after = {"fields": [{"id": 2, "label": "B", "order": 1}, {"id": 1, "label": "A", "order": 2}]}
        assert [c["path"] for c in diff(before, after)] == ["fields[id=1].order", "fields[id=2].order"]

    def test_added_and_removed_items(self):
        before = {"fields": [{"id": 1}]}
        after = {"fields": [{"id": 2}]}
        assert diff(before, after) == [
            {"path": "fields[id=1]", "before": {"id": 1}, "after": None},
            {"path": "fields[id=2]", "before": None, "after": {"id": 2}},
        ]

    def test_empty_list_equals_empty_object(self):
        assert diff({"properties": []}, {"properties": {}}) == []

    def test_long_values_are_shortened(self):
        change = diff({"html": "a" * 500}, {"html": "b"})[0]
        assert change["before"].endswith("(500 chars)")


class TestUnexpectedChanges:
    def test_change_outside_the_patch_is_unexpected(self):
        changes = [
            {"path": "fields[id=2].label", "before": "A", "after": "B"},
            {"path": "postAction", "before": "redirect", "after": "return"},
        ]
        intended = [{"path": "fields[id=2].label", "before": "A", "after": "B"}]
        assert [c["path"] for c in unexpected_changes(changes, intended, {})] == ["postAction"]

    def test_intended_path_covers_what_is_below_it(self):
        changes = [{"path": "properties.content.css"}, {"path": "fields[id=2].label"}]
        intended = [{"path": "properties.content"}, {"path": "fields[id=2]"}]
        assert unexpected_changes(changes, intended, {}) == []

    def test_wiped_container_is_unexpected(self):
        # Editing the CSS does not account for the server emptying all of properties.
        changes = [{"path": "properties"}, {"path": "fields[id=3]"}]
        intended = [{"path": "properties.content.css"}, {"path": "fields[id=3].label"}]
        assert unexpected_changes(changes, intended, {"fields": [{"id": 3}]}) == changes

    def test_similar_ids_do_not_cover_each_other(self):
        assert unexpected_changes([{"path": "fields[id=20].label"}], [{"path": "fields[id=2]"}], {}) != []

    def test_new_item_is_expected_when_the_patch_adds_one(self):
        before = {"fields": [{"id": 1}]}
        changes = [{"path": "fields[id=9]"}]
        assert unexpected_changes(changes, [{"path": "fields[id=new1]"}], before) == []
        assert unexpected_changes(changes, [], before) == changes


class TestNotApplied:
    def test_ignored_key_is_reported(self):
        intended = [{"path": "fields[id=3].lable", "before": None, "after": "X"},
                    {"path": "name", "before": "A", "after": "B"}]
        changes = [{"path": "name", "before": "A", "after": "B"}]
        assert [c["path"] for c in not_applied(intended, changes, {})] == ["fields[id=3].lable"]

    def test_normalised_value_counts_as_applied(self):
        intended = [{"path": "properties.timeout", "before": "4", "after": 6}]
        changes = [{"path": "properties.timeout", "before": "4", "after": "6"}]
        assert not_applied(intended, changes, {}) == []

    def test_new_item_counts_as_applied_when_the_server_created_one(self):
        before = {"fields": [{"id": 1}]}
        intended = [{"path": "fields[id=new1]"}]
        assert not_applied(intended, [{"path": "fields[id=9]"}], before) == []
        assert not_applied(intended, [], before) == intended


class TestShorten:
    def test_large_objects_are_summarised(self):
        options = {f"Language {i}": f"l{i}" for i in range(300)}
        assert shorten({"list": options}) == "<object with 1 entries>"

    def test_small_values_unchanged(self):
        assert shorten({"a": "b", "c": [1, 2]}) == {"a": "b", "c": [1, 2]}
