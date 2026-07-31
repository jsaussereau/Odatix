# Odatix test suite

Regression tests for Odatix (pytest). The suite runs against the sources tree directly.
No installation needed: `tests/conftest.py` adds `sources/` to `sys.path`.

## Running

```bash
pip install -e 'sources[test]'  # once, in your venv
make test                 # everything (currently ~700 tests)
make test-fast            # skip integration + GUI tests
make test-coverage        # terminal + XML coverage report; seuil initial : 41 %
python -m pytest tests/test_config_generator.py -k power_of_two   # one area
```

## Layout

| File | Covers |
|---|---|
| `test_config_generator.py` | `lib/config_generator.py` — all dimension types (bool, range, list, multiples, power_of_two), set operations (union, intersection, …), computed variables (function, format, conversion), `$var`/`${var}` substitution, error paths |
| `test_get_from_dict.py` | `lib/get_from_dict.py` — optional/mandatory keys, type validation, raise behaviors |
| `test_utils.py` | `lib/utils.py` — copytree (whitelist/blacklist), read_from_list, create_dir, merge_dicts_of_lists, safe_df_append, … |
| `test_small_libs.py` | `lib/re_helper.py`, `lib/variables.py`, `lib/wosit.py` |
| `test_replace_params.py` | `components/replace_params.py` — delimiter-based replacement, param domains end-to-end on files |
| `test_param_domain.py` | `lib/param_domain.py` — domain resolution from settings files |
| `test_results_schema.py` | `lib/results_schema.py` — format v2, v1→v2 conversion (synthèse + workflow), identity/upsert, load/dump roundtrip |
| `test_run_settings.py` | `lib/run_settings.py` + `lib/settings.py` (OdatixSettings) |
| `test_workspace.py` | `components/workspace.py` — architectures, domaines, workflows, fichiers de configuration, helpers |
| `test_generate_configs.py` | `components/generate_configs.py` — génération de fichiers de configuration sur arborescence réelle |
| `test_handlers.py` | `lib/architecture_handler.py` + `lib/simulation_handler.py` — parsing des requêtes et résolution complète sur le workspace d'exemple (marque `integration`) |
| `test_yaml_inputs.py` | Robustesse de **tous les fichiers YAML d'entrée** : fichiers de jobs (fmax/sim/workflow), `_settings.yml` (génération + domaines + architecture), `odatix.yml`, fichiers target, fichiers de résultats — variantes vide / YAML invalide / scalaire / mauvais types / booléens YAML (`Yes`/`On`) / `#` dans les chaînes / ancres & alias / clés dupliquées / unicode / overrides par cible |
| `test_gui_components.py` | `gui/icons.py` + `gui/navigation.py` — icônes/pictogrammes, structure de la topbar, liens morts (marque `gui`) |
| `test_cli.py` | Arguments CLI — tous les sous-commandes d'`odatix` (init, generate, replace, fmax, freq, analyze, sim, workflow, monitor/stop/ls, results, res_*, clean) : défauts, alias, types invalides, options mutuellement exclusives ; parseurs d'`odatix-explorer`/`odatix-gui` ; smoke tests subprocess du vrai binaire (`-v`, `-h`, generate/replace de bout en bout, marque `integration`) |

## Fixtures (conftest.py)

- `in_tmp_dir` — exécute le test dans un répertoire temporaire vide.
- `example_workspace` — workspace Odatix complet copié depuis
  `sources/odatix_examples` (architectures, simulations, RTL, `odatix.yml`).
  Utilisé par les tests d'intégration : ils préparent les jobs mais ne lancent
  aucun outil EDA.
- `arch_dir` — architecture minimale avec un domaine de paramètres et une
  configuration.

## Conventions

- Marqueurs : `integration` (workspace d'exemple, plus lent), `gui` (composants
  Dash). Tout le reste est unitaire et rapide.
- La CI exécute la suite sur Python 3.11 et 3.13 et rejette toute baisse sous
  le seuil de couverture défini dans `.coveragerc`. Ce seuil doit être relevé
  à mesure que les exécuteurs EDA, le daemon et les pages Dash sont couverts.
- Un fichier de test par module source ; classes `Test*` par fonctionnalité.
- Les tests qui documentent un bug corrigé (ex. bornes de `power_of_two`,
  collision de préfixes `$WIDTH`/`$WIDTH_OUT`) portent un commentaire — ne pas
  les « simplifier ».
