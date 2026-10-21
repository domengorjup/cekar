# Design language

The web UI follows Home Assistant (HA) and Material conventions, so that it looks at home inside the HA sidebar. This page lists the rules, the tokens and every reusable element. Read it before adding anything to `src/cekar/web/templates/` or `static/app.css`.

## Principles

1. **Follow HA / Material.** If HA has a standard pattern (sub-page header with a back arrow, filled text fields, a floating add button, a bottom sheet on phones), use it in the same shape.
2. **Own elements only when much simpler.** Build a custom element only if it is clearly simpler than the standard one. Say why in the commit.
3. **Reuse before adding.** Look through this page first. A new class needs a new entry here; a near-duplicate of an existing element gets merged instead.
4. **No plain text links for in-app navigation.** Navigate with buttons, icon buttons, list rows, tabs, chips or segmented choices. Plain links are only for external or documentation links inside body text.
5. **Dialogs are pages first.** Every dialog is a normal server-rendered page; `app.js` only fetches it into `#overlay`. Everything works without JavaScript.
6. **Numbers never wrap.** Join a number and its unit with a non-breaking space (`with_unit`, `money`) and use `white-space: nowrap` on values.
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

Always visible. Brand (basket icon and "Cekar") and, on desktop, the tabs. A control that should submit on change carries `data-autosubmit` (with a `<noscript>` button as fallback). The handler lives in `theme.js` (loaded in the head), not in the deferred `app.js`, so a choice made while the page script is still loading is not lost. The app bar lives in `base.html`; do not copy it. Which controls the app bar gets beyond the brand and tabs is TBD for cekar.

### Tabs and bottom nav

Desktop: `.tabs` with `a.tab` (active tab has `.active`). Phone: `.bottom-nav` with icon pills. Both are written once in `base.html` and must list the same sections (currently Lists and Expenses). Add a section there, nowhere else.

### Sub-page header with back button

HA's standard sub-page header: a round icon button with an arrow on the same row as the title, left of it. Use it on every page that has a parent (sub-pages of a top-level section). Top-level pages (Lists, Expenses) have a plain `<h1>` in `.page-title`.

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

The round `+` (`a.fab`, `data-dialog`) is shown on pages where the main action is adding something. It opens a bottom sheet on phones and a small dialog on desktop, which can list `a.choice` rows when there is more than one thing to add. Which pages get it and what it offers is TBD for cekar (`base.html` has no FAB yet).

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

`toast(message)` in `app.js` shows a short `.toast` at the bottom of the screen for about three seconds. Use it only to report a background action that failed (for example saving a background choice); successful actions reload the page and need no toast.

### Empty state

`<div class="empty">No entries</div>` inside the place where the content would be (inside a `.card` when a card is expected). One short sentence; if the user can fix it, add a primary button under it.

### Page-specific layouts

TBD for cekar. Add an entry per new page layout that introduces a class.

## Checklist for a new page or element

1. Does an element above already do this? Use it.
2. Standard HA / Material pattern exists? Follow it.
3. In-app navigation uses a button, icon button, row, tab, chip or segmented choice, never a bare link.
4. Colours, spacing and radii are variables; works in light and dark and at 390px width.
5. Numbers and units do not wrap; nothing is covered by the floating button.
6. New class or macro? Add it to this page, and add a test when it carries behaviour.
