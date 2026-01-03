from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple


DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "control_gastos.json")


# ----------------------------
# Helpers de dinero / fechas
# ----------------------------
def d(value: str | int | float | Decimal) -> Decimal:
    """Convierte a Decimal con 2 decimales."""
    try:
        dec = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Número inválido.")
    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_date(s: str) -> date:
    """Acepta YYYY-MM-DD."""
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Fecha inválida. Usá el formato YYYY-MM-DD (ej: 2026-01-03).")


def month_start(dt: date) -> date:
    return dt.replace(day=1)


def month_end(dt: date) -> date:
    # primer día del mes siguiente - 1 día
    if dt.month == 12:
        first_next = dt.replace(year=dt.year + 1, month=1, day=1)
    else:
        first_next = dt.replace(month=dt.month + 1, day=1)
    return first_next - timedelta(days=1)


def days_remaining_in_month(today: date) -> int:
    end = month_end(today)
    # incluye hoy como "día por gastar"
    return (end - today).days + 1


def fmt_money(x: Decimal) -> str:
    # Formato simple estilo AR: 1234.50 (si querés, lo adaptamos a 1.234,50)
    return f"${x:,.2f}"


# ----------------------------
# Modelo de datos
# ----------------------------
@dataclass
class Expense:
    amount: str  # guardamos como string para JSON; convertimos a Decimal al operar
    category: str
    dt: str      # YYYY-MM-DD
    note: str = ""


@dataclass
class Income:
    person: str
    amount: str  # mensual base
    month: str   # YYYY-MM (ej: 2026-01)


@dataclass
class ExtraIncome:
    person: str
    amount: str
    dt: str      # YYYY-MM-DD
    note: str = ""


def default_state() -> Dict:
    return {
        "categories": [],
        "people": [],
        "monthly_incomes": [],  # lista de Income
        "extra_incomes": [],    # lista de ExtraIncome
        "expenses": [],         # lista de Expense
    }


def load_state() -> Dict:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        state = default_state()
        save_state(state)
        return state

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: Dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ----------------------------
# Operaciones
# ----------------------------
def ensure_unique_add(lst: List[str], item: str) -> bool:
    item = item.strip()
    if not item:
        return False
    if item in lst:
        return False
    lst.append(item)
    lst.sort(key=lambda x: x.lower())
    return True


def set_monthly_income(state: Dict, person: str, amount: Decimal, month_key: str) -> None:
    # si ya existe, lo reemplaza
    incomes = state["monthly_incomes"]
    for row in incomes:
        if row["person"] == person and row["month"] == month_key:
            row["amount"] = str(amount)
            return
    incomes.append(asdict(Income(person=person, amount=str(amount), month=month_key)))


def add_extra_income(state: Dict, person: str, amount: Decimal, dt: date, note: str = "") -> None:
    state["extra_incomes"].append(asdict(ExtraIncome(person=person, amount=str(amount), dt=dt.isoformat(), note=note.strip())))


def add_expense(state: Dict, amount: Decimal, category: str, dt: date, note: str = "") -> None:
    state["expenses"].append(asdict(Expense(amount=str(amount), category=category, dt=dt.isoformat(), note=note.strip())))


def totals_for_month(state: Dict, today: date) -> Tuple[Decimal, Decimal, Decimal]:
    """(ingresos_base, ingresos_extra, gastos) para el mes de 'today'."""
    month_key = today.strftime("%Y-%m")
    start = month_start(today)
    end = month_end(today)

    base_income = Decimal("0")
    for row in state["monthly_incomes"]:
        if row["month"] == month_key:
            base_income += d(row["amount"])

    extra_income = Decimal("0")
    for row in state["extra_incomes"]:
        dt = parse_date(row["dt"])
        if start <= dt <= end:
            extra_income += d(row["amount"])

    expenses = Decimal("0")
    for row in state["expenses"]:
        dt = parse_date(row["dt"])
        if start <= dt <= end:
            expenses += d(row["amount"])

    return (
        base_income.quantize(Decimal("0.01")),
        extra_income.quantize(Decimal("0.01")),
        expenses.quantize(Decimal("0.01")),
    )


def remaining_and_per_day(state: Dict, today: date) -> Tuple[Decimal, Decimal, int]:
    base_income, extra_income, expenses = totals_for_month(state, today)
    total_income = base_income + extra_income
    remaining = (total_income - expenses).quantize(Decimal("0.01"))
    days_left = days_remaining_in_month(today)
    per_day = (remaining / Decimal(days_left)).quantize(Decimal("0.01")) if days_left > 0 else Decimal("0.00")
    return remaining, per_day, days_left


# ----------------------------
# UI por consola (menú)
# ----------------------------
def pick_from_list(options: List[str], title: str) -> Optional[str]:
    if not options:
        print("No hay opciones cargadas todavía.")
        return None

    print(f"\n{title}")
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. {opt}")
    while True:
        s = input("Elegí un número (o Enter para cancelar): ").strip()
        if s == "":
            return None
        if s.isdigit():
            idx = int(s)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        print("Opción inválida.")


def input_decimal(prompt: str) -> Decimal:
    while True:
        s = input(prompt).strip().replace(",", ".")
        try:
            return d(s)
        except ValueError:
            print("Monto inválido. Probá de nuevo (ej: 15000.50).")


def input_date(prompt: str, default: Optional[date] = None) -> date:
    while True:
        s = input(prompt).strip()
        if s == "" and default is not None:
            return default
        try:
            return parse_date(s)
        except ValueError as e:
            print(e)


def show_dashboard(state: Dict) -> None:
    today = date.today()
    base_income, extra_income, expenses = totals_for_month(state, today)
    total_income = (base_income + extra_income).quantize(Decimal("0.01"))
    remaining, per_day, days_left = remaining_and_per_day(state, today)

    print("\n==============================")
    print(f"RESUMEN DEL MES ({today.strftime('%Y-%m')})")
    print("==============================")
    print(f"Ingresos base:   {fmt_money(base_income)}")
    print(f"Ingresos extra:  {fmt_money(extra_income)}")
    print(f"TOTAL ingresos:  {fmt_money(total_income)}")
    print(f"TOTAL gastos:    {fmt_money(expenses)}")
    print("------------------------------")
    print(f"Te queda:        {fmt_money(remaining)}")
    print(f"Días restantes:  {days_left}")
    print(f"Por día:         {fmt_money(per_day)}")
    print("==============================\n")


def menu() -> None:
    state = load_state()

    while True:
        print("=== Control de Gastos ===")
        print("1) Ver resumen del mes")
        print("2) Agregar categoría")
        print("3) Listar categorías")
        print("4) Agregar persona (ingresos)")
        print("5) Listar personas")
        print("6) Cargar / actualizar ingreso mensual por persona")
        print("7) Cargar ingreso extra")
        print("8) Cargar gasto")
        print("9) Salir")

        choice = input("Elegí una opción: ").strip()

        if choice == "1":
            show_dashboard(state)

        elif choice == "2":
            name = input("Nombre de la categoría: ").strip()
            if ensure_unique_add(state["categories"], name):
                save_state(state)
                print("Categoría agregada.\n")
            else:
                print("No se pudo agregar (vacía o ya existe).\n")

        elif choice == "3":
            print("\nCategorías:")
            for c in state["categories"]:
                print(f"- {c}")
            print()

        elif choice == "4":
            name = input("Nombre de la persona: ").strip()
            if ensure_unique_add(state["people"], name):
                save_state(state)
                print("Persona agregada.\n")
            else:
                print("No se pudo agregar (vacía o ya existe).\n")

        elif choice == "5":
            print("\nPersonas:")
            for p in state["people"]:
                print(f"- {p}")
            print()

        elif choice == "6":
            person = pick_from_list(state["people"], "Seleccioná la persona")
            if not person:
                continue
            today = date.today()
            month_key = today.strftime("%Y-%m")
            amount = input_decimal(f"Ingreso mensual de {person} para {month_key}: ")
            set_monthly_income(state, person, amount, month_key)
            save_state(state)
            print("Ingreso mensual guardado.\n")

        elif choice == "7":
            person = pick_from_list(state["people"], "Seleccioná la persona")
            if not person:
                continue
            amount = input_decimal("Monto del ingreso extra: ")
            dt = input_date("Fecha (YYYY-MM-DD) [Enter = hoy]: ", default=date.today())
            note = input("Nota (opcional): ")
            add_extra_income(state, person, amount, dt, note)
            save_state(state)
            print("Ingreso extra guardado.\n")

        elif choice == "8":
            category = pick_from_list(state["categories"], "Seleccioná la categoría")
            if not category:
                continue
            amount = input_decimal("Monto del gasto: ")
            dt = input_date("Fecha (YYYY-MM-DD) [Enter = hoy]: ", default=date.today())
            note = input("Nota (opcional): ")
            add_expense(state, amount, category, dt, note)
            save_state(state)
            print("Gasto guardado.\n")

        elif choice == "9":
            print("Listo. ¡Nos vemos!")
            break

        else:
            print("Opción inválida.\n")


if __name__ == "__main__":
    menu()
