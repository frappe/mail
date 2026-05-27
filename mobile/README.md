# Frappe Mail — Mobile App

NativeScript + Vue 3 mobile client for Frappe Mail, targeting iOS and Android.

## Prerequisites

```bash
npm install -g @nativescript/cli
```

For iOS (macOS only): Xcode + `ns doctor ios`
For Android: Android Studio + `ns doctor android`

## Setup

```bash
# From repo root — installs all workspaces including mobile/ and packages/types/
bun install

# Or from mobile/ directly
cd mobile && bun install
```

## Running

```bash
ns run android    # or: bun run dev:android
ns run ios        # or: bun run dev:ios
```

## Building

```bash
ns build android --release
ns build ios --release
```

## Linting

```bash
bun run lint
bun run typecheck
```

## Architecture

```
app/
  app.ts          Entry point — creates Vue app, mounts Pinia
  App.vue         Root Frame component
  app.css         Tailwind utilities (@tailwind utilities only — no base/components)
  pages/          Full-screen Page components
  components/     Reusable NativeScript-Vue components
  stores/
    site.ts       Saved sites + active site (ApplicationSettings)
    session.ts    OAuth tokens per site (ApplicationSettings — secure storage in #486)
    user.ts       User info, accounts, mailboxes — mirrors frontend/src/stores/user.ts
  utils/
    api.ts        Frappe API client (POST /api/method/<method> + Bearer token)
    format.ts     Pure formatters shared with frontend (no DOM dependencies)
  theme/
    colors.ts     Frappe UI semantic color tokens (light + dark) as plain hex values
```

## Generic vs. Mail-specific

Parts that could be extracted into a `frappe-nativescript` package if other Frappe apps adopt this stack:

- **Generic:** `app/utils/api.ts` (Frappe API client pattern), `app/stores/site.ts` (site management), `app/stores/session.ts` (OAuth token storage shape), `app/theme/colors.ts` (Frappe UI tokens), `tailwind.config.js` (NativeScript Tailwind + Frappe UI tokens)
- **Mail-specific:** `app/stores/user.ts`, all pages and components, `App_Resources/` bundle IDs

## Shared types

Types shared between this app and the web frontend live in `packages/types/`. The mobile app imports from `@mail/types`; the frontend can be migrated to the same package in a follow-up.

## Platform resources

`App_Resources/` contains the minimum required manifest files. Before building:
- Android: add launcher icons to `App_Resources/Android/src/main/res/`
- iOS: add app icon assets and a `LaunchScreen.storyboard` to `App_Resources/iOS/`

Run `ns resources generate icons <path-to-icon.png>` to auto-generate icon sizes.
