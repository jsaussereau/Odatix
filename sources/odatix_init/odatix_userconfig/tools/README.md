# Tools of your own

Drop your own tool definitions in this directory. Each tool is a
subdirectory whose name is the tool identifier and which contains at least a
`tool.yml` file (and usually a `metrics.yml` and the scripts it needs):

```
odatix_userconfig/tools/
  my_tool/
    tool.yml       # commands (test / synthesis / analysis), display metadata
    metrics.yml    # how to extract metrics from the reports
    tcl/           # scripts copied into every job directory (any language)
```

Its targets go in `odatix_userconfig/targets/target_my_tool.yml`.

A tool placed here with the same name as a built-in one (e.g. `vivado`) is
**merged** over it: you can add flows and override its metadata, but its own
flows stay read-only (what this file says about them is ignored, with a
warning). To own a built-in tool entirely, duplicate it under another name
(GUI: Configure > Tools > Duplicate).

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

See Odatix's documentation for the full `tool.yml` reference:
https://odatix.readthedocs.io/docs/tools/add_tools/
and the tutorial: https://odatix.readthedocs.io/tutorials/own_flows/add_tools/
