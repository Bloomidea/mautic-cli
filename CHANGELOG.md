# Changelog

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
