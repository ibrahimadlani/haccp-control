"""
Top-level API router — assembles all domain module routers under /api/v1.

This module is the single place where every module-level ``APIRouter`` is
mounted.  Adding a new domain module requires only one ``include_router`` call
here; no other file needs to be updated.
"""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import router as catalog_router
from app.modules.cleaning.router import router as cleaning_router
from app.modules.equipments.router import router as equipments_router
from app.modules.haccp.router import router as haccp_router
from app.modules.nonconformities.router import router as nonconformities_router
from app.modules.personnel.router import router as personnel_router
from app.modules.receptions.router import router as receptions_router
from app.modules.tenant.router import router as tenant_router

api_router = APIRouter(prefix="/api/v1")

# Domain routers are included in logical dependency order.
# Auth must come first so that OpenAPI groups authentication endpoints at the top.
api_router.include_router(auth_router)
api_router.include_router(tenant_router)
api_router.include_router(personnel_router)
api_router.include_router(catalog_router)
api_router.include_router(equipments_router)
api_router.include_router(receptions_router)
api_router.include_router(haccp_router)
api_router.include_router(cleaning_router)
api_router.include_router(nonconformities_router)
