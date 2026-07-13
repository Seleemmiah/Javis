"""Unit conversion plugin for J.A.R.V.I.S."""

from __future__ import annotations

PLUGIN_NAME = "unit_converter"
PLUGIN_DESCRIPTION = "Convert between common units (temperature, distance, weight, etc.)"
PLUGIN_TRIGGERS = [
    r"convert\s+([\d.]+)\s*(\w+)\s+(?:to|in(?:to)?)\s+(\w+)",
    r"(?:what(?:'s| is))\s+([\d.]+)\s*(\w+)\s+in\s+(\w+)",
    r"([\d.]+)\s*(celsius|fahrenheit|kelvin|km|miles?|meters?|feet|pounds?|kg|kilograms?|oz|ounces?|liters?|gallons?)\s+(?:to|in)\s+(\w+)",
]

_CONVERSIONS: dict[tuple[str, str], object] = {}


def _reg(from_unit: str, to_unit: str, fn):
    _CONVERSIONS[(from_unit, to_unit)] = fn


def _normalize_unit(u: str) -> str:
    u = u.lower().strip().rstrip("s")
    aliases = {
        "c": "celsius", "f": "fahrenheit", "k": "kelvin",
        "km": "kilometer", "mi": "mile", "m": "meter", "ft": "foot", "feet": "foot",
        "lb": "pound", "kg": "kilogram", "oz": "ounce",
        "l": "liter", "gal": "gallon", "litre": "liter",
        "cm": "centimeter", "inche": "inch",
        "yd": "yard",
    }
    return aliases.get(u, u)


# Temperature
_reg("celsius", "fahrenheit", lambda v: v * 9 / 5 + 32)
_reg("fahrenheit", "celsius", lambda v: (v - 32) * 5 / 9)
_reg("celsius", "kelvin", lambda v: v + 273.15)
_reg("kelvin", "celsius", lambda v: v - 273.15)
_reg("fahrenheit", "kelvin", lambda v: (v - 32) * 5 / 9 + 273.15)
_reg("kelvin", "fahrenheit", lambda v: (v - 273.15) * 9 / 5 + 32)

# Distance
_reg("kilometer", "mile", lambda v: v * 0.621371)
_reg("mile", "kilometer", lambda v: v * 1.60934)
_reg("meter", "foot", lambda v: v * 3.28084)
_reg("foot", "meter", lambda v: v * 0.3048)
_reg("centimeter", "inch", lambda v: v * 0.393701)
_reg("inch", "centimeter", lambda v: v * 2.54)
_reg("meter", "yard", lambda v: v * 1.09361)
_reg("yard", "meter", lambda v: v * 0.9144)

# Weight
_reg("kilogram", "pound", lambda v: v * 2.20462)
_reg("pound", "kilogram", lambda v: v * 0.453592)
_reg("ounce", "gram", lambda v: v * 28.3495)
_reg("gram", "ounce", lambda v: v * 0.035274)
_reg("kilogram", "ounce", lambda v: v * 35.274)
_reg("ounce", "kilogram", lambda v: v * 0.0283495)

# Volume
_reg("liter", "gallon", lambda v: v * 0.264172)
_reg("gallon", "liter", lambda v: v * 3.78541)


def plugin_execute(
    value: float = 0,
    from_unit: str = "",
    to_unit: str = "",
    raw_match: str = "",
    **kwargs,
) -> str:
    if not from_unit or not to_unit:
        return "Please specify both source and target units."

    try:
        value = float(value)
    except (ValueError, TypeError):
        return f"Invalid number: {value}"

    src = _normalize_unit(from_unit)
    dst = _normalize_unit(to_unit)

    fn = _CONVERSIONS.get((src, dst))
    if fn is None:
        return (
            f"I don't know how to convert {from_unit} to {to_unit}. "
            f"Supported: temperature (C/F/K), distance (km/mi/m/ft), "
            f"weight (kg/lb/oz), volume (L/gal)."
        )

    result = fn(value)
    return f"{value:g} {from_unit} is {result:.4g} {to_unit}."
