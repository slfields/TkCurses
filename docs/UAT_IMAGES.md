# UAT: Images — contents

Three scenarios live in this file, and the checklists for the later two are
a long way down it. They are:

| Scenario | What it is for | Checks |
|---|---|---|
| **35** — [Images](#uat-images) | A pixel is half a character cell. Art built in a source file, `compound`, and the reference trap | 35.0 – 35.7 |
| **36** — [The image viewer](#uat-the-image-viewer) | Opening real PNG, GIF, PGM, PPM and XBM files through the filtered file dialog, and what several in a row cost in colour pairs | 36.1 – 36.5 |
| **37** — [Image rendering quality](#uat-image-rendering-quality) | The one render path — averaged, linear light, perceptual colour, written past curses in whichever form the terminal takes | 37.0 – 37.4 |

Run one with `python3 -m uat 35`, `36` or `37`.

Scenario 37 wants a **terminal of at least 120x44**. It works in anything and
says so when the pictures are too small to judge — at 80x24 they come out
26x8 cells, where the differences are all present and none of them are
visible.

---

# UAT: Images

Scenario 35. Run it with:

```bash
python3 -m uat 35
# or
python3 -m uat.scenario_35_images
```

The claim under test is one sentence: **a pixel is one cell wide and half a
cell tall**, and it is the same pixel a Canvas draws on. There is one pixel
plane in this library and an image is on it — so `width()` and `height()`
answer in pixels, an image 8 by 6 occupies 8 cells across and 3 rows down,
and `▀`, `▄` and `█` are what reaches the screen, through the same
`compose()` a Canvas uses.

The first version of this got it wrong, with a pixel being a whole cell and
an image being a grid of glyphs. Check 35.0 is the one that would have
caught it.

Three behaviours are reproduced from Tk rather than improved on, because
tkinter code is written around them. Each was measured on Tk 9.0.2 and each
has a check below: the `compound=none` default, a widget following its image,
and an image that nothing references going away.

---

## 35.0 The circle is round

This is the check the whole design rests on. If a pixel were a whole cell,
a circle drawn as wide as it is tall would appear as an ellipse half its
proper height, because a character cell is about twice as tall as it is
wide. Half-cells are very nearly square, so it comes out round.

**Do:** look at the `round:` circle on the right.

**Look for:**

- [ ] It is **round** — as tall as it is wide, to the eye.
- [ ] It is 12 cells across and occupies **6 rows**, because it is 12 pixels
      by 12.
- [ ] Its left half is cyan and its right magenta, and the two colours meet
      cleanly down the middle.
- [ ] Its edges use `▀` and `▄`, not just `█`. That is a half-lit cell, and
      it is the only reason the curve looks smooth.

## 35.1 An image is drawn where the widget is

**Do:** start the scenario.

**Look for:**

- [ ] The `Label:` row shows a small house.
- [ ] `Bitmap:` shows an arrow **pointing right**. This is real XBM data,
      parsed a bit per pixel, not a picture of an arrow typed out. (It
      pointed left until someone ran this: XBM is least-significant-bit
      first, and the bytes had been written as though it were the other way
      round.)
- [ ] `Button:` shows the house inside a button's border.
- [ ] `Check:` shows `[x]`, the house, then `on`.
- [ ] The status line reads `image=6x4px = 6x2 cells`, and `Label asks 6x2`.
      **The two heights differ by exactly half**, and that is the point: the
      image is measured in pixels and the widget lays out in cells.

## 35.2 `compound=none` hides the text — the surprising default

Measured on Tk with `text='hello'` and an 8x4 image: the widget asks for
10x6, the image plus its border. The text contributes **nothing**.

**Do:** look at the `with text:` row before pressing anything, then press `c`
once.

**Look for:**

- [ ] Before: the house, and **no** `Home` anywhere. The label has text and
      is not drawing it.
- [ ] After one `c`: `compound=left`, and `Home` appears to the right of the
      house with one blank cell between them.
- [ ] The status line's `caption asks` grows by the width of `Home` plus that
      one cell.

## 35.3 The rest of the compounds

**Do:** keep pressing `c`. It cycles none → left → right → top → bottom →
center → none.

**Look for:**

- [ ] `right`: `Home` first, then the house.
- [ ] `top`: the house above, `Home` below it.
- [ ] `bottom`: `Home` above, the house below.
- [ ] `center`: `Home` drawn over the house — the block is the larger of the
      two in each direction, not the sum.
- [ ] Back at `none`, `Home` disappears again.
- [ ] The `Checkbutton:` never changes. It is fixed at `left` on purpose, so
      there is something still to compare the others against.

## 35.4 A widget follows its image

Measured on Tk: resizing an image from 4x2 to 20x10 moved a live Label's
request from 6x4 to 22x12 **with nothing asked of the label**.

**Do:** press `p`, then `s`, then `s` again.

**Look for:**

- [ ] `p` paints the image's top half magenta, in **every** widget showing
      it at once — the label, the captioned label, the button and the
      checkbutton. Nothing was asked of any of them; the write went to the
      image.
- [ ] `s` redraws the house at double scale — 12x8 pixels, so 12 cells wide
      and 4 rows — and every one of those widgets grows with it. It is still
      recognisably **the same house**, just bigger. The status line's
      `image=` and `Label asks` move together, still halving.
- [ ] **The rows below each grown widget move down to make room.** The
      captions, the button and the `z / x:` row all shift; nothing is drawn
      over anything else.
- [ ] `s` again returns it to 6x4 and everything moves back up.

### Why things move, and when they do not

Worth being explicit, because it is a fair thing to wonder about: the
widgets here are laid out with **`grid`**, and `grid` reflows — a widget
whose requested size changes pushes its neighbours along. That is what makes
this check visible at all.

Had they been laid out with **`place`**, nothing would have moved. `place`
is absolute positioning in Tk and here: a placed widget stays exactly where
it was put, and a grown neighbour is simply drawn over it. That is not a
bug in images, it is what `place` means — and an earlier version of this
scenario used it, which is why pressing `s` used to paint the house straight
through the button's border and across the circle.

## 35.5 A hole is not a space

**Do:** press `s`, then `h`.

**Look for:**

- [ ] A diagonal of gaps appears through the image. Press `s` first, so
      there is a solid house worth punching through.
- [ ] Those cells show the **label's** background, not something the image
      painted. The image declined to write there rather than writing a
      space — which is what transparency is when there is no alpha channel.
- [ ] Where only one of a cell's two pixels is a hole, the cell becomes `▀`
      or `▄` rather than disappearing. Half a cell can be transparent.

## 35.6 zoom and subsample

ARCHITECTURE.md used to mark both N/A. They are the two operations that
survive the move to this plane most cleanly: repeating a pixel is exactly
what enlarging means when the plane is this coarse.

**Do:** press `z`, then `x`, watching the `z / x:` slot.

**Look for:**

- [ ] `z` doubles the image in both directions — every pixel becomes a 2x2
      block of pixels, so the image grows to twice the width and twice the
      rows.
- [ ] `x` halves it, keeping every second pixel, and the house becomes a
      few cells of suggestion. That is what throwing away three quarters of
      a small image looks like.
- [ ] Only the `z / x:` widget changes. `zoom()` and `subsample()` return new
      images; they do not alter the one they were called on. (Both work from
      the house at its **original** scale, so `s` does not change what they
      produce — zooming an already-doubled house is 24 cells wide and just
      runs out of terminal.)

## 35.7 The trap

**Do:** press `d`.

**Look for:**

- [ ] The house disappears from all four widgets at once — label, caption,
      button and checkbutton.
- [ ] The status line says `image=gone` and the registry no longer lists
      `house`.
- [ ] **The widgets stay exactly the size they were** — whatever `Label
      asks` said before, it still says. This is measured Tk behaviour: deleting an image under a live
      Label left it at its old 22x12. The geometry it negotiated survives;
      only the drawing stops.
- [ ] `Home` comes back on the captioned label. With no image, `compound=none`
      has nothing to prefer over the text.
- [ ] The **arrow is unaffected**. It is still referenced, so it is still
      there — which is the whole distinction being drawn.
- [ ] Nothing raises. An image going away underneath a widget is not an
      error; only *setting* a name that does not exist is.

This is why every tkinter tutorial says to keep a reference to your images.

**Do:** press `r`.

- [ ] Everything comes back, **all four widgets included**. (The checkbutton
      was the one left blank the first time this was run: it was built
      inline and never captured, so the rebuild could not reach it.)

---

## What would count as a failure

- **An oval circle.** That is the half-cell plane not being used, and it is
  the failure this scenario exists to make visible.
- An image whose height in cells equals its height in pixels.
- Text appearing next to an image at `compound=none`.
- A widget not following its image's size, or following it only after
  something else is touched.
- A hole painting over what is behind it.
- `d` leaving the art on the screen. The image is gone and the widget agrees
  it has none; anything still drawn is a repaint that never happened.
- `d` collapsing a widget to nothing rather than leaving its size alone.
- An exception from `d`, or from the terminal being resized at any point.


---

# UAT: The image viewer

Scenario 36. Run it with:

```bash
python3 -m uat 36
```

Scenario 35 showed images built in a source file. This one opens real ones:
**PNG, GIF, PGM and PPM through `PhotoImage`, and XBM through
`BitmapImage`** — the same formats tkinter 8.6 and later read, decoded with
nothing but the standard library.

The scenario writes its own folder of test images on startup, so there is
always something to open whatever machine it runs on, and it opens the first
one for you.

---

## 36.1 Every format opens

**Do:** press `n` repeatedly to step through the folder.

**Look for:**

- [ ] `arrow.xbm` draws an arrow pointing right, and the status says
      **opened as BitmapImage**. XBM is BitmapImage's format and PhotoImage
      will not read it — in Tk either — so the viewer has to look at the
      file before choosing a class.
- [ ] `big.png`, `gradient.png`, `blocks.gif`, `colour.ppm` and `ramp.pgm`
      all draw, each **opened as PhotoImage**.
- [ ] Every one reports its size twice: in **pixels**, and in **cells**,
      the second always half the first in height.
- [ ] The gradients are smooth left to right, and the GIF's blocks are four
      distinct colours. A shifted or repeated row means a decoder bug.

## 36.2 An interlaced PNG, and a file that is not an image

**Do:** keep pressing `n` until each comes round.

**Look for:**

- [ ] `interlaced.png` **opens like any other PNG**, showing the same kind
      of gradient as the rest. It is a real Adam7 file — the image stored as
      seven passes over a lattice rather than row by row — and it used to be
      refused by name. If it opens as bands of noise, the de-interlacing is
      wrong; if it is refused, it is not being attempted.
- [ ] `bad.txt` never appears under the `Images` filter at all. Switch the
      chooser to `All files` and open it by hand: **"couldn't recognize data
      in image file"**, which is Tk's own wording, and no traceback.

## 36.3 Images load at their native size

**Do:** press `n` until `big.png` is up — 160x120 pixels, so 160 cells wide
and 60 rows, on a screen that is neither. Then press `f`.

**Look for:**

- [ ] Fitted, the status says **showing 40x15 cells** — subsampled by 4 —
      and the whole picture is on screen.
- [ ] `f` again says **showing 160x60 cells, actual size**, and the image
      now runs off the right and bottom edges.
- [ ] The reported **pixel** size never changes. The image is always
      160x120; only what the viewer chooses to show changes.

This is the part worth understanding rather than just ticking. `PhotoImage`
loads at native size, exactly as Tk's does — it does not fit itself to
anything. Fitting is the viewer's job, done here with `subsample()`.

## 36.4 The file dialog filters to images

**Do:** press `o`.

**Look for:**

- [ ] The listing shows **only openable images** — no `bad.txt`.
- [ ] Above the filter box is a chooser reading `Images`. Open it: `PNG`,
      `GIF`, `Netpbm`, `Bitmaps`, `All files`.
- [ ] Choosing `PNG` leaves only the three `.png` files. Choosing `Netpbm`
      leaves the `.ppm` and the `.pgm` — **one filetype, two patterns**.
- [ ] Choosing `All files` shows everything, `bad.txt` included.
- [ ] Choosing a file opens it.
- [ ] Escape cancels and the status says so.

Both halves of this were broken until this cycle: a filetype naming several
patterns matched **nothing**, because the whole string went to `fnmatch` as
one pattern; and every filetype after the first was unreachable, because
only `filetypes[0]` was ever read.

---

## 36.5 The tenth image looks like the tenth image

**This is the check for a bug UAT 36 passed over.** The first picture always
looked right, which is exactly why nobody noticed.

**Do:** press `n` repeatedly, going right round the folder at least twice.
Press `i` after each one, or at least after the first, second and last.

**Look for:**

- [ ] Every picture is drawn **in its own colours**. Not "colourful" — the
      tenth should look like the tenth, not like a wash of whatever the
      first one was made of.
- [ ] `i` reports `exhausted=False` throughout, however many you load.
- [ ] `pairs=` goes up and comes **back down** as pictures are replaced. It
      should sit near what the current picture needs, not climb to the
      capacity and stay there.
- [ ] Going round a second time, a picture looks the same as it did the
      first time.

A colour pair is a `(foreground, background)` combination and the terminal
has 255 of them — eight bits in the attribute, not a tunable. They used to
be handed out and never given back, so measured on `xterm-256color`:

    mickey.gif  pairs=238  exhausted=False
    earth.gif   pairs=255  exhausted=True
    mickey.gif  pairs=255  exhausted=True     and from here, wrong colours

Now the table is rebuilt from what is actually on screen whenever it runs
dry, so the same sequence reads 238, 240, 238, 240 and never exhausts.

---

## What would count as a failure

- A format that will not open, or opens with rows shifted or repeated.
- An XBM opened as a PhotoImage, or any file opened as the wrong class.
- A traceback from `bad.txt` or `interlaced.png`, rather than a message.
- `interlaced.png` refused without naming interlacing.
- An image that shrinks itself to fit without `f` being pressed.
- The dialog listing `bad.txt` under `Images`, or listing nothing under
  `Netpbm`.
- The filetype chooser missing, or choosing a type changing nothing.


---

# UAT: Image rendering quality

Scenario 37. Run it with:

```bash
python3 -m uat 37
```

**The image is technically right and it looks wrong.** That was the problem
this scenario was built to chase, and chasing it produced a render path with
no remaining choices in it.

One render, and the reasons it is the one:

| step | what it does |
|---|---|
| shrink | the block **averaged**, never every n-th pixel dropped |
| arithmetic | in **linear light**, not in sRGB bytes |
| colour | matched **perceptually**, in DIN99d |
| dithering | **none** |
| colour combinations | written past curses in whichever form the terminal takes; fitted to the free pairs only where it takes neither |

The first four are what chafa does, checked against its source. **The scenario
used to show all four combinations at once and ask which looked best; that
question is answered and the choice is gone.**

The fifth is about a limit chafa does not have. Curses paints a registered
*pair*, and there are 255 of them — Python's binding packs the number into
eight bits, so `color_pair(300)` wraps to 44. A photograph wants thousands.
So the cells are written as SGR ourselves: `ESC[38;2;r;g;b` where `COLORTERM`
says the terminal takes direct colour, `ESC[38;5;N` against the palette where
it merely has 256. **Both escape the ceiling** — a palette terminal has no
pair limit either once the sequences are written by hand. Only below 256
colours, or with the escape hatch shut, is the picture fitted to the pairs
that are free.

Measured at 106x33 against a Lanczos reference:

| | TkCurses | chafa |
|---|---|---|
| mickey.gif, 256 | **25.03**, 88 colours | 33.16, 88 colours |
| mickey.gif, truecolor | **6.88**, 1793 colours | 11.78, 1778 colours |
| earth.gif, 256 | **24.06**, 35 colours | 27.83, 36 colours |
| earth.gif, truecolor | **6.54**, 4309 colours | 7.48, 3785 colours |

---

## 37.0 Enough room, and the table not full

**Do:** start the scenario. Press `t`.

**Look for:**

- [ ] The picture is at least **52x16 cells**. Below that the differences
      are all present and none of them visible. A 120x44 terminal gives
      about 106x33.
- [ ] `t` reports `direct=`. **Read that first, because it decides what the
      rest of this scenario means.** It has three values:

| `direct=` | when | what to expect |
|---|---|---|
| `truecolor` | `COLORTERM` says so | exact colour, thousands of them |
| `palette` | 256 colours, no `COLORTERM` | the cube, hundreds of them |
| `off` | 8 or 16 colours, or the hatch shut | fitted to the free pairs, a handful |

- [ ] With `truecolor` or `palette`, the status line says the ceiling does
      not apply and the colour count is in the hundreds or thousands.
      `exhausted` may say `True` and **does not matter** — that is the curses
      layer underneath, which is only a fallback.
- [ ] With `off`, the status line reads `pairs wanted: N of M budget` with N
      at or below M, and `t` reports `exhausted=False`.
- [ ] These four give the three, and the first should look best:

```bash
COLORTERM=truecolor python3 -m uat 37             # truecolor
COLORTERM= python3 -m uat 37                      # palette
TKCURSES_DISPLAY_DIRECT_IMAGES=0 python3 -m uat 37  # off
TERM=xterm python3 -m uat 37                      # off, and 8 colours
```

The old four-panel version of this scenario could not pass this check. Its
four pictures wanted 984 pairs between them, the table filled during the
second, and the two drawn last — both of them the dithered ones — were drawn
from the leftovers. `TkCurses-8cn`.

---

## 37.1 The fitting is doing something, and says so

**This check needs `direct=off`**, because fitting is what happens only when
the cells are not written past curses. Run it as:

```bash
TKCURSES_DISPLAY_DIRECT_IMAGES=0 python3 -m uat 37
```

**Do:** read the second status line. Press `f` to turn fitting off, then
`f` again.

**Look for:**

- [ ] Fitted, it reports what the picture *would* have wanted:
      `(unfitted this picture would want 991)` against a budget near 231.
- [ ] With `f` off, `t` now reports `exhausted=True` on a photograph at 256
      colours — that is the ceiling being hit, and it is what fitting avoids.
- [ ] With `f` off the picture is **worse**, not better: colours drift as
      later cells fall back to whatever pair is nearest among those already
      taken.
- [ ] Press `f` again and it recovers.

**`f` does nothing unless `direct=off`**, because there is no ceiling to fit
to otherwise. Run `TKCURSES_DISPLAY_DIRECT_IMAGES=0 python3 -m uat 37` to
exercise this check.

---

## 37.2 The picture looks like the picture

**Do:** look at it. Press `n` to cycle.

**Look for:**

- [ ] Recognisable shapes with clean edges. Mickey's outline should be a
      line, not a smear.
- [ ] **No horizontal banding** in smooth regions. Stripes there were a real
      bug — `TkCurses-20y` — caused by the two halves of a cell being
      resolved against different palettes.
- [ ] No large flat area of one wrong colour where the source has a gradient.
- [ ] Nothing painted black on black, which shows as a hole.

---

## 37.3 Colour depth changes it in the right direction

**Do:** run with `TERM=xterm`, `xterm-16color`, `xterm-256color`.

**Look for:**

- [ ] Each step up is **better, or at least no worse**. A richer terminal
      that looked worse was a real bug and the reason much of this exists.
- [ ] At 8 colours the picture is coarse but still the right *shape*, and
      still not striped.
- [ ] At 256 the colours are close enough to argue about.
- [ ] `t` reports the depth it actually detected, matching the TERM you set.

---

## 37.3a Truecolor against the palette, which is the difference you can see

**Do:** run it twice, once with `COLORTERM=truecolor` and once with
`COLORTERM=`, on the same 256-colour terminal. Press `t` in each.

**Look for:**

- [ ] `direct=truecolor` in the first, `direct=palette` in the second.
- [ ] Both report thousands of colours and both say the ceiling does not
      apply. Neither should look like the `off` case.
- [ ] The truecolor one is **better**, and visibly: it can say the exact
      colour, where the palette one is held to the 256-entry cube. Measured
      against a Lanczos reference, 6.88 against 25.03 on mickey.gif.
- [ ] The palette one honours your terminal's **theme** — it names cube
      entries, so a themed palette shows through. The truecolor one does
      not, because an exact RGB has no theme to honour. That is the trade,
      and it is the right way round for a photograph.

---

## 37.4 It is quick enough to be usable

**Do:** press `n` a few times.

**Look for:**

- [ ] Each picture appears promptly. Fitting a full-screen photograph was
      measured at about 200ms; it was **8.7 seconds** before the palette was
      grown once rather than rebuilt for every candidate size, and that is
      the kind of regression this check exists to catch.
- [ ] Cycling right round the list and back gives the same picture again,
      in the same colours.

---

## What would count as a failure

- `t` reporting `exhausted=True` while fitting is on and `direct=off`.
- `direct=palette` looking no better than `direct=off` — the whole reason
  the palette form exists is that a 256-colour terminal has no pair ceiling
  either. Measured, mickey.gif goes from 17 colours to 1584.
- Horizontal stripes in any smooth region.
- A picture at a higher colour depth looking worse than at a lower one.
- Turning fitting off making the picture *better* — that would mean the
  fitting is costing more than the ceiling does.
- A noticeable wait between pressing `n` and seeing the picture.
