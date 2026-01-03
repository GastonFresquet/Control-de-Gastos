import json
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import tkinter as tk
from tkinter import ttk, messagebox

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "control_gastos.json")

def d(x):
    try:
        dec = Decimal(str(x).replace(",", "."))
    except InvalidOperation:
        raise ValueError("Número inválido")
    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def parse_date(s):
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()

def month_start(dt): return dt.replace(day=1)

def month_end(dt):
    if dt.month == 12:
        first_next = dt.replace(year=dt.year + 1, month=1, day=1)
    else:
        first_next = dt.replace(month=dt.month + 1, day=1)
    return first_next - timedelta(days=1)

def days_remaining_in_month(today):
    end = month_end(today)
    return (end - today).days + 1

def default_state():
    return {"categories": [], "people": [], "monthly_incomes": [], "extra_incomes": [], "expenses": []}

def load_state():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        st = default_state()
        save_state(st)
        return st
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(st):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)

def ensure_unique_add(lst, item):
    item = item.strip()
    if not item or item in lst:
        return False
    lst.append(item)
    lst.sort(key=lambda x: x.lower())
    return True

def set_monthly_income(st, person, amount, month_key):
    for row in st["monthly_incomes"]:
        if row["person"] == person and row["month"] == month_key:
            row["amount"] = str(amount)
            return
    st["monthly_incomes"].append({"person": person, "amount": str(amount), "month": month_key})

def add_extra_income(st, person, amount, dt, note=""):
    st["extra_incomes"].append({"person": person, "amount": str(amount), "dt": dt.isoformat(), "note": note.strip()})

def add_expense(st, category, amount, dt, note=""):
    st["expenses"].append({"category": category, "amount": str(amount), "dt": dt.isoformat(), "note": note.strip()})

def totals_for_month(st, today):
    month_key = today.strftime("%Y-%m")
    start, end = month_start(today), month_end(today)

    base = Decimal("0")
    for r in st["monthly_incomes"]:
        if r["month"] == month_key:
            base += d(r["amount"])

    extra = Decimal("0")
    for r in st["extra_incomes"]:
        dt = parse_date(r["dt"])
        if start <= dt <= end:
            extra += d(r["amount"])

    exp = Decimal("0")
    for r in st["expenses"]:
        dt = parse_date(r["dt"])
        if start <= dt <= end:
            exp += d(r["amount"])

    return base, extra, exp

def money(x: Decimal):
    return f"${x:,.2f}"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Control de Gastos")
        self.geometry("720x520")
        self.resizable(False, False)

        self.state = load_state()
        self.today = date.today()

        self._build_ui()
        self.refresh_lists()
        self.refresh_summary()

    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Tab 1: Resumen
        self.tab_summary = ttk.Frame(nb)
        nb.add(self.tab_summary, text="Resumen")

        self.lbl_summary = ttk.Label(self.tab_summary, text="", font=("Segoe UI", 12), justify="left")
        self.lbl_summary.pack(anchor="w", padx=12, pady=12)

        btn_refresh = ttk.Button(self.tab_summary, text="Actualizar", command=self.refresh_summary)
        btn_refresh.pack(anchor="w", padx=12)

        # --- Tab 2: Config (categorías/personas)
        self.tab_config = ttk.Frame(nb)
        nb.add(self.tab_config, text="Configuración")

        frm_cat = ttk.LabelFrame(self.tab_config, text="Categorías")
        frm_cat.place(x=10, y=10, width=335, height=430)

        self.ent_cat = ttk.Entry(frm_cat)
        self.ent_cat.place(x=10, y=10, width=220)
        ttk.Button(frm_cat, text="Agregar", command=self.add_category).place(x=240, y=8, width=80)

        self.lst_cat = tk.Listbox(frm_cat)
        self.lst_cat.place(x=10, y=45, width=310, height=360)

        frm_people = ttk.LabelFrame(self.tab_config, text="Personas (ingresos)")
        frm_people.place(x=365, y=10, width=335, height=430)

        self.ent_person = ttk.Entry(frm_people)
        self.ent_person.place(x=10, y=10, width=220)
        ttk.Button(frm_people, text="Agregar", command=self.add_person).place(x=240, y=8, width=80)

        self.lst_people = tk.Listbox(frm_people)
        self.lst_people.place(x=10, y=45, width=310, height=360)

        # --- Tab 3: Movimientos
        self.tab_moves = ttk.Frame(nb)
        nb.add(self.tab_moves, text="Movimientos")

        month_key = self.today.strftime("%Y-%m")
        ttk.Label(self.tab_moves, text=f"Mes actual: {month_key}", font=("Segoe UI", 10, "bold")).place(x=10, y=10)

        # Ingreso mensual
        frm_inc = ttk.LabelFrame(self.tab_moves, text="Ingreso mensual (por persona)")
        frm_inc.place(x=10, y=45, width=690, height=110)

        ttk.Label(frm_inc, text="Persona:").place(x=10, y=10)
        self.cmb_inc_person = ttk.Combobox(frm_inc, state="readonly")
        self.cmb_inc_person.place(x=70, y=10, width=200)

        ttk.Label(frm_inc, text="Monto:").place(x=290, y=10)
        self.ent_inc_amount = ttk.Entry(frm_inc)
        self.ent_inc_amount.place(x=340, y=10, width=140)

        ttk.Button(frm_inc, text="Guardar", command=self.save_monthly_income).place(x=500, y=8, width=90)

        ttk.Label(frm_inc, text="(Se guarda para el mes actual)").place(x=10, y=45)

        # Ingreso extra
        frm_extra = ttk.LabelFrame(self.tab_moves, text="Ingreso extra")
        frm_extra.place(x=10, y=165, width=690, height=125)

        ttk.Label(frm_extra, text="Persona:").place(x=10, y=10)
        self.cmb_extra_person = ttk.Combobox(frm_extra, state="readonly")
        self.cmb_extra_person.place(x=70, y=10, width=200)

        ttk.Label(frm_extra, text="Monto:").place(x=290, y=10)
        self.ent_extra_amount = ttk.Entry(frm_extra)
        self.ent_extra_amount.place(x=340, y=10, width=140)

        ttk.Label(frm_extra, text="Fecha (YYYY-MM-DD):").place(x=10, y=45)
        self.ent_extra_date = ttk.Entry(frm_extra)
        self.ent_extra_date.place(x=145, y=45, width=125)
        self.ent_extra_date.insert(0, self.today.isoformat())

        ttk.Label(frm_extra, text="Nota:").place(x=290, y=45)
        self.ent_extra_note = ttk.Entry(frm_extra)
        self.ent_extra_note.place(x=340, y=45, width=240)

        ttk.Button(frm_extra, text="Agregar", command=self.save_extra_income).place(x=590, y=8, width=90)

        # Gasto
        frm_exp = ttk.LabelFrame(self.tab_moves, text="Gasto")
        frm_exp.place(x=10, y=300, width=690, height=150)

        ttk.Label(frm_exp, text="Categoría:").place(x=10, y=10)
        self.cmb_exp_cat = ttk.Combobox(frm_exp, state="readonly")
        self.cmb_exp_cat.place(x=80, y=10, width=190)

        ttk.Label(frm_exp, text="Monto:").place(x=290, y=10)
        self.ent_exp_amount = ttk.Entry(frm_exp)
        self.ent_exp_amount.place(x=340, y=10, width=140)

        ttk.Label(frm_exp, text="Fecha (YYYY-MM-DD):").place(x=10, y=45)
        self.ent_exp_date = ttk.Entry(frm_exp)
        self.ent_exp_date.place(x=145, y=45, width=125)
        self.ent_exp_date.insert(0, self.today.isoformat())

        ttk.Label(frm_exp, text="Nota:").place(x=290, y=45)
        self.ent_exp_note = ttk.Entry(frm_exp)
        self.ent_exp_note.place(x=340, y=45, width=240)

        ttk.Button(frm_exp, text="Agregar", command=self.save_expense).place(x=590, y=8, width=90)

        ttk.Button(frm_exp, text="Actualizar resumen", command=self.refresh_summary).place(x=10, y=95)

    def refresh_lists(self):
        self.lst_cat.delete(0, tk.END)
        for c in self.state["categories"]:
            self.lst_cat.insert(tk.END, c)

        self.lst_people.delete(0, tk.END)
        for p in self.state["people"]:
            self.lst_people.insert(tk.END, p)

        self.cmb_inc_person["values"] = self.state["people"]
        self.cmb_extra_person["values"] = self.state["people"]
        self.cmb_exp_cat["values"] = self.state["categories"]

        if self.state["people"]:
            self.cmb_inc_person.set(self.state["people"][0])
            self.cmb_extra_person.set(self.state["people"][0])
        if self.state["categories"]:
            self.cmb_exp_cat.set(self.state["categories"][0])

    def refresh_summary(self):
        base, extra, exp = totals_for_month(self.state, self.today)
        total_inc = base + extra
        remaining = (total_inc - exp).quantize(Decimal("0.01"))
        days_left = days_remaining_in_month(self.today)
        per_day = (remaining / Decimal(days_left)).quantize(Decimal("0.01")) if days_left > 0 else Decimal("0.00")

        text = (
            f"Mes: {self.today.strftime('%Y-%m')}\n\n"
            f"Ingresos base:   {money(base)}\n"
            f"Ingresos extra:  {money(extra)}\n"
            f"TOTAL ingresos:  {money(total_inc)}\n\n"
            f"TOTAL gastos:    {money(exp)}\n"
            f"---------------------------\n"
            f"Te queda:        {money(remaining)}\n"
            f"Días restantes:  {days_left}\n"
            f"Por día:         {money(per_day)}\n"
        )
        self.lbl_summary.config(text=text)

    def add_category(self):
        name = self.ent_cat.get()
        if ensure_unique_add(self.state["categories"], name):
            save_state(self.state)
            self.ent_cat.delete(0, tk.END)
            self.refresh_lists()
        else:
            messagebox.showwarning("Atención", "Categoría vacía o ya existe.")

    def add_person(self):
        name = self.ent_person.get()
        if ensure_unique_add(self.state["people"], name):
            save_state(self.state)
            self.ent_person.delete(0, tk.END)
            self.refresh_lists()
        else:
            messagebox.showwarning("Atención", "Persona vacía o ya existe.")

    def save_monthly_income(self):
        person = self.cmb_inc_person.get().strip()
        amt_s = self.ent_inc_amount.get().strip()
        if not person:
            messagebox.showwarning("Atención", "Cargá personas primero (Configuración).")
            return
        try:
            amt = d(amt_s)
        except ValueError:
            messagebox.showwarning("Atención", "Monto inválido.")
            return

        month_key = self.today.strftime("%Y-%m")
        set_monthly_income(self.state, person, amt, month_key)
        save_state(self.state)
        self.ent_inc_amount.delete(0, tk.END)
        self.refresh_summary()
        messagebox.showinfo("OK", "Ingreso mensual guardado.")

    def save_extra_income(self):
        person = self.cmb_extra_person.get().strip()
        if not person:
            messagebox.showwarning("Atención", "Cargá personas primero (Configuración).")
            return
        try:
            amt = d(self.ent_extra_amount.get().strip())
            dt = parse_date(self.ent_extra_date.get().strip())
        except Exception:
            messagebox.showwarning("Atención", "Revisá monto y fecha (YYYY-MM-DD).")
            return
        note = self.ent_extra_note.get().strip()
        add_extra_income(self.state, person, amt, dt, note)
        save_state(self.state)
        self.ent_extra_amount.delete(0, tk.END)
        self.ent_extra_note.delete(0, tk.END)
        self.refresh_summary()
        messagebox.showinfo("OK", "Ingreso extra agregado.")

    def save_expense(self):
        cat = self.cmb_exp_cat.get().strip()
        if not cat:
            messagebox.showwarning("Atención", "Cargá categorías primero (Configuración).")
            return
        try:
            amt = d(self.ent_exp_amount.get().strip())
            dt = parse_date(self.ent_exp_date.get().strip())
        except Exception:
            messagebox.showwarning("Atención", "Revisá monto y fecha (YYYY-MM-DD).")
            return
        note = self.ent_exp_note.get().strip()
        add_expense(self.state, cat, amt, dt, note)
        save_state(self.state)
        self.ent_exp_amount.delete(0, tk.END)
        self.ent_exp_note.delete(0, tk.END)
        self.refresh_summary()
        messagebox.showinfo("OK", "Gasto agregado.")

if __name__ == "__main__":
    app = App()
    app.mainloop()
