"""CSV parse helpers — parsers return list[dict]."""

from weekchef.data.csv_parse import (
    parse_energy_dict,
    parse_ingredient_dict,
    parse_time_cook_minutes,
)


def test_parse_time() -> None:
    assert parse_time_cook_minutes("15 minutes") == 15
    assert parse_time_cook_minutes("1 hour") == 60
    assert parse_time_cook_minutes("1 hour 20 minutes") == 80


def test_parse_ingredients_list() -> None:
    arr = parse_ingredient_dict("Egg: 1 piece, Milk: 100 ml")
    assert isinstance(arr, list)
    assert arr == [
        {"ingredient": "Egg", "quantity": "1 piece"},
        {"ingredient": "Milk", "quantity": "100 ml"},
    ]


def test_parse_energy_list() -> None:
    arr = parse_energy_dict("Calorius 87 kcal, proteins 8 grams")
    assert isinstance(arr, list)
    assert {"energy": "calories", "quantity": 87} in arr
    assert {"energy": "proteins", "quantity": 8} in arr
