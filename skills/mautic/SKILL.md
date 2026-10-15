---
name: mautic
description: >-
  Mautic marketing automation: manage contacts, segments, emails, campaigns,
  forms, Focus items (popups), companies, notes, stages, assets, tags,
  categories, pages, webhooks, fields, reports, points, and stats tables. Use
  when the user asks to "list contacts", "send email", "create segment",
  "check campaign", "search contacts", "add to segment", "list companies",
  "create webhook", "edit the popup", "focus stats", "mautic", or any
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

`emails edit` is a plain PATCH. On an email with dynamic content, a PATCH without `dynamicContent` replaces it with Mautic's placeholder ("Dynamic Content 1" / "Default Dynamic Content"), verified on 7.1.1: copy `dynamicContent` from `emails get` into every edit of such an email.

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
mautic forms edit <ID> --json '<PATCH>' [--dry-run]
mautic forms fields delete <FORM_ID> <FIELD_ID>...
mautic forms submissions <ID> [--limit N] [--offset N]
mautic forms submission <FORM_ID> <SUBMISSION_ID>
mautic forms contact-submissions <FORM_ID> <CONTACT_ID>
mautic forms embed <ID> [--type js|iframe|html]
mautic forms delete <ID>
```

**Mautic 7 choice fields (radiogrp/checkboxgrp), five gotchas verified on 7.1:**

- Field types are `radiogrp`/`checkboxgrp`; the pre-Mautic-5 names `radiogrouplist`/`checkboxgrouplist` fail with an opaque 500 (Twig `LoaderError`; the exception only appears in the Mautic log file, not in the API response).
- Options go in `properties.optionlist.list` as `[{"label": ..., "value": ...}]`, but they do NOT render unless `properties.syncList` is ALSO defined - always send `"syncList": false` alongside `optionlist`. (Upstream case bug in `group.html.twig`: the render gate checks `optionList` camelCase, the fallback reads `optionlist` lowercase; a defined `syncList` is what opens the gate.)
- Do not leave `syncList: true` on a field with custom labels: on save it overwrites the `optionlist` labels with the mapped contact field's labels and adds a derived `properties.list` key that a later `forms edit` rejects ("This form should not contain extra fields") - strip `list` from properties before resubmitting.
- An option with value `0` renders pre-checked when the field has no `defaultValue` (Twig loose `null == 0`); set `"defaultValue": ""` on the field to prevent it.

Map form fields to contact fields with `"mappedObject": "contact"` + `"mappedField": "<field alias>"` (replaces the old `leadField`).

**`forms edit` merges, and why it has to.** A raw PATCH to `/forms/{id}/edit` without `postAction` sets it to `return`: the visitor stays on an empty form instead of going to the thank-you page. The fields in a request are renumbered 1..n by their position and their `order` key is ignored, so a request with one field moves it to the top. `forms edit` reads the form, merges the patch (objects key by key, `fields` and `actions` by `id`), and sends every top-level key, plus every field by id in order with its `mappedObject`/`mappedField` whenever the patch has fields. Only the patch:

```bash
mautic forms edit 5 --json '{"fields":[{"id":3,"label":"Your email"}]}' --dry-run   # see the change first
mautic forms edit 5 --json '{"fields":[{"id":3,"label":"Your email"}]}'
mautic forms edit 5 --json '{"fields":[{"id":7,"order":1}]}'                       # move a field to the top
mautic forms edit 5 --json '{"fields":[{"label":"Phone","type":"tel","order":3}]}' # add a field (no id) in third place
mautic forms fields delete 5 7                                                      # remove field 7
```

The output is `{"id", "changes": [{"path", "before", "after"}]}`, from a GET before and a GET after (e.g. `fields[id=3].label`). If `unexpected` appears, the server changed a key the patch did not ask for: report it to the user before doing anything else. If `not_applied` appears, a key in the patch did not change, usually a misspelt or unknown key name. `order` on a field moves it to that position (1 is first). Publish dates go as `YYYY-MM-DD HH:MM`; the ISO format `get` returns is rejected with "Please enter a valid date and time", so the CLI only sends them when the patch sets them. On a field with `syncList: true`, GET returns the option list derived from the contact field, keyed by label, and sending it back fails with a 500; the CLI drops it when you patch that field's `properties`, and the form still renders every option.

### focus

Focus items are Mautic's popups, bars and notifications.

```bash
mautic focus list [--search QUERY] [--limit N] [--offset N]
mautic focus get <ID>
mautic focus create --json '<DATA>'
mautic focus edit <ID> [--json '<PATCH>'] [--html TEXT|@FILE] [--css TEXT|@FILE] [--publish|--unpublish] [--dry-run]
mautic focus js <ID>
mautic focus stats <ID> [--since DATE] [--until DATE]
mautic focus delete <ID>
```

- `focus edit` merges like `forms edit`: it reads the item, merges the patch (also inside `properties`), sends the whole item and prints `{"id", "changes"}`, with `unexpected` and `not_applied` as in `forms edit`. Run it with `--dry-run` first and show the user the changes.
- The custom CSS lives in `properties.content.css` (`--css`). `--html` sets `html` and switches `htmlMode` to `html`, the only mode that renders it.
- GET returns `htmlMode`, but the API only accepts it as `html_mode`; `htmlMode` in a request is silently ignored. `focus create` and `focus edit` translate it.
- Do not assume a property exists: `properties.min_page_views` and `frequency: "days"` come from an unmerged Mautic patch (mautic/mautic#17672) and exist only on instances that carry it. Read `focus get` first; the CLI passes unknown properties through untouched.
- `focus js` prints the script a visitor receives (`POST /focus/{id}/js`), without recording a view or creating a contact: use it to check what is published instead of opening the site.
- `focus stats` counts the `focus_stats` rows by type: `views`, `clicks`, `submissions` (`--until` is exclusive; dates are UTC). A submission is recorded when the form is actually submitted. The "stop after conversion" cookie, though, is set when the visitor clicks the submit button, before validation: someone who clicks with an empty email and leaves never sees the popup again.

**Layout, verified on 7.1.1.** The Focus is rendered in an iframe whose height is set to the content's height, capped at the window's (`generate.js.twig`). An element that grows to its own aspect ratio, such as an image in a side column, stretches the popup to the full window height; take it out of the flow (`position: absolute` with `object-fit: cover`) so the text sets the height. The content starts with a reset, `.mautic-focus * { all: revert; }`, and `properties.content.css` comes after it: put the styles there, because anything injected before the reset with one class of specificity or less is reverted to browser defaults.

### stats

```bash
mautic stats                                          # tables and their columns
mautic stats <TABLE> [--where COL=VAL]... [--order COL[:asc|desc]] [--limit N] [--offset N]
mautic --page-all stats <TABLE> --where COL=VAL       # every row, NDJSON
```

`--where` takes `=`, `!=`, `>`, `>=`, `<`, `<=`; repeat it to combine with AND. Useful tables: `email_stats` (sends, reads), `focus_stats`, `form_submissions`, `page_hits`. Sort by `id`, never by a date: on large tables an ORDER BY on a date column times out. The stats API reports a bad column with HTTP 200 and an `errors` key; the CLI turns that into an error and exit code 1.

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

Page WRITES are not covered by the CLI yet - use the REST API directly (`POST /api/pages/new`, `PATCH /api/pages/<ID>/edit`, with `title` and `customHtml`; set `"template": "blank"` for full custom HTML). Two rendering notes: a `{form=ID}` token inside `customHtml` renders as the JS embed of that form, and non-ASCII characters in CSS `content:` strings get entity-encoded on save and display literally - keep CSS-generated text ASCII-only.

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
- **focus**: id, name, type, style, isPublished

## Safety Rules

> [!CAUTION]
> **Write commands** (`create`, `edit`, `delete`, `send`, `send-to-segment`, `add-points`, `subtract-points`, `clone`) modify data. Always confirm with the user before executing.

> [!CAUTION]
> Before `forms edit` or `focus edit` on a live instance, run it with `--dry-run` and show the user the `changes`. After the edit, check that `changes` holds only what was asked and that there is no `unexpected` or `not_applied` key.

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
