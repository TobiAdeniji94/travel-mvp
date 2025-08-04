import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from app.core.settings import Settings

from sqlmodel import SQLModel

import app.db.models
from sqlalchemy.dialects import postgresql

# Alembic Config object
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Load .env and settings
settings = Settings()
config.set_main_option("sqlalchemy.url", settings.DB_URL)

# Use SQLModel's metadata for autogenerate
target_metadata = SQLModel.metadata

def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "type" and name == "bookingstatus":
        return False
    if type_ == "table":
        return name in target_metadata.tables
    return True

# this callback will be asked “should we emit a type-changing ALTER?”
def compare_type(context, inspected_column, metadata_column,
                 inspected_type, metadata_type) -> bool | None:
    # if it’s the bookingstatus enum, say “no diff”
    if (
        isinstance(inspected_type, postgresql.ENUM)
        and getattr(inspected_type, "name", None) == "bookingstatus"
    ) or (
        isinstance(metadata_type, postgresql.ENUM)
        and getattr(metadata_type, "name", None) == "bookingstatus"
    ):
        return False
    # otherwise fall back to default behavior
    return None

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=compare_type,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as conn:
        context.configure(
            connection=conn,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=compare_type,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
