---
title: "API Reference"
description: "Every class, method and setting of odatix.workspace and odatix.run."
weight: 100
---

# API Reference

> [!IMPORTANT] Requires Odatix 4.0+

Every public name of **`odatix.workspace`** and **`odatix.run`**, what it does
and what it takes. The [Python API overview](/docs/python_api/) is the place to
start; this page is the one to come back to.

Both modules re-export everything worth using, so nothing below needs to be
imported from a submodule:

{{< code lang=python filename="imports.py" >}}
from odatix.workspace import Workspace, NotFoundError
from odatix.run import Run, RunError
{{< /code >}}

> [!NOTE]
> Every path is resolved against the workspace, never against the current
> directory, so an object obtained from a `Workspace` reads and writes the same
> files as the commands run from inside it.

---

## odatix.workspace

### `Workspace`

The entry point of the configuration API. Everything a user can configure hangs
off it.

| Constructor | |
|---|---|
| `Workspace(root=".", settings=None)` | Build a workspace on a directory, optionally with settings already in hand. |
| `Workspace.open(root=".", required=False)` | Open the workspace held by a directory. With `required=True`, raises `NotAWorkspaceError` when the directory holds no `odatix.yml`; without it, the Odatix defaults apply — which is what a directory about to be initialized looks like. |
| `Workspace.from_dict(settings, root=".")` | Open a workspace from settings already read, without reading the file again. |
| `Workspace.init(root=".", examples=False)` | Create the configuration files of a workspace and open it, as `odatix init` does. An existing configuration is overwritten. `examples=True` also copies the example designs. |

| Attribute | Type | What it is |
|---|---|---|
| `root` | `str` | The workspace directory. |
| `settings_file` | `str` | Path of `odatix.yml`. |
| `exists` | `bool` | Whether the directory actually holds a workspace. |
| `settings` | `dict` | The settings file, as plain values. Missing keys are *not* filled in: `paths` is what applies the defaults. |
| `paths` | `WorkspacePaths` | Where each part of the workspace is. |
| `architectures` | `ArchitectureCollection` | The [architectures](/docs/reference/architecture/). |
| `simulations` | `SimulationCollection` | The [simulations](/docs/reference/simulation/). |
| `workflows` | `WorkflowCollection` | The [workflows](/docs/reference/workflow/). |
| `tools` | `ToolCollection` | The [EDA tools](/docs/reference/tools/), built-in ones included. |
| `targets` | `TargetFileCollection` | The [target files](/docs/reference/targets/), one per tool. |
| `jobs` | `JobConfigCollection` | The [run settings files](/docs/reference/run_settings/), one per command. |
| `derived_metrics` | `DerivedMetricsFile` | The [derived metrics](/docs/reference/metrics/) of the workspace. |

| Method | What it does |
|---|---|
| `reload()` | Read the settings file again, and forget the resolved paths. |
| `save_settings(values=None, **kwargs)` | Write `odatix.yml`. Only the settings actually set are written: an empty file means "use the Odatix defaults". |
| `odatix_settings()` | The settings as an `OdatixSettings` object, for the parts of Odatix that take one. |

`Workspace.SETTINGS_FILENAME` is the name of the settings file (`odatix.yml`).

{{< code lang=python filename="workspace.py" >}}
from odatix.workspace import Workspace

ws = Workspace.open()                 # the workspace of the current directory
ws = Workspace.open("~/designs")      # another one
ws = Workspace.init("new_dir")        # create it, then open it

ws.save_settings(work_path="build", result_path="out")
{{< /code >}}

### `WorkspacePaths`

Where each part of a workspace is, the Odatix defaults applied. Every attribute
is a path resolved against the workspace directory.

| Group | Attributes |
|---|---|
| What is configured | `arch_path`, `sim_path`, `workflow_path`, `tools_path`, `target_path` |
| Where jobs run | `work_path`, and under it `simulation_work_path`, `fmax_synthesis_work_path`, `custom_freq_synthesis_work_path`, `pnr_work_path`, `analysis_work_path`, `workflow_work_path` |
| What runs produce | `result_path`, `benchmark_file`, `derived_metrics_file` |
| Run settings files | `fmax_synthesis_settings_file`, `custom_freq_synthesis_settings_file`, `pnr_settings_file`, `simulation_settings_file`, `workflow_settings_file`, `analysis_settings_file`, `clean_settings_file` |

| Method | What it does |
|---|---|
| `under_work_path(name)` | The work directory of one kind of job, e.g. `under_work_path("pnr_work_path")`. Those settings name a *sub-directory* of the work directory, so they are joined to it rather than resolved against the workspace. |
| `resolve(path)` | A workspace path as a path usable from anywhere. |
| `to_dict()` | Every path, by name. |

### `Entry`

One directory of a workspace, holding the definition of an architecture, a
simulation, a workflow or a tool. Base class of `Architecture`, `Simulation`,
`Workflow` and `Tool`.

| Member | What it is |
|---|---|
| `kind` | What this entry is called to a user (`"architecture"`, `"tool"`, …). |
| `name` | Its name, which is also its directory name. |
| `path` | Path of its directory. |
| `exists` | Whether it is on disk. |
| `require()` | Raise `NotFoundError` unless it exists. Returns the entry, to be chained. |
| `create()` | Create its directory. Does nothing when it is already there. |
| `delete()` | Delete it and everything in its directory. |
| `rename(new_name)` | Rename it. The object keeps pointing at it under its new name. |
| `duplicate(new_name)` | Copy it under another name, and return the copy. |

### `Collection`

The entries of one kind held by a workspace. Base class of
`ArchitectureCollection`, `SimulationCollection`, `WorkflowCollection` and
`ToolCollection`.

Collections behave like the mappings they are: `len(c)`, `"name" in c`,
`c["name"]` (raising `NotFoundError`, which is also a `KeyError`), and iteration
— which yields **entry objects**, not names.

| Member | What it does |
|---|---|
| `path` | Directory holding the entries. |
| `kind` | What one entry is called. |
| `names()` | Names of the entries, in natural order. |
| `get(name, default=None)` | The entry, or `default` when there is none. |
| `entry(name)` | The entry of that name, **whether or not it exists yet**. Its settings are then the defaults, and saving it is what creates it — this is what an editor works on while a new entry is being filled in. |
| `exists(name)` | Whether there is such an entry. |
| `create(name, **kwargs)` | Create an entry and return it. Raises `AlreadyExistsError` when the name is taken, so a creation never silently lands on someone else's directory. `kwargs` are settings applied to it. |
| `delete(name)` | Delete an entry. Raises when there is none. |
| `rename(name, new_name)` | Rename an entry, and return it. |
| `duplicate(name, new_name)` | Copy an entry under another name, and return the copy. |

{{< code lang=python filename="collections.py" >}}
"MyCPU" in ws.architectures
ws.architectures["MyCPU"]              # NotFoundError if there is none
ws.architectures.get("MyCPU")          # None instead
ws.architectures.entry("MyCPU")        # whether or not it exists yet

for architecture in ws.architectures:
    print(architecture.name, architecture.settings.top_level_module)
{{< /code >}}

### `Settings`

Base class of every settings object. Instances behave both as objects
(`settings.rtl_path`) and as mappings (`settings["rtl_path"]`,
`dict(settings.items())`), so they can be handed to code expecting either.

Values are read as their declared type whatever they come as: `"Yes"`, `true`
and `True` all mean the same thing, and `"50"` is stored as `50`.

| Member | What it does |
|---|---|
| `Settings(**values)` | Build a settings object, the unset keys taking their defaults. |
| `specs()` *(classmethod)* | The declared settings, in file order, as `{name: Setting}`. |
| `spec(name)` *(classmethod)* | One declaration. |
| `from_dict(data)` *(classmethod)* | Build from a plain mapping, keeping unknown keys in `extra`. |
| `get(key, default=None)`, `keys()`, `values()`, `items()` | The mapping interface. |
| `update(values=None, **kwargs)` | Set several settings at once. |
| `to_dict(include_extra=True, skip_disabled=False)` | A plain mapping. `skip_disabled=True` leaves out the keys whose `when` condition does not hold, i.e. the ones that would not be written. |
| `copy()` | An independent copy. |
| `extra` | Everything the file holds that the class does not declare. Never lost, never rewritten. |

### `Setting`

One declared key of a settings file. Reading the declarations is how a generic
editor — the graphical interface, a form generator — knows what a settings file
holds.

`Setting(default=None, type="any", key=None, section=None, comment=None,
style=None, when=None, skip_if_empty=False, doc=None, factory=None,
alt_key=None, alt_comment=None, stored=True)`

| Argument | What it says |
|---|---|
| `default` / `factory` | The value used when the file does not define the key. `factory` for mutable defaults, so two settings objects never share one. |
| `type` | How the value is read and written: `"any"`, `"str"`, `"int"`, `"optional_int"`, `"bool"`, `"list"`, `"str_list"`, `"int_list"`, `"dict"`, or a `Settings` subclass for a nested block. |
| `key` | Name of the key in the file, when it differs from the attribute name. |
| `section` | Title of the block this key opens, rendered as a comment above it in a generated file. |
| `comment` | End-of-line comment, rendered the same way. |
| `style` | `"yesno"` to write booleans as `Yes`/`No`, `"flow"` to write a list inline as `[a, b]`. |
| `when` | Name of another (boolean) setting this key depends on, optionally prefixed with `!` to negate it. The key is only written while the condition holds, and is removed when it stops holding, so mutually exclusive settings never coexist in a file. |
| `alt_key` / `alt_comment` | Key the value is written under when `when` does not hold, instead of being removed. This is how a file remembers a value that is currently switched off. |
| `stored` | `False` for a setting that only exists in memory (a switch whose state is read back from *which* key the file uses). It is never written, but it is part of the settings. |
| `skip_if_empty` | Do not write the key at all when its value is empty. |
| `doc` | What the setting means, used by this documentation and by the command line help. |

| Method | What it does |
|---|---|
| `make_default()` | A fresh default value. |
| `coerce(value)` | Read a value of any origin (file, form field, user code) as this setting's type. |
| `dump(value)` | Turn a value into what is written in the file. |
| `is_empty(value)` | Whether `skip_if_empty` would drop it. |

> [!NOTE]
> Saving a settings file keeps what you put in it: its comments, its key order,
> its quoting and every key Odatix does not know about. Only what actually
> changed is rewritten. A file that does not exist yet is generated with the
> section comments that make it readable.

---

## Architectures

### `Architecture`

One architecture of a workspace. Its settings are those of its **main parameter
domain**, so `arch.settings` and `arch.domains.main.settings` are the same
object, and `arch.configs` are the configurations of that main domain.

Everything of [`Entry`](#entry), plus:

| Member | What it is |
|---|---|
| `settings` | `ArchitectureSettings`, read from file on first access. Assignable. |
| `settings_path` | Path of its `_settings.yml`. |
| `settings_class` | `ArchitectureSettings`. |
| `main_domain` | The `ParameterDomain` the architecture carries itself. |
| `domains` | `ParameterDomainCollection` — the main domain first, then the named ones. |
| `configs` | `ConfigurationCollection` of the main domain. |
| `reload()` | Forget the settings held in memory and read them again. |
| `save(regenerate=False)` | Write the settings back. `regenerate=True` rewrites the whole file from scratch, section comments included. |
| `update(values=None, **kwargs)` | Change some settings and write them back, in one call. |
| `parameter_domains()` | `{domain: [configuration, …]}` for every domain that actually uses parameters. Domains that substitute nothing, and domains without configurations, are left out: they add no axis to the sweep. |
| `combinations()` | Every configuration combination, written the way a job selection names it. |
| `count_combinations()` | How many that amounts to. |
| `frequencies(target="", configuration="", mode="fmax", fallback=None)` | The frequencies this architecture is run at — see [`resolve_frequencies`](#resolve_frequencies). |
| `generate_configurations(overwrite=False, clear=False, domains=None)` | Generate the configurations of the domains set to generate them, returning `{domain: [name, …]}`. `overwrite` replaces existing ones, `clear` deletes them first, `domains` restricts which are generated. |

### `ArchitectureCollection`

The architectures of a workspace (`ws.architectures`). A [`Collection`](#collection)
of `Architecture`.

### `ArchitectureSettings`

Settings of an architecture — `<architecture>/_settings.yml`, which are also the
settings of its main parameter domain.

| Setting | Type | Default | What it says |
|---|---|---|---|
| `generate_rtl` | bool | `False` | Whether the RTL is generated by a command instead of read from a directory. |
| `design_path` | str | `""` | Directory of the design sources the generation runs on. *(when `generate_rtl`)* |
| `design_path_whitelist` | list | `[]` | What to copy from it. Everything, when empty. *(when `generate_rtl`)* |
| `design_path_blacklist` | list | `[]` | What not to copy from it. *(when `generate_rtl`)* |
| `generate_command` | str | `""` | Command that generates the RTL. *(when `generate_rtl`)* |
| `generate_output` | str | `""` | Directory the command writes the RTL to. *(when `generate_rtl`)* |
| `rtl_path` | str | `""` | Directory holding the RTL of the design. *(when not `generate_rtl`)* |
| `top_level_file` | str | `""` | File holding the top level module. |
| `top_level_module` | str | `""` | Name of the top level module. |
| `clock_signal` | str | `""` | Name of the clock signal of the top level. |
| `reset_signal` | str | `""` | Name of the reset signal of the top level. |
| `use_parameters` | bool | `False` | Whether the configurations of the main domain are substituted into a file. |
| `param_target_file` | str | `""` | File the parameters are written into. The top level file, when empty. |
| `start_delimiter` | str | `""` | Text after which the parameters are written. |
| `stop_delimiter` | str | `""` | Text before which the parameters are written. |
| `file_copy_enable` | bool | `False` | Whether an extra file is copied into each work directory. |
| `file_copy_source` | str | `""` | File to copy. *(when `file_copy_enable`)* |
| `file_copy_dest` | str | `""` | Where to copy it, in the work directory. *(when `file_copy_enable`)* |
| `fmax_synthesis` | `FrequencyBounds` | | Bounds of the fmax binary search for this architecture. |
| `custom_freq_synthesis` | `CustomFrequencies` | | Frequencies a custom frequency synthesis runs it at. |
| `generate_configurations` | bool | `False` | Whether the configurations of the main domain are generated from a template. |
| `generate_configurations_settings` | `ConfigGeneration` | | Template, name and variables they are generated from. |

Method: `frequencies(target="", configuration="", mode="fmax", fallback=None)`.

> [!NOTE]
> Frequency settings given **per target** — a mapping named after the target,
> holding its own `fmax_synthesis` and `custom_freq_synthesis` blocks — are not
> declared here, but they are preserved: like any other key Odatix does not
> know about, they stay in the file and in `settings.extra`.

### `FrequencyBounds`

The frequency range an fmax binary search runs in, in MHz. A bound left unset
falls back to the workspace default, so only the bounds actually set are
written.

| Setting | Type | Default |
|---|---|---|
| `lower_bound` | optional int | `None` |
| `upper_bound` | optional int | `None` |

### `CustomFrequencies`

The frequencies a custom frequency synthesis runs at, in MHz. They come as a
list, as a range, or as both — a range is expanded and appended to the list.

| Setting | Type | Default | What it says |
|---|---|---|---|
| `frequencies` | int list *(key `list`)* | `[]` | Frequencies to synthesize at. |
| `list_append` | bool | `False` | Whether this list adds to the one of the level above instead of replacing it. |
| `lower_bound` | optional int | `None` | First frequency of the range. |
| `upper_bound` | optional int | `None` | Last frequency of the range. |
| `step` | any | `None` | Step between two frequencies. A step that is missing, zero or `No` switches the range off, which is how a block keeps a range it does not currently use. |

### `resolve_frequencies`

`resolve_frequencies(settings, target="", configuration="", mode="fmax", fallback=None)`

The frequencies a run uses for one configuration of an architecture, once every
level of its settings file has had its say — global, then per target, then per
configuration. `mode` is `"fmax"` or `"custom_freq"`. Returns a
**`ResolvedFrequencies`**:

| Attribute | What it is |
|---|---|
| `lower_bound` / `upper_bound` | The bounds the fmax binary search tries. |
| `frequencies` | The frequencies a custom frequency synthesis runs at, the range expanded. |
| `deprecated_bounds` | The file still spells its bounds the old way (`fmax_lower_bound` instead of an `fmax_synthesis` block). |
| `messages` | What the file has that a user should know about, as [`Message`](#message) objects. |

### `check_bounds`

`check_bounds(lower_bound, upper_bound, step=0, kind="fmax synthesis")`

What is wrong with a frequency range, as a list of [`Message`](#message) — empty
when it can be run.

---

## Parameter domains and configurations

### `ParameterDomain`

One [parameter domain](/docs/configurations/param_domains/) of an architecture
or of a workflow.

| Member | What it is |
|---|---|
| `name` | Its name. `MAIN_DOMAIN` for the main one. |
| `is_main` | Whether it is the domain the instance carries itself. |
| `label` | How it is named to a user: the instance's name, for the main one. |
| `path` / `settings_path` | Its directory, and its `_settings.yml`. |
| `exists` / `require()` | Whether it is on disk. |
| `settings_class` | The instance's own settings class for the main domain (an architecture's main file holds much more than a domain's), `DomainSettings` for the others. |
| `settings` | Read from file on first access, kept until `save()` or `reload()`. Assignable. |
| `use_parameters` | Whether this domain substitutes parameters into the design. A domain without a settings file substitutes nothing: there is nowhere for it to say where its parameters go. |
| `configs` | `ConfigurationCollection` of this domain. |
| `save(regenerate=False)` | Write the settings back, keeping the comments and the unknown keys. |
| `update(values=None, **kwargs)` | Change some settings and write them back. |
| `reload()` | Read them from file again. |
| `preview_configurations()` | `{name: content}` the generation settings would produce, **writing nothing**. Empty when the domain does not generate its configurations, or when its generation settings are incomplete. |
| `generate_configurations(overwrite=False, clear=False)` | Generate the configuration files, and return the names written. |
| `create()` / `delete()` / `rename(new_name)` | The main domain can be neither deleted nor renamed. |
| `duplicate(new_name, instance=None)` | Copy this domain, under `instance` when given — so a domain can be copied from one architecture to another. Copying the *main* domain keeps only what a domain is made of: its configuration files and the settings a domain declares. |

### `ParameterDomainCollection`

The parameter domains of an architecture or of a workflow (`arch.domains`).
Iterating yields the main domain first, then the named ones in natural order.

| Member | What it does |
|---|---|
| `main` | The domain the instance carries itself. |
| `names()` | Every domain, the main one first. |
| `sub_names()` | Only the domains stored in a subdirectory. |
| `get(name, default=None)` / `exists(name)` | |
| `entry(name)` | The domain of that name, whether or not it exists yet. |
| `create(name, **settings)` | Create a named parameter domain, and return it. |
| `delete(name)` / `rename(name, new_name)` | |
| `duplicate(name, new_name, instance=None)` | |
| `configs()` | The configurations of every domain, as `{domain: [name, …]}`. |

`MAIN_DOMAIN` is the name Odatix gives the main domain.

### `DomainSettings`

Settings of a named parameter domain — `<instance>/<domain>/_settings.yml`.

| Setting | Type | Default | What it says |
|---|---|---|---|
| `use_parameters` | bool | `True` | Whether the configurations of this domain are substituted into a file at all. |
| `param_target_file` | str | `""` | File the parameters are written into, relative to the design directory. |
| `start_delimiter` | str | `""` | Text after which the parameters are written. |
| `stop_delimiter` | str | `""` | Text before which the parameters are written. |
| `generate_configurations` | bool | `False` | Whether the configurations are generated from a template. |
| `generate_configurations_settings` | `ConfigGeneration` | | Template, name and variables they are generated from. |

### `Configuration`

One configuration file of a parameter domain. The name never carries the `.txt`
extension: that is a detail of how it is stored, and every other part of Odatix
(job selections, result files, work directories) names a configuration without
it.

| Member | What it does |
|---|---|
| `name` / `filename` / `path` | |
| `exists` / `require()` | |
| `read()` | The parameters it holds, as text (`""` when it does not exist). |
| `write(content)` | Replace its content, creating it if needed. |
| `content` | The same, as a property. Assignable. |
| `delete()` / `rename(new_name)` / `duplicate(new_name)` | |

### `ConfigurationCollection`

The configurations of one parameter domain (`arch.configs`,
`domain.configs`).

| Member | What it does |
|---|---|
| `path` | The directory holding them. |
| `names()` | Configuration names, **without** extension, in natural order. |
| `filenames()` | Their file names, extension included. |
| `get(name, default=None)` / `exists(name)` | |
| `create(name, content="")` | Create a configuration. Raises when one of that name exists. |
| `write(name, content="")` | Create **or replace** one. |
| `delete(name)` / `rename(name, new_name)` / `duplicate(name, new_name)` | |
| `clear()` | Delete every configuration file of the domain. |

`CONFIG_EXTENSION` is `".txt"`; `configuration_names(path)` lists the
configurations held by a directory.

### `ConfigGeneration`

How the configurations of a domain are
[generated](/docs/configurations/config_generation/).

| Setting | Type | What it says |
|---|---|---|
| `name` | str | Name given to each generated configuration, e.g. `"${width}bits"`. |
| `template` | any | Text written in each generated configuration file. |
| `variables` | dict | Definition of each variable, by name. |

| Method | What it does |
|---|---|
| `set_variable(name, type, settings, format=None, group=None)` | Declare a variable, replacing any declaration of the same name. `type` is `"range"`, `"list"` or `"function"`; `settings` is what that type needs, e.g. `{"from": 1, "to": 8}` or `{"list": [1, 2, 4]}`. `format` is applied to the values; variables sharing a `group` are zipped together value by value instead of being crossed. |
| `remove_variable(name)` | |
| `variable_names()` | |

`variable_definition(name, type, settings, format=None, group=None)` builds a
single `{name: definition}` mapping, for callers assembling a generation block
themselves.

### `combinations`, `count_combinations`

- `combinations(domains_configs, arch_name)` — expand a
  `{domain: [configuration, …]}` mapping into the list of combinations it stands
  for, each written the way a job selection names it
  (`<domain>/<configuration>`, the main domain being named after the
  architecture itself).
- `count_combinations(domains_configs)` — how many that amounts to, i.e. the
  size of the cross product.

{{< code lang=python filename="domains.py" >}}
architecture.configs.write("08bits", "\n  parameter WIDTH = 8;\n")

width = architecture.domains.create("width", param_target_file="rtl/cpu.sv")
width.settings.start_delimiter = "#("
width.settings.stop_delimiter = ")"
width.settings.generate_configurations = True
width.settings.generate_configurations_settings.name = "${width}bits"
width.settings.generate_configurations_settings.template = "WIDTH = ${width}"
width.settings.generate_configurations_settings.set_variable(
    "width", "range", {"from": 8, "to": 64, "step": 8}
)
width.save()

width.preview_configurations()                  # {name: content}, writes nothing
width.generate_configurations(overwrite=True)
{{< /code >}}

---

## Simulations

### `Simulation`

One simulation of a workspace. Everything of [`Entry`](#entry), plus:

| Member | What it is |
|---|---|
| `settings` | `SimulationSettings`. Assignable. |
| `settings_path` | Its `_settings.yml`. |
| `metrics_path` / `metrics` | The [`MetricsFile`](#metricsfile) it extracts from its runs. |
| `save(regenerate=False)` / `update(values=None, **kwargs)` / `reload()` | |

### `SimulationCollection`

The simulations of a workspace (`ws.simulations`). A [`Collection`](#collection)
of `Simulation`.

### `SimulationSettings`

| Setting | Type | Default | What it says |
|---|---|---|---|
| `architectures` | list | `[]` | The [architectures](/docs/reference/simulation/#architectures) this simulation runs on, and what it changes for each of them (`param_domains`, `metrics_file`). Read and written with `odatix.workspace.sim_architectures`. |
| `use_parameters` | bool | `True` | Whether the parameters of the architecture are substituted into the testbench. |
| `param_target_file` | str | `""` | File they are written into. |
| `start_delimiter` | str | `""` | Text after which they are written. |
| `stop_delimiter` | str | `""` | Text before which they are written. |
| `override_parameters` | bool | `False` | Whether this simulation substitutes parameters of its own on top of the architecture's. |
| `override_param_file` | str | `""` | File holding the overriding parameters. *(when `override_parameters`)* |
| `override_param_target_file` | str | `""` | File they are written into. *(when `override_parameters`)* |
| `override_start_delimiter` | str | `""` | Text after which they are written. *(when `override_parameters`)* |
| `override_stop_delimiter` | str | `""` | Text before which they are written. *(when `override_parameters`)* |
| `invariant_domains` | any | `None` | Parameter domains this simulation's result does not depend on. A list of domain names, or a mapping giving the value to run for each. |
| `progress` | `ProgressSettings` | | How the run reports its progress to the monitor. |
| `tasks` | list | `[]` | What the simulation runs, as a task graph. Without it, `make sim` is run. |

### `ProgressSettings`

| Setting | Type | What it says |
|---|---|---|
| `file` | str | Log file the progress is read from. |
| `regex` | str | Pattern the percentage is read with. |

---

## Workflows

### `Workflow`

One workflow of a workspace. A workflow is swept exactly like an architecture —
same parameter domains, same configurations, same generation — so it **is** an
[`Architecture`](#architecture) here too; what differs is its settings and the
metrics file it carries.

| Member | What it is |
|---|---|
| everything of `Architecture` | `domains`, `configs`, `combinations()`, `generate_configurations()`, … |
| `settings` | `WorkflowSettings`. |
| `metrics_path` / `metrics` | The [`MetricsFile`](#metricsfile) it extracts from its runs. |
| `tasks` | Its task graph, as it is stored. Assignable. |

### `WorkflowCollection`

The workflows of a workspace (`ws.workflows`).

### `WorkflowSettings`

| Setting | Type | Default | What it says |
|---|---|---|---|
| `sources` | `SourcesSettings` | | Where the files the workflow runs on come from. |
| `use_parameters` | bool | `True` | Whether the configurations of the main domain are substituted into a file. |
| `param_target_file` | str | `""` | File they are written into. |
| `start_delimiter` | str | `""` | Text after which they are written. |
| `stop_delimiter` | str | `""` | Text before which they are written. |
| `progress` | `ProgressSettings` | | How the run reports its progress to the monitor. |
| `tasks` | list | `[]` | What the workflow runs, as a task graph. Execution starts at the task named `main`. |
| `generate_configurations` | bool | `False` | Whether the configurations of the main domain are generated from a template. |
| `generate_configurations_settings` | `ConfigGeneration` | | Template, name and variables. |

### `SourcesSettings`

| Setting | Type | What it says |
|---|---|---|
| `path` | str | Directory copied into each work directory. |
| `whitelist` | list | What to copy from it. |
| `blacklist` | list | What not to copy from it. |

---

## EDA tools

### `Tool`

One EDA tool usable by a workspace. A tool is either **defined by the
workspace**, or **shipped with Odatix**. For a built-in one, what the workspace
holds is an *overlay*.

Everything of [`Entry`](#entry), plus:

| Member | What it is |
|---|---|
| `exists` | A tool exists once it has a `tool.yml`; an empty directory is not one. |
| `is_builtin` | Whether Odatix ships a tool of this name. Whatever the workspace holds for it is then an overlay, never a tool of its own. |
| `has_overlay` | Whether the workspace holds something for this built-in tool. |
| `builtin_dir` | Directory of the built-in tool of that name, or `None`. |
| `settings_path` / `metrics_path` | Its `tool.yml` and its `metrics.yml`. |
| `settings` | `ToolSettings` **as they apply**: its own for a workspace tool, the built-in definition with the workspace overlay on top for a built-in one. These are the settings to edit. Assignable. |
| `builtin_settings` | What Odatix ships, or empty settings. |
| `effective_settings` | What actually runs. |
| `document` | The workspace `tool.yml`, as plain values. |
| `builtin_document` | The `tool.yml` Odatix ships. |
| `effective_document` | What actually runs, as plain values: the built-in definition with the overlay applied on top, the way Odatix resolves it at run time. What an overlay says about the *built-in flows* is dropped, so this is what runs, not what was asked for. |
| `metrics` | The [`ToolMetrics`](#toolmetrics) it reads from its reports. |
| `targets` | The [`TargetFile`](#targetfile) it runs on. |
| `save(as_overlay=None)` | Write the tool's file. A workspace tool is written whole; a built-in one gets an overlay holding only the flows added to it and the settings that differ from the built-in definition. An overlay left with nothing to say is removed rather than kept empty. `as_overlay` forces one of the two. |
| `save_overlay(overrides, flows)` | Write the overlay of a built-in tool from what it overrides and the flows it adds, without going through `settings`. |
| `update(values=None, **kwargs)` | Change some settings and write them back. |
| `delete()` | Delete the workspace directory. A built-in tool stays available. |
| `reload()` | |

> [!NOTE]
> Saving a built-in tool writes only what differs from the built-in definition,
> so putting a setting back to what Odatix says **drops it** from the workspace
> file instead of freezing it there.

### `ToolCollection`

The EDA tools of a workspace (`ws.tools`). Only the tools the workspace
*defines* are listed by `names()`: what it holds for a built-in tool is an
overlay on it, not a tool of its own.

| Member | What it does |
|---|---|
| `names()` | Tools defined by this workspace. |
| `builtin_names()` | Tools shipped with Odatix. |
| `all_names()` | Every tool usable by this workspace. |
| `exists(name)` | Whether the workspace defines it (built-in tools excluded). |
| `get(name, default=None)` | |
| `create(name, **settings)` | Create a workspace tool with a minimal `tool.yml`, and return it. |
| `import_builtin(name, new_name)` | Copy a built-in tool into the workspace under another name, so it can be edited as a tool of its own. |

### `ToolSettings`

The settings of a tool, as its `tool.yml` describes them. The file spreads the
flows over three places — the default flow's commands sit at the top level,
`default_flow` names it, and `flows` holds the rest. This object holds them as
**one list**, the default flow first, and puts them back where they belong on
save.

`ToolSettings(label="", description="", icon="", process_group=True,
report_path="", target_file="", default_metrics_file="", flows=None,
format=None, extra=None)`

| Member | What it is |
|---|---|
| `label`, `description`, `icon` | How the tool is presented. |
| `process_group` | Whether the jobs of this tool run in a process group of their own. |
| `report_path` | Where the tool writes the reports the metrics are read from. |
| `target_file` | Name of its target file. |
| `default_metrics_file` | Metrics file used when a flow names none. |
| `format` | A [`ToolFormat`](#toolformat). |
| `extra` | Everything the file holds that the class does not own. |
| `default_flow` | The [`Flow`](#flow) that runs when no other is asked for. |
| `flow_names()` / `flow(name)` | |
| `add_flow(name, label="", description="", icon="", metrics_file="", is_default=False)` | Add a flow, and return it. |
| `remove_flow(name)` / `set_default_flow(name)` | |
| `from_dict(data)` *(classmethod)* | Read a tool, either as its `tool.yml` spells it out or as `to_dict()` hands it back. Both are accepted, so settings can be passed around without being pinned to the file layout. |
| `to_dict()` | The settings as plain values, in the canonical shape used by the editors. |
| `to_document(header=None)` | Build the full `tool.yml` of a workspace tool. |
| `overlay_overrides(builtin)` | Only the values that differ from a built-in definition. The flows are not part of it: the built-in ones belong to Odatix, and the added ones are written on their own. |

`OVERRIDABLE_KEYS` lists what an overlay may override; `PLATFORMS` is
`("unix", "windows")`.

`overlay_document(name, overrides, flows, header=None)` builds the workspace
overlay of a built-in tool: the flows it adds and the settings it overrides,
nothing of the built-in flows.

### `Flow`

One way of running a tool: a set of commands, per platform and job type.

`Flow(name, label="", description="", icon="", metrics_file="",
is_default=False, platforms=None)`

| Method | What it does |
|---|---|
| `execution(job_type, platform="unix")` | The [`JobExecution`](#jobexecution) of a job type. |
| `command(job_type, platform="unix")` | Its command, or an empty list when it is not a plain command. |
| `steps(job_type, platform="unix")` | Its [steps](#step), or an empty list when it is not run in steps. |
| `set_command(job_type, command, platform="unix")` | Make a job type run one command. |
| `session(job_type, platform="unix")` | How it opens the tool, as a [`Session`](#session). |
| `set_steps(job_type, steps, platform="unix", session=None)` | Make it run a sequence of resumable steps. Each step is a `{"name", "command", "default"}` mapping or a `Step`; steps declaring `args` are fragments of `session`. |
| `inherit(job_type, platform="unix")` | Declare nothing, so the default flow's commands apply. |
| `from_dict(data)` / `to_dict()` | |
| `declares_nothing()` | True when the flow says nothing of its own — no metadata, and not a single command or step on any platform. Such a flow is what reading an empty file yields, and writing it back would only add noise. |

`JOB_TYPES` is `("tool_test", "fmax_synthesis", "custom_freq_synthesis", "pnr",
"analysis")`; `STEPPED_JOB_TYPES` are the ones that can be split into steps
(every one but `tool_test`).

### `JobExecution`

What one flow runs for one job type on one platform. Three modes:

| Mode | Meaning |
|---|---|
| `"inherit"` | Nothing declared: the tool's default flow applies. |
| `"command"` | A single command. |
| `"steps"` | A sequence of resumable steps. |

`JobExecution(mode="inherit", command=None, steps=None, session=None)`, with
`from_dict()` and `to_dict()`.

### `Step`

One resumable step of a job type: `Step(name, command=None, default=False,
args=None)`, with `from_dict()` and `to_dict()`.

A step declares either the whole `command` it runs — it is then a process of its
own — or the `args` it adds to the job type's session, in which case
`in_session` is true and the steps of a run share a single process of the tool.

### `Session`

How a job type opens the tool, once for all the steps of a run:
`Session(command=None, begin=None, end=None)`, with `declares_nothing()`,
`from_dict()` and `to_dict()`. What the steps add is run between `begin` and
`end`.

### `ToolFormat`

How the output of a tool is read: which markers make a line an error or a
warning, which ones carry a tag, and what to rewrite in it.

`ToolFormat(logs=None, tags=None, replace=None)`, with `is_empty()`,
`from_dict()`, `to_dict()` and `to_document(only_non_empty=False)`.

### `ToolMetrics`

The metrics of a tool (`metrics.yml`), one mapping per job type plus the common
ones. For a built-in tool, the file holds only what the workspace says about
them: the metrics it adds, the built-in ones it overrides, and — as entries
mapped to nothing — the built-in ones it removes.

| Member | What it does |
|---|---|
| `exists` | |
| `sections` | The metric definitions, by section key. Assignable. |
| `section(section_key)` | One section. |
| `set(name, definition, section_key="metrics")` | Add or replace one metric. |
| `remove(name, section_key="metrics")` | |
| `to_dict()` / `reload()` | |
| `save()` | Write the file back, keeping its comments and the keys it does not own. |

Section keys are `fmax_synthesis_metrics`, `custom_freq_synthesis_metrics`,
`pnr_metrics` and `metrics` (the common ones), listed by `METRIC_SECTIONS`.

{{< code lang=python filename="tools.py" >}}
tool = ws.tools["vivado"]
tool.is_builtin                              # True
tool.settings.flow_names()                   # ["standard", "power_opt"]
tool.settings.default_flow.command("fmax_synthesis")

tool.settings.label = "Vivado 2024.1"
tool.save()                                  # writes only what differs

own = ws.tools.create("my_tool", label="My Tool")
own.settings.default_flow.set_command("fmax_synthesis", ["make fmax"])
own.save()
{{< /code >}}

---

## Targets

### `Target`

One synthesis target of a tool. A target that is not enabled is remembered but
not run.

`Target(name, enabled=True, script_copy_enable=False, script_copy_source="",
original_name=None)`, with `enable()`, `disable()`, `from_dict()` and
`to_dict()`.

### `TargetFile`

The target file of one EDA tool (`ws.targets["vivado"]`, `tool.targets`).
Changes are held in memory until `save()`, which rewrites the target list while
leaving the rest of the file — its comments, its constraint file, its install
path — as it was.

| Member | What it does |
|---|---|
| `path` | Path of the target file, as Odatix resolves it: the name comes from the tool (`target_file` in its `tool.yml`), and an existing file found at the old default location next to the workspace settings is edited where it is rather than moved. |
| `target_path` / `fallback_path` | The two places it is looked up in. |
| `exists` | |
| `targets` | The targets, in file order. Assignable. |
| `names()` | Every target name. |
| `enabled_names()` | The ones the jobs of this tool actually run on. |
| `get(name, default=None)` / `exists_target(name)` | |
| `add(name, enabled=True, script_copy_enable=False, script_copy_source="", save=True)` | Add a target and, unless told otherwise, write the file back. |
| `remove(name, save=True)` | Remove a target and its per-target settings. |
| `rename(name, new_name, save=True)` | Rename it, carrying its per-target settings over. |
| `duplicate(name, new_name, save=True)` | Copy it, per-target settings included. |
| `enable(name, save=True)` / `disable(name, save=True)` | |
| `save()` | Write the target list back. Disabled targets are written as commented-out entries. |
| `settings()` | Everything the file holds, as plain values — useful to read the keys that belong to the tool rather than to the target list. |
| `reload()` | |

### `TargetFileCollection`

The target files of a workspace, one per EDA tool (`ws.targets`). Supports
`ws.targets["vivado"]`, `get(tool, default=None)` and `names()` — the tools this
workspace has a target file for.

---

## Metrics

### `MetricsFile`

The metrics definition file (`_metrics.yml`) of a workflow or of a simulation.
`metrics` and `metadata` are read on first access and written back by `save()`,
which keeps the comments and the keys the API does not own.

| Member | What it does |
|---|---|
| `exists` | |
| `metrics` | The metric definitions, by name. Assignable. |
| `metadata` | The extra result dimensions declared by the file, by name. Assignable. |
| `set(name, definition)` / `remove(name)` | |
| `to_dict()` / `reload()` / `save()` / `delete()` | |

### `DerivedMetricsFile`

The [derived metrics](/docs/metrics/) file of a workspace
(`ws.derived_metrics`).

| Member | What it does |
|---|---|
| `exists` | |
| `metrics` | The derived metric definitions, by name. Assignable. |
| `groups` | The groups they are computed over, by name. Assignable. |
| `set(name, definition)` / `remove(name)` | |
| `set_group(name, definition)` / `remove_group(name)` | |
| `to_dict()` / `reload()` / `save()` | |

---

## Run settings files

### `JobConfigCollection`

The run settings files of a workspace, one per command (`ws.jobs`). Reachable by
attribute (`ws.jobs.fmax_synthesis`) or by key (`ws.jobs["simulation"]`), and
iterable.

| Member | What it does |
|---|---|
| `names()` | The run modes. |
| `get(mode, default=None)` | |

### `JobConfig`

The settings file of one run command.

| Member | What it is |
|---|---|
| `mode` | The run mode this file belongs to. |
| `label` | How this run is named to a user. |
| `command` | The Odatix command that reads this file (`fmax`, `sim`, …). |
| `settings_class` | The `JobSettings` subclass of this mode. |
| `selection_key` | The key holding what this run targets (`architectures`, `simulations`, `workflows`, `sources`). |
| `path` / `exists` | |
| `settings` | Read from file on first access, the way the graphical interface edits it: what it leaves out falls back on a default, and a file that does not exist yet is simply an empty configuration. Assignable. |
| `selection` | What this run targets, whatever the run calls it. Assignable. |
| `raw_selection` | What the file holds under its selection key, **exactly as written**. Reading it this way keeps the difference between "no entry" (an empty list) and "the key is there but says nothing" (`None`), which is what the run flows report as an empty run settings file. |
| `load()` | Read the file **the way a run needs it**, and keep it. The file must exist, hold a mapping, spell out every key of `REQUIRED_KEYS` plus the one saying what to run, and give them values of the right kind. Returns the settings; raises `InvalidSettingsError` when the file cannot be run from. |
| `save(regenerate=False)` / `update(values=None, **kwargs)` / `reload()` | |

`REQUIRED_KEYS` is `("overwrite", "ask_continue", "nb_jobs")`.

`job_config(path, mode="fmax_synthesis")` builds a run settings file worked on
**by path**, outside of a workspace — a temporary file a run is started from,
for instance.

### `JOB_MODES`

The run modes, each with its label, its settings class, the workspace setting
naming its file, and the command that reads it.

| Mode | Command | Settings class |
|---|---|---|
| `fmax_synthesis` | `odatix fmax` | `FmaxSynthesisJobSettings` |
| `custom_freq_synthesis` | `odatix synth` | `CustomFreqSynthesisJobSettings` |
| `pnr` | `odatix pnr` | `PnrJobSettings` |
| `analysis` | `odatix analyze` | `AnalysisJobSettings` |
| `simulation` | `odatix sim` | `SimulationJobSettings` |
| `workflow` | `odatix workflow` | `WorkflowJobSettings` |

The short names of the commands (`fmax`, `synth`, `sim`, `analyze`, …) are
accepted wherever a mode is: `resolve_mode(mode)` gives the canonical one.

### `JobSettings`

What every run command reads, whatever it runs. Base class of all the settings
below.

| Setting | Type | Default | What it says |
|---|---|---|---|
| `overwrite` | bool | `False` | Whether results that already exist are run again. *(`-o`)* |
| `ask_continue` | bool | `False` | Whether the run stops for a confirmation once it knows what it will do. *(`-y`)* |
| `exit_when_done` | bool | `False` | Whether the monitor closes by itself once every job is done. *(`-E`)* |
| `log_size_limit` | int | `300` | How many log lines the monitor keeps per job. *(`--logsize`)* |
| `nb_jobs` | any | `8` | How many jobs run in parallel — an integer, or `"auto"` (the number of CPUs minus one). *(`-j`)* |
| `force_single_thread` | bool | `False` | Whether each job is asked to use a single thread, to avoid overloading the CPU when many run in parallel. |

### `FmaxSynthesisJobSettings`

`JobSettings`, plus:

| Setting | Type | What it says |
|---|---|---|
| `architectures` | list | The architecture configurations to synthesize. |
| `fmax_synthesis` | `FmaxBoundsSettings` | Bounds the binary search runs in. |

**`FmaxBoundsSettings`** — `override` (bool, `False`: when false, these values
are only used where no architecture-specific bounds are defined), `lower_bound`
and `upper_bound` (optional ints, in MHz, overridden by `--from` / `--to`).

### `CustomFreqSynthesisJobSettings`

`JobSettings`, plus:

| Setting | Type | What it says |
|---|---|---|
| `architectures` | list | The architecture configurations to synthesize. |
| `frequencies` | `FrequenciesSettings` | The frequencies they are synthesized at. |

**`FrequenciesSettings`** — a list and a range can both be kept in the file, each
switched on or off: the one that is off is written under `disabled_list` /
`disabled_range`, so its values are remembered without being run.

| Setting | Type | Default | What it says |
|---|---|---|---|
| `override` | bool | `False` | Whether these frequencies replace the architecture-specific ones. |
| `use_custom_freq_list` | bool *(not stored)* | `True` | Whether the list is used. |
| `frequencies` | int list *(key `list`)* | Odatix default | Frequencies to synthesize at, in MHz. *(`--at`)* |
| `use_custom_freq_range` | bool *(not stored)* | `True` | Whether the range is used. |
| `range` | `FrequencyRange` | | The range to synthesize at. |

**`FrequencyRange`** — `start` (key `from`, default `50`), `stop` (key `to`,
default `100`) and `step` (default `10`), in MHz, overridden by `--from`,
`--to` and `--step`.

### `PnrJobSettings`

`JobSettings`, plus `sources` (list): the completed synthesis jobs to start
from, written

```
<source_type>/<source_tool>[@<source_flow>]/<target>/<architecture>/<configuration>[@<frequency>MHz]
```

with `*` accepted at every level.

### `AnalysisJobSettings`

`JobSettings`, plus `architectures` (list) and `tools` (string list): the EDA
tools the RTL analysis runs with. *(`-t`)*

### `SimulationJobSettings`

`JobSettings`, plus `simulations`: the simulations to run, each with the
architecture configurations it runs on. Held as a
`{simulation: [configuration, …]}` mapping, written to file as the list of
single-key mappings `odatix sim` expects.

`simulation_selection_list(selection)` builds that file value from the mapping.

### `WorkflowJobSettings`

`JobSettings`, plus `workflows`: the workflow configurations to run, as
`"<workflow>/<configuration>"`.

{{< code lang=python filename="jobs.py" >}}
run = ws.jobs.fmax_synthesis
run.settings.architectures = ["MyCPU/08bits", "MyCPU/16bits"]
run.settings.nb_jobs = "auto"
run.settings.fmax_synthesis.lower_bound = 50
run.save()

ws.jobs.simulation.settings.simulations = {"TB_Counter": ["MyCPU/08bits"]}
ws.jobs.simulation.save()

settings = ws.jobs.fmax_synthesis.load()     # checked the way a run needs it
{{< /code >}}

---

## Reading a selection

### `JobRequest`

One entry of a run selection, read.

| Attribute | What it is |
|---|---|
| `text` | The entry as written, without its spaces. |
| `entry` | What holds the configurations, i.e. the architecture or the workflow (`"counter"`). |
| `configuration` | The configuration selected (`"08bits"`). An entry that selects none names the entry itself, which is how "the design with its parameters left alone" has always been written. |
| `path` | `"<entry>/<configuration>"`, the configuration file without its extension. |
| `domains` | The other parameter domains selected, each written `"<domain>/<configuration>"`. |
| `has_configuration` | Whether a configuration was actually selected. |
| `notes` | What reading this entry has to tell the user, as [`Message`](#message) objects. |
| `work_dirname` | The directory this entry runs in, under the one named after its entry. The other domains are part of it: two runs of the same configuration with different domains are two different results. |

| Method | What it does |
|---|---|
| `display_name(target="", only_one_target=True)` | How this entry is named in what a run prints: the other domains between brackets, and the target too when a run has several. |
| `with_domains(domains)` | The same entry, targeting these parameter domains instead. |

### `parse_request`

`parse_request(text, keep_extension_note=True)` — read one entry of a selection
into a `JobRequest`.

### `expand_selection`

`expand_selection(requests, root, messages=None)` — turn a selection into the
entries it stands for, resolving its wildcards against what `root` holds.
`messages` collects what a user should be told; `domain_names(root, entry)`
lists the parameter domains an entry holds.

### `Message`

Something a user should be told about. `Message(level, text, hints=None)`, where
`level` is one of `"error"`, `"warning"`, `"note"` or `"tip"` — which is how
Odatix already names what it prints — and `hints` are the lines that follow it.

---

## Errors

| Exception | Also a | Raised when |
|---|---|---|
| `WorkspaceError` | `Exception` | Base class of every error of this API. |
| `NotFoundError` | `KeyError` | There is no such architecture, simulation, workflow, tool, domain, target… |
| `AlreadyExistsError` | `ValueError` | The name asked for is already taken. |
| `InvalidNameError` | `ValueError` | The name cannot be used on disk (empty, holds a path separator…). |
| `NotAWorkspaceError` | `ValueError` | The directory holds no Odatix settings file, and one was required. |
| `InvalidSettingsError` | `ValueError` | A settings file cannot be used as it is: missing, not valid YAML, or holding a value of the wrong kind. |

`InvalidSettingsError(message, path=None, key=None, hints=None)` carries `path`
(the file it is wrong in), `key` (the key it is wrong at, when it is about one)
and `hints` (what a user can do about it).

> [!NOTE]
> `InvalidSettingsError` is what reading a file **for a run** raises. Reading one
> to *edit* it never does: a file being written is allowed to be incomplete.

---

## YAML helpers

`odatix.workspace.yaml_io` holds what the API reads and writes files with. It is
worth reaching for when a script has to touch a file the API does not model.

| Function | What it does |
|---|---|
| `read_yaml(path, default=None)` | Read a YAML file into plain Python values. |
| `read_mapping(path)` | Read a YAML file that has to hold a mapping, reporting what is wrong with it instead of falling back on a default. |
| `read_document(path)` | Read into a round-trip mapping, keeping comments and formatting. A missing or empty file yields an empty mapping. |
| `write_document(path, data, yaml_obj=None)` | Write a mapping, creating the parent directories. |
| `new_document(header=None)` | An empty round-trip mapping, optionally with a header comment. |
| `file_header(title, generator="Odatix")` | The banner Odatix puts at the top of the files it generates. |
| `flow_seq(values)` / `block_seq(values)` | A sequence rendered inline (`[a, b, c]`) or one item per line. |
| `parse_bool(value, default=False)` | Read a boolean the way the workspace files write them: YAML booleans, but also the `Yes`/`No` spelling Odatix generates. |
| `parse_int(value, default=None)` | Read an integer, `default` for anything that is not one. |
| `parse_int_list(value)` | Read a list of integers, accepting a real list or the free text a form field holds (`"50, 100; 200"`). |
| `yes_no(value)` | Render a boolean the way the generated files spell it. |

`odatix.workspace.settings` holds the rendering primitives underneath:
`load_settings(settings_class, path)`, `save_settings(settings, path,
header=None, regenerate=False)`, `render(settings, header=None)` — a complete
YAML document with its section comments — and `apply(settings, data)` — writing
a settings object into an existing document, leaving everything it holds that
the class does not declare untouched.

---

## odatix.run

`odatix.workspace` says what a workspace is configured to do; `odatix.run` gets
it done. Nothing here exits the interpreter and nothing asks a question: what a
run cannot do raises `RunError`.

### `Run`

A run of one of the commands of a workspace.

`Run(workspace, mode, options=None, reporter=None, cancel_event=None,
**overrides)`

| Argument | What it is |
|---|---|
| `workspace` | The `Workspace` the run belongs to. |
| `mode` | What to run, one of [`JOB_MODES`](#job_modes). |
| `options` | A [`RunOptions`](#runoptions): what this run does differently from what its settings file says. Built from the keyword arguments when not given. |
| `reporter` | A [`Reporter`](#reporter): where what the run says is collected. |
| `cancel_event` | A `threading.Event` asking the run to stop. Checking and preparing look at it between jobs and raise `RunCancelled`. |
| `**overrides` | Any `RunOptions` setting, e.g. `overwrite=True`. |

| Member | What it is |
|---|---|
| `config` | The [`JobConfig`](#jobconfig) of this run. |
| `settings_file` | The run settings file it reads. |
| `work_path` | Where its jobs live. |
| `result_path` | Where the results go. Nothing is exported when there is none, which is what a run working outside of a workspace does. |
| `use_benchmark` / `benchmark_file` | What the results are compared against. |
| `path(name)` | Where one part of the workspace is, letting this run replace it: a run started from a script works on the workspace as it is configured, while the command line lets a user point one of its parts elsewhere for a single run (`--archpath`, `--work`). |
| `reporter` | Everything the run said along the way. |

| Step | What it does |
|---|---|
| `check()` | Read everything the run needs and work out what it would do with each of its jobs, **without touching anything**. Returns a [`JobPlan`](#jobplan). Raises `RunError` when the run cannot be started at all, `RunCancelled` when it was asked to stop. |
| `prepare()` | Write the work directory of every job — its sources, its parameters and the script that runs it. Nothing is started. Returns the jobs, ready to be run. |
| `start(detach=None, session=None)` | Hand the prepared jobs over to the daemon. `detach` returns as soon as they are enqueued instead of attaching the monitor — which is what a run started from a script does, unless told otherwise. `session` is the daemon session to enqueue into. |
| `execute()` | Check, prepare and start, in one call. |

Each step does the ones before it when they have not been done, so `start()`
alone runs everything.

| Member | What it is |
|---|---|
| `was_checked` | Whether checking has been done and its plan is in hand. |
| `plan` | What the run would do. |
| `jobs` | The jobs it would run, as the objects its flow builds. |
| `checked()` | What checking produced, checking first when it has not been done. |

### `run_job`

`run_job(mode, workspace=None, **overrides)` — run one of the commands of a
workspace from beginning to end. The whole of `Run` in one call.

{{< code lang=python filename="run.py" >}}
from odatix.workspace import Workspace
from odatix.run import Run, RunError

run = Run(Workspace.open(), "fmax_synthesis", tool="vivado", overwrite=True)

try:
    plan = run.check()             # what would be run, having touched nothing
    print(plan.counts())           # {'new': 12, 'cached': 3, 'error': 0, ...}
    run.prepare()                  # every work directory written
    run.start()                    # handed over to the daemon
except RunError as error:
    print(error, error.errors())
{{< /code >}}

### `RunOptions`

What one run does differently from what its settings file says — the command
line flags, by name. Built the same way as the settings of a workspace, so a
value given as text is read the same way here as it is there.

**What runs**

| Setting | Type | Default | What it says |
|---|---|---|---|
| `tool` | any | `""` | EDA tool the jobs run with, or the tools an analysis runs. |
| `flow` | any | `None` | Flow of that tool. Its default flow when unset. |
| `until` | any | `None` | Last step of the flow to run, inclusive. |
| `rerun_from` | any | `None` | Step to run again, with the ones after it. |
| `overwrite` | bool | `False` | Run again what is already done. |
| `keep` | bool | `False` | Keep previous results, by timestamping the new ones. |
| `resume` | bool | `False` | Pick a stopped run up where it left off. |
| `continue_on_error` | bool | `False` | Keep going when a job fails. |
| `check_eda_tool` | bool | `True` | Check the EDA tool actually runs before using it. |

**How it runs**

| Setting | Type | Default | What it says |
|---|---|---|---|
| `nb_jobs` | any | `None` | How many jobs run at once. The settings file's own value when unset. |
| `force_single_thread` | bool | `False` | Ask each job to use a single thread. |
| `log_size_limit` | optional int | `None` | How many log lines the monitor keeps per job. |
| `noask` | bool | `True` | Do not stop for the "Continue?" confirmation. |
| `exit_when_done` | bool | `False` | Close the monitor once every job is done. |
| `detach` | bool | `True` | Hand the jobs over to the daemon without attaching a monitor. |
| `session` | any | `None` | Daemon session to enqueue into. |
| `debug` | bool | `False` | Report what reading the settings files finds. |

**Frequencies**

| Setting | Type | Default | What it says |
|---|---|---|---|
| `lower_bound` | optional int | `None` | Lowest frequency of an fmax search, in MHz. |
| `upper_bound` | optional int | `None` | Highest frequency of an fmax search, in MHz. |
| `frequencies` | int list | `[]` | Frequencies a custom frequency synthesis runs at. The settings file's own when empty. |

**Where a place & route starts from**

| Setting | Type | What it says |
|---|---|---|
| `source_result_types` | any | Result types a place & route starts from. |
| `from_type` | any | Result type the sources come from. |
| `from_tool` | any | EDA tool they come from. |
| `from_flow` | any | Flow they come from. |
| `source_work_root` | any | Work directory the sources are read from. |

**Paths**

| Setting | Type | What it says |
|---|---|---|
| `settings_file` | any | Run settings file to read, instead of the workspace's own. |
| `work_path` | any | Where the jobs run. |
| `result_path` | any | Where the results are written. Nothing is exported when empty. |
| `arch_path`, `sim_path`, `workflow_path`, `target_path` | any | Where the architectures, simulations, workflows and target files are. |
| `use_benchmark` / `benchmark_file` | any | Whether the results are compared against a benchmark, and which. |
| `custom_metrics_file` | any | Extra metrics to read from the reports. |
| `output_filename` | any | Name of the result file, when the run writes one. |

### `JobPlan`

What checking found: every job, with its category. Returned by `Run.check()`,
and also what the command line prints its checklist from.

| Member | What it does |
|---|---|
| `add(name, category, **details)` | Record one job. `details` holds extra facts to display (tasks, target, …). |
| `merge(other, suffix="")` | Append the entries of another plan, optionally suffixing their names — one plan per EDA tool, one checklist for the user. |
| `names(category, colored=True)` | Names of the jobs of one category, in insertion order. `colored=False` strips the terminal color codes. |
| `counts()` | How many jobs per category. |
| `run_count()` | How many are actually going to be launched. |
| `sorted_entries()` | Entries by category severity, then by name. |
| `to_list()` | A JSON-serializable form. |
| `print_summary(noun="architectures")` | The CLI checklist: one section per non-empty category. |

Categories, from `odatix.lib.run_report.Category`:

| Category | Runs | What it means |
|---|---|---|
| `new` | yes | A job with no result yet. |
| `overwrite` | yes | Existing results, which will be overwritten. |
| `incomplete` | yes | Incomplete results, which will be overwritten. |
| `resume` | yes | Partially done: the run resumes at the first missing step. |
| `cached` | no | Existing results, skipped — use `overwrite` to run them again. |
| `daemon` | no | Already managed in a daemon session, skipped. |
| `error` | no | Invalid settings, skipped. |

### `JobPlanner`

What a run decides to do with each of its job directories, and the plan it
builds from those decisions. A run builds its own; this is the class to reach
for when writing a front-end that has to reproduce the same verdicts.

`JobPlanner(work_path="", work_log_path="", status_filename="",
valid_status="", overwrite=False, requested_steps=None, rerun_step_index=None)`

| Method | What it does |
|---|---|
| `classify_job(tmp_dir, subject, job_noun="synthesis")` | Decide what to do with a job directory. Returns `(state, daemon_entry)`, the state being one of `"cached"`, `"daemon"`, `"overwrite"`, `"incomplete"`, `"resume"` or `"new"`. The verdict comes from three sources, in that order of precedence: the step state of the directory, its status file, then the daemon sessions. |
| `steps_decision(tmp_dir)` | The step-level verdict for a flow split into steps, or `None` when the flow is not stepped. `"cached"` when the directory holds every step this run asks for, `"resume"` when it holds some of them, `"new"` otherwise. This takes precedence over the status file: a directory left by a run that stopped at an earlier step holds a perfectly valid status file, and must not be mistaken for a complete result. |
| `daemon_decision(tmp_dir, steps_decision=None)` | Whether a job is already handled by a daemon session (`"skip"`), can be re-enqueued over a failed one (`"replace"`), or is unknown to every session (`"none"`). |
| `refresh_daemon_jobs()` | Read what the daemon sessions are working on. |
| `record(name, state, daemon_entry=None)` | Add a job to the plan under the category its state calls for, returning whether it is one this run will actually work on. |
| `reset()` | Forget every decision taken so far. |

### `Reporter`

Collects what a run reports, keeping it printed as it always was. Everything
Odatix reports goes through `odatix.lib.printc`, so a reporter listens there
rather than asking the run flows to report differently.

| Class | What it does |
|---|---|
| `Reporter` | The base: collects inside `listening()`. |
| `TerminalReporter` | What the command line uses: printed as it happens, **and** kept. |
| `CollectingReporter` | Kept and **not** printed: what a script or a server wants, so a run does not write to a standard output nobody is reading. |

| Member | What it does |
|---|---|
| `listening()` | A context manager collecting everything reported inside it. |
| `messages` | Everything reported, as `(level, text)` pairs. |
| `of_level(level)` | Only what was reported at that level. |
| `errors` / `warnings` | |
| `last_error()` | |
| `clear()` | |

### `RunError`, `RunCancelled`

- **`RunError(message, messages=None, code=-1)`** — the run cannot go on: its
  settings are unusable, its EDA tool is missing, there is nothing left to run.
  `messages` holds what it reported before stopping, as `(level, text)` pairs,
  the last error being the exception's own message; `errors()` gives only what
  was reported as an error; `code` is the exit code the command line uses.
- **`RunCancelled`** — the run was asked to stop while it was checking or
  preparing its jobs.

---

## See also

- [Python API overview](/docs/python_api/) — the same API, told as a story.
- [Configuration file reference](/docs/reference/) — every file, every key.
- [Commands reference](/docs/commands/) — every command and its options.
