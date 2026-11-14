# Module functions

```{eval-rst}
.. autofunction:: tkcurses.mainloop

.. autofunction:: tkcurses.NoDefaultRoot

.. autofunction:: tkcurses.getboolean

.. autofunction:: tkcurses.getint

.. autofunction:: tkcurses.getdouble

.. autofunction:: tkcurses.image_names

.. autofunction:: tkcurses.image_types

.. autoexception:: tkcurses.TclError
```

## Versions

Two describe the Tk and Tcl this library follows, as tkinter's do; two
describe TkCurses itself. Compare with `version_info`, not the string:

```python
import tkcurses

if tkcurses.version_info < (0, 3):
    raise SystemExit(f"needs TkCurses 0.3, found {tkcurses.__version__}")
```

```{eval-rst}
.. autodata:: tkcurses.TkVersion

.. autodata:: tkcurses.TclVersion

.. autodata:: tkcurses.__version__
   :no-value:

.. autodata:: tkcurses.version_info
   :no-value:
```

`Misc.info_patchlevel` gives the Tcl version in the same shape as
`version_info`.
