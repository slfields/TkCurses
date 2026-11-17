# Contributing to TkCurses

**Changes come from the project's collaborators only.** The repository is
public to read, fork and install from, but it takes no issues and no pull
requests from outside: both are switched off for everyone else. To report a
security problem, see [SECURITY.md](SECURITY.md).

What follows is how the project is built, tested, documented and released,
and the rules that keep it working. Most of them were learned from a failure, and the failure is
given with the rule so the rule can be judged rather than only obeyed.

## Setting up

```bash
pip install -e ".[dev]"     # the library, editable, with the test tools
pip install -e ".[docs]"    # the documentation toolchain, if you build the site
pip install -e ".[mutation]"  # mutmut, for tests/support/mutate.py (see TESTING.md)
```

CI installs the same tools from the lock files under `requirements/`, which
pin every package to an exact version with its hashes, so a run cannot pick
up a release published since the lock was made:

```bash
pip install --require-hashes -r requirements/dev.txt
pip install --no-deps --no-build-isolation -e .
```

After changing a dependency in `pyproject.toml`, or to take newer versions,
regenerate them with `sh requirements/lock.sh` (it needs
[uv](https://docs.astral.sh/uv/)) and commit the result. CI's security job
audits every lock for known vulnerabilities on each run.

## The checks CI runs

```bash
ruff check .            # lint
ruff format --check .   # formatting
mypy                    # type-check (strict; src/tkcurses)
pytest                  # full suite, including the tty tests
pytest -n 4             # the same suite in a quarter of the time
pytest -m "not tty"     # fast subset, no pseudo-terminals
python3 -m sphinx -W --keep-going -b html docs docs/_build/html  # the docs site
```

[TESTING.md](TESTING.md) is the map of what these run: the suite's unit and
integration levels, which modules hold each functional and non-functional
concern, the property-based and mutation testing, what Ruff, mypy, Bandit
and pip-audit each check, and the gaps still open.

**`-n 4` is safe and a large difference.** Measured on a 12-core machine, the
suite takes about five minutes serially and under a minute and a half across
four workers. The tests that drive pseudo-terminals are about a sixth of the
tests and nearly all of the wall clock; they wait rather than compute, which is
why they parallelise almost perfectly. The harness forks, and a child forked
from a threaded process may do nothing but async-signal-safe calls before it
execs - `tests/test_harness.py` checks that by reading the code. CI still runs
the suite serially: a small runner under four-way contention is where the
worst timing flakes came from.

## Working on a change

**Every change is a branch and a pull request.** Nothing reaches `master`
except by merging one, and a pull request is merged only once CI passes. A
related set of changes is one branch with one commit per change, so each
commit leaves the tree green on its own.

**Run the checks against a clean checkout before pushing**, not against the
working copy, which may hold untracked files CI never sees:

```bash
git worktree add -q --detach /tmp/verify HEAD
cd /tmp/verify && ruff check . && ruff format --check . && mypy && pytest
git worktree remove --force /tmp/verify
```

That recipe is correct as written because `tests/conftest.py` puts the
checkout's own `src/` first on `sys.path`, and the pty harness puts it first on
the `PYTHONPATH` of every program it runs. Without that, the editable install's
`.pth` file - aimed at the checkout `pip install -e .` was run in - wins
everywhere, and a worktree's tests exercise the *working copy's* library: a
commit that forgot to add a new source file would pass.
`tests/test_harness.py::test_a_program_imports_this_checkouts_library` holds
it. The tell, if it ever regresses: coverage reports `TOTAL … 0%`.

**Name the paths you commit; never `git add -A <directory>`.** The working copy
can hold scratch programs that are deliberately untracked, and sweeping them
into a commit once failed CI on lint errors in files that should never have
been linted. And do not filter the evidence out of your own check: a
`git status` piped through `grep -v` to hide those files hid them from the very
output meant to show the commit was clean.

**A pull request that changes only documentation runs no code checks.**
`ci.yml` still runs on it, because `master` requires its `CI passed` check,
but its first job sees nothing changed outside `docs/**`, Markdown files and
the docs workflows, and the code jobs are skipped. A release still runs
everything.

**`master` takes a pull request only when its checks pass**: `CI passed`,
which is green when every job in `ci.yml` passed or was skipped, and
`Build the site`. No approval is required - the maintainer cannot approve
their own pull request.

## Documentation

The site is Sphinx with Markdown (MyST) pages under `docs/`, the Furo theme,
and an API reference that is autodoc on the docstrings - so **a docstring is
user-facing text**. `docs.yml` builds it with warnings as errors on every pull
request, and every release carries it as a zip.

**Docstrings follow the reference's convention**, which
`tests/support/docsurface.py` states and `tests/test_docstrings.py` enforces:

- written for a user: no issue numbers and no private names, in extensions and
  in the `#:` comments on module data too;
- a `Differences from tkinter:` section where behaviour differs
  (`Differences from curses:` in `curses` and `panel`), and
  `TkCurses extension:` on API tkinter lacks;
- a `Sample output:` example on every widget and every option that changes how
  one looks.

The breaches that predate the convention are listed in
`tests/support/docstring_debt.json`, which may only shrink. Measurements and
history go in comments or `ARCHITECTURE.md`, not in a docstring.

**Every widget option is measured, and one that shows has a sample.**
`tests/support/record_visible_options.py` draws each widget with and without
each option and records which change the screen, in `visible_options.json`.
The convention test then wants every option named in the class docstring, and
every one that shows sampled - a widget's own in a `Sample output (name):`
section, a shared one once on `docs/reference/options.md`. An option added to a
widget fails the test until the recorder is run again. "Invisible" there means
no difference in the states it tried, not "draws nothing": look before writing
that.

**A themed widget has Tk's options, not its own.** The ttk widgets subclass the
classic ones and keep the classic options as the defaults their drawing reads,
but refuse them to a program as Tk does: only the names in
`tk_ttk_options.json` are accepted, through `ttk._TK_OPTIONS`, which a test
holds equal to it. A default a themed widget needs goes in its
`_widget_options`, never through `kw`. The record is
`tests/support/record_tk_ttk_options.py`'s, taken from real tkinter; it needs a
display, and is re-run when the Tk the reference follows changes. An option Tk
has and TkCurses lacks is `missing`, and must still be named in the docstring.

**A method with two names is documented once**, under the name it was defined
with (`wm_title`, not `title`): `docs/_ext/aliases.py` skips the second. A
cross-reference must name the first - `` :meth:`Wm.wm_title` `` - or it points
at nothing, and Sphinx does not warn.

**A sample output is a program the docs build runs.** `docs/_ext/tkscreens.py`
runs each `Sample output:` example in the test harness's pseudo-terminal and
puts an SVG of the screen beside it; an example that raises, or writes anything
to stderr, fails the build. The body runs after `import tkcurses as tk`,
`from tkcurses import ttk` and `root = tk.Tk()`, in 40x10 cells unless a first
line says `# size: 60x15`.

**The guides' examples are tested.** Each complete program on a page carries a
`% expect: <text>` comment and is run in a pseudo-terminal by
`tests/test_docs_tutorial.py`, so a documentation-only change is still checked
against the library.

## Where Tk's manual is silent, ARCHITECTURE.md carries the measurement

This library is a compatibility layer, so most behaviour can be cited: "the
manual says X" settles an argument. Two cases need writing down in
`ARCHITECTURE.md`, next to the widget, rather than in a commit message:

- **Tk does something its manual does not describe.** Tk 9.0 added
  `-placeholder` and `-placeholderforeground` to the entry family and
  documented neither.
- **Tk does something its manual describes wrongly.** `-tabs numeric` is
  documented in three sentences and all three are looser than the behaviour.

A measurement in a commit message is one nobody will find. Write down how it
was measured, too. **Some behaviour needs eyes:** when the answer can only be
read off a screen, write a throwaway tkinter probe, say what to look at, and
have a person run it, rather than inferring what seems reasonable.

## Writing a tty test

**A test must wait for every cell it asserts on.** Curses writes to the pty and
the harness drains it in chunks, so a sample can land mid-frame. Waiting for one
thing and asserting on another fails a different test on a different Python
version each run, never reproducibly. Use
`term.wait_for_cell(row, column, predicate)`, or one `wait_for` whose predicate
names every cell the assertions read.

```bash
python3 tests/support/audit_waits.py   # tests that may have the fault
```

Not every flagged test is wrong - waiting for `"hello"` and asserting on the
row holding `"hello"` is fine. Run it when adding tty tests.

**Wait for something the application draws, not for a sentinel it will paint
over.** A `buffer.write(row, col, "ready")` before `mainloop()` is overwritten
by the first redraw if that cell belongs to a widget, so it exists only for a
moment: a fast machine samples inside it and passes, a contended runner does
not, and the wait reports the program's exit rather than the cause.

```bash
TKCURSES_LATE_SAMPLE=1 pytest -m tty   # settle the screen before sampling
```

That makes this fault certain instead of occasional. A few tests fail under it
and are correct as written - each waits for a "before" state and schedules its
change with `after(100)` - so read the failures rather than keeping it green.

## Borrowed code and algorithms

Credit is written **in the source file**, next to the code. Commits are not
read by whoever maintains the function later.

- **A published algorithm** implemented from its own published description is
  not derived from wherever it was noticed - the sRGB transfer function
  (IEC 61966-2-1), DIN99d, median cut, Floyd–Steinberg. Credit it anyway,
  naming the algorithm and its source.
- **chafa's own engineering** - the 8×8 work cell, symbol-bitmap matching, the
  PCA colour split, smolscale - is Hans Petter Jansson's work, not a standard.
  Taking any of it makes a derived work that must carry his copyright and the
  LGPL notice. Ask the maintainer first.
- **Tcl/Tk and tkinter** are credited in
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), with their licence texts,
  which ship in every built package. `tests/test_licensing.py` enforces two
  rules. Code that follows a Tk or Tcl library procedure names the procedure
  beside it (`tk::TextSelectTo`, `ttk::entry::ExtendTo`, `scrlbar.tcl`), and a
  source file that names one carries the Tcl/Tk credit in its header; add the
  script to the notices table when it is a new one. Code adapted from CPython's
  `Lib/tkinter` keeps the PSF copyright line in its header and is listed in the
  notices with a summary of the changes. Reimplementing tkinter's *interface* -
  names, signatures, constants - is not adapting its code.

## Versions and releases

**The version comes from git** (setuptools-scm): the last tag, then
`.devN+g<hash>` counting the commits since it, so every merge is a newer
version and `pip install -U git+...` upgrades. Never write a version by hand.
An editable install records the version it was installed at; run
`pip install -e .` again to refresh `tkcurses.__version__`.

```bash
python3 tests/support/check_upgrade.py  # install, commit, upgrade: CI's build job runs it
```

**Releasing is pushing a tag**, and only the maintainer decides when. An
annotated tag such as `v0.3.0rc1` on a `master` commit runs
`.github/workflows/release.yml`: the whole CI suite, a check that the tagged
commit is on `master`, a build that must be exactly the tag's version, a
smoke install of the wheel, the maintainer's approval of the run (the
publishing job is in the `release` environment, which only a `v*` tag may
deploy to), then a GitHub release with the sdist, the wheel,
the documentation and a `SHA256SUMS` of the three - a pre-release for an rc,
alpha or beta, with the CHANGELOG's section for that version as its text.
Each file carries a signed build-provenance attestation:
`gh attestation verify <file> -R slfields/TkCurses` checks that it was
built by this workflow from this repository. Run
the workflow from the Actions tab to rehearse without publishing. Its
decisions are in `.github/scripts/release.py`, tested by
`tests/test_release_script.py`.
