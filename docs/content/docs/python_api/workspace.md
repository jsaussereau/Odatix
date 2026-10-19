---
title: "odatix.workspace"
description: "Every class, method and setting of odatix.workspace: opening a workspace and reading and writing what it holds."
weight: 100
---
<!--
  This page is generated from the source code by docs/tools/gen_api_reference.py.
  Do not edit it by hand: edit the docstrings of odatix.workspace, then run
  `make api-docs`.
-->

# `odatix.workspace`

> [!IMPORTANT] Requires Odatix 4.0+

Every public name of **`odatix.workspace`**, what it does and what it takes:
opening a workspace, and reading and writing everything it holds. The
[Python API overview](/docs/python_api/) is the place to start; this page is the
one to come back to. What a workspace describes is then run through
[`odatix.run`](/docs/python_api/run/).

The module re-exports everything worth using, so nothing below needs to be
imported from a submodule:

{{< code lang=python filename="imports.py" >}}
from odatix.workspace import Workspace, NotFoundError
{{< /code >}}

> [!NOTE]
> Every path is resolved against the workspace, never against the current
> directory, so an object obtained from a `Workspace` reads and writes the same
> files as the commands run from inside it.

The Odatix workspace configuration API.

Everything a user configures by hand in the YAML files of a workspace can be
read and written from here, from Python.
The graphical interface uses the very same API, so nothing it can do is out of
reach of a script.

Start by opening the workspace of the current directory:

```python
from odatix.workspace import Workspace

ws = Workspace.open()
```

Then work on what it holds. Collections behave like the mappings they are
(`in`, `[]`, iteration, `len`), and every entry knows where it lives, so
no path is ever passed around:

```python
counter = ws.architectures.create("Counter")
counter.settings.rtl_path = "examples/counter"
counter.settings.top_level_file = "counter.sv"
counter.settings.top_level_module = "counter"
counter.settings.clock_signal = "clk"
counter.settings.use_parameters = True
counter.save()

counter.configs.write("08bits", "WIDTH = 8")
counter.configs.write("16bits", "WIDTH = 16")

width = counter.domains.create("width")
width.settings.configurations.name = "${width}bits"
width.settings.configurations.template = "WIDTH = ${width}"
width.settings.set_variable("width", "range", {"from": 8, "to": 32, "step": 8})
width.save()
width.configuration_names()  # a run resolves these; writing them out is optional
```

Settings objects are typed: they know their keys, their defaults and how each
one is written. What a settings file holds that Odatix does not know about is
never lost: it stays in the file, and in `settings.extra`.

Writing a settings file keeps its comments and its layout. A file that does not
exist yet is generated with the section comments that make it readable.

## Entry point

### `Workspace`

`Workspace(root='.', settings=None)`

An Odatix workspace.

This is the entry point of the configuration API: everything a user can
configure hangs off it, and nothing else needs to be given a path.

| Attribute | What it is |
|---|---|
| `SETTINGS_FILENAME` | Name of the settings file of a workspace. |
| `settings_file` *(property)* | Path of the settings file of this workspace. |
| `exists` *(property)* | Whether the directory actually holds a workspace. |
| `settings` *(property)* | The settings file of this workspace, as plain values. Missing keys are not filled in here: `paths` is what applies the defaults. |
| `default_tool` *(property)* | The eda tool a run uses when it is not told which: "default_tool" of the settings file, or else the only tool this workspace has a target file for. None when neither singles one out. |
| `paths` *(property)* | Where each part of this workspace is. |
| `architectures` *(property)* | The architectures of this workspace. |
| `simulations` *(property)* | The simulations of this workspace. |
| `workflows` *(property)* | The workflows of this workspace. |
| `tools` *(property)* | The EDA tools usable by this workspace, built-in ones included. |
| `targets` *(property)* | The synthesis targets, one file per EDA tool. |
| `jobs` *(property)* | What each run command of this workspace runs, and how. |
| `derived_metrics` *(property)* | The metrics this workspace computes from the ones its runs produce. Always the same object for a given workspace (until `reload()`), so `ws.derived_metrics.set(...)` then `ws.derived_metrics.save()` saves the change. |
| `clean_settings` *(property)* | What "odatix clean" removes from this workspace. Always the same object for a given workspace (until `reload()`). |

| Method | What it does |
|---|---|
| `open(root='.', required=False)` *(classmethod)* | Open the workspace held by a directory. *Args:* `root` *(str)* — the workspace directory. The current one by default, which is where the Odatix commands run.; `required` *(bool)* — raise `NotAWorkspaceError` when the directory holds no settings file. Without it, the workspace opens on the Odatix defaults, which is what a directory about to be initialized looks like. |
| `from_dict(settings, root='.')` *(classmethod)* | Open a workspace from settings already in hand, without reading the settings file again. |
| `init(root='.', examples=False)` *(classmethod)* | Create the configuration files of a workspace in a directory, and open it. An existing configuration is overwritten, as "odatix init" does. |
| `configured_tools()` | The eda tools this workspace has a target file for. |
| `reload()` | Read the settings file again, and resolve the paths anew. |
| `save_settings(values=None, **kwargs)` | Write settings into the settings file of this workspace. Only the ones given are changed, everything else in the file is left as it was. An empty one is removed: it means "use the Odatix default". |
| `odatix_settings()` | The settings as an `OdatixSettings` object, for the parts of Odatix that take one. |

### `WorkspacePaths`

`WorkspacePaths(root, settings=None)`

Where each part of a workspace is.

Every path is resolved against the workspace directory, so an API used from
anywhere reads and writes the same files as the commands run from inside it.
A path a workspace does not set falls back to the Odatix default.

| Attribute | What it is |
|---|---|
| `target_fallback_path` | Where a target file kept at the old default location is looked up. |

| Method | What it does |
|---|---|
| `under_work_path(name, work_path=None)` | The work directory of one kind of job ("fmax_synthesis_work_path", ...). Those settings name a sub-directory of the work directory, not a path of their own, so they are joined to it rather than resolved against the workspace like every other path. *Args:* `work_path` *(str)* — the work directory to join it to, when a run works in another one than the workspace's ("--work"). |
| `work_subpath(name)` | What one of the work sub-directory settings says, as written. |
| `resolve(path)` | A workspace path as an absolute-or-relative path usable from anywhere. |
| `to_dict()` |  |

### `WorkspaceSettings`

Derives from `Settings`.

The settings file of a workspace ("odatix.yml").

Every setting is optional: one left empty is removed from the file, and
Odatix uses its default instead. Saving only touches the keys that changed,
so the comments, the layout and the keys this class does not know about
(one a newer Odatix added, a deprecated one still read) stay as they were.

| Attribute | What it is |
|---|---|
| `moved_keys` | The keys that named the settings files before they were named after their command: saved under the current key, where the former one was. |

| Method | What it does |
|---|---|
| `normalize()` | Read a former settings file key as the current one (see `moved_keys`). |

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| `workspace` | `str` | `'odatix'` | Marks the directory as an Odatix workspace. |
| **Tools** | | | |
| `default_tool` | `str` |  | EDA tool the run commands use when "-t/--tool" does not name one. |
| **Main paths** | | | |
| `arch_path` | `str` |  | Where the architectures are. |
| `sim_path` | `str` |  | Where the simulations are. |
| `workflow_path` | `str` |  | Where the workflows are. |
| `tools_path` | `str` |  | Where the workspace's own tools are. |
| `target_path` | `str` |  | Where the target files are. |
| `gui_theme_path` | `str` |  | Where the user themes of the GUI are. |
| **Settings files** | | | |
| `clean_settings_file` | `str` |  | What "odatix clean" removes. |
| `sim_settings_file` | `str` |  | Settings of "odatix sim". |
| `fmax_settings_file` | `str` |  | Settings of "odatix fmax". |
| `synth_settings_file` | `str` |  | Settings of "odatix synth". |
| `pnr_settings_file` | `str` |  | Settings of "odatix pnr". |
| `analyze_settings_file` | `str` |  | Settings of "odatix analyze". |
| `workflow_settings_file` | `str` |  | Settings of "odatix workflow". |
| `dse_settings_file` | `str` |  | Settings of "odatix dse". |
| `dse_campaign_path` | `str` |  | Where the exploration campaigns are kept. |
| `derived_metrics_file` | `str` |  | The metrics computed from the ones runs produce. |
| **Work directories** | | | |
| `work_path` | `str` |  | Where jobs run. |
| `simulation_work_path` | `str` |  | Sub-directory of the work path for simulations. |
| `fmax_synthesis_work_path` | `str` |  | Sub-directory of the work path for Fmax synthesis. |
| `custom_freq_synthesis_work_path` | `str` |  | Sub-directory of the work path for fixed-frequency synthesis. |
| `pnr_work_path` | `str` |  | Sub-directory of the work path for place and route. |
| `analysis_work_path` | `str` |  | Sub-directory of the work path for analyses. |
| `workflow_work_path` | `str` |  | Sub-directory of the work path for workflows. |
| **Results** | | | |
| `result_path` | `str` |  | Where results are written. |
| **Resource guard** | | | |
| `resource_guard` | `any` |  | Whether running jobs are paused while the machine is overloaded. |
| `cpu_limit` | `any` |  | CPU usage (%) above which jobs are paused. |
| `mem_limit` | `any` |  | Memory usage (%) above which jobs are paused. |
| **Sessions** | | | |
| `session_access` | `str` |  | Who may use the sessions started in this workspace besides their owner: "user" (nobody, the default), "group" (the group of the workspace directory) or "other" (every user). Using a session is running commands as its owner. |

### `open_workspace(root='.', required=False)`

Open the workspace held by a directory (see `Workspace.open()`).

## Errors

### `WorkspaceError`

Derives from `Exception`.

Base class of every error raised by the workspace API.

### `NotFoundError`

Derives from `WorkspaceError`, `KeyError`.

An architecture, simulation, workflow, tool, domain... does not exist.

### `AlreadyExistsError`

Derives from `WorkspaceError`, `ValueError`.

The name asked for is already taken.

### `InvalidNameError`

Derives from `WorkspaceError`, `ValueError`.

The name asked for cannot be used on disk (empty, path separator, ...).

### `NotAWorkspaceError`

Derives from `WorkspaceError`, `ValueError`.

The directory holds no Odatix settings file.

### `InvalidSettingsError`

`InvalidSettingsError(message, path=None, key=None, hints=None)`

Derives from `WorkspaceError`, `ValueError`.

A settings file cannot be used as it is: it is missing, it is not valid
YAML, or it holds a value of the wrong kind.

This is what reading a file *for a run* raises. Reading one to edit it never
does: a file being written is allowed to be incomplete.

**Args:**

- `message` *(str)* — what is wrong, as told to a user.
- `path` *(str)* — the file it is wrong in.
- `key` *(str)* — the key it is wrong at, when it is about one key.
- `hints` *(list)* — what a user can do about it, one line each.

## Building blocks

### `Entry`

`Entry(workspace, root, name)`

One directory of a workspace, holding the definition of an architecture, a
simulation, a workflow or a tool.

| Attribute | What it is |
|---|---|
| `kind` | What this kind of entry is called in error messages. |
| `path` *(property)* | Path of the directory holding this entry. |
| `exists` *(property)* |  |

| Method | What it does |
|---|---|
| `require()` | Raise unless the entry exists on disk. Returns the entry, to be chained. |
| `create()` | Create the directory of this entry. Does nothing if it already exists. |
| `delete()` | Delete this entry and everything in its directory. |
| `rename(new_name)` | Rename this entry. The object keeps pointing at it under its new name. |
| `duplicate(new_name)` | Copy this entry under another name, and return the copy. |

### `Collection`

`Collection(workspace, path)`

The entries of one kind held by a workspace.

Iterating over a collection yields entry objects; `names()` gives their
names. Both `"MyArch" in ws.architectures` and
`ws.architectures["MyArch"]` work.

Supports `len(x)`, `"name" in x`, `x["name"]`, iteration.

| Attribute | What it is |
|---|---|
| `entry_class` | `Entry` |
| `path` *(property)* | Directory holding the entries of this collection. |
| `kind` *(property)* |  |

| Method | What it does |
|---|---|
| `names()` | Names of the entries, in natural order. |
| `get(name, default=None)` | The entry, or `default` when there is no such entry. |
| `entry(name)` | The entry of that name, whether or not it exists yet. Its settings are then the defaults, and saving it is what creates it: this is what an editor works on while a new entry is being filled in. |
| `exists(name)` |  |
| `create(name, **kwargs)` | Create an entry and return it. Raises if it already exists, so a creation never silently lands on someone else's directory. |
| `delete(name)` | Delete an entry. Deleting one that is already gone does nothing. |
| `rename(name, new_name)` | Rename an entry, and return it. |
| `duplicate(name, new_name)` | Copy an entry under another name, and return the copy. |

### `Setting`

`Setting(default=None, type='any', key=None, section=None, comment=None, style=None, when=None, skip_if_empty=False, doc=None, factory=None, alt_key=None, alt_comment=None, stored=True, comment_out=False)`

One key of a settings file.

**Args:**

- `default` — value used when the file does not define the key.
- `type` *(str | type)* — how the value is read and written. One of "any", "str", "int", "optional_int", "bool", "list", "str_list", "int_list", "dict", or a `Settings` subclass for a nested block.
- `key` *(str)* — name of the key in the file, when it differs from the attribute name.
- `section` *(str)* — title of the block this key opens. Rendered as a comment above it when Odatix generates the file.
- `comment` *(str)* — end-of-line comment, rendered the same way.
- `style` *(str)* — "yesno" to write booleans as Yes/No, "flow" to write a list inline as "[a, b]".
- `when` *(str)* — name of another (boolean) setting this key depends on, optionally prefixed with "!" to negate it. The key is only written when the condition holds, and is removed from the file when it stops holding, so mutually exclusive settings never coexist in a file.
- `alt_key` *(str)* — key the value is written under when the `when` condition does not hold, instead of being removed. This is how a workspace file remembers a value that is currently switched off.
- `alt_comment` *(str)* — end-of-line comment of that other key.
- `stored` *(bool)* — False for a setting that only exists in memory (a switch whose state is read back from which key the file uses, for instance). It is never written, but it is part of the settings.
- `skip_if_empty` *(bool)* — do not write the key at all when its value is empty.
- `comment_out` *(bool)* — for a list of names, written one per line: an entry taken out of the list is commented out where it is rather than deleted, and a commented-out entry put back is uncommented where it is. This is how a run settings file keeps the catalogue of commented-out entries its author keeps at hand.
- `doc` *(str)* — what the setting means, for the API documentation and the command line help.

| Method | What it does |
|---|---|
| `make_default()` | A fresh default value (never shared between two settings objects). |
| `coerce(value)` | Read a value of any origin (file, form field, user code) as this setting's type. |
| `dump(value)` | Turn a value into what is written in the file. |
| `is_empty(value)` |  |

### `Settings`

`Settings(**values)`

Derives from `_SettingsBase`.

Base class of every settings object of the workspace API.

Instances behave both as objects (`settings.rtl_path`) and as mappings
(`settings["rtl_path"]`, `dict(settings.items())`), so they can be
handed to code that expects either.

Setting an attribute the class does not declare raises AttributeError,
so that a misspelled setting is not silently left out of the file. A key it
does not declare is set as a mapping key, and kept in `extra`.

Supports `len(x)`, `"name" in x`, `x["name"]`, iteration.

| Attribute | What it is |
|---|---|
| `write_all_settings` | Former way of saying that a file spells every key out. A file Odatix generates always does; a file it updates only gets the keys of `required_keys` added to it, never a default nobody asked for. |
| `required_keys` | Keys written to a file that does not hold them, even at their default: the ones a reader of the file refuses to do without (a run settings file has to say whether to overwrite, ask and how many jobs to run). Any other key left at its default is not added to a file that never mentioned it. |
| `dropped_keys` | Keys a file may still hold, that are read but never written again. They are dropped from a file the next time it is saved, so that a settings file only ever shows the form that is documented. What such a key used to mean has to be carried over when the file is read, in `from_dict()`, or saving would lose it. |
| `replacement_key` | The key the dropped ones leave their place to, written where the first of them was rather than at the end of the file. |
| `moved_keys` | Keys the class does not declare, that `normalize()` may carry over into a declared one, as `(former key, key)` pairs. Once carried over (gone from `extra`), the key takes the place of the former one in the file. |

| Method | What it does |
|---|---|
| `specs()` *(classmethod)* | The declared settings, in file order. |
| `spec(name)` *(classmethod)* |  |
| `get(key, default=None)` |  |
| `keys()` |  |
| `values()` |  |
| `items()` |  |
| `update(values=None, **kwargs)` | Set several settings at once, from a mapping and/or keyword arguments. |
| `from_dict(data)` *(classmethod)* | Build a settings object from a plain mapping, keeping unknown keys in `extra`. |
| `to_dict(include_extra=True, skip_disabled=False)` | A plain mapping of the settings. *Args:* `include_extra` *(bool)* — include the keys the class does not declare.; `skip_disabled` *(bool)* — leave out the keys whose `when` condition does not hold, i.e. the ones that would not be written to file. |
| `copy()` |  |
| `file_keys()` | The keys the file these settings were read from actually holds. |

## What a run targets

### `JobRequest`

`JobRequest(text, entry, configuration, domains, has_configuration=True, notes=None)`

One entry of a run selection, read.

**Attributes:**

- `text` *(str)* — the entry as written, without its spaces.
- `entry` *(str)* — what holds the configurations, i.e. the architecture or the workflow ("counter").
- `configuration` *(str)* — the configuration selected ("08bits"). An entry that selects none names the entry itself, which is what running "the design with its parameters left alone" has always been written as.
- `path` *(str)* — "<entry>/<configuration>", the configuration file without its extension.
- `domains` *(list)* — the other parameter domains selected, each written "<domain>/<configuration>".
- `has_configuration` *(bool)* — whether a configuration was actually selected.
- `notes` *(list)* — what reading this entry has to tell the user.

| Attribute | What it is |
|---|---|
| `path` *(property)* | The configuration file of the main domain, without its extension. |
| `work_dirname` *(property)* | The directory this entry runs in, under the one named after its entry. The other domains are part of it: two runs of the same configuration with different domains are two different results. |

| Method | What it does |
|---|---|
| `display_name(target='', only_one_target=True)` | How this entry is named in what a run prints: the other domains between brackets, and the target too when a run has several of them. |
| `with_domains(domains)` | The same entry, targeting these parameter domains instead. |

### `Message`

`Message(level, text, hints=None)`

Something a user should be told about a selection.

`level` is one of "error", "warning", "note" or "tip", which is how Odatix
already names what it prints. `hints` are the lines that follow it.

### `parse_request(text, keep_extension_note=True)`

Read one entry of a selection.

**Args:**

- `text` *(str)* — the entry, e.g. "counter/08bits+corner/tt".
- `keep_extension_note` *(bool)* — report a configuration written with its ".txt" extension, which works but is not how it is meant to be written.

### `expand_selection(requests, root, messages=None)`

Turn a selection into the entries it stands for, resolving its wildcards
against what `root` holds.

**Args:**

- `requests` *(list)* — the selection, as written in a run settings file.
- `root` *(str)* — the directory holding the entries (the architectures of the workspace, or its workflows).
- `messages` *(list)* — appended with the `Message` objects the expansion produces. Errors do not stop it: what can be run is run, and what cannot is reported.

**Returns:**

- `list` — one string per entry, deduplicated. In natural order, unless the selection stands for more entries than `NATURAL_ORDER_LIMIT`, which are left in the order the wildcards produced them.

## Architectures

### `Architecture`

`Architecture(workspace, root, name)`

Derives from `Entry`.

One architecture of a workspace.

Its settings are those of its main parameter domain, so
`arch.settings` and `arch.domains.main.settings` are the same object,
and `arch.configs` are the configurations of that main domain.

| Attribute | What it is |
|---|---|
| `kind` | `'architecture'` |
| `settings_class` | Settings class of the main domain of this kind of instance. |
| `substitutes_in_commands` | Whether the value of a parameter domain is substituted into the commands this kind of instance runs, rather than into a file of its sources. A domain that substitutes nothing into a file ("use_parameters: no") is still a dimension of the sweep when it does -- which is what a workflow replacing "${domain}" in its tasks is made of. |
| `main_domain` *(property)* | The parameter domain this architecture carries itself. |
| `settings_path` *(property)* |  |
| `settings` *(property)* | The settings of this architecture, read from file on first access. |
| `domains` *(property)* | The parameter domains of this architecture, the main one first. |
| `configs` *(property)* | The configurations of the main parameter domain. |
| `attributes` *(property)* | How the configurations of each of its domains are read, as a `{domain: Attributes}` mapping (see `odatix.workspace.attributes`). |

| Method | What it does |
|---|---|
| `reload()` | Forget the settings held in memory and read them from file again. |
| `save(regenerate=False)` | Write the settings of this architecture back to its file. |
| `update(values=None, **kwargs)` | Change some settings and write them back, in one call. |
| `exclusions(applied=None)` | The combinations of its parameter domains this architecture does not have (see `odatix.workspace.exclusions`). *Args:* `applied` *(list)* — which kinds to apply -- `illegal` and `duplicate` when nothing says otherwise, a campaign being the one entitled to ask for `dominated` too. *Returns:* `ExclusionSet` — the rules, empty when the architecture declares none. |
| `parameter_domains()` | The configurations of every domain that actually uses parameters, as a `{domain: [configuration, ...]}` mapping. Domains that substitute nothing, and domains without configurations, are left out: they add no axis to the sweep. |
| `variable_combinations()` | The combinations of the variables this architecture substitutes into its commands (the variables of a file without a configuration template), each a list of `"variable/value"` selectors. Paired variables are zipped, the others crossed, as a run does. Empty without such variables. |
| `combinations(exclusions=True)` | Every configuration combination of this architecture, written the way a job selection names it: its parameter domains crossed with its variables (see `variable_combinations()`). This is the full sweep, every domain included -- what the selection `"<arch>/* + <domain>/* + ..."` runs, naming every domain. A selection that leaves a domain out (`"<arch>/*"`) does not sweep it: the sources keep the value written in them. *Args:* `exclusions` *(bool)* — leave out the combinations the architecture excludes (see `exclusions()`), as a run does. |
| `count_combinations(exclusions=True)` | How many configuration combinations this architecture amounts to: the length of `combinations()`, i.e. how many jobs the full sweep runs per target and frequency. |
| `preview_configurations()` | The configurations the rules of the main parameter domain describe, as a `{name: content}` mapping, without writing anything (see `ParameterDomain.preview_configurations()`; the other domains have their own, under `domains`). |
| `frequencies(target='', configuration='', tool='', flow='', mode='fmax', fallback=None)` | The frequencies this architecture is run at, for one of its configurations on one target (see `resolve_frequencies()`). |
| `generate_configurations(overwrite=False, clear=False, domains=None)` | Generate the configurations of the domains that are set to generate them, and return what was written, as a `{domain: [name, ...]}` mapping. *Args:* `overwrite` *(bool)* — replace configurations that already exist.; `clear` *(bool)* — delete the existing configurations of a domain first.; `domains` *(list)* — restrict the generation to these domains. |

### `ArchitectureCollection`

Derives from `Collection`.

The architectures of a workspace.

| Attribute | What it is |
|---|---|
| `entry_class` | `Architecture` |

### `ArchitectureSettings`

Derives from `WithVariables`, `Settings`.

Settings of an architecture ("<architecture>/_settings.yml"), which are also
the settings of its main parameter domain.

What the architecture says for a part of its jobs only lives in the
"overrides" section: an ordered list of rules, each selecting the jobs it
applies to by tool, flow, target and configuration, and holding whatever
those jobs should use instead ("constraints", "file_copy_*",
"fmax_synthesis", "fixed_freq_synthesis", or any other key of this file).
See `odatix.lib.overrides`. The section is not declared here, but it is
preserved: like any other key Odatix does not know about, it stays in the
file and in `settings.extra`.

| Attribute | What it is |
|---|---|
| `dropped_keys` | `('generate_configurations', 'generate_configurations_settings')` |
| `replacement_key` | `'configurations'` |
| `moved_keys` |  |

| Method | What it does |
|---|---|
| `normalize()` | Carry what the former keys hold over to the ones that replace them (see `WithVariables.normalize()`), the fmax bounds written before "fmax_synthesis" existed included (see `carry_over_legacy_bounds()`). |
| `frequencies(target='', configuration='', tool='', flow='', mode='fmax', fallback=None)` | The frequencies a run uses, for one configuration on one target (see `resolve_frequencies()`). |

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| **RTL generation** | | | |
| `generate_rtl` | `bool` | `False` | Whether the RTL is generated by a command instead of read from a directory. |
| `design_path` | `str` |  | Directory of the design sources the generation runs on. |
| `design_path_whitelist` | `list` |  | What to copy from the design directory. Everything, when empty. |
| `design_path_blacklist` | `list` |  | What not to copy from the design directory. |
| `generate_command` | `str` |  | Command that generates the RTL. |
| `generate_output` | `str` |  | Directory the command writes the RTL to. |
| **Source files** | | | |
| `rtl_path` | `str` |  | Directory holding the RTL of the design. |
| `top_level_file` | `str` |  | File holding the top level module. |
| `top_level_module` | `str` |  | Name of the top level module. |
| **Signals** | | | |
| `clock_signal` | `str` |  | Name of the clock signal of the top level. |
| `reset_signal` | `str` |  | Name of the reset signal of the top level. |
| `reset_active_low` | `any` |  | Whether the reset is active low. Guessed from its name when empty (rst_n, resetn, nreset). |
| **Delimiters for parameter files** | | | |
| `use_parameters` | `bool` | `False` | Whether the configurations of the main domain are substituted into a file. |
| `param_target_file` | `str` |  | File the parameters are written into. The top level file, when empty. |
| `start_delimiter` | `str` |  | Text after which the parameters are written. Escape sequences such as \n are supported. |
| `stop_delimiter` | `str` |  | Text before which the parameters are written. Escape sequences such as \n are supported. |
| `file_copy_enable` | `bool` | `False` | Whether an extra file is copied into each work directory. |
| `file_copy_source` | `str` |  | File to copy. |
| `file_copy_dest` | `str` |  | Where to copy it, in the work directory. |
| **Constraints** | | | |
| `constraints` | `list` |  | Constraint files read by the jobs of this architecture. Either file paths, or mappings with a "files" key and a "scope" among "synthesis", "pnr" and "all". |
| **Testbench** | | | |
| `testbench` | `Testbench` | `Testbench(top='', files=[], parameters={}, cycles=None, stimulus='', waves=None)` | Testbench of the design: "top", "files" and "parameters". Any simulation template runs it, unless the simulation names its own. |
| **Default frequencies (in MHz)** | | | |
| `fmax_synthesis` | `FrequencyBounds` | `FrequencyBounds(lower_bound=None, upper_bound=None)` | Bounds of the fmax binary search for this architecture. |
| `fixed_freq_synthesis` | `CustomFrequencies` | `CustomFrequencies(frequencies=[], list_append=False, lower_bound=None, upper_bound=None, step=None)` | Frequencies a fixed-frequency synthesis runs this architecture at (formerly "custom_freq_synthesis", still read). |
| **Configurations** | | | |
| `configurations` | `Configurations` | `Configurations(enabled=False, name='', template='', blacklist=[], constraints=[])` | Name and template the configurations of the main domain are built from. A list declares several rule sets, whose union the domain is. |
| **Variables** | | | |
| `variables` | `dict` |  | Definition of each variable, by name. Variables are the values the configurations are built from. An architecture with no template substitutes them as "${name}" into its commands instead. |
| **Attributes** | | | |
| `attributes` | `dict` |  | How to read values off the name or the content of the configurations of the main domain, so that exclusions can be written about hand-written ones. "defaults", "from_name", "from_content" and "values". See odatix.workspace.attributes. |
| **Exclusions** | | | |
| `exclusions` | `any` |  | Combinations of the parameter domains of this architecture that are not part of its design space. Each one has a "when", optionally a "require" naming what it should be instead, a "kind" among "illegal", "duplicate" and "dominated", and a "message". See odatix.workspace.exclusions. |

### `FrequencyBounds`

Derives from `Settings`.

The frequency range an fmax binary search runs in, in MHz.

A bound left unset falls back to the workspace default, so only the bounds
that are actually set are written.

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| `lower_bound` | `optional_int` |  | Lowest frequency tried, in MHz. |
| `upper_bound` | `optional_int` |  | Highest frequency tried, in MHz. |

### `CustomFrequencies`

Derives from `Settings`.

The frequencies a fixed-frequency synthesis runs at, in MHz.

They come as a list, as a range, or as both: a range is expanded and
appended to the list. A range whose step is missing, zero or "No" is off,
which is how a block keeps a range it does not currently use.

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| `frequencies` | `int_list` |  | Frequencies to synthesize at, in MHz. |
| `list_append` | `bool` | `False` | Whether this list adds to the one of the level above instead of replacing it. |
| `lower_bound` | `optional_int` |  | First frequency of the range, in MHz. |
| `upper_bound` | `optional_int` |  | Last frequency of the range, in MHz. |
| `step` | `any` |  | Step between two frequencies of the range, in MHz. "No" to use no range. |

## Parameter domains and configurations

### `MAIN_DOMAIN`

Name of the domain an instance carries itself, rather than in a subdirectory.

```python
MAIN_DOMAIN = '__main__'
```

### `ParameterDomain`

`ParameterDomain(instance, name='__main__')`

One parameter domain of an architecture or of a workflow.

| Attribute | What it is |
|---|---|
| `kind` | `'parameter domain'` |
| `is_main` *(property)* |  |
| `path` *(property)* | Directory holding the settings and the configurations of this domain. |
| `settings_path` *(property)* |  |
| `exists` *(property)* |  |
| `label` *(property)* | How the domain is named to a user: the instance's name for the main one. |
| `settings_class` *(property)* | The settings class of this domain: the instance's own for the main domain (an architecture's main settings file holds much more than a domain's), `DomainSettings` for the others. |
| `settings` *(property)* | The settings of this domain, read from file on first access and kept until `save()` or `reload()`. |
| `use_parameters` *(property)* | Whether this domain substitutes parameters into the design. A domain without a settings file substitutes nothing: there is nowhere for it to say where its parameters go. |
| `configs` *(property)* | The configurations of this domain. |
| `config_set` *(property)* | Everything this domain resolves to: what its rules describe, together with the configuration files it holds. Resolving is a computation, so what a domain holds can be asked for without anything having been generated first. A named domain says everything by declaring a single variable; the main one shares its settings file with the instance, whose variables may instead feed its commands, so there nothing is implied. |
| `attributes` *(property)* | How the configurations of this domain are read beyond their name (see `odatix.workspace.attributes`). This is what makes a hand-written configuration readable by an exclusion: a topology whose name says where its pipeline barriers are becomes `$config.stage_EX`, without a variable having to exist. |
| `describes_configurations` *(property)* | Whether this domain says how its configurations are built. |

| Method | What it does |
|---|---|
| `require()` |  |
| `reload()` | Forget the settings held in memory and read them from file again. |
| `save(regenerate=False)` | Write the settings of this domain back to its file, keeping the comments and the keys Odatix does not know about. |
| `update(values=None, **kwargs)` | Change some settings and write them back, in one call. |
| `resolve_configurations()` | The configurations of this domain, rules and files together. |
| `blacklisted_configurations()` | Rule-produced configurations excluded from runs but shown by the editor. |
| `configuration_names()` | The names of the configurations of this domain, in natural order. What the rules describe counts, whether or not it was ever written to disk: a sweep is over what the domain holds, not over what happens to have been generated. |
| `preview_configurations()` | The configurations the rules of this domain describe, as a `{name: content}` mapping, without writing anything. Returns an empty mapping when the domain describes none, i.e. when its configurations are only the files it holds. |
| `generate_configurations(overwrite=False, clear=False, prune=False)` | Write the configuration files this domain describes, and return the names written. Generating is no longer something to do before a run -- a run resolves what it needs on its own. It stays available for a workspace that would rather keep its configurations as files, to read them or to track them. *Args:* `overwrite` *(bool)* — take a configuration that was edited by hand back to what its rule says. Without it, edits are left alone.; `clear` *(bool)* — delete every existing configuration first, so that only what the rules describe is left.; `prune` *(bool)* — delete what an earlier generation left behind and the rules no longer describe -- never a file written by hand. |
| `create()` | Create the directory of this domain. |
| `delete()` | Delete this domain and its configurations. The main domain cannot be deleted. |
| `rename(new_name)` | Rename this domain. The main domain cannot be renamed. |
| `duplicate(new_name, instance=None)` | Copy this domain, under `instance` when given (so a domain can be copied from one architecture to another) or next to itself otherwise. Copying the main domain keeps only what a domain is made of: its configuration files and the settings a domain declares. The rest of an instance's main settings (its sources, its signals...) does not belong to a named domain. |

### `ParameterDomainCollection`

`ParameterDomainCollection(instance)`

The parameter domains of an architecture or of a workflow.

Iterating over it yields the main domain first, then the named ones in
natural order. `sub_names()` gives only the named ones, i.e. the
subdirectories that exist on disk.

Supports `len(x)`, `"name" in x`, `x["name"]`, iteration.

| Attribute | What it is |
|---|---|
| `main` *(property)* | The domain the instance carries itself. |

| Method | What it does |
|---|---|
| `sub_names()` | Names of the domains stored in a subdirectory, in natural order. |
| `names()` | Names of every domain, the main one first. |
| `get(name, default=None)` |  |
| `entry(name)` | The domain of that name, whether or not it exists yet. |
| `exists(name)` |  |
| `create(name, **settings)` | Create a named parameter domain, and return it. |
| `delete(name)` | Delete a domain. Deleting one that is already gone does nothing. |
| `rename(name, new_name)` |  |
| `duplicate(name, new_name, instance=None)` |  |
| `configs()` | The configuration files of every domain, as a `{domain: [name, ...]}` mapping -- what each `domain.configs` holds on disk. What the rules of a domain describe without having been written is not among them: see `configuration_names()`. |
| `configuration_names()` | The configurations of every domain, rules and files together, as a `{domain: [name, ...]}` mapping (see `ParameterDomain.configuration_names()`): what a run sweeps. |

### `DomainSettings`

Derives from `WithVariables`, `Settings`.

Settings of a named parameter domain ("<instance>/<domain>/_settings.yml").

A domain says where its parameters are written in the design, and how its
configurations are built -- when they are not simply written by hand, one
file each.

| Attribute | What it is |
|---|---|
| `dropped_keys` | `('generate_configurations', 'generate_configurations_settings')` |
| `replacement_key` | `'configurations'` |

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| **Delimiters for parameter files** | | | |
| `use_parameters` | `bool` | `True` | Whether the configurations of this domain are substituted into a file at all. |
| `param_target_file` | `str` |  | File the parameters are written into, relative to the design directory. |
| `start_delimiter` | `str` |  | Text after which the parameters are written. Escape sequences such as \n are supported. |
| `stop_delimiter` | `str` |  | Text before which the parameters are written. Escape sequences such as \n are supported. |
| **Configurations** | | | |
| `configurations` | `Configurations` | `Configurations(enabled=False, name='', template='', blacklist=[], constraints=[])` | Name and template the configurations of this domain are built from. A list declares several rule sets, whose union the domain is. |
| **Matching** | | | |
| `match` | `dict` |  | Which configuration is substituted for the ones this directory does not hold, by selector: a name, a pattern ("P*"), a regular expression ("/^M[0-9]+$/") or a condition on "$name" and "$value" ("$value > 7"). See odatix.workspace.selectors. |
| **Variables** | | | |
| `variables` | `dict` |  | Definition of each variable, by name. Variables are the values the configurations are built from. A domain with no template substitutes them as "${name}" into commands instead. |
| **Attributes** | | | |
| `attributes` | `dict` |  | How to read values off the name or the content of the configurations of this domain, so that exclusions can be written about hand-written ones. "defaults", "from_name", "from_content" and "values". See odatix.workspace.attributes. |

### `Configuration`

`Configuration(domain, name)`

One configuration file of a parameter domain.

The name never carries the ".txt" extension: that is a detail of how it is
stored, and every other part of Odatix (job selections, result files, work
directories) names a configuration without it.

| Attribute | What it is |
|---|---|
| `kind` | `'configuration'` |
| `filename` *(property)* |  |
| `path` *(property)* |  |
| `exists` *(property)* |  |
| `content` *(property)* |  |

| Method | What it does |
|---|---|
| `require()` |  |
| `read()` | The parameters held by this configuration, as text ("" when it does not exist). |
| `write(content)` | Replace the content of this configuration, creating it if needed. |
| `delete()` |  |
| `rename(new_name)` |  |
| `duplicate(new_name)` |  |

### `ConfigurationCollection`

`ConfigurationCollection(domain)`

The configurations of one parameter domain.

Supports `len(x)`, `"name" in x`, `x["name"]`, iteration.

| Attribute | What it is |
|---|---|
| `path` *(property)* |  |

| Method | What it does |
|---|---|
| `names()` | Configuration names, without extension, in natural order. |
| `filenames()` | Configuration file names, extension included. |
| `get(name, default=None)` |  |
| `exists(name)` |  |
| `create(name, content='')` | Create a configuration file. Raises if one of that name already exists. |
| `write(name, content='')` | Create or replace a configuration file. |
| `delete(name)` | Delete a configuration. Deleting one that is already gone does nothing. |
| `rename(name, new_name)` |  |
| `duplicate(name, new_name)` |  |
| `clear()` | Delete every configuration file of the domain. |

### `ConfigGeneration`

Derives from `Settings`.

The former way of describing the configurations of a domain
("generate_configurations_settings"), read but no longer written.

See `Configurations` for what replaces it.

`template` is the text substituted into the design and `name` the name given
to each generated configuration, both written with `${variable}`
placeholders.

The values behind those placeholders are the `variables` of the instance
or of the domain, declared at the root of its settings file, since they are
not specific to generation (see `WithVariables`). `variables` is
still read here, where it used to be declared, and is moved to the root the
next time the file is written.

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| `name` | `str` |  | Name given to each generated configuration, e.g. "${width}bits". |
| `template` | `any` |  | Text written in each generated configuration file. |
| `variables` | `dict` |  | Former location of the variables, read for backward compatibility. |
| `blacklist` | `list` |  | Generated configuration names excluded from runs. |
| `constraints` | `list` |  | Boolean expressions over the variables. |

### `combinations(domains_configs, arch_name)`

Expand a `{domain: [configuration, ...]}` mapping into the list of
configuration combinations it stands for, each written the way a job
selection names it ("<domain>/<configuration>", the main domain being named
after the architecture itself).

### `count_combinations(domains_configs)`

How many configurations the given `{domain: [configuration, ...]}` mapping
amounts to, i.e. the size of the cross product of its domains.

## What a design space does not hold

### `Attributes`

`Attributes(defaults=None, from_name=(), from_content=(), values=(), source='')`

How the configurations of one parameter domain are read.

**Attributes:**

- `defaults` *(dict)* — what every configuration of the domain has, before anything is read off it.
- `from_name` *(list)* — regular expressions matched against the name.
- `from_content` *(list)* — regular expressions matched against the content.
- `values` *(list)* — `[(selector, {attribute: value}), ...]`, written for the configurations a pattern cannot reach.
- `errors` *(list)* — the patterns that do not compile, as text.

| Attribute | What it is |
|---|---|
| `declared` *(property)* | Whether the block says anything at all. |

| Method | What it does |
|---|---|
| `of(name, content=None, variables=None)` | Everything known about one configuration. *Args:* `name` *(str)* — the name of the configuration.; `content` *(str)* — what is written in its file, when it is at hand.; `variables` *(dict)* — the values its rules produced it from, when rules did. *Returns:* `dict` — `{attribute: value}`, values already read as numbers. |

### `parse_attributes(settings, source='')`

The `attributes` block of a settings file, read.

**Args:**

- `settings` *(dict)* — content of a "_settings.yml".
- `source` *(str)* — path of that file, for error messages.

**Returns:**

- `Attributes` — the block, empty when the file declares none.

### `Exclusion`

`Exclusion(when='', require='', kind='illegal', message='', id='', source='')`

One rule of an `exclusions` block.

A point is rejected when `when` holds and, if a `require` is written,
that `require` does not.

| Attribute | What it is |
|---|---|
| `identifier` *(property)* | How the rule is named when a campaign turns it off, or a run reports it. |
| `valid` *(property)* | A rule that says nothing rejects nothing. |
| `id` | The name a campaign uses to turn the rule off ("" when unnamed). |
| `kind` | Why the points are out: `illegal`, `duplicate` or `dominated`. |
| `message` | The explanation shown when a point is rejected. |
| `require` | What those points must also satisfy ("" rejects them all). |
| `source` | Where the rule was written (a file, or a domain), for messages. |
| `when` | The condition that selects the points the rule is about. |

| Method | What it does |
|---|---|
| `rejects(values)` | Whether this rule takes one point out of the space. *Raises:* `ExpressionError` — one of its expressions could not be evaluated. |
| `pins()` | What the `require` of this rule fixes, when it is a plain equality -- `{name: value}`, empty when it is anything else. This is what makes a `duplicate` cheap to a search: rather than throwing away every point whose ignored parameter is not the canonical one, the point is moved to the canonical one, and the space keeps its density. |
| `describe()` | One line saying what this rule rules out, and why. |
| `to_dict()` |  |

### `ExclusionSet`

`ExclusionSet(rules=(), applied=None, ignored=(), source='')`

The exclusions that apply to one architecture, and which kinds of them a run
is applying.

**Attributes:**

- `rules` *(list)* — the rules, in declaration order.
- `applied` *(tuple)* — the kinds that are being applied.
- `ignored` *(set)* — the ids that are turned off.
- `errors` *(list)* — the rules that could not be evaluated, reported once.

Supports `len(x)`, iteration.

| Attribute | What it is |
|---|---|
| `empty` *(property)* |  |
| `declared_applied` | What the block itself said to apply, None when it said nothing -- which is what lets a campaign leave the choice to the architecture. |

| Method | What it does |
|---|---|
| `active()` | The rules a run is actually applying. |
| `merge(other)` | This set, plus what a campaign says on top of it. The rules add up -- a campaign may write an exclusion of its own -- and what the campaign says about which kinds to apply and which ids to ignore replaces what the architecture said, because that is the decision a campaign is entitled to make. |
| `with_kinds(applied)` | The same rules, applying the given kinds. |
| `check(values)` | Whether one point belongs to the space. *Args:* `values` *(dict)* — what the names of the expressions are worth, as `context()` builds it. *Returns:* `Excluded` — why the point is out, or None when it is in. A rule whose expression cannot be evaluated is reported once, and rejects nothing: a typo must not empty a space silently, and an exclusion is never the thing a run is about. |
| `take_errors()` | The evaluation errors gathered so far, cleared on the way out. |

### `parse_exclusions(settings, source='', applied=None)`

The `exclusions` block of a settings file, read.

Written as a list, it is the rules themselves. Written as a mapping, it also
says what to apply:

```python
exclusions:
  apply: [illegal, duplicate, dominated]
  ignore: [alu-share-adder-vs-bp]
  rules:
    - when: "..."
```

**Args:**

- `settings` *(dict)* — content of a settings file, or the block itself.
- `source` *(str)* — path of that file, for error messages.
- `applied` *(list)* — what to apply when the block does not say.

**Returns:**

- `ExclusionSet` — the block, empty when the file declares none.

### `ILLEGAL`

The design does not work.

```python
ILLEGAL = 'illegal'
```

### `DUPLICATE`

The design is the same hardware as another one.

```python
DUPLICATE = 'duplicate'
```

### `DOMINATED`

The design works, but another one beats it on every objective.

```python
DOMINATED = 'dominated'
```

## Simulations

### `Simulation`

`Simulation(workspace, root, name)`

Derives from `Entry`.

One simulation of a workspace.

| Attribute | What it is |
|---|---|
| `kind` | `'simulation'` |
| `settings_class` | `SimulationSettings` |
| `settings_path` *(property)* |  |
| `settings` *(property)* | The settings of this simulation, read from file on first access. |
| `architecture_entries` *(property)* | What this simulation says about the architectures it runs on. |
| `param_dirs` *(property)* | The configuration directories this simulation substitutes parameters from, in the order they are written and without repetition. |
| `domains` *(property)* | The configuration directories of this simulation, as parameter domains. |
| `metrics_path` *(property)* |  |
| `metrics` *(property)* | The metrics this simulation extracts from its runs. The same object on every access, like `settings`: what is set on it is what `metrics.save()` writes. |

| Method | What it does |
|---|---|
| `reload()` | Forget the settings held in memory and read them from file again. |
| `save(regenerate=False)` | Write the settings of this simulation back to its file. |
| `update(values=None, **kwargs)` | Change some settings and write them back, in one call. |

### `SimulationCollection`

Derives from `Collection`.

The simulations of a workspace.

| Attribute | What it is |
|---|---|
| `entry_class` | `Simulation` |

| Method | What it does |
|---|---|
| `templates()` | The simulation templates Odatix provides (ghdl, verilator, questa, ..., see odatix.sim.templates), which a run names like the simulations of the workspace, and which a simulation can start from. One that a simulation of the workspace has the name of is replaced by it, and is left out. |

### `SimulationDomainCollection`

Derives from `ParameterDomainCollection`.

The configuration directories a simulation substitutes parameters from.

A simulation has no parameter domains of its own: what it has are the
"param_dir" directories its architecture entries point at, one configuration
per value of the domain they override. They hold configuration files and
rules like an architecture's domains do, so they are presented as domains,
named by the path they are written as. There is no main domain: a simulation
directory is not a configuration directory.

| Attribute | What it is |
|---|---|
| `main` *(property)* | A simulation has no main domain. |

| Method | What it does |
|---|---|
| `names()` | Names of every domain, the main one first. |
| `sub_names()` | Names of the domains stored in a subdirectory, in natural order. |

### `SimulationSettings`

Derives from `Settings`.

Settings of a simulation ("<simulation>/_settings.yml").

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| **Template** | | | |
| `template` | `str` |  | Simulation template the simulation starts from (ghdl, verilator, questa, xsim, icarus, or a simulation of the workspace): its settings are the template's, merged with these. See odatix.sim.templates. |
| **Testbench** | | | |
| `testbench` | `Testbench` | `Testbench(top='', files=[], parameters={}, cycles=None, stimulus='', waves=None)` | Testbench the simulation runs: "top", "files" and "parameters". Without files, the architecture's testbench runs, else the files of "tb/", else a generated one. |
| **Architectures** | | | |
| `architectures` | `list` |  | Architectures this simulation runs on, and what it changes for each of them: a list of names, a name optionally holding "param_domains" (per-domain parameter substitution: "param_file" for the same parameters whichever configuration runs, "param_dir" for one configuration per value of the domain, and "combine" to say whether the substitution described there is done instead of the architecture's or as well as it) and "metrics_file" (the metrics file to extract with, instead of "_metrics.yml"). Names accept wildcards, "*" standing for every architecture, and entries matching the architecture under test are applied in the order they are written. Listing an architecture is an indication, not a restriction: running the simulation on one it does not list is allowed, and only prints a warning. |
| **Delimiters for parameter files (deprecated, use param_domains)** | | | |
| `use_parameters` | `any` |  | Deprecated. Whether the parameters of the architecture are substituted into the testbench. |
| `param_target_file` | `str` |  | Deprecated. File the parameters are written into. |
| `start_delimiter` | `str` |  | Deprecated. Text after which the parameters are written. Escape sequences such as \n are supported. |
| `stop_delimiter` | `str` |  | Deprecated. Text before which the parameters are written. Escape sequences such as \n are supported. |
| **Parameter override (deprecated, use param_domains)** | | | |
| `override_parameters` | `any` |  | Deprecated. Whether this simulation substitutes parameters of its own on top of the architecture's. |
| `override_param_file` | `str` |  | Deprecated. File holding the overriding parameters. |
| `override_param_target_file` | `str` |  | Deprecated. File they are written into. |
| `override_start_delimiter` | `str` |  | Deprecated. Text after which they are written. Escape sequences such as \n are supported. |
| `override_stop_delimiter` | `str` |  | Deprecated. Text before which they are written. Escape sequences such as \n are supported. |
| **Invariant parameter domains** | | | |
| `invariant_domains` | `any` |  | Parameter domains this simulation's result does not depend on. A list of domain names, or a mapping giving the value to run for each. |
| **Progress tracking** | | | |
| `progress` | `ProgressSettings` | `ProgressSettings(file='', regex='')` | How the run reports its progress to the monitor. |
| **Execution** | | | |
| `tasks` | `list` |  | What the simulation runs, as a task graph. Without it, "make sim" is run. |

## Workflows

### `Workflow`

`Workflow(workspace, root, name)`

Derives from `Architecture`.

One workflow of a workspace.

A workflow is swept exactly like an architecture (same parameter domains,
same configurations, same generation), so it is one here too; what differs
is its settings and the metrics file it carries.

| Attribute | What it is |
|---|---|
| `kind` | `'workflow'` |
| `settings_class` | `WorkflowSettings` |
| `substitutes_in_commands` | `True` |
| `metrics_path` *(property)* |  |
| `metrics` *(property)* | The metrics this workflow extracts from its runs. The same object on every access, like `settings`: what is set on it is what `metrics.save()` writes. |
| `tasks` *(property)* | The task graph of this workflow, as it is stored. |

| Method | What it does |
|---|---|
| `reload()` | Forget the settings and metrics held in memory and read them from file again. |

### `WorkflowCollection`

Derives from `ArchitectureCollection`.

The workflows of a workspace.

| Attribute | What it is |
|---|---|
| `entry_class` | `Workflow` |

### `WorkflowSettings`

Derives from `WithVariables`, `Settings`.

Settings of a workflow ("<workflow>/_settings.yml"), which are also the
settings of its main parameter domain.

| Attribute | What it is |
|---|---|
| `dropped_keys` | `('generate_configurations', 'generate_configurations_settings')` |
| `replacement_key` | `'configurations'` |

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| **Design sources (copied into each work directory)** | | | |
| `sources` | `SourcesSettings` | `SourcesSettings(path='', whitelist=[], blacklist=[])` | Where the files the workflow runs on come from. |
| **Delimiters for parameter files** | | | |
| `use_parameters` | `bool` | `True` | Whether the configurations of the main domain are substituted into a file. |
| `param_target_file` | `str` |  | File the parameters are written into. |
| `start_delimiter` | `str` |  | Text after which the parameters are written. Escape sequences such as \n are supported. |
| `stop_delimiter` | `str` |  | Text before which the parameters are written. Escape sequences such as \n are supported. |
| **Progress tracking** | | | |
| `progress` | `ProgressSettings` | `ProgressSettings(file='', regex='')` | How the run reports its progress to the monitor. |
| **Execution** | | | |
| `tasks` | `list` |  | What the workflow runs, as a task graph. Execution starts at the task named "main". |
| **Configurations** | | | |
| `configurations` | `Configurations` | `Configurations(enabled=False, name='', template='', blacklist=[], constraints=[])` | Name and template the configurations of the main domain are built from. A list declares several rule sets, whose union the domain is. |
| **Variables** | | | |
| `variables` | `dict` |  | Definition of each variable, by name. Variables are the values the configurations are built from. A workflow with no template substitutes them as "${name}" into its commands instead. |

## Tools and targets

### `Tool`

`Tool(workspace, root, name)`

Derives from `Entry`.

One EDA tool usable by a workspace.

A tool is either defined by the workspace, or shipped with Odatix. For a
built-in one, what the workspace holds is an overlay: `settings` is
what the overlay says, `builtin_settings` what Odatix ships, and
`effective_settings` what actually runs.

| Attribute | What it is |
|---|---|
| `kind` | `'tool'` |
| `settings_path` *(property)* |  |
| `metrics_path` *(property)* |  |
| `exists` *(property)* | A tool exists once it has a tool.yml, an empty directory is not one. |
| `builtin_dir` *(property)* | Directory of the built-in tool of that name, or None when there is none. |
| `is_builtin` *(property)* | True when Odatix ships a tool of this name. Whatever the workspace holds for it is then an overlay, never a tool of its own. |
| `has_overlay` *(property)* | True when the workspace holds something for this built-in tool. |
| `document` *(property)* | The workspace tool.yml of this tool, as plain values. |
| `builtin_document` *(property)* | The tool.yml Odatix ships for this tool, as plain values. |
| `effective_document` *(property)* | What actually runs, as plain values: the built-in definition with the workspace overlay applied on top, the way Odatix resolves it at run time. What an overlay says about the built-in flows is dropped, so this is what runs, not what was asked for. |
| `settings` *(property)* | The settings of this tool as they apply: its own for a workspace tool, the built-in definition with the workspace overlay on top for a built-in one. These are the settings to edit. Saving a built-in tool writes only what they add to (or differ from) the built-in definition, so putting a setting back to what Odatix says drops it from the workspace file instead of freezing it there. What the overlay holds on its own is `document`. |
| `builtin_settings` *(property)* | The tool.yml Odatix ships for this tool, or empty settings. |
| `resolved_document` *(property)* | What actually runs, the tool it extends included ("extends" in its tool.yml): that tool's resolved document, with this one's merged on top, the way Odatix resolves it at run time (see odatix.lib.eda_tools.load_tool_settings). Unlike `effective_document`, this is not what to edit: what a tool inherits belongs to the tool it extends. |
| `effective_settings` *(property)* | What actually runs (see `resolved_document`). |
| `metrics` *(property)* | The metrics this tool reads from its reports. |
| `targets` *(property)* | The synthesis targets this tool runs on. |

| Method | What it does |
|---|---|
| `reload()` |  |
| `save(as_overlay=None)` | Write this tool's file. A workspace tool is written whole. A built-in one gets an overlay holding only the flows added to it and the settings that differ from the built-in definition; an overlay left with nothing to say is removed rather than kept empty. *Args:* `as_overlay` *(bool)* — force one of the two, instead of choosing by whether Odatix ships a tool of this name. |
| `save_overlay(overrides, flows)` | Write the workspace overlay of a built-in tool from what it overrides and the flows it adds, without going through `settings`. |
| `update(values=None, **kwargs)` | Change some settings and write them back, in one call. |
| `delete()` | Delete the workspace directory of this tool (a built-in tool stays available). |

### `ToolCollection`

Derives from `Collection`.

The EDA tools of a workspace.

Only the tools the workspace defines are listed: what it holds for a
built-in tool is an overlay on it, not a tool of its own, so it is listed
with the built-in ones (`builtin_names()`).

Supports `x["name"]`, iteration.

| Attribute | What it is |
|---|---|
| `entry_class` | `Tool` |

| Method | What it does |
|---|---|
| `names()` | Names of the tools defined by this workspace. |
| `builtin_names()` | Names of the tools shipped with Odatix. |
| `all_names()` | Every tool usable by this workspace, built-in ones included. |
| `exists(name)` | True when the workspace defines this tool (built-in tools excluded). |
| `get(name, default=None)` | The entry, or `default` when there is no such entry. |
| `create(name, **settings)` | Create a workspace tool with a minimal tool.yml, and return it. |
| `import_builtin(name, new_name)` | Copy a built-in tool into the workspace under another name, so it can be edited as a tool of its own. The copy is the whole tool as it runs in this workspace: what Odatix ships (its tool.yml, scripts and metrics), with this workspace's changes to it merged in (flows added in its overlay, metrics completed or overridden, scripts added). Paths into the built-in tool's directory become paths into the copy's (`$tool_path`), so the copy runs its own scripts and reads its own metrics. Its target file is copied too, unless the tool names a target file of another tool ("target_file"). |
| `duplicate(name, new_name)` | Copy a tool of the workspace under another name, its target file included. A built-in tool is copied by `import_builtin()`. |

### `ToolSettings`

`ToolSettings(label='', description='', icon='', icon_filter=False, process_group=True, target_file='', default_metrics_file='', flows=None, format=None, extra=None, extends='')`

The settings of a tool, as its "tool.yml" describes them.

The file spreads the flows over three places (the default flow's commands
sit at the top level, "default_flow" names it, and "flows" holds the rest);
this object holds them as one list, the default flow first, and puts them
back where they belong on save.

| Attribute | What it is |
|---|---|
| `OWNED_KEYS` | Keys this class owns; anything else in the file is kept in `extra`. |
| `default_flow` *(property)* | The flow that runs when no other is asked for. |

| Method | What it does |
|---|---|
| `flow_names()` |  |
| `flow(name)` |  |
| `add_flow(name, label='', description='', icon='', metrics_file='', is_default=False)` | Add a flow to the tool, and return it. |
| `remove_flow(name)` |  |
| `set_default_flow(name)` |  |
| `from_dict(data)` *(classmethod)* | Read a tool, either as its "tool.yml" spells it out (the flows spread over "default_flow", the platform sections and "flows") or as this class hands it back (`to_dict()`, with the flows as one list). Both are accepted so that settings can be passed around without being pinned to the file layout. |
| `to_dict()` | The settings as plain values, in the canonical shape used by the editors. |
| `to_document(header=None)` | Build the full "tool.yml" of a workspace tool. The commands of the default flow are written in the top-level "unix"/"windows" sections, which is where Odatix reads them; every flow, the default one included, gets an entry under "flows" holding its metadata and, for the others, what it runs. |
| `overlay_overrides(builtin)` | What this workspace says about a built-in tool's settings: only the values that differ from the built-in definition, so a setting put back to what Odatix says drops out of the workspace file instead of being frozen into it. The flows are not part of it: the built-in ones belong to Odatix, and the added ones are written on their own. |

### `ToolFormat`

`ToolFormat(logs=None, tags=None, replace=None)`

How the output of a tool is read: which markers make a line an error or a
warning, which ones carry a tag, and what to rewrite in it.

| Method | What it does |
|---|---|
| `is_empty()` |  |
| `from_dict(data)` *(classmethod)* |  |
| `to_dict()` |  |
| `to_document(only_non_empty=False)` | The "format" section as it is written in a tool.yml. |

### `ToolMetrics`

`ToolMetrics(path)`

The metrics of a tool ("metrics.yml"), one mapping per job type plus the
common ones.

For a built-in tool, the file holds only what the workspace says about them:
the metrics it adds, the built-in ones it overrides, and, as entries mapped
to nothing, the built-in ones it removes.

| Attribute | What it is |
|---|---|
| `exists` *(property)* |  |
| `sections` *(property)* | The metric definitions, by section key. |

| Method | What it does |
|---|---|
| `reload()` |  |
| `section(section_key)` |  |
| `set(name, definition, section_key='metrics')` | Add or replace one metric of a section. |
| `remove(name, section_key='metrics')` |  |
| `to_dict()` |  |
| `save()` | Write the file back, keeping its comments and the keys it does not own. |

### `Flow`

`Flow(name, label='', description='', icon='', icon_filter=False, metrics_file='', is_default=False, platforms=None, parameters=None)`

One way of running a tool: a set of commands, per platform and job type.

| Method | What it does |
|---|---|
| `execution(job_type, platform='unix')` | What this flow runs for a job type on a platform. |
| `command(job_type, platform='unix')` | The command of a job type, or an empty list when it is not a plain command. |
| `steps(job_type, platform='unix')` | The steps of a job type, or an empty list when it is not run in steps. |
| `set_command(job_type, command, platform='unix')` | Make a job type run one command. Example: `flow = tool.settings.default_flow flow.set_command("tool_test", "mytool --version") flow.set_command("custom_freq_synthesis", "cd $work_path; python3 $tool_path/run.py")` *Args:* `job_type` *(str)* — one of `JOB_TYPES`: "tool_test" (the command checking the tool is installed, run before any job), "fmax_synthesis", "custom_freq_synthesis", "pnr" or "analysis".; `command` *(str \| list)* — the command, or its words; the words are joined with spaces. It may use the variables of the job ($work_path, $script_path, ...) and the parameters of the flow ($<name>).; `platform` *(str)* — "unix" or "windows". |
| `set_steps(job_type, steps, platform='unix', session=None)` | Make a job type run a sequence of resumable steps. Each step is a `{"name", "command", "default"}` mapping or a `Step`. Steps declaring `args` rather than a `command` are fragments of `session` (a `{"command", "begin", "end"}` mapping or a `Session`): the steps of a run then share one process of the tool. |
| `session(job_type, platform='unix')` | How a job type opens the tool, as a `Session`. |
| `inherit(job_type, platform='unix')` | Declare nothing for a job type, so the default flow's commands apply. |
| `from_dict(data)` *(classmethod)* |  |
| `to_dict()` |  |
| `declares_nothing()` | True when this flow says nothing of its own: no metadata, and not a single command or step, on any platform. Such a flow is what reading an empty file yields, and writing it back would only add noise. |

### `JobExecution`

`JobExecution(mode='inherit', command=None, steps=None, session=None)`

What one flow runs for one job type on one platform.

Three modes: "inherit" (nothing declared, the tool's default flow applies),
"command" (a single command) and "steps" (a sequence of resumable steps).
Steps declaring only what they add to the tool's session come with that
session.

| Method | What it does |
|---|---|
| `from_dict(data)` *(classmethod)* |  |
| `to_dict()` |  |

### `Step`

`Step(name, command=None, default=False, args=None)`

One resumable step of a job type.

A step runs either a whole command of its own, or only the arguments it adds
to the job type's session (see `Session`) — in which case the steps of
a run share a single process of the tool instead of one process each.

| Attribute | What it is |
|---|---|
| `in_session` *(property)* | Whether this step runs inside the job type's session. |
| `args` | What this step adds to the session, when it is a fragment of one. |
| `default` | Whether a run that is not told where to stop stops after this step. |

| Method | What it does |
|---|---|
| `from_dict(data)` *(classmethod)* |  |
| `to_dict()` |  |

### `Target`

`Target(name, enabled=True, script_copy_enable=False, script_copy_source='', original_name=None)`

One synthesis target of a tool.

A target that is not enabled is remembered but not run.

| Attribute | What it is |
|---|---|
| `original_name` | Name this target had in the file, so its settings follow a rename. |

| Method | What it does |
|---|---|
| `from_dict(data)` *(classmethod)* |  |
| `to_dict()` |  |
| `enable()` |  |
| `disable()` |  |

### `TargetFile`

`TargetFile(workspace, tool, target_path=None)`

The target file of one EDA tool.

Changes made through this object are held in memory until `save()`,
which rewrites the target list while leaving the rest of the file (its
comments, its constraint file, its install path, ...) as it was.

Supports `len(x)`, `"name" in x`, `x["name"]`, iteration.

| Attribute | What it is |
|---|---|
| `target_path` *(property)* |  |
| `fallback_path` *(property)* | Where a target file kept at the old default location is looked up. It belongs to the workspace, so it is resolved against it and never against the directory the caller happens to be in. |
| `path` *(property)* | Path of the target file, as Odatix resolves it: the name comes from the tool ("target_file" in its tool.yml), and an existing file found next to the workspace settings is edited where it is rather than moved. |
| `exists` *(property)* |  |
| `targets` *(property)* | The targets of the tool, in file order. |
| `constraint_file` *(property)* | File of the job directory that holds the clock constraint: Odatix writes it there as SDC before the job runs, then the scripts of a tool that sources `_common/init_script.tcl` rewrite it in the tool's own format. "constraints.sdc" when the file names none. |
| `tool_install_path` *(property)* | Installation directory of the tool; empty when it is on the PATH. |
| `force_single_thread` *(property)* | Whether the tool is asked to run on a single thread. |

| Method | What it does |
|---|---|
| `reload()` |  |
| `names()` |  |
| `enabled_names()` | Names of the targets the jobs of this tool actually run on. |
| `get(name, default=None)` |  |
| `exists_target(name)` |  |
| `add(name, enabled=True, script_copy_enable=False, script_copy_source='', save=True)` | Add a target and, unless told otherwise, write the file back. |
| `remove(name, save=True)` | Remove a target and its per-target settings. |
| `rename(name, new_name, save=True)` | Rename a target, carrying its per-target settings over. |
| `duplicate(name, new_name, save=True)` | Copy a target, per-target settings included. |
| `enable(name, save=True)` |  |
| `disable(name, save=True)` |  |
| `save()` | Write the target list back, keeping the comments and every other key of the file. Disabled targets are written as commented-out entries. Only what changed is written: a target added, removed, renamed, enabled or disabled changes its own line, and a setting changed by `update()` its own value, in the style the file writes it. |
| `settings()` | Everything the target file holds, as plain values. Useful to read the keys that belong to the tool rather than to the target list (its constraint file, its install path, ...). Changes made by `update()` and not saved yet are included. |
| `update(save=True, **values)` | Change the settings of the tool held by this file, and, unless told otherwise, write the file back. Example: `ws.targets["mytool"].update(constraint_file="constraints.sdc", tool_install_path="/opt/mytool")` *Args:* `constraint_file` *(str)* — file of the job directory holding the clock constraint.; `tool_install_path` *(str)* — installation directory of the tool; empty when it is on the PATH.; `force_single_thread` *(bool)* — run the tool on a single thread. |

### `TargetFileCollection`

`TargetFileCollection(workspace)`

The target files of a workspace, one per EDA tool: `ws.targets["vivado"]`.

Supports `"name" in x`, `x["name"]`, iteration.

| Method | What it does |
|---|---|
| `get(tool, default=None)` |  |
| `names()` | Tools this workspace has a target file for. |

## Metrics

### `MetricsFile`

`MetricsFile(path)`

The metrics definition file of a workflow or of a simulation.

`metrics` and `metadata` are read on first access and written back by
`save()`, which keeps the comments and the keys the API does not own.

| Attribute | What it is |
|---|---|
| `exists` *(property)* |  |
| `metrics` *(property)* | The metric definitions, by name. |
| `metadata` *(property)* | The extra result dimensions declared by the file, by name. |

| Method | What it does |
|---|---|
| `reload()` |  |
| `set(name, definition)` | Add or replace one metric definition. |
| `remove(name)` | Drop one metric definition. |
| `to_dict()` |  |
| `save()` | Write the file back, keeping its comments and anything else it holds. |
| `delete()` |  |

### `DerivedMetricsFile`

`DerivedMetricsFile(path)`

The derived metrics file of a workspace.

| Attribute | What it is |
|---|---|
| `exists` *(property)* |  |
| `groups` *(property)* | The groups the derived metrics are computed over, by name. |
| `metrics` *(property)* | The derived metric definitions, by name. |

| Method | What it does |
|---|---|
| `reload()` |  |
| `set(name, definition)` | Add or replace one derived metric. |
| `remove(name)` |  |
| `set_group(name, definition)` | Add or replace one group. |
| `remove_group(name)` |  |
| `to_dict()` |  |
| `save()` | Write the file back, keeping its comments and any top-level key the API does not own. |

## Cleaning

### `CleanSettingsFile`

`CleanSettingsFile(path, root=None)`

The clean settings file of a workspace.

| Attribute | What it is |
|---|---|
| `exists` *(property)* |  |
| `remove_list` *(property)* | The paths and glob patterns a clean removes, in file order. |
| `root` | The directory the patterns are relative to. |

| Method | What it does |
|---|---|
| `reload()` |  |
| `add(pattern)` | Add one pattern, unless the list already holds it. |
| `remove(pattern)` | Drop one pattern from the list. |
| `to_dict()` |  |
| `save()` | Write the file back, keeping its comments and any top-level key the API does not own. A file that does not exist yet is generated with the header Odatix puts on the files it writes. The list of a hand-written clean file is usually grouped by the tool that leaves each file behind, with a comment introducing every group, so the comments of the patterns that survive an edit are kept with them (see `_rebuild_remove_list()`). |
| `run(force=False, root=None)` | Remove everything the list matches. *Args:* `force` *(bool)* — remove even the patterns of `DANGEROUS_PATHS`.; `root` *(str)* — the directory the patterns are relative to. The workspace directory by default. *Returns:* `CleanResult` — what was removed, refused or failed. |

### `CleanResult`

`CleanResult()`

What a clean did.

**Attributes:**

- `removed` *(list)* — the `PathRemoval` of every path actually removed.
- `skipped` *(list)* — the ones refused because the pattern was dangerous.
- `errors` *(list)* — the ones that could not be removed.
- `unmatched` *(list)* — the resolved paths of the patterns that matched nothing at all.

| Attribute | What it is |
|---|---|
| `ok` *(property)* | Whether the clean went through without a single failure. |

| Method | What it does |
|---|---|
| `add(removal)` |  |
| `extend(other)` |  |
| `summary()` | A one line account of the clean, as the interfaces report it. |

### `PathRemoval`

`PathRemoval(path, kind='', status='removed', message='')`

What became of one path a clean tried to remove.

**Attributes:**

- `path` *(str)* — the path itself.
- `kind` *(str)* — "file", "directory" or "" when nothing was removed.
- `status` *(str)* — one of "removed", "skipped" (refused as dangerous) or "error".
- `message` *(str)* — why, for the statuses that are not "removed".

| Attribute | What it is |
|---|---|
| `removed` *(property)* |  |

### `DANGEROUS_PATHS`

The patterns that would wipe out the workspace, the home directory or the whole filesystem. They are only removed when a clean is explicitly forced.

```python
DANGEROUS_PATHS = ('/', './', './*', '*', '~', '.', '..')
```

### `remove_path(pattern, force=False, root=None)`

Remove everything one pattern of a clean list matches.

**Args:**

- `pattern` *(str)* — a path or glob pattern, resolved against `root`.
- `force` *(bool)* — remove even the patterns of `DANGEROUS_PATHS`.
- `root` *(str)* — the directory the pattern is relative to. The current one by default, which is where the Odatix commands run.

**Returns:**

- `CleanResult` — what was removed, refused or failed. A pattern matching nothing lands in `unmatched`, which is not an error: a workspace that was never run has nothing to clean.

## Runs

### `JOB_MODES`

The run commands of Odatix, with what their settings file is called in the workspace settings, what it holds, and how it is named to a user.

Keys: `fmax_synthesis`, `custom_freq_synthesis`, `pnr`, `simulation`, `workflow`, `analysis`.

### `JobConfig`

`JobConfig(workspace, mode, path)`

The settings file of one run command.

| Attribute | What it is |
|---|---|
| `label` *(property)* | How this run is named to a user. |
| `command` *(property)* | The Odatix command that reads this file. |
| `settings_class` *(property)* |  |
| `selection_key` *(property)* | The key holding what this run targets. |
| `exists` *(property)* |  |
| `settings` *(property)* | The settings of this run, read from file on first access. |
| `raw_selection` *(property)* | What the file holds under its selection key, exactly as written. Reading a selection this way keeps the difference between "no entry" (an empty list) and "the key is there but says nothing" (`None`), which is what the run flows report as an empty run settings file. |
| `selection` *(property)* | What this run targets, whatever the run calls it. |

| Method | What it does |
|---|---|
| `load()` | Read this run settings file the way a run needs it, and keep it. `settings` reads a file the way the graphical interface edits it: whatever it leaves out falls back on a default, and a file that does not exist yet is simply an empty configuration. A run cannot work like that, so this checks the file instead: it must exist, hold a mapping, spell out every key of `REQUIRED_KEYS` plus the one saying what to run, and give them values of the right kind. *Returns:* `Settings` — the settings of this run, also kept as `settings`. *Raises:* `InvalidSettingsError` — the file cannot be run from. |
| `reload()` |  |
| `save(regenerate=False)` | Write the settings of this run back to its file. |
| `update(values=None, **kwargs)` | Change some settings and write them back, in one call. |

### `JobConfigCollection`

`JobConfigCollection(workspace)`

The run settings files of a workspace, one per command:
`ws.jobs.fmax_synthesis`, `ws.jobs["simulation"]`, ...

Supports `"name" in x`, `x["name"]`, iteration.

| Method | What it does |
|---|---|
| `names()` |  |
| `get(mode, default=None)` |  |

### `JobSettings`

Derives from `Settings`.

What every run command reads, whatever it runs.

| Attribute | What it is |
|---|---|
| `required_keys` | `('overwrite', 'ask_continue', 'nb_jobs')` |

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| **Overwrite existing results** | | | |
| `overwrite` | `bool` | `False` | Whether results that already exist are run again. |
| **Prompt 'Continue? (Y/n)' after settings checks** | | | |
| `ask_continue` | `bool` | `True` | Whether the run stops for a confirmation once it knows what it will do. |
| **Exit monitor when all jobs are done** | | | |
| `exit_when_done` | `bool` | `False` | Whether the monitor closes by itself once every job is done. |
| **Size of the log history per job in the monitor** | | | |
| `log_size_limit` | `int` | `300` | How many log lines the monitor keeps per job. |
| **Maximum number of parallel jobs ('auto' = number of CPUs minus one)** | | | |
| `nb_jobs` | `any` | `8` | How many jobs run in parallel. An integer, or "auto". |
| **Force single thread execution (to avoid cpu overload when running many jobs in parallel)** | | | |
| `force_single_thread` | `bool` | `False` | Whether each job is asked to use a single thread. |

### `FmaxSynthesisJobSettings`

Derives from `JobSettings`.

Settings of an "odatix fmax" run.

| Attribute | What it is |
|---|---|
| `selection_key` | `'architectures'` |

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| **Overwrite existing results** | | | |
| `overwrite` | `bool` | `False` | Whether results that already exist are run again. |
| **Prompt 'Continue? (Y/n)' after settings checks** | | | |
| `ask_continue` | `bool` | `True` | Whether the run stops for a confirmation once it knows what it will do. |
| **Exit monitor when all jobs are done** | | | |
| `exit_when_done` | `bool` | `False` | Whether the monitor closes by itself once every job is done. |
| **Size of the log history per job in the monitor** | | | |
| `log_size_limit` | `int` | `300` | How many log lines the monitor keeps per job. |
| **Maximum number of parallel jobs ('auto' = number of CPUs minus one)** | | | |
| `nb_jobs` | `any` | `8` | How many jobs run in parallel. An integer, or "auto". |
| **Force single thread execution (to avoid cpu overload when running many jobs in parallel)** | | | |
| `force_single_thread` | `bool` | `False` | Whether each job is asked to use a single thread. |
| **Fmax binary search bounds (in MHz)** | | | |
| `fmax_synthesis` | `FmaxBoundsSettings` | `FmaxBoundsSettings(override=False, lower_bound=None, upper_bound=None)` | Bounds the binary search runs in. |
| **Targeted architectures** | | | |
| `architectures` | `any` |  | Architecture configurations to run, as "<architecture>/<configuration>". |

### `CustomFreqSynthesisJobSettings`

Derives from `JobSettings`.

Settings of an "odatix synth" run.

| Attribute | What it is |
|---|---|
| `selection_key` | `'architectures'` |

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| **Overwrite existing results** | | | |
| `overwrite` | `bool` | `False` | Whether results that already exist are run again. |
| **Prompt 'Continue? (Y/n)' after settings checks** | | | |
| `ask_continue` | `bool` | `True` | Whether the run stops for a confirmation once it knows what it will do. |
| **Exit monitor when all jobs are done** | | | |
| `exit_when_done` | `bool` | `False` | Whether the monitor closes by itself once every job is done. |
| **Size of the log history per job in the monitor** | | | |
| `log_size_limit` | `int` | `300` | How many log lines the monitor keeps per job. |
| **Maximum number of parallel jobs ('auto' = number of CPUs minus one)** | | | |
| `nb_jobs` | `any` | `8` | How many jobs run in parallel. An integer, or "auto". |
| **Force single thread execution (to avoid cpu overload when running many jobs in parallel)** | | | |
| `force_single_thread` | `bool` | `False` | Whether each job is asked to use a single thread. |
| **Synthesis frequencies (in MHz)** | | | |
| `frequencies` | `FrequenciesSettings` | `FrequenciesSettings(override=False, use_custom_freq_list=True, frequencies=[50, 100], use_custom_freq_range=True, range=FrequencyRange(start=50, stop=100, step=10))` | Frequencies the designs are synthesized at. |
| **Targeted architectures** | | | |
| `architectures` | `any` |  | Architecture configurations to run, as "<architecture>/<configuration>". |

### `PnrJobSettings`

Derives from `JobSettings`.

Settings of an "odatix pnr" run.

| Attribute | What it is |
|---|---|
| `selection_key` | `'sources'` |

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| **Overwrite existing results** | | | |
| `overwrite` | `bool` | `False` | Whether results that already exist are run again. |
| **Prompt 'Continue? (Y/n)' after settings checks** | | | |
| `ask_continue` | `bool` | `True` | Whether the run stops for a confirmation once it knows what it will do. |
| **Exit monitor when all jobs are done** | | | |
| `exit_when_done` | `bool` | `False` | Whether the monitor closes by itself once every job is done. |
| **Size of the log history per job in the monitor** | | | |
| `log_size_limit` | `int` | `300` | How many log lines the monitor keeps per job. |
| **Maximum number of parallel jobs ('auto' = number of CPUs minus one)** | | | |
| `nb_jobs` | `any` | `8` | How many jobs run in parallel. An integer, or "auto". |
| **Force single thread execution (to avoid cpu overload when running many jobs in parallel)** | | | |
| `force_single_thread` | `bool` | `False` | Whether each job is asked to use a single thread. |
| **Completed synthesis jobs to place & route, written
 <source_type>/<source_tool>[@<source_flow>]/<target>/<architecture>/<configuration>[@<frequency>MHz]
 with "*" accepted at every level** | | | |
| `sources` | `str_list` |  | Completed synthesis jobs to start from. |

### `SimulationJobSettings`

Derives from `JobSettings`.

Settings of an "odatix sim" run.

| Attribute | What it is |
|---|---|
| `selection_key` | `'simulations'` |

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| **Overwrite existing results** | | | |
| `overwrite` | `bool` | `False` | Whether results that already exist are run again. |
| **Prompt 'Continue? (Y/n)' after settings checks** | | | |
| `ask_continue` | `bool` | `True` | Whether the run stops for a confirmation once it knows what it will do. |
| **Exit monitor when all jobs are done** | | | |
| `exit_when_done` | `bool` | `False` | Whether the monitor closes by itself once every job is done. |
| **Size of the log history per job in the monitor** | | | |
| `log_size_limit` | `int` | `300` | How many log lines the monitor keeps per job. |
| **Maximum number of parallel jobs ('auto' = number of CPUs minus one)** | | | |
| `nb_jobs` | `any` | `8` | How many jobs run in parallel. An integer, or "auto". |
| **Force single thread execution (to avoid cpu overload when running many jobs in parallel)** | | | |
| `force_single_thread` | `bool` | `False` | Whether each job is asked to use a single thread. |
| **Targeted simulations** | | | |
| `simulations` | `any` |  | Simulations to run, each with the architecture configurations it runs on. |

### `WorkflowJobSettings`

Derives from `JobSettings`.

Settings of an "odatix workflow" run.

| Attribute | What it is |
|---|---|
| `selection_key` | `'workflows'` |

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| **Overwrite existing results** | | | |
| `overwrite` | `bool` | `False` | Whether results that already exist are run again. |
| **Prompt 'Continue? (Y/n)' after settings checks** | | | |
| `ask_continue` | `bool` | `True` | Whether the run stops for a confirmation once it knows what it will do. |
| **Exit monitor when all jobs are done** | | | |
| `exit_when_done` | `bool` | `False` | Whether the monitor closes by itself once every job is done. |
| **Size of the log history per job in the monitor** | | | |
| `log_size_limit` | `int` | `300` | How many log lines the monitor keeps per job. |
| **Maximum number of parallel jobs ('auto' = number of CPUs minus one)** | | | |
| `nb_jobs` | `any` | `8` | How many jobs run in parallel. An integer, or "auto". |
| **Force single thread execution (to avoid cpu overload when running many jobs in parallel)** | | | |
| `force_single_thread` | `bool` | `False` | Whether each job is asked to use a single thread. |
| **Targeted workflows** | | | |
| `workflows` | `any` |  | Workflow configurations to run, as "<workflow>/<configuration>". |

### `AnalysisJobSettings`

Derives from `JobSettings`.

Settings of an "odatix analyze" run.

| Attribute | What it is |
|---|---|
| `selection_key` | `'architectures'` |

Declared settings:

| Setting | Type | Default | What it is |
|---|---|---|---|
| **Overwrite existing results** | | | |
| `overwrite` | `bool` | `False` | Whether results that already exist are run again. |
| **Prompt 'Continue? (Y/n)' after settings checks** | | | |
| `ask_continue` | `bool` | `True` | Whether the run stops for a confirmation once it knows what it will do. |
| **Exit monitor when all jobs are done** | | | |
| `exit_when_done` | `bool` | `False` | Whether the monitor closes by itself once every job is done. |
| **Size of the log history per job in the monitor** | | | |
| `log_size_limit` | `int` | `300` | How many log lines the monitor keeps per job. |
| **Maximum number of parallel jobs ('auto' = number of CPUs minus one)** | | | |
| `nb_jobs` | `any` | `8` | How many jobs run in parallel. An integer, or "auto". |
| **Force single thread execution (to avoid cpu overload when running many jobs in parallel)** | | | |
| `force_single_thread` | `bool` | `False` | Whether each job is asked to use a single thread. |
| **Eda tools to run the analysis with** | | | |
| `tools` | `str_list` |  | EDA tools the RTL analysis runs with. |
| **Targeted architectures** | | | |
| `architectures` | `any` |  | Architecture configurations to run, as "<architecture>/<configuration>". |
| **Findings that are normal for these designs** | | | |
| `expected` | `any` |  | Findings that are normal for these designs, as {name: conditions}: they are reported apart and do not count (see odatix.lib.analysis.Expectation). |

---

## See also

- [`odatix.run`](/docs/python_api/run/) — running what a workspace describes.
- [Python API overview](/docs/python_api/) — the same API, told as a story.
- [Configuration file reference](/docs/reference/) — every file, every key.
- [Commands reference](/docs/commands/) — every command and its options.
