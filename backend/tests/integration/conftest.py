"""Shared factories and fixtures for integration tests.

All factories are plain async functions (not pytest fixtures) so they can be
composed freely within any test. Each factory flushes the created record to
obtain its primary key but does NOT commit — the test controls the transaction
boundary via the ``test_db`` fixture from the root conftest.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentEstablishment
from app.core.security import get_password_hash
from app.modules.catalog.models import Product, Supplier, SupplierCountry, SupplierStatus
from app.modules.cleaning.models import (
    CleaningRoutine,
    CleaningTaskTemplate,
    CleaningZone,
    ScheduleType,
)
from app.modules.equipments.models import Equipement, TypeEquipement
from app.modules.personnel.models import AffectationSite, Role, Utilisateur
from app.modules.production.models import (
    BatchStatut,
    FoodType,
    ProductionBatch,
    ProductionBatchIngredient,
)
from app.modules.receptions.models import (
    LotOuverture,
    ReceptionItem,
    ReceptionSession,
    ReceptionStatus,
    StatutOuverture,
)
from app.modules.tenant.models import Etablissement, Organisation, TypeSecteur

# ── Core tenant factories ─────────────────────────────────────────────────────


async def make_organisation(
    db: AsyncSession,
    *,
    nom_entite: str = "Test Organisation",
    admin_email: str | None = None,
    admin_password: str = "AdminPassword123",
) -> Organisation:
    if admin_email is None:
        admin_email = f"admin-{uuid.uuid4().hex[:8]}@test.com"
    org = Organisation(
        nom_entite=nom_entite,
        type_secteur=TypeSecteur.PRIVE,
        admin_login_email=admin_email,
        admin_password_hash=get_password_hash(admin_password),
    )
    db.add(org)
    await db.flush()
    return org


async def make_establishment(
    db: AsyncSession,
    org: Organisation,
    *,
    nom_site: str = "Site Test",
    timezone: str = "Europe/Paris",
    settings: dict | None = None,
) -> Etablissement:
    est = Etablissement(
        organisation_id=org.id,
        nom_site=nom_site,
        timezone=timezone,
        settings=settings or {},
    )
    db.add(est)
    await db.flush()
    return est


async def make_role(
    db: AsyncSession,
    *,
    nom_role: str | None = None,
    is_manager: bool = False,
    permissions: dict | None = None,
) -> Role:
    if nom_role is None:
        nom_role = f"ROLE-{uuid.uuid4().hex[:6].upper()}"
    if permissions is None:
        permissions = {"manager": True} if is_manager else {}
    role = Role(nom_role=nom_role, permissions=permissions)
    db.add(role)
    await db.flush()
    return role


async def make_user(
    db: AsyncSession,
    org: Organisation,
    est: Etablissement,
    role: Role,
    *,
    email: str | None = None,
    password: str = "UserPassword123",
    pin: str | None = "1234",
    is_active: bool = True,
) -> Utilisateur:
    if email is None:
        email = f"user-{uuid.uuid4().hex[:8]}@test.com"
    user = Utilisateur(
        nom="Test",
        prenom="User",
        email=email,
        mot_de_passe_hash=get_password_hash(password),
        code_pin=get_password_hash(pin) if pin else None,
    )
    db.add(user)
    await db.flush()

    affectation = AffectationSite(
        utilisateur_id=user.id,
        etablissement_id=est.id,
        role_id=role.id,
        is_active=is_active,
    )
    db.add(affectation)
    await db.flush()
    return user


async def make_equipment(
    db: AsyncSession,
    est: Etablissement,
    *,
    nom: str = "Chambre froide",
    min_temp: Decimal = Decimal("0.00"),
    max_temp: Decimal = Decimal("4.00"),
    type_equipement: TypeEquipement = TypeEquipement.CHAMBRE_FROIDE_POSITIVE,
) -> Equipement:
    equip = Equipement(
        etablissement_id=est.id,
        nom=nom,
        type_equipement=type_equipement,
        temperature_min_cible=min_temp,
        temperature_max_cible=max_temp,
    )
    db.add(equip)
    await db.flush()
    return equip


# ── Catalog factories ─────────────────────────────────────────────────────────


async def make_supplier(
    db: AsyncSession,
    est: Etablissement,
    *,
    name: str | None = None,
    status: SupplierStatus = SupplierStatus.APPROVED,
) -> Supplier:
    if name is None:
        name = f"Fournisseur {uuid.uuid4().hex[:6]}"
    supplier = Supplier(
        establishment_id=est.id,
        name=name,
        country=SupplierCountry.FRANCE,
        status=status,
    )
    db.add(supplier)
    await db.flush()
    return supplier


async def make_product(
    db: AsyncSession,
    est: Etablissement,
    supplier: Supplier,
    *,
    name: str | None = None,
) -> Product:
    if name is None:
        name = f"Produit {uuid.uuid4().hex[:6]}"
    product = Product(
        establishment_id=est.id,
        supplier_id=supplier.id,
        name=name,
        has_temperature_control=False,
    )
    db.add(product)
    await db.flush()
    return product


# ── Reception factories ───────────────────────────────────────────────────────


async def make_reception_session(
    db: AsyncSession,
    est: Etablissement,
    operator: Utilisateur,
    supplier: Supplier,
    *,
    status: ReceptionStatus = ReceptionStatus.OPEN,
) -> ReceptionSession:
    session = ReceptionSession(
        establishment_id=est.id,
        operator_id=operator.id,
        supplier_id=supplier.id,
        received_at=datetime.now(UTC),
        truck_condition_ok=True,
        status=status,
        opened_at=datetime.now(UTC),
    )
    db.add(session)
    await db.flush()
    return session


async def make_reception_item(
    db: AsyncSession,
    session: ReceptionSession,
    product: Product,
    *,
    lot_number: str | None = None,
    dluo: date | None = None,
    is_surgele: bool = False,
    is_compliant: bool = True,
) -> ReceptionItem:
    if lot_number is None:
        lot_number = f"LOT-{uuid.uuid4().hex[:8].upper()}"
    if dluo is None:
        dluo = (datetime.now(UTC) + timedelta(days=30)).date()
    item = ReceptionItem(
        session_id=session.id,
        product_id=product.id,
        lot_number=lot_number,
        dluo=dluo,
        packaging_ok=True,
        is_compliant=is_compliant,
        is_surgele=is_surgele,
        scanned_at=datetime.now(UTC),
    )
    db.add(item)
    await db.flush()
    return item


async def make_lot_ouverture(
    db: AsyncSession,
    est: Etablissement,
    item: ReceptionItem,
    operator: Utilisateur,
    *,
    duree_jours: int = 3,
    statut: StatutOuverture = StatutOuverture.OUVERT,
) -> LotOuverture:
    from app.modules.receptions.service import calculate_dlc_secondaire

    today = datetime.now(UTC).date()
    dlc_secondaire = calculate_dlc_secondaire(today, item.dluo, duree_jours)
    ouverture = LotOuverture(
        establishment_id=est.id,
        reception_item_id=item.id,
        operator_id=operator.id,
        ouvert_at=datetime.now(UTC),
        dluo_primaire=item.dluo,
        duree_apres_ouverture_jours=duree_jours,
        dlc_secondaire_calculee=dlc_secondaire,
        was_frozen=item.is_surgele,
        statut=statut,
    )
    db.add(ouverture)
    await db.flush()
    return ouverture


# ── Production factories ──────────────────────────────────────────────────────


async def make_production_batch(
    db: AsyncSession,
    est: Etablissement,
    *,
    nom_recette: str | None = None,
    food_type: FoodType = FoodType.AUTRE,
    operator: Utilisateur | None = None,
) -> ProductionBatch:
    if nom_recette is None:
        nom_recette = f"Recette {uuid.uuid4().hex[:6]}"
    batch = ProductionBatch(
        etablissement_id=est.id,
        nom_recette=nom_recette,
        food_type=food_type,
        date_production=datetime.now(UTC).date(),
        statut=BatchStatut.EN_COURS,
        created_by_id=operator.id if operator else None,
    )
    db.add(batch)
    await db.flush()
    return batch


async def make_production_batch_ingredient(
    db: AsyncSession,
    batch: ProductionBatch,
    item: ReceptionItem,
    operator: Utilisateur,
    *,
    quantity_used: Decimal = Decimal("1.000"),
    unit: str = "kg",
) -> ProductionBatchIngredient:
    ingredient = ProductionBatchIngredient(
        batch_id=batch.id,
        reception_item_id=item.id,
        operator_id=operator.id,
        quantity_used=quantity_used,
        unit=unit,
    )
    db.add(ingredient)
    await db.flush()
    return ingredient


# ── Cleaning factories ────────────────────────────────────────────────────────


async def make_cleaning_zone(
    db: AsyncSession,
    est: Etablissement,
    *,
    name: str | None = None,
) -> CleaningZone:
    if name is None:
        name = f"Zone {uuid.uuid4().hex[:6]}"
    zone = CleaningZone(establishment_id=est.id, name=name)
    db.add(zone)
    await db.flush()
    return zone


async def make_cleaning_routine(
    db: AsyncSession,
    est: Etablissement,
    *,
    name: str | None = None,
    schedule_type: ScheduleType = ScheduleType.OPENING,
) -> CleaningRoutine:
    if name is None:
        name = f"Routine {uuid.uuid4().hex[:6]}"
    routine = CleaningRoutine(
        establishment_id=est.id,
        name=name,
        schedule_type=schedule_type,
    )
    db.add(routine)
    await db.flush()
    return routine


async def make_cleaning_task(
    db: AsyncSession,
    routine: CleaningRoutine,
    zone: CleaningZone,
    *,
    name: str | None = None,
) -> CleaningTaskTemplate:
    if name is None:
        name = f"Tâche {uuid.uuid4().hex[:6]}"
    task = CleaningTaskTemplate(
        routine_id=routine.id,
        zone_id=zone.id,
        name=name,
    )
    db.add(task)
    await db.flush()
    return task


# ── Context builder ───────────────────────────────────────────────────────────


def make_establishment_ctx(
    org: Organisation,
    est: Etablissement,
    manager: Utilisateur,
    *,
    is_org_admin: bool = True,
    settings: dict | None = None,
) -> CurrentEstablishment:
    """Build a CurrentEstablishment context for service-layer tests (no JWT needed)."""
    return CurrentEstablishment(
        organisation_id=org.id,
        etablissement_id=est.id,
        nom_site=est.nom_site,
        timezone=est.timezone,
        manager_user_id=manager.id,
        is_org_admin=is_org_admin,
        settings=settings or est.settings or {},
    )


# ── Composite seeds ───────────────────────────────────────────────────────────


@dataclass
class BaseSeed:
    """Minimal tenant context: one org, one site, one manager, one operator."""

    org: Organisation
    est: Etablissement
    manager_role: Role
    operator_role: Role
    manager: Utilisateur
    operator: Utilisateur
    ctx: CurrentEstablishment


async def make_base_seed(db: AsyncSession) -> BaseSeed:
    """Create the minimal context used by most integration tests."""
    org = await make_organisation(db)
    est = await make_establishment(db, org)
    manager_role = await make_role(db, nom_role="MANAGER", is_manager=True)
    operator_role = await make_role(db, nom_role="OPERATEUR")
    manager = await make_user(db, org, est, manager_role)
    operator = await make_user(db, org, est, operator_role, pin="9876")
    ctx = make_establishment_ctx(org, est, manager)
    return BaseSeed(
        org=org,
        est=est,
        manager_role=manager_role,
        operator_role=operator_role,
        manager=manager,
        operator=operator,
        ctx=ctx,
    )
