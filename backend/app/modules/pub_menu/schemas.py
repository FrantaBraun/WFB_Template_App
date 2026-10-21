# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints, field_validator

from app.modules.pub_menu.models import ALLERGEN_NUMBERS

# A price in the configured currency: two decimals at most, never negative; it
# goes out as a plain JSON number (pydantic would write a Decimal as a string).
Money = Annotated[
    Decimal,
    Field(ge=0, max_digits=8, decimal_places=2),
    PlainSerializer(float, return_type=float, when_used="json"),
]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
CategoryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Portion = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]

CategoryKind = Literal["food", "drink"]
DailyKind = Literal["soup", "main", "dessert", "other"]

MAX_PRICES = 6
MAX_DAILY_ITEMS = 30
MAX_RANGE_DAYS = 62


def _allergens(values: list[int]) -> list[int]:
    unknown = [value for value in values if value not in ALLERGEN_NUMBERS]
    if unknown:
        raise ValueError(f"allergens are numbers 1-14, not {unknown}")
    return sorted(set(values))


class _WithAllergens(BaseModel):
    allergens: list[int] = Field(default_factory=list, max_length=14)

    @field_validator("allergens")
    @classmethod
    def _valid_allergens(cls, values: list[int]) -> list[int]:
        return _allergens(values)


# --- Public ------------------------------------------------------------------------


class PriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    price: Money


class ItemPublic(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    allergens: list[int]
    is_available: bool
    prices: list[PriceOut]


class CategoryPublic(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    kind: CategoryKind
    items: list[ItemPublic]


class OfferOut(BaseModel):
    """The standing menu: the active categories with their active items."""

    currency: str
    note: str
    categories: list[CategoryPublic]


class DailyItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: DailyKind
    name: str
    description: str
    amount: str
    allergens: list[int]
    price: Money | None


class DailyDayOut(BaseModel):
    day: date
    items: list[DailyItemOut]


class DailyWeekOut(BaseModel):
    """The published lunch menus of the week (Monday to Sunday) that contains the
    date asked for - a day with none has an empty list - and how far the visitor may
    browse (the Mondays of the first and last week allowed)."""

    currency: str
    note: str
    week_start: date
    week_end: date
    min_week_start: date
    max_week_start: date
    days: list[DailyDayOut]


# --- Administrators ---------------------------------------------------------------------


class PriceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Portion = ""
    price: Money


class ItemAdmin(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str
    allergens: list[int]
    is_available: bool
    is_active: bool
    position: int
    prices: list[PriceOut]


class CategoryAdmin(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    kind: CategoryKind
    position: int
    is_active: bool
    items: list[ItemAdmin]


class CategoryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CategoryName
    description: Description = ""
    kind: CategoryKind = "food"
    is_active: bool = True


class CategoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CategoryName | None = None
    description: Description | None = None
    kind: CategoryKind | None = None
    is_active: bool | None = None


class ItemIn(_WithAllergens):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID
    name: Name
    description: Description = ""
    is_available: bool = True
    is_active: bool = True
    prices: list[PriceIn] = Field(default_factory=list, max_length=MAX_PRICES)


class ItemPatch(BaseModel):
    """Only the fields sent change. `category_id` moves the item to the end of
    another category; `prices` replaces all its prices."""

    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID | None = None
    name: Name | None = None
    description: Description | None = None
    allergens: list[int] | None = Field(default=None, max_length=14)
    is_available: bool | None = None
    is_active: bool | None = None
    prices: list[PriceIn] | None = Field(default=None, max_length=MAX_PRICES)

    @field_validator("allergens")
    @classmethod
    def _valid_allergens(cls, values: list[int] | None) -> list[int] | None:
        return None if values is None else _allergens(values)


class ReorderBody(BaseModel):
    """The ids in the new order: exactly the ones that exist, each once."""

    model_config = ConfigDict(extra="forbid")

    ids: list[uuid.UUID]


class DailyItemIn(_WithAllergens):
    model_config = ConfigDict(extra="forbid")

    kind: DailyKind = "main"
    name: Name
    description: Description = ""
    amount: Portion = ""
    price: Money | None = None


class DailyIn(BaseModel):
    """A whole lunch menu of one date; its dishes replace the ones stored, in this order."""

    model_config = ConfigDict(extra="forbid")

    is_published: bool = False
    items: list[DailyItemIn] = Field(default_factory=list, max_length=MAX_DAILY_ITEMS)


class DailyAdmin(BaseModel):
    day: date
    is_published: bool
    updated_at: datetime
    items: list[DailyItemOut]


class SettingsIO(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    daily_note: Note = ""
    offer_note: Note = ""
