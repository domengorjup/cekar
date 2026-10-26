# Design language

The web UI follows Home Assistant (HA) and Material conventions, so that it looks at home inside the HA sidebar. This page lists the rules, the tokens and every reusable element. Read it before adding anything to `src/cekar/web/templates/` or `static/app.css`.

## Principles

1. **Follow HA / Material.** If HA has a standard pattern (sub-page header with a back arrow, filled text fields, a floating add button, a bottom sheet on phones), use it in the same shape.
2. **Own elements only when much simpler.** Build a custom element only if it is clearly simpler than the standard one. Say why in the commit.
3. **Reuse before adding.** Look through this page first. A new class needs a new entry here; a near-duplicate of an existing element gets merged instead.
4. **No plain text links for in-app navigation.** Navigate with buttons, icon buttons, list rows, tabs, chips or segmented choices. Plain links are only for external or documentation links inside body text.
5. **Dialogs are pages first.** Every dialog is a normal server-rendered page; `app.js` only fetches it into `#overlay`. Everything works without JavaScript.
6. **Numbers never wrap.** Dates in rows sit in `span.nw`. Money comes from `money` (`€42.10`, one token) and values use `white-space: nowrap`.
7. **Every URL goes through `url(request, ...)`** so Ingress prefixes work.

## Tokens

All colours, radii and spacing are CSS custom properties with the names HA uses (`--primary-color`, `--card-background-color`, `--divider-color`, ...). `app.css` holds light and dark defaults; `theme.js` replaces them with the live HA theme when the page runs inside HA. Never hard-code a colour; use a variable.

| Group | Tokens |
|---|---|
| Colour | `--primary-color`, `--text-primary-color`, `--primary-text-color`, `--secondary-text-color`, `--divider-color`, `--card-background-color`, `--primary-background-color`, `--secondary-background-color`, `--error-color`, `--success-color`, `--warning-color`, `--input-fill-color`, `--input-idle-line-color`, `--shadow-color` |
| Chart colours | `--color-1` to `--color-5` (meaning TBD for cekar) |
| Spacing | `--ha-space-1` 4px, `-2` 8px, `-3` 12px, `-4` 16px, `-5` 20px, `-6` 24px, `-8` 32px |
| Radius | `--ha-border-radius-sm` 4px, `-md` 8px, `-lg` 12px (cards), `-xl` 16px, `-pill` (buttons, chips) |
| Type | Font `--ha-font-family-body` (from HA when available, else system sans-serif). Body 14px; page title 20px; section heading 14px (secondary colour); list title 15px; detail 13px; small 12px; stat value 26px (22px phone, 20px compact) |
| Breakpoint | One: phone below 700px (`@media (max-width: 699px)`). Phone gets the bottom nav, full-screen dialogs and two-column card grids. Content width is capped at 880px |
| Header | `--header-height` 56px |

## Layout skeleton

Every page extends `base.html` (or `partial.html` when a dialog is fetched). `main` has bottom padding so the floating button and the phone bottom nav never cover content.

```jinja
{% extends layout %}
{% block title %}Name - Cekar{% endblock %}
{% block content %}
  ...
{% endblock %}
```

Section headings are plain `<h2>`; a heading with an action on the right uses `.summary-head` (`<h2>` plus a button).

## Standard elements

### App bar

Visible, except in add-on mode on a phone (see below). Brand (basket icon and "Cekar"), on desktop the tabs, and on the right the user menu (see below). A control that should submit on change carries `data-autosubmit` (with a `<noscript>` button as fallback); `app.js` submits its form on `change`. The app bar lives in `base.html`; do not copy it.

**Inside Home Assistant (add-on mode) on a phone** (below 700px) HA shows its own top header, so the app bar is hidden: `base.html` puts `class="embedded"` on `<body>` (`embedded(request)` in `web/ui.py`, true in add-on mode) and `app.css` hides `.app-header` under it. The bottom nav stays. The person (and "Switch person" in the picker fallback) is then reached in Settings ("Signed in as" row, or "Who are you?"). Desktop widths and standalone mode keep the bar.

### Tabs and bottom nav

Desktop: `.tabs` with `a.tab` (active tab has `.active`). Phone: `.bottom-nav` with icon pills. Both are written once in `base.html` and must list the same sections (currently Lists, Expenses and Settings). Add a section there, nowhere else.

### Sub-page header with back button

HA's standard sub-page header: a round icon button with an arrow on the same row as the title, left of it. Use it on every page that has a parent (sub-pages of a top-level section). Top-level pages (Lists, Expenses, Settings) have a plain `<h1>` in `.page-title`.

```jinja
{{ page_head(request, 'Edit list') }}                      {# parent: Lists (default) #}
{{ page_head(request, 'Settle up', '/expenses', 'Expenses') }}  {# parent: Expenses #}
```

It renders `.page-head` with `a.icon-btn` (`aria-label="Back to <parent>"`, 40px target, hover and focus background, secondary text colour) and `<h1>`. Dialogs do not use it; they have a close button (see Dialog).

### Summary cards

A grid of stat cards: label, big value with a small unit, and a hint line. `.summary-grid` is the only stat grid; add `.compact` for denser cards (dense KPI rows). Values come already formatted from Python so numbers never wrap.

```html
<div class="summary-grid">
  <div class="card stat" data-card="cost_month">
    <div class="label">Cost this month</div>
    <div class="value">90.88&nbsp;&euro;</div>
    <div class="hint">-53.48&nbsp;&euro; vs September</div>
  </div>
</div>
```

Letting the user pick which cards are shown (the **Customise** popover, `details.customise`) is TBD for cekar; the CSS exists, the script and storage do not.

### List card and rows

A card containing rows. A row is a whole-row link or button with a round badge, title, detail lines, and either an amount/date block (`.side`) or a chevron (`.chev`). Use it for list items, expense entries and settings entries. Grouping rows under `.month-head` headings is available; whether cekar uses it is TBD.

```html
<div class="card list-card">
  <a class="row" href="..." data-dialog>
    <span class="badge">{{ icon('cart', 22) }}</span>
    <span class="body"><span class="title">Groceries</span><span class="detail">12 items</span></span>
    <span class="side"><span class="amount">55.89 &euro;</span><span class="date">14 Oct</span></span>
  </a>
</div>
```

Badge colours: set `--c` per kind with a `.t-<kind>` class (the kinds are TBD for cekar). A row that also needs a checkbox is a `.row` containing `label.pick` and `a.row-link`; do not add other row variants.

### Filter chips

Single-choice filter for a list (for example by list or by person). Links, so the filter lives in the URL.

```html
<div class="chips"><a class="chip active" href="...">All</a><a class="chip" href="...">Groceries</a></div>
```

### Segmented choice

For a small set of mutually exclusive view options inside a form or filter bar (view options such as period or grouping). Use `a` for URL-driven choices, `label` with a radio input for form fields. Use chips instead when the choice filters a list on its own.

```html
<div class="seg"><a class="active" href="...">Spread</a><a href="...">As paid</a></div>
```

A filter bar is a `.card.filter-bar` of `.filter-line` rows (`span.lbl` plus a `.seg` or fields).

### Buttons

One `.btn` base (pill, text style). Variants:

| Kind | Markup | Use |
|---|---|---|
| Primary (filled) | `.btn.primary` | The one main action of a card or dialog (Save, Add list) |
| Secondary (outlined) | `.btn.outline` | Other real actions (Undo) |
| Text | `.btn` | Cancel, low-emphasis actions (`.btn.with-icon` adds an icon and compact padding) |
| Icon | `a.icon-btn` or `button.icon-btn` | Back and close; always has `aria-label` |
| Danger | `.btn.danger` (text, red) and `.btn.danger-fill` | Delete; the filled one only on the final confirmation |

```html
<a class="btn primary" href="..." data-dialog>{{ icon('plus', 18) }}Add list</a>
```

Any button that destroys data carries `data-confirm="Question?"` (browser confirm) or opens a confirm dialog. `{{ post_button(request, path, label, confirm_text) }}` renders a small outlined POST button.

### Floating button and chooser

The round `+` (`a.fab`, `data-dialog`) goes in the `{% block fab %}` of `base.html`. Cekar uses it on Expenses only (it opens "Add expense"; hidden when fewer than two members exist). Lists add through the add field instead. A page with more than one thing to add can open a chooser of `a.choice` rows.

### Dialog and confirm

All forms open as a dialog: `.scrim` (click to close) containing `form.dialog.form` with `.dialog-head`, `.dialog-body` and `.dialog-foot`. The head has a close `icon-btn` (a real link, so it works without JavaScript). On phones the form dialog is full screen. A confirmation is `form.dialog.confirm` with an `h3`, one paragraph and a foot with Cancel and the action.

```jinja
<div class="scrim" data-scrim>
<form class="dialog form" method="post" role="dialog" aria-label="Edit list" action="{{ url(request, '/lists/1/edit') }}">
  {{ dialog_head(request, 'Edit list', '/') }}
  <div class="dialog-body">{{ messages(errors) }} ...fields...</div>
  <div class="dialog-foot">
    <a class="btn" href="{{ url(request, '/') }}" data-close>Cancel</a>
    <button type="submit" class="btn primary">Save</button>
  </div>
</form>
</div>
```

Dialog pages set `{% set dialog_page = true %}` so the page behind them gets no FAB.

### Messages

`{{ messages(errors, warnings) }}` renders `.alert.error` and `.alert.warning` blocks at the top of a form or page. `.alert.success` reports the result of a finished action on the page it returns to (a result summary plus an outlined Undo button on the right, via `post_button`). Use it instead of a toast when the user needs to see what happened or reverse it. A field-level hint is `.help` (`.help.err` for an error).

### Form fields, select and switch

Use the macros from `_macros.html`; they produce HA's filled text field (label above, underline, optional unit suffix).

```jinja
{{ field('Amount', 'amount', f.amount, suffix='&euro;', inputmode='decimal', required=True) }}
{{ select('List', 'list_id', options, selected) }}
{{ switch('shared', 'Shared', 'Split between all members', f.shared) }}
{{ textarea('Notes', 'notes', f.notes) }}
```

Lay fields out with `.grid2` / `.grid3` inside `.dialog-body`; plain forms on a page use `.card.card-pad.stack`. Currency and units are suffixes, not part of the label.

### Collapsible section

A native `<details>` with a `<summary>`; no custom widget. Used for archived items (`details.archived`) and popovers (`details.customise`).

```html
<details class="archived"><summary>Archived (1)</summary> ...list card... </details>
```

### Tables and charts

`table.tbl` in `.card.card-pad.table-scroll` for tabular data; numeric cells have `.num`, columns that are dropped on phones have `.wide`. The CSS for `.card.chart-card` (SVG text and grid styling) and `.legend` exists, but there is no chart drawing script yet; charts are TBD for cekar.

### Toast

`toast(message)` in `app.js` shows a short `.toast` at the bottom of the screen for about three seconds. Use it only to report a background action that failed (for example a reorder that did not save); successful actions need no toast. Deletes use the snackbar below.

### Empty state

`<div class="empty">No entries</div>` inside the place where the content would be (inside a `.card` when a card is expected). One short sentence; if the user can fix it, add a primary button under it.

### Snackbar (delete and undo)

`.snackbar` at the bottom of the screen (above the bottom nav on phones): message, an `Undo` button and a close icon, hidden after 10 seconds. A delete redirects to the page with `?undo=<kind>&id=<uuid>&name=<text>`; `base.html` renders the snackbar from those parameters (`undo_info()` in `web/ui.py`), so Undo works without JavaScript. Undo posts to the matching `.../restore` route. `deleted_redirect()` builds the redirect. "Clear checked" also offers Undo (`?undo=clear&id=<list>&n=<count>`, restore route `/lists/<id>/unclear`, service `lists.restore_cleared`). Only deleting a whole list asks first (confirm dialog), and it offers Undo too. It replaces the toast for deletes.

```html
<div class="snackbar" id="snackbar" role="status">
  <span class="msg">Deleted item Bread</span>
  <form method="post" action="/items/ID/restore"><button class="btn">Undo</button></form>
  <a class="icon-btn" href="..." aria-label="Close">...</a>
</div>
```

### Tag

`.tag` is a small pill beside a title: `.tag.for` ("For Ana", error colour tint), `.tag.personal` ("Personal", success tint), plain `.tag` ("you" in Settings).

```html
<span class="title">Razor blades <span class="tag for">For Bor</span></span>
```

### Item row with round check

`.row.item` holds `form.pick-form` with `button.pick` (a round check: `.circle` inside, `.on` when checked), then `a.row-link` (name, `.qty`, tag, "Added by" detail) and `button.handle` (drag handle, shown only with JavaScript). Checked rows have `.is-checked`; the row just added or matched gets `.hl` for a moment. `form[data-ajax]` posts in the background and swaps the live region.

### Add field with suggestions

`.add-card` holds `form.add-field`: a leading plus icon, the name input, a compact quantity box and a `for` toggle that cycles Shared and each member (a select when there are three or more members). `.suggest` is the dropdown under it; each `button[role=option]` has the match in `<mark>` and a `.s-hint` ("checked, tap to uncheck"). Without JavaScript the same form posts normally and `.no-js-only` content (a plain "for" select) is shown.

### Checked section

`details.checked-section` ("2 checked items") with a list card of checked rows, followed by `.checked-actions` (Clear checked, outlined; Done shopping, primary). Both buttons are hidden when nothing is checked.

### Balance card

`.card.balance-card` with a `.label` and `.bal-line` rows: a sentence in `.value` (`.pos` green, `.neg` red) and a Settle up `btn outline with-icon`. One pair shows the pair sentence only. Several pairs show the viewer's total first, then one `.bal-line.sub` per pair. A viewer who is not a member sees names instead of "you".

### Collapsed trip row

A shopping trip is one `details.trip-wrap` in the month's list card. `summary.row.trip-row` has the trip badge (`.t-trip`), "Shopping trip · List", the paid by line with the expense count, the total (and "you lent") on the right and a chevron; the open state shows the trip's expenses in `.trip-children`. Expense and payment rows use badge kinds `.t-equal`, `.t-for`, `.t-personal`, `.t-exact`, `.t-payment` (icon and tint per kind).

### Alerts

`.alert` with `.error`, `.warning`, `.success` or `.info`: icon, `.txt`. `.page-alert` places one above the page content (for example "Shopping trip saved: 2 expenses recorded").

### User menu and avatar

`details.user-wrap` in the app bar: `summary.icon-btn.user-btn` shows the person's initial; `.popover` has `.user-menu-name`, `.user-menu-sub` ("Home Assistant user", plus "not a member" when it applies) and, outside Ingress, a "Switch person" `button.menu-btn`. `.avatar` (with `.sm`) is the round initial used in rows, coloured `.c1` to `.c5` from the user id (`avatar_color()`).

### Count chips

The list switcher is `.chips.lists` of `a.chip` with a `span.n` count of unchecked items; a dashed `a.chip.add` ("New list") ends it. The active chip has `.active`. The row is a polled region: it carries `data-live-chips`, `data-version` (global lists-and-items change sequence), `data-version-url` (`/lists/version`) and `data-fragment-url` (`/lists/<id>/chips`); `app.js` polls it with the items and swaps it when the version differs. It lives in `list_chips.html`.

### Dialog parts

- `.price-row`: item name with a `small` ("For Bor") and a price field (Done shopping).
- `.mini-list`, `.mini-row`, `.sum-line`: compact list of shared items with a footnote.
- `.split-wrap` with a wrapping `.seg.wrap` of radio `label`s (expense split); the panel after it (`.split-panel.panel-equal`, `-for`, `-personal`, `-exact`) is shown by CSS `:has()` for the checked radio, so it needs no script. `.member-chips` are checkbox chips.
- `.exact-rows` (one field per member) and `.left-line` (`.ok` or `.bad`; "Left to assign" with the amount, updated by `app.js`).
- `.js-only` content is shown only with JavaScript: the Done shopping preview (`#trip-preview`, `.mini-list` of the expenses that will be recorded, or an error `.alert` when the prices exceed the total).
- `.grid2` pairs the amount and the date.

### Settings rows

A `form.row` with an `.avatar`, name and `.tag`, and a `label.switch` that submits on change (`data-autosubmit`); a `.help-card` row ends the group. List rows are `.row` with `a.row-link` and a `.move` form of two icon buttons (up, down).

### Footer links (Settings page)

`div.settings-links` below the last card on Settings: centred, holds icon-only `a.icon-btn` links (`aria-label` and `title` from the catalog, `target="_blank" rel="noopener"` because the app runs in the Ingress iframe and GitHub refuses to load in a frame). Currently GitHub (`github`) and Documentation (`book-open-variant`). Same element as glovebox's `.manage-links`.

```html
<div class="settings-links">
  <a class="icon-btn" href="https://github.com/domengorjup/cekar" target="_blank" rel="noopener" aria-label="{{ t('settings.github') }}" title="{{ t('settings.github') }}">{{ icon('github', 24) }}</a>
</div>
```

### Page-specific layouts

Pages not covered above (Who are you?, Login) use `.page-title`, a `.card.list-card` of rows and a `.card.form`.

## Checklist for a new page or element

1. Does an element above already do this? Use it.
2. Standard HA / Material pattern exists? Follow it.
3. In-app navigation uses a button, icon button, row, tab, chip or segmented choice, never a bare link.
4. Colours, spacing and radii are variables; works in light and dark and at 390px width.
5. Numbers and units do not wrap; nothing is covered by the floating button.
6. New class or macro? Add it to this page, and add a test when it carries behaviour.
