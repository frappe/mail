# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Frappe Mail is a Frappe Framework app with two roles:
1. A **JMAP client** that connects to any JMAP-compatible mailbox (primarily Stalwart Mail)
2. A **Stalwart Mail orchestration layer** that deploys and manages mail clusters via Ansible over SSH

The backend is Python/Frappe, the frontend is Vue 3 + TypeScript served as a SPA from `/mail/public/frontend/`.

## Commands

### Frontend
```bash
# Development (from repo root or frontend/)
npm run dev              # Start Vite dev server via bun
bun run dev              # Equivalent, from frontend/

# Build
npm run build            # Build frontend + email CSS
npm run build-app        # Frontend only
npm run build-email-css  # Tailwind CSS for email templates (output: mail/public/css/email.css)
```

### Backend (Frappe Bench — run from bench root, not app root)
```bash
bench --site <site> install-app mail
bench --site <site> run-tests --app mail          # All tests
bench --site <site> run-tests --app mail --module mail.tests.test_foo  # Single test
bench build                                         # Rebuild assets
```

### Linting
```bash
pre-commit run --all-files   # Python (ruff) + JS (eslint) + prettier + pyupgrade
ruff check mail/             # Python only
cd frontend && bun run lint  # ESLint only
```

## Architecture

### Backend (`mail/`)

```
api/          REST endpoints — auth.py, inbound.py, outbound.py, jmap.py, admin.py, account.py
jmap/         JMAP protocol client — connection.py, models/, services/
server/       Stalwart cluster orchestration
  doctype/    Mail Cluster, Mail Server, Server Job, Server Deployment, Server Ansible Play,
              Mail Domain Request, Mail Account Request, Principal, DNS Record, etc.
client/       Email client features
  doctype/    Mailbox, Mail Message, Mail Queue, Identity, Vacation Response, Sieve Script,
              Address Book, Contact Card, Calendar, Calendar Event, Push Subscription, etc.
storage/      Storage abstraction layer
utils/        user.py, validation.py, query.py, cache.py, DNS helpers, email parser,
              Ansible utilities, rate limiter
hooks.py      App registration: website redirects, permission handlers, scheduled tasks
```

**Request flow:** Frappe routes `/auth/*`, `/outbound/*`, `/inbound/*`, `/jmap/*`, `/spamd/*` etc. via `website_route_rules` in `hooks.py` → corresponding `api/*.py` functions → JMAP client (`jmap/`) communicates with Stalwart or other JMAP servers.

**Server provisioning flow:** `server/doctype/` doctypes drive Ansible playbooks (via `ansible-runner`) over SSH (`paramiko`) to deploy Stalwart clusters.

**Scheduled tasks** (defined in `hooks.py`): every 5 min, hourly, and daily jobs for queue processing, sync, and maintenance.

### Frontend (`frontend/src/`)

```
pages/        MailboxView (main email UI), DashboardView (admin) + sub-pages,
              AddressBooksView/ContactsView, MailExchangesView, Auth views
components/   40+ reusable Vue components
stores/       Pinia stores — session, user
router.ts     Vue Router — route definitions
constants.ts  App-wide constants
types/        TypeScript types
```

The built output lands in `mail/public/frontend/` and is served by Frappe's static file handling.

### Key Technology Choices
- **Frappe Framework v16** — provides ORM, REST API scaffolding, auth, scheduler, permissions
- **JMAP** — backend client in `jmap/` uses this protocol to read/write mail on Stalwart
- **Bun** — used instead of npm for frontend package management and dev server
- **Frappe UI** — custom component library (git submodule at `frappe-ui/`)
- **Python 3.12**, ruff for linting (line-length: 110)

## Frappe Conventions

- Doctypes live in `<module>/doctype/<doctype_name>/` with `.json` (schema), `.py` (controller), and `_test.py` files
- API functions decorated with `@frappe.whitelist()` are auto-exposed; website route rules in `hooks.py` map URL paths to them
- Fixtures in `mail/fixtures/` are loaded on `bench migrate`
- Patches in `mail/patches/` run once per site on migration, registered in `patches.txt`
- Translations are in `mail/locale/`
