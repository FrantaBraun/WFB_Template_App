# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

KIND_FOOD = "food"
KIND_DRINK = "drink"
CATEGORY_KINDS = (KIND_FOOD, KIND_DRINK)

DAILY_SOUP = "soup"
DAILY_MAIN = "main"
DAILY_DESSERT = "dessert"
DAILY_OTHER = "other"
DAILY_KINDS = (DAILY_SOUP, DAILY_MAIN, DAILY_DESSERT, DAILY_OTHER)

# The 14 allergens of EU regulation 1169/2011, by their number.
ALLERGEN_NUMBERS = tuple(range(1, 15))


class MenuCategory(Base):
    """A section of the standing menu ("Hlavní jídla", "Výčepní piva", ...).
    `kind` says whether it belongs to the food menu or the drinks menu; an
    inactive category (and everything in it) is kept but not shown."""

    __tablename__ = "module_menu_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default=KIND_FOOD)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MenuItem(Base):
    """A dish or a drink of the standing menu. `allergens` are the EU allergen
    numbers (1-14); an item that is `is_available` False is shown as temporarily
    out (sold out), one that is not `is_active` is not shown at all. Prices are
    separate rows (MenuPrice) so a beer can have 0,3 l and 0,5 l."""

    __tablename__ = "module_menu_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_menu_categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    allergens: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MenuPrice(Base):
    """One price of an item with the portion it is for ("0,5 l", "150 g", or empty)."""

    __tablename__ = "module_menu_prices"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_module_menu_prices_price"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_menu_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DailyMenu(Base):
    """The lunch menu of ONE date. Until `is_published` it is a draft only the
    administrators see."""

    __tablename__ = "module_menu_days"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DailyMenuItem(Base):
    """A dish of a lunch menu. `kind` groups it (soup, main course, dessert,
    other); `amount` is the portion ("0,33 l", "150 g"); `price` is None for a
    dish included in the price of another (a soup with a main course, say)."""

    __tablename__ = "module_menu_day_items"
    __table_args__ = (CheckConstraint("price IS NULL OR price >= 0", name="ck_module_menu_day_items_price"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    day: Mapped[date] = mapped_column(Date, ForeignKey("module_menu_days.day", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default=DAILY_MAIN)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    amount: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    allergens: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MenuSettings(Base):
    """The texts around the menus - ONE row (id 1): a note under the lunch menu
    ("Podáváme Po-Pá 11-14 h") and one under the standing menu (the allergen
    statement, say)."""

    __tablename__ = "module_menu_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_module_menu_settings_single"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    daily_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    offer_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
