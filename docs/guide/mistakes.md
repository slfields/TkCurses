# Common mistakes

Nearly everyone who learns tkinter makes each of these once. They are the
same in TkCurses, and each one has a symptom that points somewhere else,
which is what makes them worth knowing in advance.

## The widget never appears

**Symptom:** a widget was made, with no error, and is not on the screen.

```python
label = tk.Label(root, text="Hello")      # made, but not shown
```

Making a widget does not show it. It appears only once a geometry manager
has been asked to manage it, with `pack()`, `grid()` or `place()`:

```python
label = tk.Label(root, text="Hello")
label.pack()
```

The same symptom has a second cause: a widget packed into a frame that is
itself never packed. The frame is not shown, so nothing inside it is.

## The command runs at the start, and never again

**Symptom:** the function given to a button runs once when the program
starts, and pressing the button does nothing.

```python
tk.Button(root, text="Save", command=save())     # calls save now
```

`save()` *calls* `save`, there and then, and gives the button whatever it
returned - usually `None`, which is no command at all. Give the function
itself, without the brackets:

```python
tk.Button(root, text="Save", command=save)
```

To give the function arguments, wrap the call in a `lambda`, which makes a
new function that makes the call when it is itself called:

```python
tk.Button(root, text="Delete", command=lambda: delete(item))
```

## Every button does the same thing

**Symptom:** buttons made in a loop, each meant to do something different,
all do what the last one should.

```python
for number in range(3):
    tk.Button(root, text=str(number), command=lambda: choose(number)).pack()
```

The `lambda` does not remember the value `number` had when it was made; it
looks `number` up when it is called, and by then the loop has finished and
`number` is 2. Make the value an argument with a default, which *is*
fixed when the `lambda` is made:

```python
for number in range(3):
    tk.Button(root, text=str(number), command=lambda n=number: choose(n)).pack()
```

## pack and grid in one container

**Symptom:** an error naming both managers - *cannot use geometry manager
grid inside . which already has slaves managed by pack*.

```python
tk.Label(root, text="Name").grid(row=0, column=0)
tk.Button(root, text="OK").pack()         # the same container as the label
```

The widgets inside one container are arranged by one manager. Put the
gridded ones in a frame of their own, and pack the frame:

```python
form = tk.Frame(root)
form.pack()
tk.Label(form, text="Name").grid(row=0, column=0)
tk.Button(root, text="OK").pack()
```

## The program freezes

**Symptom:** for a while after a button is pressed, the program does not
respond to anything, and then catches up all at once.

```python
import time

def wait_and_say():
    time.sleep(3)                      # the whole program stops here
    status.configure(text="Done")
```

Callbacks run inside the main loop, and while one runs, the loop cannot
read keys or draw. Never sleep in a callback; schedule the rest of the work
with `after` and return:

```python
def wait_and_say():
    root.after(3000, lambda: status.configure(text="Done"))
```

Work that really takes time - reading a large file, waiting for the
network - belongs in a thread. A thread must not touch widgets, or call
their methods, itself. The usual arrangement is for the thread to put its
results on a `queue.Queue`, and for an `after` callback to look in the
queue every tenth of a second or so and show what it finds.

## A progress label shows only the end

**Symptom:** a label updated in a loop shows nothing until the loop ends,
and then only the last value.

```python
def count():
    for n in range(100):
        status.configure(text=f"Step {n}")
        do_step(n)
```

The screen is drawn when the callback returns, not while it runs. Do one
step at a time, and schedule the next:

```python
def count(n=0):
    if n < 100:
        status.configure(text=f"Step {n}")
        do_step(n)
        root.after(1, count, n + 1)
```

## print() scribbles on the screen

**Symptom:** text appears on top of the widgets, in the wrong place, and is
painted over at the next redraw.

The program's screen *is* the terminal, so `print()` writes straight onto
it. Show messages in a widget, or log them to a file with the `logging`
module; [Porting](porting.md#output-and-errors) shows how, and how to see
the tracebacks of errors in callbacks while the program runs.

## A picture disappears

**Symptom:** a `PhotoImage` shown in a label, made inside a function, is
blank.

```python
def show_logo():
    logo = tk.PhotoImage(file="logo.png")
    tk.Label(root, image=logo).pack()      # logo is gone when this returns
```

A widget does not keep the picture alive, as in tkinter: when the last
Python reference to the `PhotoImage` goes, so does the picture. Keep a
reference for as long as it is shown - on the widget is a common place:

```python
def show_logo():
    logo = tk.PhotoImage(file="logo.png")
    label = tk.Label(root, image=logo)
    label.image = logo
    label.pack()
```

## Colours that mean something

**Symptom:** on someone else's terminal, a red "error" and a green "ok"
look the same.

Colours are drawn as the nearest the terminal has, and some terminals have
eight, or none; and some people cannot tell red from green on any
terminal. Say it in words or marks as well - `"✗ failed"`, `"✓ ok"` - and
let the colour be the second way of saying it.
[Terminals](terminals.md#colours) shows how to try a program on a basic
terminal.
