# Offline use (stage 2 design note)

Status: design only, nothing is built. This note is shared with the sibling app on the same infrastructure (`/mnt/data/workspace/autotracker_app/docs/dev/offline.md`). Whichever app builds offline use first sets the approach, and the other reuses it; compare both notes before changing either. The sibling's note (a draft, 2026-10-21) lists three options; this note picks the second one (browser-side outbox) and explains why the first does not work.

## Goal

Keep the most-used screens usable on a phone when there is no internet or Home Assistant is down, and send the changes once the server is reachable again, without duplicates. Keep it simple: no conflict screens, no offline version of every page.

## Why the HA panel cannot be the offline entry point

The Ingress panel lives inside the HA frontend (`/api/hassio_ingress/<token>/`). The HA frontend has to load and authenticate first, and the Ingress token in the URL can change. If HA is down or unreachable, nothing under that path loads, and a service worker there cannot help. The companion app shows the same frontend, so it has the same limit (as far as we know; not tested).

## Approach

1. **Separate installable web app (PWA)** served by the add-on on its own port, next to the Ingress UI. The obvious place is the existing optional API listener (container port 8100, off by default), extended with the app shell at `/app/` and a sync endpoint under `/api/v1/`. It is not reached through HA at all.
2. **HTTPS is required.** Service workers and installable apps need a secure context. Options: the user's own domain with a reverse proxy and a Let's Encrypt certificate in front of the port, or Tailscale with its HTTPS certificates. It is not certain whether Nabu Casa's remote access can reach add-on ports; it appears to proxy only the HA frontend, so it is probably not an option (to check before relying on it). Plain `http://<lan-ip>:8100` will not work for installation.
3. **Device pairing.** In the Ingress UI, where HA has already identified the user, "Pair a device" creates a random per-device token tied to that user and shows it as a QR code (a URL with the token in the fragment). The phone opens it, the app stores the token, and every sync call sends it as a Bearer token. Settings lists paired devices with last use and a "Revoke" button. No passwords.
4. **Local copy and outbox.** The app keeps a copy of the data it needs in IndexedDB and records every change in an outbox queue. Each change carries a client-generated UUID for the row (and one for the operation), so a resend after a lost reply is harmless.
5. **Sync.** One call: the client sends its outbox and its cursor; the server applies the operations idempotently through the normal service layer, then returns every row with `seq` greater than the cursor, plus the new cursor. The client replaces its local rows with what came back and empties the sent part of the outbox. Derived values (expense shares, balances, statistics) are computed by the server; offline they are shown as of the last sync, marked as such.
6. **Conflicts: per-field last-write-wins.** The client sends only the fields it changed. The server applies them in the order the operations arrive, so two people editing different fields of the same row both keep their change; on the same field, the later sync wins. Deletes are tombstones (`deleted_at`) and win over later edits of the same row. There is no conflict UI.
7. **Small offline scope.** Only the screens people use away from home: in the shopping app, viewing and editing lists and adding an expense; in the car-cost app, adding a refuel or expense. Everything else needs a connection.

## What v1 must do to keep the door open

- [ ] UUID primary keys on every user-data table (or a UUID public id), so a client can create rows.
- [ ] Creating a row with an existing id is a no-op, not an error or a duplicate.
- [ ] `created_at` and `updated_at` on every mutable row; `updated_at` changes on every write.
- [ ] Soft deletes: `deleted_at` tombstones instead of `DELETE`, also on child rows.
- [ ] One global, increasing change counter stored in a `seq` column on every write (or a design that lets it be added without rewriting data).
- [ ] All writes go through the service layer with plain values and the acting user, never from web routes directly, so a sync endpoint can reuse them.
- [ ] Derived data (shares, totals) is computed by the server from stored inputs, so a client never has to send it.
