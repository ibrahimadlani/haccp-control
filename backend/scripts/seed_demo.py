# ruff: noqa: E402
"""
Seed script — Lycée Jean Moulin · Cantine de démonstration
Données réalistes pour un restaurant scolaire en Île-de-France.

Applique automatiquement les migrations Alembic si le schéma n'existe pas encore.

Usage :
    docker exec haccp_api uv run python scripts/seed_demo.py

Pour forcer les migrations manuellement :
    docker exec haccp_api uv run alembic upgrade head
"""

import asyncio
import subprocess
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal, engine
from app.core.security import get_password_hash
from app.modules.catalog.models import Product, Supplier, SupplierCountry, SupplierStatus
from app.modules.cleaning.models import (
    CleaningLog,
    CleaningRoutine,
    CleaningStatus,
    CleaningTaskTemplate,
    CleaningZone,
    ScheduleType,
)
from app.modules.equipments.models import Equipement, TypeEquipement
from app.modules.haccp.models import (
    Pointage,
    ReleveTemperature,
    SourceReleve,
    TypeEvenementPointage,
)
from app.modules.nonconformities.models import (
    NonConformity,
    NonConformityStatus,
    WorkflowType,
)
from app.modules.personnel.models import AffectationSite, Role, Utilisateur
from app.modules.production.models import DailyMenuItem
from app.modules.receptions.models import ReceptionItem, ReceptionSession, ReceptionStatus
from app.modules.tenant.models import Etablissement, Organisation, TypeSecteur

TZ = ZoneInfo("Europe/Paris")

# ── Identifiants fixes ────────────────────────────────────────────────────────

ORG_ID = UUID("11111111-1111-4111-8111-111111111111")
SITE_ID = UUID("22222222-2222-4222-8222-222222222222")

ROLE_MANAGER_ID = UUID("33333333-3333-4333-8333-333333333333")
ROLE_OPERATEUR_ID = UUID("44444444-4444-4444-8444-444444444444")
ROLE_CHEF_ID = UUID("33333333-3333-4333-8333-333333333334")

USER_MANAGER_ID = UUID("55555555-5555-4555-8555-555555555555")
USER_OPERATOR_ID = UUID("66666666-6666-4666-8666-666666666666")
USER_CHEF_ID = UUID("66666666-6666-4666-8666-666666666667")
USER_AGENT1_ID = UUID("66666666-6666-4666-8666-666666666668")
USER_AGENT2_ID = UUID("66666666-6666-4666-8666-666666666669")

# ── Credentials (affichés en fin de script) ───────────────────────────────────

ORG_ADMIN_EMAIL = "org.admin@lycee-jeanmoulin.fr"
ORG_ADMIN_PASSWORD = "OrgAdmin2024!"
MANAGER_EMAIL = "gestionnaire@lycee-jeanmoulin.fr"
MANAGER_PASSWORD = "Manager2024!"
MANAGER_PIN = "1111"
CHEF_EMAIL = "j.rousseau@lycee-jeanmoulin.fr"
AGENT1_EMAIL = "f.benali@lycee-jeanmoulin.fr"
AGENT2_EMAIL = "t.girard@lycee-jeanmoulin.fr"
OPERATOR_EMAIL = "a.diallo@lycee-jeanmoulin.fr"
SHARED_OPERATOR_PIN = "1234"
CHEF_PIN = "2222"
AGENT1_PIN = "3333"
AGENT2_PIN = "4444"


# ── Helpers ───────────────────────────────────────────────────────────────────


async def upsert(session, model, pk_value, **values):
    result = await session.execute(select(model).where(model.id == pk_value))
    obj = result.scalar_one_or_none()
    if obj is None:
        obj = model(id=pk_value, **values)
        session.add(obj)
    else:
        for k, v in values.items():
            setattr(obj, k, v)
    await session.flush()
    return obj


async def upsert_assignment(session, user_id, site_id, role_id, poste=None):
    result = await session.execute(
        select(AffectationSite).where(
            AffectationSite.utilisateur_id == user_id,
            AffectationSite.etablissement_id == site_id,
            AffectationSite.role_id == role_id,
        )
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        obj = AffectationSite(
            utilisateur_id=user_id,
            etablissement_id=site_id,
            role_id=role_id,
            is_active=True,
            poste_principal=poste,
        )
        session.add(obj)
    else:
        obj.is_active = True
        if poste:
            obj.poste_principal = poste
    await session.flush()


def paris(dt: datetime) -> datetime:
    return dt.replace(tzinfo=TZ)


def days_ago(n: int, hour=10, minute=0) -> datetime:
    return paris(
        datetime.now(TZ).replace(hour=hour, minute=minute, second=0, microsecond=0)
        - timedelta(days=n)
    )


async def schema_is_ready() -> bool:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables "
                "  WHERE table_schema = 'public' AND table_name = 'organisations'"
                ")"
            )
        )
        return bool(result.scalar())


def run_migrations() -> None:
    print("Schéma absent — application des migrations Alembic…")
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        check=True,
    )


async def ensure_schema() -> None:
    if await schema_is_ready():
        return
    run_migrations()
    if not await schema_is_ready():
        print(
            "Erreur : le schéma PostgreSQL n'a pas pu être initialisé.\n"
            "Vérifiez que la base est démarrée, puis exécutez :\n"
            "  docker exec haccp_api uv run alembic upgrade head",
            file=sys.stderr,
        )
        sys.exit(1)


# ── MAIN ──────────────────────────────────────────────────────────────────────


async def main() -> None:
    await ensure_schema()

    async with AsyncSessionLocal() as s:
        # ── Organisation ──────────────────────────────────────────────────────
        org = await upsert(
            s,
            Organisation,
            ORG_ID,
            nom_entite="Région Île-de-France — Restauration Scolaire",
            type_secteur=TypeSecteur.PUBLIC,
            identifiant_legal="21750001400019",
            admin_login_email=ORG_ADMIN_EMAIL,
            admin_password_hash=get_password_hash(ORG_ADMIN_PASSWORD),
            email_facturation="compta.restauration@iledefrance.fr",
            adresse_facturation="2 rue Simone Veil, 93400 Saint-Ouen",
        )

        # ── Établissement ─────────────────────────────────────────────────────
        site = await upsert(
            s,
            Etablissement,
            SITE_ID,
            organisation_id=org.id,
            nom_site="Lycée Jean Moulin — Cantine",
            adresse="15 avenue Charles de Gaulle, 77100 Meaux",
            siret="21750001400019",
            type_activite="Restaurant scolaire",
            timezone="Europe/Paris",
            telephone_site="+33164340100",
            settings={"timeclock": {"enabled": True, "applies_to_managers": False}},
        )

        # ── Rôles ─────────────────────────────────────────────────────────────
        role_manager = await upsert(
            s,
            Role,
            ROLE_MANAGER_ID,
            nom_role="MANAGER",
            permissions={"manager": True, "can_manage_device_login": True},
        )
        role_chef = await upsert(
            s,
            Role,
            ROLE_CHEF_ID,
            nom_role="CHEF_DE_CUISINE",
            permissions={
                "can_create_temperature_record": True,
                "can_clock": True,
                "can_receive": True,
            },
        )
        role_op = await upsert(
            s,
            Role,
            ROLE_OPERATEUR_ID,
            nom_role="AGENT_DE_RESTAURATION",
            permissions={"can_create_temperature_record": True, "can_clock": True},
        )

        # ── Utilisateurs ──────────────────────────────────────────────────────
        manager = await upsert(
            s,
            Utilisateur,
            USER_MANAGER_ID,
            nom="Leblanc",
            prenom="Marie",
            email=MANAGER_EMAIL,
            telephone_mobile="+33611000001",
            mot_de_passe_hash=get_password_hash(MANAGER_PASSWORD),
            code_pin=get_password_hash(MANAGER_PIN),
        )
        chef = await upsert(
            s,
            Utilisateur,
            USER_CHEF_ID,
            nom="Rousseau",
            prenom="Jean-Pierre",
            email=CHEF_EMAIL,
            telephone_mobile="+33611000002",
            mot_de_passe_hash=get_password_hash("Chef2024!"),
            code_pin=get_password_hash(CHEF_PIN),
        )
        agent1 = await upsert(
            s,
            Utilisateur,
            USER_AGENT1_ID,
            nom="Benali",
            prenom="Fatima",
            email=AGENT1_EMAIL,
            telephone_mobile="+33611000003",
            mot_de_passe_hash=get_password_hash("Agent2024!"),
            code_pin=get_password_hash(AGENT1_PIN),
        )
        agent2 = await upsert(
            s,
            Utilisateur,
            USER_AGENT2_ID,
            nom="Girard",
            prenom="Thomas",
            email=AGENT2_EMAIL,
            telephone_mobile="+33611000004",
            mot_de_passe_hash=get_password_hash("Agent2024!"),
            code_pin=get_password_hash(AGENT2_PIN),
        )
        operator = await upsert(
            s,
            Utilisateur,
            USER_OPERATOR_ID,
            nom="Diallo",
            prenom="Aïcha",
            email=OPERATOR_EMAIL,
            telephone_mobile="+33611000005",
            mot_de_passe_hash=get_password_hash("Agent2024!"),
            code_pin=get_password_hash(SHARED_OPERATOR_PIN),
        )

        await upsert_assignment(
            s, manager.id, site.id, role_manager.id, "Gestionnaire de restauration"
        )
        await upsert_assignment(s, chef.id, site.id, role_chef.id, "Chef de cuisine")
        await upsert_assignment(s, agent1.id, site.id, role_op.id, "Cuisinière")
        await upsert_assignment(s, agent2.id, site.id, role_op.id, "Agent de restauration")
        await upsert_assignment(s, operator.id, site.id, role_op.id, "Plonge / Service")

        # ── Équipements ───────────────────────────────────────────────────────
        EQUIP = [
            (
                UUID("77777777-7777-4777-8777-777777777771"),
                "Chambre froide positive — Viandes",
                "CHAMBRE_FROIDE_POSITIVE",
                Decimal("0"),
                Decimal("4"),
            ),
            (
                UUID("77777777-7777-4777-8777-777777777772"),
                "Chambre froide positive — Légumes & Fruits",
                "CHAMBRE_FROIDE_POSITIVE",
                Decimal("4"),
                Decimal("8"),
            ),
            (
                UUID("77777777-7777-4777-8777-777777777773"),
                "Chambre froide négative — Surgelés",
                "CHAMBRE_FROIDE_NEGATIVE",
                Decimal("-25"),
                Decimal("-18"),
            ),
            (
                UUID("77777777-7777-4777-8777-777777777774"),
                "Réfrigérateur — Produits laitiers",
                "REFRIGERATEUR_VIANDE",
                Decimal("2"),
                Decimal("6"),
            ),
            (
                UUID("77777777-7777-4777-8777-777777777775"),
                "Vitrine réfrigérée — Self",
                "VITRINE_REFRIGEREE",
                Decimal("2"),
                Decimal("6"),
            ),
            (
                UUID("77777777-7777-4777-8777-777777777776"),
                "Cellule de refroidissement rapide",
                "CELLULE_REFROIDISSEMENT",
                Decimal("0"),
                Decimal("3"),
            ),
            (
                UUID("77777777-7777-4777-8777-777777777777"),
                "Réfrigérateur — Poissons",
                "REFRIGERATEUR_POISSON",
                Decimal("0"),
                Decimal("2"),
            ),
            (
                UUID("77777777-7777-4777-8777-777777777778"),
                "Friteuse — Ligne self",
                "CHAUFFE_ASSIETTE_FOUR",
                Decimal("160"),
                Decimal("190"),
            ),
            (
                UUID("77777777-7777-4777-8777-777777777779"),
                "Friteuse — Cuisine centrale",
                "CHAUFFE_ASSIETTE_FOUR",
                Decimal("160"),
                Decimal("190"),
            ),
        ]
        equip_objects = {}
        for eid, enom, etype, tmin, tmax in EQUIP:
            eq = await upsert(
                s,
                Equipement,
                eid,
                etablissement_id=site.id,
                nom=enom,
                type_equipement=TypeEquipement(etype),
                temperature_min_cible=tmin,
                temperature_max_cible=tmax,
            )
            equip_objects[eid] = eq

        # ── Fournisseurs ──────────────────────────────────────────────────────
        SUPPLIERS_DATA = [
            (
                UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                "Boucherie Centrale Île-de-France",
                "France",
                "75012300000012",
                "approved",
                "94 avenue du Général Leclerc, 94000 Créteil",
                "Créteil",
                "Hugues Delorme",
                "h.delorme@boucherie-idf.fr",
                "+33148980011",
                "IFS Food",
                "Agrément sanitaire FR 94.001.001 CE",
            ),
            (
                UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
                "Maraîchers Bio de Beauce",
                "France",
                "28001560000037",
                "approved",
                "Route des Champs, 28300 Saint-Prest",
                "Saint-Prest",
                "Sylvie Chartier",
                "contact@bio-beauce.fr",
                "+33237412289",
                "AB Agriculture Biologique",
                "Certification Ecocert n°28-123",
            ),
            (
                UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
                "Coopérative Laitière de Normandie",
                "France",
                "14001420000029",
                "approved",
                "Chemin des Herbages, 14120 Mondeville",
                "Mondeville",
                "Patrick Lebreton",
                "p.lebreton@coop-normandie.fr",
                "+33231800055",
                "IFS Food",
                "Quota hebdomadaire confirmé chaque lundi",
            ),
            (
                UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
                "Marée de Rungis",
                "France",
                "94046000000081",
                "approved",
                "Pavillon de la Marée, MIN de Rungis, 94150 Rungis",
                "Rungis",
                "Ahmed Tazi",
                "a.tazi@maree-rungis.fr",
                "+33149785050",
                "MSC Pêche Durable",
                "Livraisons lundi + jeudi matin avant 6h",
            ),
            (
                UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"),
                "Boulangerie Artisanale Moreau",
                "France",
                "77001080000016",
                "approved",
                "3 place du Marché, 77100 Meaux",
                "Meaux",
                "Éric Moreau",
                "eric@boulangerie-moreau.fr",
                "+33164340987",
                None,
                "Pain livré chaque matin avant 7h30",
            ),
            (
                UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"),
                "Metro Cash & Carry Roissy",
                "France",
                "95001560000047",
                "approved",
                "Zone Commerciale Paris Nord 2, 95912 Roissy-en-France",
                "Roissy-en-France",
                "Service commercial",
                "b2b@metro.fr",
                "+33800880099",
                None,
                "Commandes en ligne — livraison J+1",
            ),
        ]
        supplier_objects = {}
        for (
            sid,
            name,
            country,
            siret,
            status,
            addr,
            city,
            cname,
            cemail,
            cphone,
            cert,
            notes,
        ) in SUPPLIERS_DATA:
            sup = await upsert(
                s,
                Supplier,
                sid,
                establishment_id=site.id,
                name=name,
                country=SupplierCountry(country),
                company_registration_id=siret,
                status=SupplierStatus(status),
                address=addr,
                city=city,
                contact_name=cname,
                contact_email=cemail,
                contact_phone=cphone,
                certification_type=cert,
                internal_notes=notes,
                is_active=True,
            )
            supplier_objects[sid] = sup

        SUPP_VIANDES = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        SUPP_BIO = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        SUPP_LAITIER = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
        SUPP_MAREE = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
        SUPP_BOULANG = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
        SUPP_METRO = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")

        # ── Produits ──────────────────────────────────────────────────────────
        PRODUCTS_DATA = [
            # (id, supplier_id, name, ref, has_temp, min_t, max_t)
            (
                UUID("11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                SUPP_VIANDES,
                "Escalope de dinde",
                "VIA-001",
                True,
                0.0,
                4.0,
            ),
            (
                UUID("22222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                SUPP_VIANDES,
                "Steak haché surgelé 15%MG",
                "VIA-002",
                True,
                -25.0,
                -18.0,
            ),
            (
                UUID("33333333-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                SUPP_VIANDES,
                "Poulet fermier entier",
                "VIA-003",
                True,
                0.0,
                4.0,
            ),
            (
                UUID("44444444-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                SUPP_VIANDES,
                "Jambon cuit supérieur tranché",
                "VIA-004",
                True,
                2.0,
                6.0,
            ),
            (
                UUID("11111111-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
                SUPP_BIO,
                "Carottes bio (sac 5kg)",
                "BIO-001",
                False,
                None,
                None,
            ),
            (
                UUID("22222222-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
                SUPP_BIO,
                "Pommes de terre bio",
                "BIO-002",
                False,
                None,
                None,
            ),
            (
                UUID("33333333-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
                SUPP_BIO,
                "Salade frisée bio",
                "BIO-003",
                True,
                4.0,
                8.0,
            ),
            (
                UUID("44444444-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
                SUPP_BIO,
                "Tomates cerises bio",
                "BIO-004",
                True,
                8.0,
                12.0,
            ),
            (
                UUID("11111111-cccc-4ccc-8ccc-cccccccccccc"),
                SUPP_LAITIER,
                "Lait demi-écrémé UHT (colis 6×1L)",
                "LAI-001",
                False,
                None,
                None,
            ),
            (
                UUID("22222222-cccc-4ccc-8ccc-cccccccccccc"),
                SUPP_LAITIER,
                "Yaourt nature (carton 24)",
                "LAI-002",
                True,
                2.0,
                6.0,
            ),
            (
                UUID("33333333-cccc-4ccc-8ccc-cccccccccccc"),
                SUPP_LAITIER,
                "Emmental râpé (500g)",
                "LAI-003",
                True,
                2.0,
                8.0,
            ),
            (
                UUID("44444444-cccc-4ccc-8ccc-cccccccccccc"),
                SUPP_LAITIER,
                "Beurre doux plaquette (250g)",
                "LAI-004",
                True,
                2.0,
                6.0,
            ),
            (
                UUID("11111111-dddd-4ddd-8ddd-dddddddddddd"),
                SUPP_MAREE,
                "Filet de cabillaud frais",
                "MAR-001",
                True,
                0.0,
                2.0,
            ),
            (
                UUID("22222222-dddd-4ddd-8ddd-dddddddddddd"),
                SUPP_MAREE,
                "Crevettes entières surgelées",
                "MAR-002",
                True,
                -25.0,
                -18.0,
            ),
            (
                UUID("33333333-dddd-4ddd-8ddd-dddddddddddd"),
                SUPP_MAREE,
                "Saumon portions surgelées",
                "MAR-003",
                True,
                -25.0,
                -18.0,
            ),
            (
                UUID("11111111-eeee-4eee-8eee-eeeeeeeeeeee"),
                SUPP_BOULANG,
                "Baguette tradition (lot 10)",
                "BOU-001",
                False,
                None,
                None,
            ),
            (
                UUID("22222222-eeee-4eee-8eee-eeeeeeeeeeee"),
                SUPP_BOULANG,
                "Pain de mie tranché (500g)",
                "BOU-002",
                False,
                None,
                None,
            ),
            (
                UUID("11111111-ffff-4fff-8fff-ffffffffffff"),
                SUPP_METRO,
                "Huile de tournesol (bidon 5L)",
                "MET-001",
                False,
                None,
                None,
            ),
            (
                UUID("22222222-ffff-4fff-8fff-ffffffffffff"),
                SUPP_METRO,
                "Riz long grain (sac 5kg)",
                "MET-002",
                False,
                None,
                None,
            ),
            (
                UUID("33333333-ffff-4fff-8fff-ffffffffffff"),
                SUPP_METRO,
                "Farine T45 (sac 5kg)",
                "MET-003",
                False,
                None,
                None,
            ),
        ]
        product_objects = {}
        for pid, supp_id, pname, ref, has_temp, tmin, tmax in PRODUCTS_DATA:
            prod = await upsert(
                s,
                Product,
                pid,
                establishment_id=site.id,
                supplier_id=supp_id,
                name=pname,
                internal_reference=ref,
                has_temperature_control=has_temp,
                min_temperature=tmin,
                max_temperature=tmax,
            )
            product_objects[pid] = prod

        # ── Zones de nettoyage ────────────────────────────────────────────────
        ZONES_DATA = [
            (UUID("a0000001-0000-4000-8000-000000000001"), "Cuisine chaude"),
            (UUID("a0000001-0000-4000-8000-000000000002"), "Cuisine froide / Préparations froides"),
            (UUID("a0000001-0000-4000-8000-000000000003"), "Zone de plonge — Vaisselle"),
            (UUID("a0000001-0000-4000-8000-000000000004"), "Salle de restauration"),
            (UUID("a0000001-0000-4000-8000-000000000005"), "Chambres froides"),
            (UUID("a0000001-0000-4000-8000-000000000006"), "Quai de réception & déchets"),
            (UUID("a0000001-0000-4000-8000-000000000007"), "Vestiaires & sanitaires personnel"),
        ]
        zone_objects = {}
        for zid, zname in ZONES_DATA:
            zone_objects[zid] = await upsert(
                s,
                CleaningZone,
                zid,
                establishment_id=site.id,
                name=zname,
            )

        Z_CHAUD = UUID("a0000001-0000-4000-8000-000000000001")
        Z_FROID = UUID("a0000001-0000-4000-8000-000000000002")
        Z_PLONGE = UUID("a0000001-0000-4000-8000-000000000003")
        Z_SALLE = UUID("a0000001-0000-4000-8000-000000000004")
        Z_CF = UUID("a0000001-0000-4000-8000-000000000005")
        Z_QUAI = UUID("a0000001-0000-4000-8000-000000000006")
        Z_VEST = UUID("a0000001-0000-4000-8000-000000000007")

        # ── Routines de nettoyage ─────────────────────────────────────────────
        ROUTINES_DATA = [
            (
                UUID("b0000001-0000-4000-8000-000000000001"),
                "Ouverture — Mise en place",
                ScheduleType.OPENING,
            ),
            (
                UUID("b0000001-0000-4000-8000-000000000002"),
                "Fermeture Midi — Nettoyage service",
                ScheduleType.CLOSING,
            ),
            (
                UUID("b0000001-0000-4000-8000-000000000003"),
                "Grand Nettoyage Hebdomadaire",
                ScheduleType.WEEKLY,
            ),
        ]
        routine_objects = {}
        for rid, rname, rtype in ROUTINES_DATA:
            routine_objects[rid] = await upsert(
                s,
                CleaningRoutine,
                rid,
                establishment_id=site.id,
                name=rname,
                schedule_type=rtype,
            )

        R_OUVERTURE = UUID("b0000001-0000-4000-8000-000000000001")
        R_FERMETURE = UUID("b0000001-0000-4000-8000-000000000002")
        R_HEBDO = UUID("b0000001-0000-4000-8000-000000000003")

        # ── Tâches par routine ────────────────────────────────────────────────
        TASKS_DATA = [
            # Ouverture
            (
                UUID("c0000001-0000-4000-8000-000000000001"),
                R_OUVERTURE,
                Z_CHAUD,
                "Vérifier la propreté des plans de travail",
                "S'assurer de l'absence de résidus de la veille.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000002"),
                R_OUVERTURE,
                Z_CHAUD,
                "Allumer et vérifier les fours",
                "Contrôle visuel + test de chauffe.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000003"),
                R_OUVERTURE,
                Z_FROID,
                "Contrôler les températures des enceintes froides",
                "Noter les relevés sur le registre HACCP.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000004"),
                R_OUVERTURE,
                Z_CF,
                "Vérifier les joints des portes de CF",
                "Signaler tout joint abîmé au gestionnaire.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000005"),
                R_OUVERTURE,
                Z_SALLE,
                "Disposer les sets de table et couverts",
                None,
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000006"),
                R_OUVERTURE,
                Z_PLONGE,
                "Mettre en route le lave-vaisselle industriel",
                "Vérifier le niveau de sel et rinçage.",
            ),
            # Fermeture Midi
            (
                UUID("c0000001-0000-4000-8000-000000000010"),
                R_FERMETURE,
                Z_CHAUD,
                "Nettoyer et désinfecter les fours",
                "Produit agréé P3 — contact 15 min minimum.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000011"),
                R_FERMETURE,
                Z_CHAUD,
                "Nettoyer la friteuse et vider l'huile",
                "Filtrer l'huile si < 20 utilisations.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000012"),
                R_FERMETURE,
                Z_CHAUD,
                "Désinfecter les plans de travail inox",
                "Spray désinfectant + lavette à usage unique.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000013"),
                R_FERMETURE,
                Z_FROID,
                "Ranger et filmer tous les aliments entamés",
                "Étiqueter avec date et heure.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000014"),
                R_FERMETURE,
                Z_FROID,
                "Nettoyer et désinfecter le plan de découpe",
                "Changer les planches si abîmées.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000015"),
                R_FERMETURE,
                Z_PLONGE,
                "Désinfecter le bac de plonge",
                "Produit chloré dilué 0,5%.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000016"),
                R_FERMETURE,
                Z_PLONGE,
                "Passer la raclette et le balai sur le sol plonge",
                None,
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000017"),
                R_FERMETURE,
                Z_SALLE,
                "Débarrasser et essuyer les tables",
                "Produit désinfectant multi-surfaces.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000018"),
                R_FERMETURE,
                Z_SALLE,
                "Balayer et passer la serpillère salle",
                None,
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000019"),
                R_FERMETURE,
                Z_QUAI,
                "Sortir les poubelles et rincer les bacs",
                "Tri sélectif — vérifier les sacs.",
            ),
            # Hebdo
            (
                UUID("c0000001-0000-4000-8000-000000000020"),
                R_HEBDO,
                Z_CHAUD,
                "Démonter et nettoyer les grilles de ventilation",
                "Trempage eau chaude + brosse.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000021"),
                R_HEBDO,
                Z_CHAUD,
                "Dégraisser les hottes aspirantes",
                "Produit dégraissant puissant — EPI obligatoires.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000022"),
                R_HEBDO,
                Z_CF,
                "Nettoyer l'intérieur des chambres froides",
                "Eau chaude + désinfectant alimentaire.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000023"),
                R_HEBDO,
                Z_CF,
                "Défrosting du congélateur si nécessaire",
                "Débrancher 30 min, éponger.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000024"),
                R_HEBDO,
                Z_PLONGE,
                "Détartrer le lave-vaisselle",
                "Produit détartrant — cycle à vide.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000025"),
                R_HEBDO,
                Z_VEST,
                "Nettoyer et désinfecter les sanitaires personnel",
                "Détartrant + désinfectant WC.",
            ),
            (
                UUID("c0000001-0000-4000-8000-000000000026"),
                R_HEBDO,
                Z_QUAI,
                "Laver le quai de livraison au karcher",
                None,
            ),
        ]
        task_objects = {}
        for tid, rid, zid, tname, tdesc in TASKS_DATA:
            task_objects[tid] = await upsert(
                s,
                CleaningTaskTemplate,
                tid,
                routine_id=rid,
                zone_id=zid,
                name=tname,
                description=tdesc,
            )

        # ── Pointages (5 jours) ───────────────────────────────────────────────
        timeclock_events = []
        for dago, user_id in [
            (0, chef.id),
            (0, agent1.id),
            (1, chef.id),
            (1, agent1.id),
            (2, chef.id),
        ]:
            timeclock_events += [
                Pointage(
                    etablissement_id=site.id,
                    utilisateur_id=user_id,
                    type_evenement=TypeEvenementPointage.CLOCK_IN,
                    pointe_at=days_ago(dago, 7, 0),
                ),
                Pointage(
                    etablissement_id=site.id,
                    utilisateur_id=user_id,
                    type_evenement=TypeEvenementPointage.BREAK_START,
                    pointe_at=days_ago(dago, 12, 30),
                ),
                Pointage(
                    etablissement_id=site.id,
                    utilisateur_id=user_id,
                    type_evenement=TypeEvenementPointage.BREAK_END,
                    pointe_at=days_ago(dago, 13, 15),
                ),
                Pointage(
                    etablissement_id=site.id,
                    utilisateur_id=user_id,
                    type_evenement=TypeEvenementPointage.CLOCK_OUT,
                    pointe_at=days_ago(dago, 15, 30),
                ),
            ]
        for evt in timeclock_events:
            s.add(evt)
        await s.flush()

        # ── Relevés de température ────────────────────────────────────────────
        EQUIP_CF_VIANDES = UUID("77777777-7777-4777-8777-777777777771")
        EQUIP_CF_LEGUMES = UUID("77777777-7777-4777-8777-777777777772")
        EQUIP_CF_NEG = UUID("77777777-7777-4777-8777-777777777773")
        EQUIP_REF_LAIT = UUID("77777777-7777-4777-8777-777777777774")

        temp_records = []
        nc_list = []
        for dago, equip_id, val, is_ok in [
            (0, EQUIP_CF_VIANDES, Decimal("3.2"), True),
            (0, EQUIP_CF_LEGUMES, Decimal("6.1"), True),
            (0, EQUIP_CF_NEG, Decimal("-20.5"), True),
            (0, EQUIP_REF_LAIT, Decimal("4.8"), True),
            (1, EQUIP_CF_VIANDES, Decimal("2.8"), True),
            (1, EQUIP_CF_NEG, Decimal("-19.2"), True),
            (2, EQUIP_CF_VIANDES, Decimal("6.4"), False),  # NC !
            (2, EQUIP_CF_LEGUMES, Decimal("5.3"), True),
            (3, EQUIP_CF_VIANDES, Decimal("3.0"), True),
            (3, EQUIP_REF_LAIT, Decimal("7.2"), False),  # NC !
        ]:
            releve = ReleveTemperature(
                etablissement_id=site.id,
                equipement_id=equip_id,
                utilisateur_id=chef.id,
                valeur_mesuree=val,
                is_conforme=is_ok,
                source=SourceReleve.MANUEL,
                mesure_effectuee_at=days_ago(dago, 7, 30),
            )
            s.add(releve)
            temp_records.append((releve, is_ok, dago))
        await s.flush()

        for releve, is_ok, dago in temp_records:
            if not is_ok:
                nc = NonConformity(
                    establishment_id=site.id,
                    workflow_type=WorkflowType.TEMPERATURE,
                    status=NonConformityStatus.OPEN,
                    source_record_id=releve.id,
                    opened_by_id=chef.id,
                    opened_at=days_ago(dago, 7, 35),
                )
                s.add(nc)
        await s.flush()

        # ── Sessions de réception ─────────────────────────────────────────────
        # Session 1 : livraison viandes + laitiers (J-1, conforme)
        sess1 = ReceptionSession(
            id=UUID("d0000001-0000-4000-8000-000000000001"),
            establishment_id=site.id,
            operator_id=chef.id,
            supplier_id=SUPP_VIANDES,
            received_at=days_ago(1, 7, 45),
            status=ReceptionStatus.CLOSED,
            opened_at=days_ago(1, 7, 45),
            closed_at=days_ago(1, 8, 10),
        )
        # workaround: delete & re-insert to avoid PK conflict on re-run
        existing = await s.execute(select(ReceptionSession).where(ReceptionSession.id == sess1.id))
        if existing.scalar_one_or_none() is None:
            s.add(sess1)
            await s.flush()
            items1 = [
                ReceptionItem(
                    session_id=sess1.id,
                    product_id=UUID("11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                    lot_number="VIA24-0610",
                    dluo=date.today() + timedelta(days=3),
                    measured_temperature=2.8,
                    is_compliant=True,
                    scanned_at=days_ago(1, 7, 50),
                ),
                ReceptionItem(
                    session_id=sess1.id,
                    product_id=UUID("33333333-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                    lot_number="VIA24-0611",
                    dluo=date.today() + timedelta(days=2),
                    measured_temperature=3.5,
                    is_compliant=True,
                    scanned_at=days_ago(1, 7, 52),
                ),
                ReceptionItem(
                    session_id=sess1.id,
                    product_id=UUID("22222222-cccc-4ccc-8ccc-cccccccccccc"),
                    lot_number="LAI24-0890",
                    dluo=date.today() + timedelta(days=14),
                    measured_temperature=4.1,
                    is_compliant=True,
                    scanned_at=days_ago(1, 7, 55),
                ),
            ]
            for it in items1:
                s.add(it)

        # Session 2 : livraison poissons — 1 NC température
        sess2 = ReceptionSession(
            id=UUID("d0000001-0000-4000-8000-000000000002"),
            establishment_id=site.id,
            operator_id=agent1.id,
            supplier_id=SUPP_MAREE,
            received_at=days_ago(2, 6, 30),
            status=ReceptionStatus.CLOSED,
            opened_at=days_ago(2, 6, 30),
            closed_at=days_ago(2, 6, 55),
        )
        existing2 = await s.execute(select(ReceptionSession).where(ReceptionSession.id == sess2.id))
        if existing2.scalar_one_or_none() is None:
            s.add(sess2)
            await s.flush()
            nc_reception = NonConformity(
                establishment_id=site.id,
                workflow_type=WorkflowType.RECEPTION,
                status=NonConformityStatus.OPEN,
                opened_by_id=agent1.id,
                opened_at=days_ago(2, 6, 40),
            )
            s.add(nc_reception)
            await s.flush()
            items2 = [
                ReceptionItem(
                    session_id=sess2.id,
                    product_id=UUID("11111111-dddd-4ddd-8ddd-dddddddddddd"),
                    lot_number="MAR24-1102",
                    dluo=date.today() + timedelta(days=2),
                    measured_temperature=4.2,
                    is_compliant=False,
                    nc_id=nc_reception.id,
                    scanned_at=days_ago(2, 6, 40),
                ),
                ReceptionItem(
                    session_id=sess2.id,
                    product_id=UUID("22222222-dddd-4ddd-8ddd-dddddddddddd"),
                    lot_number="MAR24-1103",
                    dluo=date.today() + timedelta(days=60),
                    measured_temperature=-20.0,
                    is_compliant=True,
                    scanned_at=days_ago(2, 6, 45),
                ),
            ]
            for it in items2:
                s.add(it)

        # ── Logs de nettoyage ─────────────────────────────────────────────────
        FERMETURE_TASKS_DONE = [
            UUID("c0000001-0000-4000-8000-000000000010"),
            UUID("c0000001-0000-4000-8000-000000000011"),
            UUID("c0000001-0000-4000-8000-000000000012"),
            UUID("c0000001-0000-4000-8000-000000000013"),
            UUID("c0000001-0000-4000-8000-000000000014"),
            UUID("c0000001-0000-4000-8000-000000000015"),
            UUID("c0000001-0000-4000-8000-000000000016"),
        ]
        for dago in [1, 2]:
            for i, tid in enumerate(FERMETURE_TASKS_DONE):
                log = CleaningLog(
                    establishment_id=site.id,
                    operator_id=agent1.id if i % 2 == 0 else agent2.id,
                    task_id=tid,
                    status=CleaningStatus.DONE,
                    comment=None,
                    executed_at=days_ago(dago, 14, 0 + i * 2),
                )
                s.add(log)

        # 1 anomalie sur la friteuse (J-1)
        log_issue = CleaningLog(
            establishment_id=site.id,
            operator_id=chef.id,
            task_id=UUID("c0000001-0000-4000-8000-000000000011"),
            status=CleaningStatus.ISSUE,
            comment="Résistance de la friteuse à changer — huile impossible à filtrer correctement. Signalé au gestionnaire.",
            executed_at=days_ago(1, 14, 5),
        )
        s.add(log_issue)

        # ── Menu du jour (tablette allergènes) ───────────────────────────────
        menu_today = datetime.now(TZ).date()
        MENU_DEMO = [
            (
                UUID("d0000001-0000-4000-8000-000000000001"),
                "Déjeuner",
                "Blanquette de veau",
                ["Gluten", "Lait", "Céleri"],
            ),
            (
                UUID("d0000001-0000-4000-8000-000000000002"),
                "Déjeuner",
                "Gratin dauphinois",
                ["Lait"],
            ),
            (
                UUID("d0000001-0000-4000-8000-000000000003"),
                "Déjeuner",
                "Salade composée",
                ["Œufs", "Moutarde", "Sésame"],
            ),
            (
                UUID("d0000001-0000-4000-8000-000000000004"),
                "Déjeuner",
                "Poisson pané (cabillaud)",
                ["Gluten", "Poisson", "Œufs"],
            ),
            (
                UUID("d0000001-0000-4000-8000-000000000005"),
                "Déjeuner",
                "Mousse au chocolat",
                ["Lait", "Œufs"],
            ),
            (
                UUID("d0000001-0000-4000-8000-000000000006"),
                "Goûter",
                "Fruits de saison",
                [],
            ),
        ]
        for mid, meal, dish, allergens in MENU_DEMO:
            await upsert(
                s,
                DailyMenuItem,
                mid,
                establishment_id=site.id,
                service_date=menu_today,
                meal_service=meal,
                dish_name=dish,
                allergens=allergens,
            )

        await s.commit()

    # ── Résumé ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SEED DEMO — Lycée Jean Moulin · Cantine")
    print("=" * 60)
    print(f"\n  Établissement UUID : {SITE_ID}")
    print(f"  Organisation UUID  : {ORG_ID}")
    print("\n  ── Comptes ──────────────────────────────────────────────")
    print(f"  Admin org        : {ORG_ADMIN_EMAIL}  /  {ORG_ADMIN_PASSWORD}")
    print(f"  Gestionnaire     : {MANAGER_EMAIL}    /  {MANAGER_PASSWORD}   PIN: {MANAGER_PIN}")
    print(f"  Chef de cuisine  : {CHEF_EMAIL}        →  PIN: {CHEF_PIN}")
    print(f"  Cuisinière       : {AGENT1_EMAIL}      →  PIN: {AGENT1_PIN}")
    print(f"  Agent restau.    : {AGENT2_EMAIL}      →  PIN: {AGENT2_PIN}")
    print(f"  Agente plonge    : {OPERATOR_EMAIL}    →  PIN: {SHARED_OPERATOR_PIN}")
    print("\n  ── Données insérées ─────────────────────────────────────")
    print("  • 6 fournisseurs (viandes, bio, laitier, marée, boulang., épicerie)")
    print("  • 20 produits avec/sans contrôle température")
    print("  • 9 équipements (chambres froides, réfrigérateurs, friteuses)")
    print("  • Menu du jour avec allergènes (6 plats)")
    print("  • 7 zones de nettoyage + 3 routines + 26 tâches")
    print("  • Pointages sur 3 jours (chef + cuisinière)")
    print("  • 10 relevés de température (2 NC)")
    print("  • 2 sessions de réception (1 NC réception)")
    print("  • Logs de nettoyage fermeture sur 2 jours (1 anomalie)")
    print("=" * 60 + "\n")


async def run() -> None:
    try:
        await main()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
