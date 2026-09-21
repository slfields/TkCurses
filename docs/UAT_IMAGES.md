# UAT: Images — contents

Three scenarios live in this file, and the checklists for the later two are
a long way down it. They are:

| Scenario | What it is for | Checks |
|---|---|---|
| **35** — [Images](#uat-images) | A pixel is half a character cell. Art built in a source file, `compound`, and the reference trap | 35.0 – 35.7 |
| **36** — [The image viewer](#uat-the-image-viewer) | Opening real PNG, GIF, PGM, PPM and XBM files through the filtered file dialog | 36.1 – 36.4 |
| **37** — [Image rendering quality](#uat-image-rendering-quality) | Averaging against dropping pixels, and dithering against flat colour | 37.0 – 37.5 |

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

Two problems with the same shape, and one screen that shows both: **the
image is technically right and it looks wrong.** The same picture is
prepared four ways and drawn side by side, because the difference is a
thing to see, and showing them one at a time would ask you to remember a
colour instead.

| | shrinking | colour |
|---|---|---|
| `dropped, flat` | every n-th pixel kept | nearest per pixel |
| `averaged, flat` | the block averaged | nearest per pixel |
| `dropped, dithered` | every n-th pixel kept | error diffused |
| `averaged, dithered` | the block averaged | error diffused |

The fourth is what a viewer should do. **The first is what this library did
until now.**

---

## 37.0 Enough room to judge them

**Do:** look at line 4 of the screen, and at the picture size on line 2.

**Look for:**

- [ ] The pictures are at least **52x16 cells**, and line 4 is blank.
- [ ] If line 4 says the pictures are too small, the terminal is too small.
      Make it **120x44 or larger** and run it again. At 80x24 they come out
      26x8, where every difference below is present and none is visible.

The panels size themselves to the terminal, so this costs nothing but a
bigger window. It is first because judging 37.2 and 37.3 in a small one
wastes the effort.

## 37.1 The numbers, which are the checkable part

Each caption reads `N/M unavailable` — of the M colours in that panel, N are
ones the terminal cannot show and would have to approximate.

**Look for:**

- [ ] Both **dithered** panels read **`0/…`**. That is the whole guarantee:
      after dithering, nothing is left that still needs approximating.
- [ ] Both **flat** panels read nearly all unavailable — on mickey at 256
      colours, `11/12` and `260/261`.
- [ ] `averaged, flat` has far more colours than `dropped, flat` (261
      against 12). Averaging invents intermediate colours; dropping pixels
      can only ever return ones that were already there.
- [ ] Dithering **reduces** the count on the averaged panel (261 → 45). It
      does not add colours; it snaps every pixel to one that exists.

## 37.2 Shrinking: dropped against averaged

**Do:** compare the two left panels with the two right ones, then press `n`
to change picture.

**Look for:**

- [ ] `dropped` loses thin features — whichever pixels missed the grid are
      simply gone, so fine detail flickers in and out between pictures.
- [ ] `averaged` keeps something of every pixel; edges are softer and
      shapes stay put.
- [ ] On the `earth` picture the terminator (the day/night line) is smooth
      under averaging and stepped under dropping.

Measured against a Lanczos reference at 320x200 reduced by six, averaging is
**38% to 93% closer at every colour depth** — including the flat cartoon,
which is the case where dropping pixels should have preserved the palette
and won.

## 37.3 Colour: flat against dithered

This check has no right answer written down, because **the first person to
run it disagreed with the measurement and was correct.**

**Do:** look at mickey's forest — the large dark area behind him — in the
flat panels and then the dithered ones. Then decide which of the four
panels you would rather look at.

**Look for:**

- [ ] In the **flat** panels the forest is one single flat grey. The
      256-colour palette has nothing for a dark reddish brown: its cube is
      empty between 0 and 95 while the grey ramp is dense there, so every
      distance metric — plain RGB, redmean, a chroma penalty, CIE Lab —
      picks that same grey.
- [ ] In the **dithered** panels it is a mix of eleven colours instead of
      one.
- [ ] **Whether that is an improvement is the thing being asked.** Record
      which panel you prefer.

Two measurements, both on mickey at 256 colours against an ideal reduction,
and they disagree:

| | flat | dithered |
|---|---|---|
| per-pixel | **13.48** | 18.50 |
| after a 3x3 blur | 10.03 | **3.71** |

Dithering trades colour accuracy for spatial noise, and that pays only when
the eye merges neighbouring pixels back together. It does on a monitor,
where a pixel is a quarter of a millimetre. **It does not here**, where a
pixel is half a character cell, so you see the dither pattern itself. Across
a grey ramp and two photographs at two depths, flat wins four times of six
per-pixel, and every time at 256 colours.

The blurred number was the only one taken when `dither()` was written, and
it encoded an assumption about the viewer that had never been checked.

## 37.5 Which one would you actually use

**Do:** ignore every number above and pick a favourite.

**Look for:**

- [ ] `averaged, flat` is expected to win on a normal terminal. If it does,
      that confirms the per-pixel measurement and the conclusion that
      dithering is a tool rather than a default.
- [ ] If a **dithered** panel wins for you, say so — it would mean the
      cells are small enough on your terminal for the eye to merge them,
      which is the case dithering is for, and worth knowing.

## 37.4 Dithering knows when to do nothing

**Do:** press `t`, and read the depth on line 2.

**Look for:**

- [ ] **On a truecolor terminal the dithered panels are identical to the
      flat ones, and all four read `0/…`.** That is correct, not a failure:
      every colour is available, so no pixel accumulates any error and there
      is nothing to spread. Dithering is self-limiting, which is what makes
      it safe to apply without asking whether it will help.
- [ ] At 8 colours the difference is at its most dramatic, because there is
      least to work with.
- [ ] `t` also reports the pairs allocated. It should be well under 255 —
      past that a pair number cannot be named in an attribute, which is the
      bug `TkCurses-7sh` fixed.

---

## What would count as a failure

- A dithered panel reading anything but `0/…` unavailable.
- The two averaged panels looking identical to the two dropped ones.
- Mickey's forest still a single flat grey in the dithered panels.
- Dithering changing anything at all on a truecolor terminal.
- A caption clipped so its numbers cannot be read — the panel is 38 cells
  and the first wording ran to 41, which is how this check was nearly
  impossible to make.
