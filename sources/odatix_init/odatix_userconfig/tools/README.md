# Custom EDA tools

Drop your own EDA tool definitions in this directory. Each tool is a
subdirectory whose name is the tool identifier and which contains at least a
`tool.yml` file (and usually a `metrics.yml` and the scripts it needs):

```
odatix_userconfig/tools/
  my_tool/
    tool.yml       # commands (test / synthesis / analysis), display metadata
    metrics.yml    # how to extract metrics from the reports
    ...             # any script / makefile your commands reference
```

Tools are resolved with the user directory taking precedence over the built-in
tools shipped with Odatix: a tool placed here with the same name as a built-in
one (e.g. `vivado`) overrides it.

Inside `tool.yml`, use the `$tool_path` variable to reference files that live in
your tool directory, e.g.:

```yaml
unix:
  analysis_command:
    - make -f $tool_path/makefile.mk analyze
```

Optional display keys used by the GUI tool-selection page:

```yaml
label: "My Tool"
description: "A short one-line description"
icon: "assets/icons/my_tool.png"
```

The directory searched for tools defaults to `odatix_userconfig/tools` and can
be changed with the `tools_path` key of your workspace `odatix.yml`.

See Odatix's documentation for the full `tool.yml` reference. You can copy any
of the built-in tools (shipped under `odatix_eda_tools/`) as a starting point.
