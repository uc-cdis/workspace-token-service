from alembic import context
from logging.config import fileConfig
import json
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine.url import URL

from wts.models import db
from wts.utils import get_config_var


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

target_metadata = db.metadata

postgres_creds = get_config_var("POSTGRES_CREDS_FILE", "")
if postgres_creds:
    with open(postgres_creds, "r") as f:
        creds = json.load(f)
        try:
            config.set_main_option(
                "sqlalchemy.url",
                str(
                    URL(
                        drivername="postgresql",
                        host=creds["db_host"],
                        port="5432",
                        username=creds["db_username"],
                        password=creds["db_password"],
                        database=creds["db_database"],
                    )
                ),
            )
        except KeyError as e:
            print("Postgres creds misconfiguration: {}".format(e))
            exit(1)
else:
    url = get_config_var("SQLALCHEMY_DATABASE_URI")
    if url:
        config.set_main_option("sqlalchemy.url", url)
    else:
        print("Cannot find postgres creds location")
        exit(1)


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
