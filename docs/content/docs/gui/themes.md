---
title: "Themes"
description: "Pick a theme for Odatix GUI and Odatix Explorer, or write your own."
weight: 4
---

# Themes

Odatix GUI and Odatix Explorer share the same themes, picked from the dropdown in the top bar. The choice is stored in a cookie, so it survives page reloads and application restarts, and the theme of browsers without a saved choice can be set at startup:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui --theme odatix_dark
$ odatix-explorer --theme solarized_light
{{< /code >}}

The theme also drives the charts: figures are drawn with the text and grid colors of the active theme, over a transparent background, so they blend into the page. An image exported that way keeps those colors: from a dark theme, pick **Image background: White** in the Explorer **Save** tab to get dark text on white for a document. `--theme` sets the default theme for browsers without a saved choice.

{{< toc >}}

## Custom themes

A theme is a single CSS file overriding a set of variables. Drop yours in `odatix_userconfig/themes/gui/`, and it appears in the theme picker the next time the page is loaded — no restart needed:

```
odatix_userconfig/themes/gui/
  my_theme.css     ->  .theme.my_theme { ... }
```

Custom themes are read from the workspace the application is started in (the
current directory, and its `gui_theme_path` setting): an `odatix-explorer`
started elsewhere, pointed at the results with `-i`, only offers the built-in
themes. Start it from the workspace to get yours.

The file name is the theme name, and must match the class the file defines. It may only contain letters, digits, `-` and `_`. A theme whose name matches a built-in one (e.g. `odatix_dark`) replaces it, which is how you retouch a shipped theme.

Only the variables you set are overridden: everything else falls back to the defaults. The full list of variables is in `00_base.css`, in Odatix's `odatix/gui/assets/themes/` directory, next to every built-in theme — any of them makes a good starting point.

The variables a theme most often sets:

| Variable | What it colors or sizes |
|----------|-------------------------|
| `--theme-background-color` | Page background. |
| `--theme-element-background-color` | Cards and tiles. |
| `--theme-tertiary-color` | Background of input fields. |
| `--theme-primary-color` | Tooltips and switches. |
| `--theme-secondary-color` | Important buttons. |
| `--theme-accent-color` | Accent icons (default: `--theme-primary-color`). |
| `--theme-success-color`, `--theme-caution-color` | Confirmations and errors, such as the line saying a page was saved or why it was not. |
| `--theme-text-color`, `--theme-subtle-text-color` | Text, and secondary text. |
| `--theme-font-family` | Font of the page. |
| `--theme-font-size` | Text of the page, where an element does not set its own size (default: `--theme-large-font-size`, 16px). |
| `--theme-border-color`, `--theme-border-color-hover` | Borders, at rest and under the pointer. |
| `--theme-normal-border-radius` | Corner radius of buttons, cards and dropdowns. |

Workspace themes are served together from a single URL, so a relative `url()` in one of them does not resolve against your theme directory. Reference images and fonts with an absolute URL, or inline them as a `data:` URI.

## The `odatix-theme` header

Plotly figures cannot read CSS variables, and the theme picker needs a readable label, so a theme declares those in a header comment at the top of its file:

```css
/* odatix-theme
 * name: My Theme
 * dark: true
 * plot-text-color: #e6e6e6
 * plot-grid-color: rgba(230, 230, 230, 0.15)
 * plot-zeroline-color: rgba(230, 230, 230, 0.4)
 */
```

| Field | Description |
|-------|-------------|
| `name` | Label shown in the theme picker (default: the file name). |
| `dark` | Whether the page background is dark. Drives the default plot colors. |
| `plot-text-color` | Color of the axis labels and legends of the figures. |
| `plot-grid-color` | Color of the grid lines of the figures. |
| `plot-zeroline-color` | Color of the zero lines of the figures. |

Only `dark` really matters: the three `plot-*` colors default to sensible light or dark values according to it. The header must appear within the first 4 kB of the file.

## Example

{{< code lang=css filename="odatix_userconfig/themes/gui/my_theme.css" >}}
/* odatix-theme
 * name: My Theme
 * dark: true
 * plot-text-color: #d7e4e2
 * plot-grid-color: rgba(215, 228, 226, 0.16)
 * plot-zeroline-color: rgba(78, 205, 196, 0.5)
 */

.theme.my_theme {
    /* page and surfaces */
    --theme-background-color: #10201f;
    --theme-element-background-color: #172c2b;
    --theme-tertiary-color: #1e3735;         /* background of input fields */
    --theme-contrast-background-color: #0a1615;

    /* accents */
    --theme-primary-color: #4ecdc4;          /* tooltips, switches */
    --theme-secondary-color: #4ecdc4;        /* important buttons */

    /* text */
    --theme-text-color: #d7e4e2;
    --theme-subtle-text-color: #6f8b88;

    /* borders */
    --theme-border-color: #24413f;
    --theme-border-color-hover: #4ecdc4;
}
{{< /code >}}

A workspace initialized with `odatix init` already contains this file, as `example_theme.css`, next to a `README.md` recalling the format.

The directory searched for themes defaults to `odatix_userconfig/themes/gui` and can be changed with the [`gui_theme_path`](/docs/reference/workspace/) key of your workspace `odatix.yml`.
