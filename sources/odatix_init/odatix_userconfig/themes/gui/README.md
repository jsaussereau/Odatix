# Custom GUI themes

Drop your own themes for the Odatix GUI and Explorer in this directory. Each
theme is a single `.css` file whose name is the theme name, as it appears in the
theme picker and in the CSS class it defines:

```
odatix_userconfig/themes/gui/
  my_theme.css     ->  .theme.my_theme { ... }
```

The file name must contain only letters, digits, `-` and `_`.

A theme only has to override the tokens it cares about: everything it leaves out
falls back to the defaults declared by Odatix (see `00_base.css` in Odatix's
`gui/assets/themes/` directory, which lists every available token). A theme
whose name matches a built-in one (e.g. `odatix_dark`) replaces it.

## The `odatix-theme` header

Plotly figures cannot read CSS variables, and the theme picker needs a readable
label, so each theme declares those in a header comment at the top of the file:

```css
/* odatix-theme
 * name: My Theme
 * dark: true
 * plot-text-color: #e6e6e6
 * plot-grid-color: rgba(230, 230, 230, 0.15)
 * plot-zeroline-color: rgba(230, 230, 230, 0.4)
 */
```

Only `dark` really matters: the three `plot-*` colors default to sensible light
or dark values according to it, and `name` defaults to the file name. The header
must appear within the first 4 kB of the file.

## Writing a theme

Copy `example_theme.css` next to this README, rename it and edit it. Any
built-in theme is also a good starting point: they are shipped under Odatix's
`odatix/gui/assets/themes/` directory.

Themes are re-read whenever a file in this directory changes, so refreshing the
page is enough to see an edit — no need to restart the GUI.

The directory searched for themes defaults to `odatix_userconfig/themes/gui` and
can be changed with the `gui_theme_path` key of your workspace `odatix.yml`.

Note: the themes of this directory are served together from a single URL, so a
relative `url()` does not resolve against this directory. Reference images and
fonts with an absolute URL, or inline them as a `data:` URI.
