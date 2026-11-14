# TkCurses - a tkinter-compatible API layer that renders to curses
# Copyright (C) 2026  Scott L. Fields
#
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""A form: labelled fields laid out with grid, and a check before it is sent.

Tab moves between the fields, space ticks a box or chooses a plan, and
Return presses the focused button. While the account is being made the form
is busy: a click on it does nothing until it is done.
"""

import tkcurses as tk
from tkcurses import messagebox, ttk

root = tk.Tk()
root.title("New account")

form = ttk.Frame(root, padding=1)
form.pack(fill="both", expand=True)
form.columnconfigure(1, weight=1)

name = tk.StringVar()
email = tk.StringVar()
country = tk.StringVar(value="Norway")
plan = tk.StringVar(value="free")
news = tk.BooleanVar(value=True)

ttk.Label(form, text="Name").grid(row=0, column=0, sticky="w", padx=(0, 1))
first = ttk.Entry(form, textvariable=name)
first.grid(row=0, column=1, sticky="ew")
ttk.Label(form, text="Email").grid(row=1, column=0, sticky="w", padx=(0, 1))
ttk.Entry(form, textvariable=email).grid(row=1, column=1, sticky="ew")
ttk.Label(form, text="Country").grid(row=2, column=0, sticky="w", padx=(0, 1))
ttk.Combobox(
    form, textvariable=country, values=("Norway", "Peru", "Japan"), state="readonly"
).grid(row=2, column=1, sticky="ew")

plans = ttk.Frame(form)
plans.grid(row=3, column=1, sticky="w", pady=1)
for value, label in (("free", "Free"), ("pro", "Pro"), ("team", "Team")):
    ttk.Radiobutton(plans, text=label, value=value, variable=plan).pack(
        side="left", padx=(0, 2)
    )
ttk.Checkbutton(form, text="Send me the newsletter", variable=news).grid(
    row=4, column=1, sticky="w"
)

status = ttk.Label(form, text="")
status.grid(row=5, column=0, columnspan=2, sticky="w", pady=1)


def submit():
    if not name.get().strip() or "@" not in email.get():
        status.config(text="A name and an email address, please")
        return
    # Busy holds the pointer off the form while the work is done. Keys
    # still reach the focused widget, as in Tk, so the focus goes to the
    # status line, which takes none.
    status.config(text="Creating your account...")
    form.tk_busy_hold()
    status.focus_set()
    root.after(1000, created)


def created():
    form.tk_busy_forget()
    status.config(text="")
    messagebox.showinfo(
        "Welcome", f"{name.get()}, your {plan.get()} account is ready.", parent=root
    )


buttons = ttk.Frame(form)
buttons.grid(row=6, column=0, columnspan=2, sticky="e")
ttk.Button(buttons, text="Create", command=submit).pack(side="left", padx=1)
ttk.Button(buttons, text="Cancel", command=root.destroy).pack(side="left")

first.focus_set()
root.mainloop()
