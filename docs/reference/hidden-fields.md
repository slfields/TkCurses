# Hidden fields

A field with `show` set hides what is typed in it: a password, a passphrase,
a token. Four widgets take `show`: {class}`tkcurses.Entry`,
{class}`tkcurses.ttk.Entry`, {class}`tkcurses.ttk.Combobox` and
{class}`tkcurses.ttk.Spinbox`. {func}`tkcurses.simpledialog.askstring`
passes `show` on to its field.

This page covers four things:

- what such a field hides;
- where it keeps the text, and for how long;
- which parts of the tkinter API still hand the text out as a Python
  string;
- how a program should read the value.

## In short

```python
password = tk.Entry(root, show="*")    # hidden from the start
...
with password.secret() as view:        # the value, without a str
    key = kdf.derive(view)             # hashlib, hmac, cryptography...
password.delete(0, "end")              # the field's memory is wiped
```

Set `show` when the field is made. Don't give it a `textvariable` or a
`validatecommand`. Read the value with {meth}`~tkcurses.Entry.secret`, not
`get()`. Clear the field when you are done.

## What the widget hides

With `show="*"`, everything that leaves the widget on its own gets the mask
character:

- **The screen** shows one mask character for each character typed. The
  field's width comes from the mask, so a wide character does not show up
  as a wider gap.
- **The selection** that other programs read (PRIMARY: OSC 52 or the
  desktop's own) holds the mask characters, as in Tk.
- **Copy and Cut** put the mask characters on the clipboard, as in Tk.
- **Control-Left and Control-Right** in an Entry or a ttk.Entry go to the
  start or the end, as in Tk, so the cursor does not show where the words
  break. A ttk.Combobox and a ttk.Spinbox still move by word, which is also
  what Tk does.
- **Nothing is logged.** TkCurses writes no log, so keys typed into a field
  are never written to a file.

A `placeholder` is drawn as plain text, not masked, because it is not the
field's contents.

## Where the text is kept

A Python `str` cannot be changed once it is made, and Python does not clear
the memory a string used when it frees it. So a password kept in a `str`
stays in the process's memory after it is deleted, until that memory happens
to be reused. Python's own developers do not consider this a bug, because a
`str` cannot be cleared safely.

**So a field with `show` set never keeps its contents in a `str`.** The text
lives in memory of its own, outside Python's objects, one character per four
bytes:

- **Wiped.** Every byte is overwritten with zeros when text is deleted,
  when the field grows and moves to a larger block, when `show` is turned
  off, and when the widget is destroyed.
- **Locked.** The memory is locked into RAM where the system allows it, so
  it is not written to swap. On Linux it is also left out of core dumps.
- **Guarded, with libsodium.** When the system has libsodium installed
  (`libsodium` from the package manager), the memory comes from libsodium's
  `sodium_malloc`. That puts guard pages around it and wipes it with
  `sodium_memzero`. Without libsodium it is an anonymous `mmap`, locked with
  `mlock` and wiped with `memset`. Either way the field behaves the same.
- **Typing makes no copies.** A keystroke changes the field's memory in
  place. The text is not assembled anywhere else unless something below
  asks for it.

If the memory cannot be locked, for example because of a container's
`RLIMIT_MEMLOCK`, the field still works and is still wiped. The program
prints one line about it on stderr when it exits:

```text
tkcurses: a hidden field's memory could not be locked against swap - Cannot allocate memory. It was still wiped.
```

## What still makes a string

These are part of tkinter's API, and they keep working as they do in
tkinter. Each one makes a Python `str` of the text, and the widget can't
wipe that string. A program that uses them gives up some of the protection
described above.

| Feature | What it copies, and when |
|---|---|
| `get()` | The whole text, each time it is called. |
| `textvariable` | The whole text, into the variable, on every keystroke. |
| `validatecommand` | `%P`, `%s` and `%S` (or a callable's argument), on every keystroke it validates. |
| `insert(index, string)` | The `string` you pass is yours, and it stays a `str`. |
| Paste | The clipboard's text, before it reaches the field. |
| `show` set after text is in the field | The `str` the text was held in until then. |
| ttk.Spinbox stepping, ttk.Combobox matching | The text, while comparing it with `values`. |
| `askstring(..., show="*")` | The answer it returns is a `str`. For a secret, use an Entry and `secret()`. |

Each key also reaches the widget as a one-character string. Python shares a
single object for each Latin-1 character, so typing does not add copies of
those. A character beyond Latin-1 is a short-lived string of its own, but
only ever that one character, never the text.

## Reading the value

{meth}`~tkcurses.Entry.secret` is a TkCurses extension. Use it in a `with`
statement. It gives a read-only `memoryview` of the text as UTF-8, in memory
of its own, and wipes and releases that memory when the block ends, even if
the block raises:

```python
import hashlib, hmac

with password.secret() as view:
    ok = hmac.compare_digest(hashlib.sha256(view).digest(), stored_digest)
password.delete(0, "end")
```

Pass the view straight to whatever needs the value. `hashlib`, `hmac`,
`cryptography` and `socket.send` all take a buffer. `bytes(view)` and
`view.tobytes()` make an ordinary `bytes` object, which is a copy that
can't be wiped, so avoid them.

## What a program should do

TkCurses can only protect the text while the widget holds it. What the
program does with the value afterwards is up to the program. These habits
keep the copies few:

- **Set `show` when you create the field**, so its contents are never a
  `str`.
- **Leave out `textvariable` and `validatecommand` on a hidden field.**
  Check the value after it has been entered, through `secret()`.
- **Read it with `secret()`, once, when it is needed**, and use it straight
  away. Do not keep it on an object or in a global.
- **Clear the field when you are done** with `delete(0, "end")`, and
  destroy the dialog it was in.
- **Never log, print or show the value**, and never put it in an
  exception's message, a `messagebox`, or a traceback that is reported
  somewhere.
- **Hand key material to a native library.** `cryptography`, PyNaCl and
  the operating system's keyring keep secrets in memory they manage
  themselves, outside Python. That is what Python's developers recommend
  for secrets.
- **Turn off core dumps and use encrypted swap** where the value matters:
  `resource.setrlimit(resource.RLIMIT_CORE, (0, 0))` in the program, and
  encrypted swap on the system.

## What this does not protect against

This is defence in depth, not a guarantee. Anything that can read the
process's memory while the field holds the text can read the text: a
debugger, another process running as the same user, or the kernel. Python's
own threat model leaves such an attacker out of scope, and so does this one.
What the hidden field does is keep the text from lingering, so it isn't
there to be found after the program has finished with it.
