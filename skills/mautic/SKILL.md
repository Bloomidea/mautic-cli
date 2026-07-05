---
name: mautic
description: >-
  Mautic marketing automation: manage contacts, segments, emails, campaigns,
  forms, companies, notes, stages, assets, tags, categories, pages, webhooks,
  fields, reports, and points. Use when the user asks to "list contacts",
  "send email", "create segment", "check campaign", "search contacts",
  "add to segment", "list companies", "create webhook", "mautic", or any
  marketing automation task involving Mautic.
---

# mautic-cli

CLI for Mautic marketing automation. Wraps the Mautic REST API (v1, Mautic 4-7).

```bash
mautic [GLOBAL FLAGS] <resource> <command> [OPTIONS]
```

## Authentication

Credentials are stored in `~/.mautic-cli/config.json`. Never pass credentials as env vars or CLI arguments - they will be visible in the tool call output.

**If you get a "No Mautic credentials found" error:** Tell the user to run `mautic auth setup` themselves in their terminal. Do NOT attempt to read, create, or write the config file yourself. The setup command is interactive (prompts for password with hidden input) and must be run by the user directly.

**Exception, when you already hold the credentials:** if you generated the credentials yourself (e.g. you just installed the Mautic instance and created the admin password), create the profile non-interactively by writing `~/.mautic-cli/config.<profile>.json` with `{"base_url": "https://...", "auth_method": "basic", "username": "...", "password": "..."}`, run `chmod 600` on it, and verify with `mautic auth test --profile <profile>`. Flag placement: `auth test` is the exception that takes `--profile` as its own option; every other command uses the GLOBAL flag, placed immediately after `mautic` (e.g. `mautic --profile <profile> forms create ...`, never `mautic forms create --profile <profile>`).

## Profiles

Multiple Mautic instances are supported via named profiles:

- `default` - used when no `--profile` flag is passed
- Named profiles (e.g. `staging`, `production`) - use `--profile <name>`

To check which profiles exist, run:
```bash
mautic auth list
```

When the user mentions a specific Mautic instance (e.g. "the staging mautic", "production mautic"), check available profiles and use the matching `--profile` flag. If unsure which profile to use, ask the user.

## Global Flags

| Flag | Description |
|------|-------------|
| `--format json\|table\|csv` | Output format (default: json) |
| `--pretty` | Pretty-print JSON |
| `--page-all` | Auto-paginate, output NDJSON (one JSON object per line) |
| `--dry-run` | Show HTTP request without executing |
| `--verbose` | Show HTTP request/response details |
| `--published-only` | Filter to published items only |
| `--no-verify-ssl` | Skip SSL certificate verification |
| `--profile NAME` | Use a named config profile |

Global flags go BEFORE the resource group:

```bash
mautic --pretty --format table contacts list --limit 10
```

## Resources

### contacts

```bash
mautic contacts list [--search QUERY] [--limit N] [--offset N] [--order-by FIELD] [--order-dir asc|desc]
mautic contacts get <ID>
mautic contacts create --json '{"firstname":"Ana","email":"ana@example.com"}'
mautic contacts edit <ID> --json '{"lastname":"Silva"}'
mautic contacts delete <ID>
mautic contacts add-points <ID> <DELTA>
mautic contacts subtract-points <ID> <DELTA>
mautic contacts add-to-segment <CONTACT_ID> <SEGMENT_ID>
mautic contacts remove-from-segment <CONTACT_ID> <SEGMENT_ID>
mautic contacts add-to-campaign <CONTACT_ID> <CAMPAIGN_ID>
mautic contacts remove-from-campaign <CONTACT_ID> <CAMPAIGN_ID>
mautic contacts activity <ID> [--limit N] [--include-events TYPES] [--exclude-events TYPES]
```

### segments

```bash
mautic segments list [--search QUERY] [--limit N] [--offset N]
mautic segments get <ID>
mautic segments contacts <ID> [--limit N]
mautic segments create --json '{"name":"VIP Customers","isPublished":true}'
mautic segments edit <ID> --json '{"name":"Updated Name"}'
mautic segments delete <ID>
mautic segments add-contact <SEGMENT_ID> <CONTACT_ID>
mautic segments remove-contact <SEGMENT_ID> <CONTACT_ID>
```

### emails

```bash
mautic emails list [--search QUERY] [--limit N] [--offset N]
mautic emails get <ID>
mautic emails create --json '{"name":"Welcome","subject":"Hello","emailType":"template"}'
mautic emails edit <ID> --json '{"subject":"Updated"}'
mautic emails send <EMAIL_ID> --contact <CONTACT_ID>
mautic emails send-to-segment <EMAIL_ID>
```

### campaigns

```bash
mautic campaigns list [--search QUERY] [--limit N] [--offset N]
mautic campaigns get <ID>
mautic campaigns contacts <ID> [--limit N]
mautic campaigns create --json '{"name":"Onboarding","isPublished":true}'
mautic campaigns edit <ID> --json '{"name":"Updated"}'
mautic campaigns clone <ID>                          # Mautic 7+ only
mautic campaigns delete <ID>
mautic campaigns add-contact <CAMPAIGN_ID> <CONTACT_ID>
mautic campaigns remove-contact <CAMPAIGN_ID> <CONTACT_ID>
```

### forms

```bash
mautic forms list [--search QUERY] [--limit N] [--offset N]
mautic forms get <ID>
mautic forms create --json '<DATA>'
mautic forms edit <ID> --json '<DATA>'
mautic forms submissions <ID> [--limit N] [--offset N]
mautic forms submission <FORM_ID> <SUBMISSION_ID>
mautic forms contact-submissions <FORM_ID> <CONTACT_ID>
mautic forms embed <ID> [--type js|iframe|html]
mautic forms delete <ID>
```

**Mautic 7 form field types:** in `forms create` JSON, radio/checkbox groups are `radiogrp` and `checkboxgrp`, with options in `properties.optionlist.list` (e.g. `{"optionlist": {"list": [{"label": "A", "value": "a"}]}}`). The pre-Mautic-5 names `radiogrouplist`/`checkboxgrouplist` fail with an opaque 500 (Twig `LoaderError` on the field template). Map form fields to contact fields with `"mappedObject": "contact"` + `"mappedField": "<field alias>"` (replaces the old `leadField`).

### companies

```bash
mautic companies list [--search QUERY] [--limit N] [--offset N]
mautic companies get <ID>
mautic companies create --json '{"companyname":"Acme Inc"}'
mautic companies edit <ID> --json '{"companyname":"Updated"}'
mautic companies delete <ID>
mautic companies add-contact <COMPANY_ID> <CONTACT_ID>
mautic companies remove-contact <COMPANY_ID> <CONTACT_ID>
```

### notes

```bash
mautic notes list --contact <CONTACT_ID> [--search QUERY] [--limit N] [--offset N]
mautic notes get <ID>
mautic notes create --json '{"lead":42,"type":"general","text":"Called, no answer"}'
```

### stages

```bash
mautic stages list [--search QUERY] [--limit N] [--offset N]
mautic stages set <CONTACT_ID> <STAGE_ID>
```

### assets

```bash
mautic assets list [--search QUERY] [--limit N] [--offset N]
mautic assets get <ID>
```

### tags

```bash
mautic tags list [--search QUERY] [--limit N] [--offset N]
mautic tags create --json '{"tag":"vip"}'
```

### categories

```bash
mautic categories list [--search QUERY] [--limit N] [--offset N] [--bundle TYPE]
mautic categories create --json '{"title":"Q1 2026","bundle":"email"}'
```

### pages

```bash
mautic pages list [--search QUERY] [--limit N] [--offset N]
mautic pages get <ID>
```

### webhooks

```bash
mautic webhooks list [--search QUERY] [--limit N] [--offset N]
mautic webhooks get <ID>
mautic webhooks create --json '{"name":"New Lead","webhookUrl":"https://...","triggers":["mautic.lead_post_save_new"]}'
mautic webhooks delete <ID>
```

### fields

```bash
mautic fields list [--search QUERY] [--limit N] [--offset N]
mautic fields create --json '{"label":"Company Size","type":"number","group":"professional"}'
```

### reports

```bash
mautic reports list [--search QUERY] [--limit N] [--offset N]
mautic reports get <ID>
```

### points

```bash
mautic points list [--search QUERY] [--limit N] [--offset N]
mautic points triggers list [--search QUERY] [--limit N] [--offset N]
```

## JSON Input

All write commands (`create`, `edit`) accept JSON in three forms:

```bash
--json '{"key":"value"}'           # Inline
--json @contact.json               # From file
cat data.json | mautic ... --json @-   # From stdin
```

## Search Syntax

The `--search` flag passes through to Mautic's native search. Examples:

```bash
--search "email:*@company.com"         # Wildcard email match
--search "is:published"                # Published items only
--search "name:Newsletter"             # Name contains
--search "email:*@company.com is:published"  # Combined
```

## Pagination

- Default limit: 30, max: 200
- Use `--page-all` to auto-paginate through all results as NDJSON
- NDJSON output (one JSON object per line) is ideal for piping to `jq`

```bash
# Get all contacts as NDJSON
mautic --page-all contacts list | jq '.fields.all.email'

# Count all published emails
mautic --page-all --published-only emails list | wc -l
```

## Output Formats

- `--format json` (default): Full API response with `total` and resource dict
- `--format table`: Flattened key fields in aligned columns
- `--format csv`: Flattened key fields as CSV

Table/CSV show these fields per resource:
- **contacts**: id, firstname, lastname, email, points, dateAdded
- **segments**: id, name, alias, isPublished, isGlobal
- **emails**: id, name, subject, emailType, isPublished, readCount
- **campaigns**: id, name, isPublished, dateAdded
- **forms**: id, name, alias, isPublished, dateAdded
- **companies**: id, companyname, companyemail, companycity, companywebsite
- **notes**: id, text, type, dateTime
- **stages**: id, name, weight, isPublished
- **assets**: id, title, alias, downloadCount, isPublished
- **tags**: id, tag
- **categories**: id, title, alias, bundle, color
- **pages**: id, title, alias, isPublished, hits
- **webhooks**: id, name, webhookUrl, isPublished
- **fields**: id, label, alias, type, group
- **reports**: id, name, system, source
- **points**: id, name, type, delta, isPublished
- **triggers**: id, name, points, isPublished

## Safety Rules

> [!CAUTION]
> **Write commands** (`create`, `edit`, `delete`, `send`, `send-to-segment`, `add-points`, `subtract-points`, `clone`) modify data. Always confirm with the user before executing.

> [!CAUTION]
> `send` and `send-to-segment` send real emails to real people. Double-check the email ID and recipient before executing.

## Common Workflows

### Find a contact by email
```bash
mautic contacts list --search "email:user@example.com"
```

### Bulk export contacts to CSV
```bash
mautic --page-all --format csv contacts list > contacts.csv
```

### Check campaign performance
```bash
mautic --format table campaigns list
mautic campaigns contacts <CAMPAIGN_ID> --limit 100
```

### Add contact to segment
```bash
# Find the contact
mautic contacts list --search "email:user@example.com"
# Add to segment (contact ID, segment ID)
mautic contacts add-to-segment 42 5
```
