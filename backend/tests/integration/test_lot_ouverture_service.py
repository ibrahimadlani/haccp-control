"""Integration tests for lot ouverture service functions."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.receptions.models import StatutOuverture
from app.modules.receptions.schemas import LotOuvertureCreate
from app.modules.receptions.service import (
    close_lot_ouverture,
    list_active_ouvertures,
    open_lot_ouverture,
)
from tests.integration.conftest import (
    make_base_seed,
    make_lot_ouverture,
    make_product,
    make_reception_item,
    make_reception_session,
    make_supplier,
)


async def test_open_lot_creates_ouverture_with_correct_dlc(test_db: AsyncSession):
    """Opening a lot computes the secondary DLC correctly."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    dluo = (datetime.now(UTC) + timedelta(days=14)).date()
    item = await make_reception_item(test_db, session, product, dluo=dluo)

    result = await open_lot_ouverture(
        item.id,
        LotOuvertureCreate(duree_apres_ouverture_jours=5),
        test_db,
        seed.ctx,
        seed.operator,
    )

    today = datetime.now(UTC).date()
    expected_dlc = min(today + timedelta(days=5), dluo)
    assert result.id is not None
    assert result.dlc_secondaire_calculee == expected_dlc
    assert result.dluo_primaire == dluo
    assert result.statut == StatutOuverture.OUVERT
    assert result.was_frozen is False


async def test_open_lot_dlc_capped_at_dluo(test_db: AsyncSession):
    """Requesting 60 days after opening on a lot expiring in 2 days → DLC = DLUO."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    dluo = (datetime.now(UTC) + timedelta(days=2)).date()
    item = await make_reception_item(test_db, session, product, dluo=dluo)

    result = await open_lot_ouverture(
        item.id,
        LotOuvertureCreate(duree_apres_ouverture_jours=60),
        test_db,
        seed.ctx,
        seed.operator,
    )

    assert result.dlc_secondaire_calculee == dluo


async def test_open_lot_expired_item_raises_422(test_db: AsyncSession):
    """Opening a lot whose DLUO is in the past raises 422."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    expired_dluo = date(2020, 1, 1)
    item = await make_reception_item(test_db, session, product, dluo=expired_dluo)

    with pytest.raises(HTTPException) as exc:
        await open_lot_ouverture(
            item.id,
            LotOuvertureCreate(duree_apres_ouverture_jours=3),
            test_db,
            seed.ctx,
            seed.operator,
        )

    assert exc.value.status_code == 422


async def test_open_lot_already_open_raises_409(test_db: AsyncSession):
    """Opening the same lot twice without closing it first raises 409."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    item = await make_reception_item(test_db, session, product)
    await make_lot_ouverture(test_db, seed.est, item, seed.operator)

    with pytest.raises(HTTPException) as exc:
        await open_lot_ouverture(
            item.id,
            LotOuvertureCreate(duree_apres_ouverture_jours=3),
            test_db,
            seed.ctx,
            seed.operator,
        )

    assert exc.value.status_code == 409


async def test_open_lot_wrong_establishment_raises_404(test_db: AsyncSession):
    """A lot from a different establishment is invisible → 404."""
    seed1 = await make_base_seed(test_db)
    seed2 = await make_base_seed(test_db)

    supplier = await make_supplier(test_db, seed1.est)
    product = await make_product(test_db, seed1.est, supplier)
    session = await make_reception_session(test_db, seed1.est, seed1.operator, supplier)
    item = await make_reception_item(test_db, session, product)

    with pytest.raises(HTTPException) as exc:
        await open_lot_ouverture(
            item.id,
            LotOuvertureCreate(duree_apres_ouverture_jours=3),
            test_db,
            seed2.ctx,
            seed2.operator,
        )

    assert exc.value.status_code == 404


async def test_open_lot_frozen_product_sets_was_frozen_true(test_db: AsyncSession):
    """A frozen item (is_surgele=True) produces was_frozen=True on the ouverture."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    item = await make_reception_item(test_db, session, product, is_surgele=True)

    result = await open_lot_ouverture(
        item.id,
        LotOuvertureCreate(duree_apres_ouverture_jours=3),
        test_db,
        seed.ctx,
        seed.operator,
    )

    assert result.was_frozen is True


async def test_close_lot_transitions_to_consomme(test_db: AsyncSession):
    """Closing with CONSOMME transitions statut correctly."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    item = await make_reception_item(test_db, session, product)
    ouverture = await make_lot_ouverture(test_db, seed.est, item, seed.operator)

    result = await close_lot_ouverture(
        ouverture.id, StatutOuverture.CONSOMME, test_db, seed.ctx
    )

    assert result.statut == StatutOuverture.CONSOMME


async def test_close_lot_transitions_to_jete(test_db: AsyncSession):
    """Closing with JETE transitions statut correctly."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    item = await make_reception_item(test_db, session, product)
    ouverture = await make_lot_ouverture(test_db, seed.est, item, seed.operator)

    result = await close_lot_ouverture(ouverture.id, StatutOuverture.JETE, test_db, seed.ctx)

    assert result.statut == StatutOuverture.JETE


async def test_close_already_closed_lot_raises_409(test_db: AsyncSession):
    """Closing a lot that is already CONSOMME raises 409."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    item = await make_reception_item(test_db, session, product)
    ouverture = await make_lot_ouverture(
        test_db, seed.est, item, seed.operator, statut=StatutOuverture.CONSOMME
    )

    with pytest.raises(HTTPException) as exc:
        await close_lot_ouverture(
            ouverture.id, StatutOuverture.JETE, test_db, seed.ctx
        )

    assert exc.value.status_code == 409


async def test_list_active_ouvertures_returns_only_ouvert(test_db: AsyncSession):
    """list_active_ouvertures returns only OUVERT lots, not closed ones."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)

    item_open = await make_reception_item(test_db, session, product)
    item_closed = await make_reception_item(test_db, session, product)

    await make_lot_ouverture(test_db, seed.est, item_open, seed.operator)
    await make_lot_ouverture(
        test_db, seed.est, item_closed, seed.operator, statut=StatutOuverture.CONSOMME
    )

    result = await list_active_ouvertures(test_db, seed.ctx)

    assert len(result.items) == 1
    assert result.items[0].reception_item_id == item_open.id


async def test_list_active_ouvertures_sorted_by_dlc_asc(test_db: AsyncSession):
    """Active ouvertures are sorted by dlc_secondaire_calculee ascending (soonest first)."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)

    today = datetime.now(UTC).date()
    item_soon = await make_reception_item(
        test_db, session, product, dluo=(today + timedelta(days=30))
    )
    item_later = await make_reception_item(
        test_db, session, product, dluo=(today + timedelta(days=30))
    )

    await make_lot_ouverture(test_db, seed.est, item_soon, seed.operator, duree_jours=2)
    await make_lot_ouverture(test_db, seed.est, item_later, seed.operator, duree_jours=7)

    result = await list_active_ouvertures(test_db, seed.ctx)

    assert len(result.items) == 2
    assert result.items[0].dlc_secondaire_calculee <= result.items[1].dlc_secondaire_calculee


async def test_list_active_ouvertures_excludes_other_establishment(test_db: AsyncSession):
    """Active ouvertures from another establishment are not visible."""
    seed1 = await make_base_seed(test_db)
    seed2 = await make_base_seed(test_db)

    supplier = await make_supplier(test_db, seed1.est)
    product = await make_product(test_db, seed1.est, supplier)
    session = await make_reception_session(test_db, seed1.est, seed1.operator, supplier)
    item = await make_reception_item(test_db, session, product)
    await make_lot_ouverture(test_db, seed1.est, item, seed1.operator)

    result = await list_active_ouvertures(test_db, seed2.ctx)

    assert len(result.items) == 0


async def test_close_lot_wrong_establishment_raises_404(test_db: AsyncSession):
    """Closing a lot that belongs to another establishment raises 404."""
    seed1 = await make_base_seed(test_db)
    seed2 = await make_base_seed(test_db)

    supplier = await make_supplier(test_db, seed1.est)
    product = await make_product(test_db, seed1.est, supplier)
    session = await make_reception_session(test_db, seed1.est, seed1.operator, supplier)
    item = await make_reception_item(test_db, session, product)
    ouverture = await make_lot_ouverture(test_db, seed1.est, item, seed1.operator)

    with pytest.raises(HTTPException) as exc:
        await close_lot_ouverture(
            ouverture.id, StatutOuverture.CONSOMME, test_db, seed2.ctx
        )

    assert exc.value.status_code == 404


async def test_close_lot_unknown_id_raises_404(test_db: AsyncSession):
    """Closing a non-existent lot ID raises 404."""
    seed = await make_base_seed(test_db)

    with pytest.raises(HTTPException) as exc:
        await close_lot_ouverture(
            uuid.uuid4(), StatutOuverture.CONSOMME, test_db, seed.ctx
        )

    assert exc.value.status_code == 404
