# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""add portfolio items table

Creates module_portfolio_items and seeds it with the five projects the
portfolio opened with. The seed is copied into this file on purpose: a
migration must stay runnable however the module's code changes later.

Revision ID: 7b2b78afd56d
Revises: 2148e8844cda
Create Date: 2026-10-19 12:31:42.748310

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7b2b78afd56d'
down_revision: Union[str, Sequence[str], None] = '2148e8844cda'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_ITEMS: list[dict] = [
    {
        "slug": "withfbraun",
        "title_cs": "WithFBraun",
        "title_en": "WithFBraun",
        "summary_cs": (
            "Osobní prostor, kde vedle sebe existují příběhy, vzdělávací obsah, experimenty a "
            "menší softwarové nástroje – propojené do jednoho ekosystému aplikací."
        ),
        "summary_en": (
            "A personal space where stories, educational content, experiments and smaller "
            "software tools live side by side – connected into one ecosystem of applications."
        ),
        "description_cs": (
            "WithFBraun je můj osobní prostor, kde vedle sebe existují příběhy, fiktivní světy, "
            "vzdělávací obsah, experimenty i menší softwarové nástroje. Každá aplikace se věnuje "
            "jiné oblasti, ale všechny spojuje stejná filozofie – zvídavost, radost z objevování "
            "a chuť sdílet nápady.\n\n"
            "Jednotlivé aplikace fungují samostatně, přesto tvoří jeden propojený ekosystém: "
            "sdílejí přihlášení a vznikají ze společného jádra, takže vylepšení základů stačí "
            "udělat jednou."
        ),
        "description_en": (
            "WithFBraun is my personal space where stories, fictional worlds, educational "
            "content, experiments and smaller software tools live side by side. Each application "
            "deals with a different area, but they all share the same philosophy – curiosity, "
            "the joy of discovery and the wish to share ideas.\n\n"
            "The applications work on their own, yet form one connected ecosystem: they share "
            "sign-in and are built from a common core, so an improvement to the foundations only "
            "has to be made once."
        ),
        "url": "https://www.withfbraun.com",
        "status": "live",
        "tags": ["React", "TypeScript", "FastAPI", "PostgreSQL"],
        "published": True,
        "sort_order": 1,
    },
    {
        "slug": "auth",
        "title_cs": "Auth",
        "title_en": "Auth",
        "summary_cs": (
            "Autorizační aplikace pro celý ekosystém WithFBraun – správa účtů, přihlášení a "
            "přístupových oprávnění."
        ),
        "summary_en": (
            "The authorization application for the whole WithFBraun ecosystem – account "
            "management, sign-in and access permissions."
        ),
        "description_cs": (
            "Jedno místo pro účty a přihlášení všech aplikací ekosystému. Aplikace se na ni "
            "napojují přes vlastní zadní část, takže prohlížeč nikdy nevidí API klíč. Podporuje "
            "přihlášení e-mailem a heslem i přes Google a samostatný souhlas uživatele s tím, k "
            "čemu která aplikace smí přistupovat."
        ),
        "description_en": (
            "One place for the accounts and sign-in of every application in the ecosystem. "
            "Applications connect to it through their own backend, so the browser never sees an "
            "API key. It supports sign-in with email and password as well as through Google, and "
            "a separate user consent for what each application may access."
        ),
        "url": "https://auth.withfbraun.com",
        "status": "live",
        "tags": ["JWT", "OAuth"],
        "published": True,
        "sort_order": 2,
    },
    {
        "slug": "template-app",
        "title_cs": "Template App",
        "title_en": "Template App",
        "summary_cs": (
            "Šablona aplikace s funkční autorizací, na jejímž základě vznikají ostatní aplikace "
            "ekosystému."
        ),
        "summary_en": (
            "An application template with working authorization, which the other applications of "
            "the ecosystem are built from."
        ),
        "description_cs": (
            "Společné jádro, ze kterého vznikají nové aplikace: zadní část ve FastAPI, přední "
            "část v Reactu, napojení na Auth, vícejazyčné rozhraní, světlý a tmavý režim, systém "
            "zásuvných modulů (například kontaktní formulář nebo kalendář akcí) a nástroje pro "
            "nasazení. Díky němu každá nová aplikace začíná tam, kde ta předchozí skončila."
        ),
        "description_en": (
            "The common core that new applications are built from: a FastAPI backend, a React "
            "frontend, the connection to Auth, a multilingual interface, light and dark mode, a "
            "system of pluggable modules (for example a contact form or an event calendar) and "
            "deployment tooling. Thanks to it, every new application starts where the previous "
            "one left off."
        ),
        "url": "https://template-app.withfbraun.com",
        "status": "live",
        "tags": ["FastAPI", "React", "TypeScript", "PostgreSQL", "Tailwind CSS"],
        "published": True,
        "sort_order": 3,
    },
    {
        "slug": "api-hub",
        "title_cs": "API Hub",
        "title_en": "API Hub",
        "summary_cs": "Přehledná evidence API dokumentace – s historií, upozorněními a týmovou spoluprací.",
        "summary_en": (
            "A clear register of API documentation – with history, notifications and team "
            "collaboration."
        ),
        "description_cs": (
            "Nahrajte OpenAPI/Swagger specifikaci ze souboru, nebo na ni jen odkažte – API Hub "
            "sám hlídá nové verze a archivuje každou z nich, takže se k nim můžete vrátit i "
            "poté, co originál zmizí. Dokumentace patří vašemu týmu, dá se sdružovat do kolekcí "
            "a integrací a doplnit o vlastní poznámky ve znalostní bázi."
        ),
        "description_en": (
            "Upload an OpenAPI/Swagger specification from a file, or just link to it – API Hub "
            "watches for new versions itself and archives each of them, so you can go back to "
            "them even after the original disappears. The documentation belongs to your team, "
            "can be grouped into collections and integrations and supplemented with your own "
            "notes in a knowledge base."
        ),
        "url": "https://api-hub.withfbraun.com",
        "status": "live",
        "tags": ["OpenAPI", "Swagger", "FastAPI", "React"],
        "published": True,
        "sort_order": 4,
    },
    {
        "slug": "my-repository",
        "title_cs": "My Repository",
        "title_en": "My Repository",
        "summary_cs": (
            "Osobní úložiště položek jako knihy nebo hry, s vlastními typy objektů, vazbami a "
            "generovanými statistikami."
        ),
        "summary_en": (
            "A personal repository of items such as books or games, with custom object types, "
            "relations and generated statistics."
        ),
        "description_cs": (
            "Osobní úložiště položek jako knihy nebo hry, s vlastními typy objektů, vazbami mezi "
            "nimi a generovanými statistikami.\n\n"
            "Aplikace se připravuje."
        ),
        "description_en": (
            "A personal repository of items such as books or games, with custom object types, "
            "relations between them and generated statistics.\n\n"
            "The application is in preparation."
        ),
        "url": None,
        "status": "in_preparation",
        "tags": [],
        "published": True,
        "sort_order": 5,
    },
]


def _insert_seed_items() -> None:
    """Also called by tests/test_modules_portfolio_seed.py, which replays it
    inside a rolled-back transaction to check the rows really fit the table."""
    items = sa.table(
        'module_portfolio_items',
        sa.column('id', sa.UUID()),
        sa.column('slug', sa.String(length=80)),
        sa.column('title_cs', sa.String(length=120)),
        sa.column('title_en', sa.String(length=120)),
        sa.column('summary_cs', sa.String(length=400)),
        sa.column('summary_en', sa.String(length=400)),
        sa.column('description_cs', sa.Text()),
        sa.column('description_en', sa.Text()),
        sa.column('url', sa.String(length=500)),
        sa.column('status', sa.String(length=20)),
        sa.column('tags', postgresql.ARRAY(sa.String(length=40))),
        sa.column('published', sa.Boolean()),
        sa.column('sort_order', sa.Integer()),
    )
    op.bulk_insert(items, [{'id': uuid.uuid4(), **item} for item in SEED_ITEMS])


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('module_portfolio_items',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('title_cs', sa.String(length=120), nullable=False),
    sa.Column('title_en', sa.String(length=120), nullable=False),
    sa.Column('summary_cs', sa.String(length=400), nullable=False),
    sa.Column('summary_en', sa.String(length=400), nullable=False),
    sa.Column('description_cs', sa.Text(), nullable=False),
    sa.Column('description_en', sa.Text(), nullable=False),
    sa.Column('url', sa.String(length=500), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('tags', postgresql.ARRAY(sa.String(length=40)), nullable=False),
    sa.Column('published', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_module_portfolio_items_slug'), 'module_portfolio_items', ['slug'], unique=True)
    _insert_seed_items()


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_module_portfolio_items_slug'), table_name='module_portfolio_items')
    op.drop_table('module_portfolio_items')
