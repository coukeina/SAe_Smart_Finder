from typing import Any

import psycopg

from ..config import settings


def get_connection() -> psycopg.Connection[Any]:
	if settings.database_url:
		return psycopg.connect(settings.database_url)

	return psycopg.connect(
		host=settings.db_host,
		port=settings.db_port,
		dbname=settings.db_name,
		user=settings.db_user,
		password=settings.db_password,
	)