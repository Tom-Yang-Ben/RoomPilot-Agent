"""Backward-compatible imports for the catalog PostgreSQL repository.

Catalog SQL belongs to Kai's ``backend.catalog`` module.  Keep this shim so
older imports do not break while FastAPI moves to the owner module directly.
"""

from ..catalog.postgres_repository import (
    CatalogPage,
    CatalogQuery,
    _database_config,
    _payload_from_row,
    catalog_provider_mode,
    catalog_provider_status,
    close_catalog_pools,
    get_catalog_item,
    load_catalog,
    postgres_catalog_requested,
    query_catalog_page,
)

__all__ = [
    "CatalogPage",
    "CatalogQuery",
    "_database_config",
    "_payload_from_row",
    "catalog_provider_mode",
    "catalog_provider_status",
    "close_catalog_pools",
    "get_catalog_item",
    "load_catalog",
    "postgres_catalog_requested",
    "query_catalog_page",
]
