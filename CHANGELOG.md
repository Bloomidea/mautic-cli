# Changelog

## [0.2.0] - 2026-10-15

### Added

- `focus` commands: `list`, `get`, `create`, `edit`, `delete`, `js` (the script a visitor receives, without recording a view) and `stats` (views, clicks and form submissions, with `--since`/`--until`)
- `focus edit` shortcuts: `--html`, `--css` (sets `properties.content.css`), `--publish`/`--unpublish`
- `stats [TABLE]` - query any stats table (`email_stats`, `focus_stats`, `page_hits`...) with `--where column=value` (also `!=`, `>`, `>=`, `<`, `<=`), `--order` and `--page-all`
- `forms fields delete <FORM_ID> <FIELD_ID>...`
- `--dry-run` on `forms edit` and `focus edit`: prints the changes and sends nothing

### Changed

- `forms edit` no longer sends the JSON as a bare PATCH, which made Mautic reset `postAction` to `return` and renumber the fields in the request. It reads the form, merges the patch (fields and actions by `id`), sends a complete payload with every field in order and its contact mapping, and prints `{"id", "changes"}` from a GET before and a GET after, plus `unexpected` when the server changed a key the patch did not ask for and `not_applied` when a key the patch asked for did not change. `order` on a field moves it to that position. The output used to be the API response.
- `focus create` and `focus edit` send `htmlMode` as `html_mode`, the only name the API accepts.

---

## [0.1.5] - 2026-03-17

### Added

- `forms submission <FORM_ID> <SUBMISSION_ID>` - get a specific form submission by ID
- `forms contact-submissions <FORM_ID> <CONTACT_ID>` - get submissions for a contact on a form
- `forms submissions` now supports `--offset` for manual pagination and `--page-all` for auto-pagination

---

## [0.1.3] - 2026-03-13

### Changed

- New CLI banner (slant font, cleaner look)
- Added hero screenshot to README

---

## [0.1.2] - 2026-03-13

### Fixed

- CLI banner now shows updated tagline
- Version is now derived from pyproject.toml (single source of truth)

---

## [0.1.1] - 2026-03-13

### Fixed

- Empty/non-JSON API response handling (Mautic 6.x 401 responses)
- Shell completion instruction concatenation with rc file
- Segments contacts endpoint path

### Added

- Phase 2 resources: forms, companies, notes, stages, assets, tags, categories, pages, webhooks, fields, reports, points
- GitHub Actions CI (tests on Python 3.11/3.12/3.13) and PyPI trusted publishing

---

## [0.1.0] - 2026-03-12

### Initial Release

- **17 resource groups**: contacts, segments, emails, campaigns, forms, companies,
  notes, stages, assets, tags, categories, pages, webhooks, fields, reports, points
- **65 commands** covering list, get, create, edit, delete, and resource-specific actions
- **Output formats**: JSON (default), table (Rich), CSV, NDJSON (auto-paginating)
- **Auth**: Basic Auth and OAuth2 Client Credentials with named profiles
- **Global flags**: --format, --page-all, --published-only, --dry-run, --verbose, --no-verify-ssl
- **AI agent skill**: installable via `npx skills add bloomidea/mautic-cli`
- Mautic 4.x through 7.x supported
