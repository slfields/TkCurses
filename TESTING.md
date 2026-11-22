# Testing TkCurses

This is what the tests and the static checks are for, how they are divided,
and where each kind lives. [CONTRIBUTING.md](CONTRIBUTING.md) has the rules for
working on a change: which commands CI runs, running them in a clean
checkout, and how to write a tty test that does not flake. This document is
the map of the suite those commands run.

TkCurses is a library with two contracts: a program written for tkinter must
behave the same here, and what it draws must reach a real terminal correctly.
Most of the suite holds one or the other. Where Tk's behaviour cannot be
cited from its manual, a test holds the behaviour measured on Tk 9.0.2, and
[ARCHITECTURE.md](ARCHITECTURE.md) records how it was measured.

## Running the tests

```bash
pytest                    # everything, about five minutes
pytest -n 4               # the same across four workers, about a minute and a half
pytest -m "not tty"       # unit and integration tests without a pseudo-terminal, seconds
pytest -m tty             # only the tests that drive a pseudo-terminal
pytest tests/integration  # only the multi-widget integration tests
```

Two markers are declared in `pyproject.toml`, and `--strict-markers` refuses
any other:

- `tty` marks a test that runs a program in a pseudo-terminal.
- `slow` marks a test worth leaving out of a quick run.

Every test has a 60-second timeout, so a hung curses read fails one test
rather than stalling the whole run.

## The levels

**A unit test exercises one module or one widget.** It needs no terminal:

- A widget is built on a bare root whose panel stack is a stub.
- Time comes from a fake clock where timing matters.
- The core modules under `src/tkcurses/_core/` are tested directly in
  `tests/test_core_*.py`.

Most of the suite is at this level, in `tests/test_*.py` files without `_tty`
in the name. These tests run in seconds.

**An integration test needs more than one part to be able to fail.** There are
three kinds, from narrowest to widest.

- **Widgets together, `tests/integration/`.** These tests build an
  application rather than a widget. Each one needs more than one widget to be
  able to fail: stacking and hit-testing, nested geometry, event routing
  through binding tags, shared variables, scrollbar pairs, focus traversal,
  dialogs over an application, resizing, and teardown.
  [tests/integration/README.md](tests/integration/README.md) states the rule
  and how each module was checked against the fault it claims to catch.
- **The library and a real terminal, `tests/*_tty.py`.** The test runs a
  complete program in a pseudo-terminal, through the real curses library. It
  types real bytes at the program and reads the screen back through a
  terminal emulator (pyte). The harness is `tests/support/terminal.py`, and
  `tests/test_harness.py` tests the harness itself. This is the only level
  that sees the bytes a terminal actually receives:
  - mouse and paste modes;
  - the cursor;
  - colour pairs;
  - what is left behind after a widget moves.
- **Programs as a reader writes them.** These tests run every complete
  program printed in the documentation and every example under `examples/`,
  and check that each does what its page says. Every acceptance scenario
  under `uat/` is run too, to check it still starts, draws and exits cleanly:
  - `tests/test_docs_tutorial.py`, `tests/test_docs_porting.py`,
    `tests/test_docs_terminals.py` and `tests/test_docs_cfg.py` for the
    documentation;
  - `tests/test_examples.py` for the examples;
  - `tests/test_uat_scenarios_tty.py` for the scenarios.

**Acceptance by a person** is the UAT suites. Each one is a runnable scenario
under `uat/` and a checklist under `docs/UAT_*.md` saying what to look at.
They cover what only eyes can judge: whether a drag feels right, whether a
colour reads. They are run by hand when a cycle produces something a person
can look at, and their acceptance is recorded in the checklist.

## Functional tests

These hold what TkCurses does.

| Test type | Unit level | Integration level |
|---|---|---|
| **Positive (happy path)** | A widget's methods and options return and draw what Tk's do: `tests/test_entry.py`, `tests/test_text.py`, `tests/test_listbox.py` and a file for every other widget; the core modules in `tests/test_core_*.py`. | Widgets working together in `tests/integration/`. Each widget driven through real keys and clicks in its `*_tty.py`. Every documented program and example running as its page says. |
| **Negative (sad path)** | A bad value is a `TclError` in Tk's own words: `tests/test_tcl_errors.py`, `tests/test_option_refusals.py`, and `tests/test_option_values_against_tk.py`, which gives every option of every widget a bad value and compares the result with real tkinter. | A callback that raises: `tests/test_callback_exceptions_tty.py`. A terminal that cannot do the job: `tests/test_terminal_environment_tty.py`. `tkcurses-cfg`'s errors and exit statuses: `tests/test_cfg_cli.py`. |
| **Boundary and edge cases** | One character, one cell: `tests/test_drawing.py`. Wide and zero-width characters: `tests/test_core_cells.py`, `tests/test_wide_text.py`. A paste larger than the limit kept: `tests/test_core_input.py`. Empty widgets, index ends, the first and last row. | A widget hanging off the screen or its master: `tests/test_clipping_tty.py`, `tests/test_master_clipping_tty.py`. A widget that shrinks: `tests/test_shrink_tty.py`. The terminal resized under a full application: `tests/integration/test_resize_full_screen_tty.py`. |
| **State and behaviour** | Undo and redo: `tests/test_text_undo.py`. Variables and traces: `tests/test_variables.py`. Timers: `tests/test_core_timers.py`. Allocation, mapping and destruction: `tests/test_widget_lifecycle.py`. | One variable shared by several widgets: `tests/integration/test_shared_variables.py`. Destroying a populated tree: `tests/integration/test_teardown.py`. `tkcurses-cfg` saving a file whole or not at all, which is this project's transaction: `tests/test_cfg_store.py`. |
| **Contract and schema** | tkinter's interface is the contract. What a star-import provides: `tests/test_tkinter_namespace.py`. Positional calls: `tests/test_tkinter_signatures.py`. Each widget's methods and options against real tkinter: `tests/test_method_surface.py`, `tests/test_classic_option_surface.py`, `tests/test_ttk_option_surface.py`. Behaviour replayed from recordings of Tk 9.0.2 (the `*.json` files in `tests/support/`, made by its `record_*.py` scripts). | The configuration reference is generated from the code and true of it: `tests/test_configref.py`. The compatibility matrix is complete: `tests/test_compat_matrix.py`. The docstrings keep the API reference's convention: `tests/test_docstrings.py`. A program written for the `curses` module runs here: `tests/test_curses_module_tty.py`. |

## Non-functional tests

These hold how well TkCurses behaves under constraints.

| Test type | Unit level | Integration level |
|---|---|---|
| **Security** | Here the injection risk is the terminal: text a program shows must not be able to drive it. `tests/test_input_hostile.py` covers environment values, configuration files and reports on the way out. `tests/test_image_hostile.py` covers image files built to exhaust memory or crash a decoder. `tests/test_cfg_safety.py` covers the paths `tkcurses-cfg` writes through and the text it shows. `tests/test_wipeable.py` covers the wipeable memory a hidden field keeps its contents in. Each of these tests fails without its fix. | A terminal sending faster than the program reads: `tests/test_input_flood_tty.py`. The system clipboard over OSC 52 and the desktop's tools: `tests/test_system_clipboard.py`. In CI, Bandit scans `src/` and pip-audit checks every lock file (see [Static checks](#static-checks)). `tests/test_hygiene.py` keeps private files out of this public repository. A password typed into a hidden entry is never held as a `str`, which is checked by scanning the process's own memory: `tests/test_entry_hidden.py`. |
| **Performance** | Work counted rather than timed, so the result is the same on any machine: `tests/test_text_layout_cost.py` holds that typing into a long Text lays out only the line typed into. | A repaint stays cheap enough to run inside a click handler: `tests/test_redraw_cost_tty.py`. Timings, outside the gate: `tests/support/bench.py` (see [Timing the hot paths](#timing-the-hot-paths)). |
| **Resilience** | Partial input: an escape sequence or UTF-8 character split across reads, a terminal reply that arrives late, a paste cut off before its end marker (`tests/test_core_input.py`). A `tkcurses-cfg` save interrupted by `SIGTERM` or `SIGHUP`, or failing on a full disk, changes nothing (`tests/test_cfg_store.py`). | Ctrl-Z and `fg` hand the terminal's modes back and take them again: `tests/test_bracketed_paste_tty.py`. Ctrl-C in a dialog: `tests/test_dialog_interrupt_tty.py`. A raising callback leaves a usable screen: `tests/test_callback_exceptions_tty.py`. A resize in the middle of everything: `tests/integration/test_resize_full_screen_tty.py`. The terminal hanging up under `mainloop()` or a dialog shown before it, with SIGHUP at its default, ignored, or handled by the program, ends it with status 129 after its `finally` and `atexit` run: `tests/test_terminal_hangup_tty.py`. |
| **Concurrency** | Calls from other threads are queued and run on the thread that owns curses, in order, and a call left waiting when the queue closes is released: `tests/test_core_dispatcher.py`. These tests synchronise on events, not sleeps. A queued call wakes the main loop at once, and only the loop's own wait, not the waits inside reading a key or a paste: `tests/test_core_input.py`. End to end, a worker thread updates a Label, a variable, a Text and a Listbox, and schedules callbacks with `after`, while a person types; every update, callback and key arrives, in order: `tests/integration/test_worker_thread_tty.py`. | Several processes saving one configuration file at once, and a reader that never sees a half-written file: `tests/test_cfg_store.py`. The test harness forks from xdist's threaded workers, so the child may make only async-signal-safe calls before exec. `tests/test_harness.py` checks that by reading the code. |

## Property-based testing and fuzzing

Hypothesis generates the inputs for invariants that must hold for every
input, not only the ones someone thought of:

| Module | The property |
|---|---|
| `tests/test_layout_properties.py` | For any tree, options and terminal size, packed and gridded children never overlap, stay inside their container and never get a negative size; laying out again changes nothing; a layout survives a resize and back; and a nested tree always settles. |
| `tests/test_core_geometry.py` | Content and padding never escape their window. |
| `tests/test_core_screen.py` | Dirty regions lie inside the buffer, and any resize yields a consistent grid. |
| `tests/test_core_colors.py` | Every hex colour resolves, at every colour depth. |
| `tests/test_canvas_arcs.py` | An arc is one connected piece, inside its box. |
| `tests/test_text_embedded.py` | Undo and redo still line up after any sequence of edits around an embedded window. |
| `tests/test_cfg_inifile.py` | A file the editor accepts is read the same way by a program, an unedited file comes back byte for byte, and `unset` removes only its own line. |
| `tests/test_cfg_session.py`, `tests/test_cfg_invariants.py` | What the `tkcurses-cfg` screen previews is what a program reads once the file is saved. |
| `tests/test_input_properties.py` | Any byte stream from the terminal, with keys curses decoded mixed in, is read to the end without an exception and leaves nothing unread. Typed text arrives as exactly that text; bytes that are not UTF-8 never become a character they do not spell; a paste is one event holding what was pasted, with typing either side kept; a paste whose end never comes is kept and marked incomplete; and a late reply to a start-up query is never typed. |
| `tests/test_image_properties.py` | Any bytes, anything after a valid magic number, and good PNG, GIF and PPM files that have been cut, overwritten or grown (a PNG's checksums mended, so the damage reaches the decoder) either decode to a rectangular picture of `#rrggbb` cells within `MAX_PIXELS`, or raise `TclError`, holding under 64 MB while they do. A file our own encoders wrote reads back exactly. Any XBM source makes a bitmap or a `TclError`, and so does any photo data. |
| `tests/test_bargraph_render.py` | For any values, a stacked bar's tip is exactly their total and an overlaid bar's the longest value, a threshold zone's tip is exact, and no cell holds more than two colours. |
| `tests/test_bargraph_layout.py` | For any options and size, a graph's regions stay inside it and never overlap, and its natural size fits everything it draws. |
| `tests/test_bargraph_decor.py` | A composed graph never writes outside its window or onto its border. |
| `tests/test_bargraph_scale.py`, `tests/test_bargraph_model.py` | A value never maps past the bar's peak, and an autoscaled maximum never cuts a value off, for any sequence of values. |
| `tests/test_charts_numformat.py` | A number is never written with more significant digits than asked, with no leading zeros but one before the point, and with exactly the decimals asked. |
| `tests/test_charts_text.py` | Text cut to fit a width never takes more cells than that width. |
| `tests/test_bargraph_gradient.py` | The shades run evenly from the start colour to the series colour. |
| `tests/test_wipeable.py` | Any sequence of inserts and deletes leaves a hidden field's wipeable buffer holding what the same edits make of a `str`, and a hidden `TextField` keeps the same cursor, selection, view and columns as a plain one. |
| `tests/test_core_config.py` | For any value of any setting, a program keeps what the parser accepts, clamps what is out of range, and falls back on anything else, so `tkcurses-cfg` and a program never disagree. |

The number of examples is set per test with `@settings`, where the default
is too few or too many. A failing example is shrunk to the smallest case
that fails, and that case is worth adding as an ordinary test once fixed.

The two fuzzing modules, `test_input_properties.py` and
`test_image_properties.py`, cover the code that reads bytes from outside the
program. They run 300 examples a test in the suite, which takes seconds. After
changing the input reader or a decoder, run them for longer. The suite's
60-second timeout would stop a long run, so lift it:

```bash
TKCURSES_FUZZ_EXAMPLES=20000 pytest --timeout=0 -n 4 \
    tests/test_input_properties.py tests/test_image_properties.py
```

They complement the hand-built cases in test_image_hostile and
test_input_hostile (listed under the non-functional tests), each a file or
byte sequence that once broke something. The two kinds catch different faults. With `decode`'s catch-all
for unexpected exceptions removed, 20,000 damaged files still raised nothing
but `TclError`, because every refusal is an explicit check; the catch-all is
a second line. Removing the `MAX_PIXELS` check is caught only by the
hand-built gigabyte cases, since a random file almost never declares a huge
image *and* carries enough data to reach the allocation. Each of four faults
put back into the input reader on purpose (bytes that are not UTF-8 decoded
as text, a paste's end marker missed when split, a late reply typed, a
continuation byte dropped) failed a property within the default 300
examples.

## Mutation testing

A mutation test changes the code under test on purpose and checks that some
test fails. A mutant that survives means either a test is missing or the
change cannot alter behaviour. Coverage says a line ran. A killed mutant says
some test would have noticed if that line were wrong. The tool is
[mutmut](https://mutmut.readthedocs.io/), run through
`tests/support/mutate.py`.

### Running it

```bash
pip install -e ".[mutation]"
python3 tests/support/mutate.py                              # every module HEAD changed since origin/master
python3 tests/support/mutate.py src/tkcurses/_core/cells.py  # one module
python3 tests/support/mutate.py --base v0.4.2                # changed since a tag
```

Run it on a change to the library's logic before opening its pull request,
and say what it found in the pull request. It is not part of CI, for two
reasons:

- **It takes too long.** A small module takes about two minutes: one to find
  which tests reach each function, and the rest to run them against each
  mutant.
- **A survivor needs reading, not just counting.** It can be a missing test
  or a change that can never matter, and only a person can tell which.

The script applies what was learned running mutation tests by hand, so
nobody has to remember it:

- **It mutates the commit, not the working copy.** mutmut runs in a fresh
  worktree of HEAD outside the repository, so your files are never touched
  and a half-made change is not what gets measured. Commit first. The
  worktree is kept afterwards for reading the results.
- **Only the modules named are mutated.** mutmut replaces each function with
  a copy per mutant. Mutated whole, `__init__.py` grows from 1 MB to 43 MB,
  every test slows down importing it, and a test that caps its child process
  at 512 MB runs out. The script sets `only_mutate` in the worktree's
  `pyproject.toml` alone.
- **Every process has a memory cap**, 8 GiB unless `--memory` says otherwise.
  A mutant that removes a bound can make one test allocate without end. By
  hand, once, a test grew to 12.8 GB in 35 seconds before the kernel killed
  it and the terminal with it. Under the cap the test fails with
  `MemoryError` instead, and the mutant counts as killed.
- **No bytecode is written**, so a stale `.pyc` can never stand in for a
  source file.

mutmut itself refuses to start unless the selected tests pass unmutated,
and it checks that a forced mutant fails them. A survivor is never the
product of a broken baseline.

### Which tests can kill a mutant

The configuration is `[tool.mutmut]` in `pyproject.toml`. mutmut runs the
whole suite once, tracing which tests call each function, then runs only
those tests against that function's mutants. Two kinds of test are left out:

- **The tty tests.** They reach the library in a child process the harness
  forks, which mutmut's tracing cannot see, so they would never be chosen.
  Leaving them out keeps the tracing run to about a minute.
- **Tests about the repository rather than the library.** These ask git
  about the tree, and mutmut's copy of it is not a checkout.

So a function that only a tty test exercises reports **no tests**. That is a
gap in the unit tests, not proof the code is untested.

### Reading the results

The script ends with every mutant that was not killed, grouped by status,
and the commands to read one and to remove the worktree.

| Status | Meaning | What to do |
|---|---|---|
| killed | A test failed. | Nothing. |
| survived | Every test passed with the mutant in place. | Read it (below). |
| no tests | No traced test calls the function. | Write a unit test, or check by hand that a tty test catches it (below). |
| timeout | The tests ran far longer than they do unmutated: usually a loop that no longer ends. | Treat as killed, unless the slowness itself is what a test should have caught. |
| suspicious, segfault | The test run ended in a way that is neither a pass nor a failure. | Read it. It may be a fault in a test's cleanup. |

To read one, in the worktree the script printed:

```bash
python3 -m mutmut show tkcurses._core.cells.x_char_cells__mutmut_1   # the change, as a diff
python3 -m mutmut browse                                            # all of them, interactively
```

### What to do about a survivor

A surviving mutant is one of two things.

1. **A test that is missing.** The mutant changes behaviour that a program
   could see, and nothing checks it. Write the test that fails with the
   mutant in place, then run the script again to see it killed. The test
   should state the behaviour, not the mutant. "U+0300 takes no cells" is a
   fact about terminals; "`<` is not `<=`" is not a test name.
2. **An equivalent mutant.** No input can tell it from the original, so no
   test can ever kill it. Typically the mutant changes a shortcut that the
   slow path agrees with, an optimisation, or a value that is overwritten
   before it is read. Say in the pull request why it is equivalent.

   `# pragma: no mutate` on a line stops mutmut mutating that line at all.
   Use it only when every mutant of the line is equivalent, because it hides
   the meaningful ones too.

To check a **no tests** mutant against the tty tests, apply it in the
worktree, never in your own checkout. The worktree is disposable:

```bash
cd /tmp/tkcurses-mutation
python3 -m mutmut apply NAME
python3 -m pytest -m tty TESTS   # the tty tests that should catch it
git checkout -- src              # the worktree's src, not yours
```

### A worked example

`src/tkcurses/_core/cells.py`, which measures how many terminal cells text
takes, was the first module run this way. 63 mutants, 14 survived:

- **13 were missing tests**, now in `tests/test_core_cells.py`:
  - U+0300, the first combining mark, where Latin's fast path ends;
  - the last code point of the embedding range;
  - an embedded character whose window has gone;
  - clipping or skipping zero cells of text that starts with a combining
    mark;
  - skipping past the end of the text, including a cut through a wide
    character.
- **1 is equivalent.** It changes `character < "\u0300"` so that the fast path
  ends at `"X"` instead. Every character it moves to the slow path gets the
  same answer from the Unicode database there.

Its first run also found a test that depended on the order tests ran in.
`tests/test_image_command.py` expected Tk's unnamed images to be numbered
from `image1`. Tk numbers them across the whole process, and so does
TkCurses, so the test passed only because no earlier test made one. It now
takes the name Tk gives.

## Static checks

CI runs all of these on every pull request that changes code.

**Ruff lint** (`ruff check .`) checks every Python file in the repository:
`src/`, `tests/`, `docs/_ext/`, `uat/`, `examples/` and the workflow scripts.
The rule sets are chosen in `pyproject.toml`:

| Rules | What they catch |
|---|---|
| `E`, `W` | pycodestyle errors and warnings. Line length (`E501`) is left to the formatter. |
| `F` | Pyflakes: undefined and unused names, and imports that shadow each other. |
| `I` | Import order, with `tkcurses` as first-party. |
| `B` | bugbear: mutable defaults, loop variables captured by closures, and similar. |
| `C4` | Comprehensions written the long way. |
| `UP` | Syntax that Python 3.11 makes unnecessary. |
| `ARG` | Unused arguments. |
| `SIM` | Conditions and blocks that can be simpler. |
| `TC` | Imports needed only for type checking, kept out of the runtime. |
| `PTH` | `os.path` where `pathlib` would do. |
| `RUF` | Ruff's own rules, including invisible or confusable characters in strings. Write those as `\u` escapes. |

The per-file exceptions are in `pyproject.toml`, each with its reason:

- `src/tkcurses/__init__.py` may star-import and re-export, as tkinter does.
- `filedialog.py` and its tests keep `os.path`, because tkinter's file
  dialogs take and return path strings.
- Tests, examples and UAT scenarios may leave arguments unused, because a
  binding callback takes an event whether it reads it or not.

Markdown is excluded: the Python fragments in `ARCHITECTURE.md` are sketches,
not programs. The complete programs in the documentation are run by the
tests instead.

**Ruff format** (`ruff format --check .`) checks that every Python file is
formatted as Ruff would format it, at 88 columns. It reports a difference
and changes nothing; run `ruff format` to apply the changes.

**mypy** (`mypy`) checks `src/tkcurses`, `tests/support`, `docs/_ext` and
`.github/scripts` in strict mode, plus the flags listed in `pyproject.toml`:
the library, and the tooling that tests, documents and releases it. It
reports:

- any function without full annotations;
- `Any` leaking out of a typed function;
- unreachable code, and an `# type: ignore` that is no longer needed;
- an equality check between types that cannot be equal.

The tooling is held to the same strict mode as the library. Where a
recorder in `tests/support` feeds tkinter values read from a table or from
JSON, those values are typed `Any` on purpose; and where typeshed leaves a
tkinter method unannotated (`curselection`, `paneconfigure`, `splitlist`),
the call carries an ignore that says so. The documentation extensions
import Sphinx and docutils, which mypy does not follow: Sphinx is written
for Python 3.12, while this checks for 3.11, and CI's lint job installs
neither. pyte's missing imports are ignored.

Not checked: the tests themselves, `examples/` and `uat/`. Those are
programs written as a user would write them, against the library's
annotations, and mypy is not asked to hold them to strict mode. `tests/test_packaging.py` checks that the built package
carries its `py.typed` marker, so a program using TkCurses is type-checked
against it.

**Bandit** scans `src/` at medium severity and above. Findings below medium
were read in the 2026-11 security review and are not acted on.

**pip-audit** checks every lock file under `requirements/` for packages with
known vulnerabilities.

**The convention tests** check what no linter can:

- `tests/test_licensing.py`: every source file carries its licence and its
  credits.
- `tests/test_docstrings.py`: docstrings keep the API reference's
  convention.
- `tests/test_hygiene.py`: the repository holds only the project.
- `tests/test_suite_tests_its_own_tree.py`: the suite exercises the checkout
  it is run in, not an installed copy.

The documentation site is also built with warnings as errors on every pull
request.

## Coverage

Python 3.12's CI job runs the suite under coverage, with branch coverage. The
other interpreters don't, because coverage more than doubles the run time:
every tty test forks a process, and each process writes its own data file.
The report lists the lines and branches that never ran.

The job fails if the total drops below 93.5%. On 2026-11-17 coverage put
master's library at 93.78%. Across four master runs the report's missed
lines and partial branches move by about a tenth of a point, because of the
tty tests' timing, so the floor sits about three tenths below. Read the
total coverage prints. It can't be worked out from the report's columns,
because a missed branch on a line that never ran is not in the
partial-branch count. Coverage reports to two decimal places (`precision`
in `pyproject.toml`), so the figure printed is the figure the floor is
compared with, not a whole number rounded from it. The floor is set on CI's command, not in
`pyproject.toml`, so `pytest --cov` on a few files does not fail for
covering only part of the library. Each run's summary on GitHub records
the total, which is where to look when raising the floor. Raise it as the
figure rises, and lower it only for a reason written beside it in
`.github/workflows/ci.yml`.

## Timing the hot paths

The gate counts work, because a count is the same on every machine. A
count cannot see a path that does the same work more slowly, so
`tests/support/bench.py` times the paths where that would hurt:

- typing into a long Text;
- tagging every line;
- decoding a PNG and a GIF;
- reading typed text as keys;
- measuring the cells of mixed-script text.

```bash
python3 tests/support/bench.py                          # this tree
python3 tests/support/bench.py --compare origin/master  # against a base
```

A timing belongs to the machine and the moment it was taken, so the script
never compares against a number written down earlier. `--compare` checks
the base out into a temporary worktree and times the two trees in turn,
each in a fresh interpreter importing its own `src`. It reports each
median against the base's and exits 1 if any is more than 15% slower
(`--threshold`). A measurement that imported the library from anywhere
but the tree being timed is refused: an editable install of another
checkout would otherwise be timed against itself and show no change.

Measured on one machine on 2026-11-17, against master:

- **Unchanged paths** came in within 2% of master.
- **One path deliberately slowed**, with `cells()` made to do its work
  twice, showed +56.7% and was marked. The script exited 1.

It is not part of CI: a shared runner's timings vary more than the
slowdowns worth catching. Run it before merging a change to a hot path.
`tests/test_bench_script.py` checks that every benchmark still runs
against the library as it stands, and that a comparison marks what it
should.

## Setting the priority of a problem a test finds

A problem's priority comes from two ratings, each judged against a
description below rather than by feel: how bad the effect is (**impact**)
and who meets it (**reach**). Rate the worst effect that can be shown, not
the worst that can be imagined. Record both ratings in the issue, e.g.
`Impact 3, reach 2: P1`, so the priority can be checked by someone else.

| Impact | The effect |
|---|---|
| 4 | Security or data: input from outside the program runs code, reads or writes what it should not, or loses or corrupts a user's data; or a release publishes the wrong thing. |
| 3 | Failure: an exception escapes that the documentation does not name, the program hangs or spins, or the terminal is left unusable after it exits. |
| 2 | Wrong behaviour: the program carries on but does something other than Tk does or the documentation says, including drawing the wrong thing. Or too slow to use: one operation takes ten times as long as it should, or a person waits more than 100 ms for something Tk does at once. |
| 1 | Cosmetic or slow: everything works and reads correctly, but looks wrong or takes noticeably longer, short of impact 2's bounds. |
| 0 | No effect on a program: the tests, tools or documentation are wrong or missing. |

| Reach | Who meets it |
|---|---|
| 3 | Any program, in ordinary use, or anyone who can send it bytes: terminal input, an image file, a pasted clipboard. |
| 2 | A program using a common feature in the usual way. |
| 1 | A particular input, option, platform or sequence of steps, or there is a workaround. |

| Priority | Impact and reach |
|---|---|
| P0 | Impact 4 with reach 2 or 3. Drop other work. |
| P1 | Impact 4 with reach 1; impact 3 with reach 2 or 3. |
| P2 | Impact 3 with reach 1; impact 2 with reach 3. |
| P3 | Impact 2 with reach 1 or 2; impact 1 with reach 3. |
| P4 | Impact 1 with reach 1 or 2; impact 0. |

**A gap in the tests**, with no failure known, is rated as the failure it
would most plausibly let through, one priority lower, and never above P2.
**A test that fails intermittently** is rated by what it hides: until it is
fixed, it can hide any failure in the code it covers, so it is P2 if that
code reads outside bytes or runs on every program's main loop, and P3
otherwise.

Three worked examples. Typing a no-break space did nothing: wrong
behaviour, impact 2, met only with that character, reach 1, so P3. The
image decoders had no fuzzing: the failure that could slip through is an
exception escaping on a hostile file (impact 3, reach 3: P1), and as a gap
that is P2. A Listbox insert from a worker thread took a second, where it
takes milliseconds from the main thread: far past ten times as long, so
impact 2 rather than 1, in a common pattern, reach 2, so P3.

## Gaps

None are open. The review that wrote this document, epic `TkCurses-us5p`,
found seven and closed them all:

- mutation testing;
- the type-checking scope;
- a coverage floor;
- fuzzing the input reader and the image decoders;
- a worker thread updating widgets;
- a terminal that hangs up;
- timing.

Two of these found bugs, and both are fixed: the worker thread found the
main loop's 50 ms wait, and the hangup gap found the full-CPU spin. The
hangup work left one case, a dialog shown before `mainloop()`, which was
fixed after the review (`TkCurses-wk51`). A gap found later is filed as an
issue and listed here, rated as
[above](#setting-the-priority-of-a-problem-a-test-finds).
