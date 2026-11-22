# Security

## Reporting a vulnerability

Report it privately, through GitHub: on this repository's **Security** tab,
choose **Report a vulnerability**. Please do not describe it anywhere public
first. The report reaches the maintainer only, and the fix and any advisory
are worked out there.

Include what you can of: the TkCurses version (`tkcurses.__version__`), the
terminal and `TERM`, the Python version, and the smallest program that shows
the problem.

## What is supported

Fixes go into the next release from `master`. Older releases are not patched;
upgrade with `pip install -U git+https://github.com/slfields/TkCurses`.

## Scope

TkCurses runs inside the program that imports it, with that program's
permissions. Of most interest are ways for **data shown on screen** -
clipboard contents, file names, text loaded into a widget, an image file - to
make the library write control sequences the program did not ask for, read
files it was not given, or run commands.

## How the code is held to it

The rules the code follows - what counts as untrusted input, the limits on
it, failing safely, keeping secrets out of the repository, and the scans CI
runs - are in [CONTRIBUTING.md](CONTRIBUTING.md#secure-coding). What a
password field hides, and how long its text stays in memory, is on the
documentation's [hidden fields](docs/reference/hidden-fields.md) page.
