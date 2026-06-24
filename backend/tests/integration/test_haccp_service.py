"""Integration tests for app/modules/haccp/service.py."""

from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import now_for_site
from app.modules.haccp.models import TypeEvenementPointage
from app.modules.haccp.schemas import (
    PointageCreate,
    TemperatureRecordBulkCreate,
    TemperatureRecordCreate,
    TimeclockStatus,
)
from app.modules.haccp.service import (
    create_temperature_record,
    create_temperature_records_bulk,
    create_time_clock_event,
    get_establishment_operator_statuses,
    get_operator_timeclock_status,
)
from app.modules.nonconformities.models import NonConformity, NonConformityStatus
from tests.integration.conftest import (
    make_base_seed,
    make_equipment,
    make_establishment,
    make_organisation,
)

_PARIS = ZoneInfo("Europe/Paris")

# ── Temperature records ───────────────────────────────────────────────────────


async def test_create_temperature_record_compliant_no_nc(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)

    payload = TemperatureRecordCreate(
        equipment_id=equip.id,
        measured_value=Decimal("2.5"),
    )
    result = await create_temperature_record(payload, test_db, seed.ctx, seed.operator)

    assert result.is_conforme is True
    assert result.nonconformity_id is None
    assert result.action_corrective_required is False

    # No NC must exist in DB
    ncs = (
        (
            await test_db.execute(
                select(NonConformity).where(NonConformity.establishment_id == seed.est.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(ncs) == 0


async def test_create_temperature_record_non_compliant_opens_nc(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est, min_temp=Decimal("0"), max_temp=Decimal("4"))

    payload = TemperatureRecordCreate(
        equipment_id=equip.id,
        measured_value=Decimal("8.0"),  # out of range
    )
    result = await create_temperature_record(payload, test_db, seed.ctx, seed.operator)

    assert result.is_conforme is False
    assert result.nonconformity_id is not None
    assert result.action_corrective_required is True

    # NC must exist in DB with OPEN status
    nc = (
        await test_db.execute(
            select(NonConformity).where(NonConformity.id == result.nonconformity_id)
        )
    ).scalar_one()
    assert nc.status == NonConformityStatus.OPEN


async def test_create_temperature_record_equipment_not_found_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    # Create equipment in a DIFFERENT establishment
    other_org = await make_organisation(test_db)
    other_est = await make_establishment(test_db, other_org)
    other_equip = await make_equipment(test_db, other_est)

    payload = TemperatureRecordCreate(
        equipment_id=other_equip.id,  # not in seed.est
        measured_value=Decimal("2.0"),
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_temperature_record(payload, test_db, seed.ctx, seed.operator)
    assert exc_info.value.status_code == 404


async def test_create_temperature_record_at_boundary_compliant(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est, min_temp=Decimal("0"), max_temp=Decimal("4"))

    for boundary in [Decimal("0"), Decimal("4")]:
        payload = TemperatureRecordCreate(equipment_id=equip.id, measured_value=boundary)
        result = await create_temperature_record(payload, test_db, seed.ctx, seed.operator)
        assert result.is_conforme is True


# ── measured_at validation ────────────────────────────────────────────────────


async def test_create_temperature_record_with_recent_measured_at_succeeds(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)

    recent_at = now_for_site("Europe/Paris") - timedelta(hours=3)
    payload = TemperatureRecordCreate(
        equipment_id=equip.id,
        measured_value=Decimal("2.5"),
        measured_at=recent_at,
    )
    result = await create_temperature_record(payload, test_db, seed.ctx, seed.operator)
    assert result.is_conforme is True


async def test_create_temperature_record_with_none_measured_at_always_succeeds(
    test_db: AsyncSession,
):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)

    payload = TemperatureRecordCreate(
        equipment_id=equip.id,
        measured_value=Decimal("2.5"),
        measured_at=None,
    )
    result = await create_temperature_record(payload, test_db, seed.ctx, seed.operator)
    assert result.is_conforme is True
    assert result.measured_at is not None


async def test_create_temperature_record_with_backdated_measured_at_raises_422(
    test_db: AsyncSession,
):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)

    too_old = now_for_site("Europe/Paris") - timedelta(hours=9)
    payload = TemperatureRecordCreate(
        equipment_id=equip.id,
        measured_value=Decimal("2.5"),
        measured_at=too_old,
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_temperature_record(payload, test_db, seed.ctx, seed.operator)
    assert exc_info.value.status_code == 422


async def test_create_temperature_record_with_future_measured_at_raises_422(
    test_db: AsyncSession,
):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)

    future_at = now_for_site("Europe/Paris") + timedelta(minutes=10)
    payload = TemperatureRecordCreate(
        equipment_id=equip.id,
        measured_value=Decimal("2.5"),
        measured_at=future_at,
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_temperature_record(payload, test_db, seed.ctx, seed.operator)
    assert exc_info.value.status_code == 422


# ── Bulk temperature records ──────────────────────────────────────────────────


async def test_create_temperature_records_bulk_all_compliant(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    eq1 = await make_equipment(test_db, seed.est, min_temp=Decimal("0"), max_temp=Decimal("4"))
    eq2 = await make_equipment(test_db, seed.est, min_temp=Decimal("-25"), max_temp=Decimal("-18"))

    payload = TemperatureRecordBulkCreate(
        records=[
            TemperatureRecordCreate(equipment_id=eq1.id, measured_value=Decimal("2.0")),
            TemperatureRecordCreate(equipment_id=eq2.id, measured_value=Decimal("-20.0")),
        ]
    )
    result = await create_temperature_records_bulk(payload, test_db, seed.ctx, seed.operator)

    assert result.count == 2
    assert result.nonconformity_count == 0
    assert all(r.is_conforme for r in result.created)

    ncs = (
        (
            await test_db.execute(
                select(NonConformity).where(NonConformity.establishment_id == seed.est.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(ncs) == 0


async def test_create_temperature_records_bulk_mixed_compliance_opens_nc(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    eq1 = await make_equipment(test_db, seed.est, min_temp=Decimal("0"), max_temp=Decimal("4"))
    eq2 = await make_equipment(test_db, seed.est, min_temp=Decimal("0"), max_temp=Decimal("4"))

    payload = TemperatureRecordBulkCreate(
        records=[
            TemperatureRecordCreate(equipment_id=eq1.id, measured_value=Decimal("2.0")),  # conforme
            TemperatureRecordCreate(
                equipment_id=eq2.id, measured_value=Decimal("8.0")
            ),  # hors seuil
        ]
    )
    result = await create_temperature_records_bulk(payload, test_db, seed.ctx, seed.operator)

    assert result.count == 2
    assert result.nonconformity_count == 1

    nc_results = [r for r in result.created if not r.is_conforme]
    assert len(nc_results) == 1
    assert nc_results[0].nonconformity_id is not None

    nc = (
        await test_db.execute(
            select(NonConformity).where(NonConformity.id == nc_results[0].nonconformity_id)
        )
    ).scalar_one()
    assert nc.status == NonConformityStatus.OPEN


async def test_create_temperature_records_bulk_all_noncompliant_opens_all_ncs(
    test_db: AsyncSession,
):
    seed = await make_base_seed(test_db)
    equipments = [
        await make_equipment(test_db, seed.est, min_temp=Decimal("0"), max_temp=Decimal("4"))
        for _ in range(3)
    ]

    payload = TemperatureRecordBulkCreate(
        records=[
            TemperatureRecordCreate(equipment_id=eq.id, measured_value=Decimal("15.0"))
            for eq in equipments
        ]
    )
    result = await create_temperature_records_bulk(payload, test_db, seed.ctx, seed.operator)

    assert result.count == 3
    assert result.nonconformity_count == 3

    ncs_in_db = (
        (
            await test_db.execute(
                select(NonConformity).where(NonConformity.establishment_id == seed.est.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(ncs_in_db) == 3


async def test_create_temperature_records_bulk_unknown_equipment_raises_400(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    other_org = await make_organisation(test_db)
    other_est = await make_establishment(test_db, other_org)
    foreign_equip = await make_equipment(test_db, other_est)

    payload = TemperatureRecordBulkCreate(
        records=[
            TemperatureRecordCreate(equipment_id=foreign_equip.id, measured_value=Decimal("2.0")),
        ]
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_temperature_records_bulk(payload, test_db, seed.ctx, seed.operator)
    assert exc_info.value.status_code == 400


async def test_create_temperature_records_bulk_future_timestamp_raises_422(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)

    payload = TemperatureRecordBulkCreate(
        records=[
            TemperatureRecordCreate(
                equipment_id=equip.id,
                measured_value=Decimal("2.0"),
                measured_at=now_for_site("Europe/Paris") + timedelta(minutes=10),
            ),
        ]
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_temperature_records_bulk(payload, test_db, seed.ctx, seed.operator)
    assert exc_info.value.status_code == 422


async def test_create_temperature_records_bulk_preserves_order(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equipments = [
        await make_equipment(test_db, seed.est, min_temp=Decimal("0"), max_temp=Decimal("4"))
        for _ in range(3)
    ]
    values = [Decimal("1.0"), Decimal("2.0"), Decimal("3.0")]

    payload = TemperatureRecordBulkCreate(
        records=[
            TemperatureRecordCreate(equipment_id=eq.id, measured_value=val)
            for eq, val in zip(equipments, values, strict=True)
        ]
    )
    result = await create_temperature_records_bulk(payload, test_db, seed.ctx, seed.operator)

    assert result.count == 3
    for response, expected_value in zip(result.created, values, strict=True):
        assert response.measured_value == expected_value


# ── Timeclock state machine ───────────────────────────────────────────────────


async def test_timeclock_initial_status_clocked_out(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    result = await get_operator_timeclock_status(test_db, seed.ctx, seed.operator)
    assert result.status == TimeclockStatus.CLOCKED_OUT


async def test_timeclock_full_cycle(test_db: AsyncSession):
    seed = await make_base_seed(test_db)

    # CLOCK_IN
    result = await create_time_clock_event(
        PointageCreate(type_evenement=TypeEvenementPointage.CLOCK_IN),
        test_db,
        seed.ctx,
        seed.operator,
    )
    assert result.type_evenement == TypeEvenementPointage.CLOCK_IN

    status_after_in = await get_operator_timeclock_status(test_db, seed.ctx, seed.operator)
    assert status_after_in.status == TimeclockStatus.ACTIVE

    # BREAK_START
    await create_time_clock_event(
        PointageCreate(type_evenement=TypeEvenementPointage.BREAK_START),
        test_db,
        seed.ctx,
        seed.operator,
    )
    status_after_break = await get_operator_timeclock_status(test_db, seed.ctx, seed.operator)
    assert status_after_break.status == TimeclockStatus.ON_BREAK

    # BREAK_END
    await create_time_clock_event(
        PointageCreate(type_evenement=TypeEvenementPointage.BREAK_END),
        test_db,
        seed.ctx,
        seed.operator,
    )
    status_after_end = await get_operator_timeclock_status(test_db, seed.ctx, seed.operator)
    assert status_after_end.status == TimeclockStatus.ACTIVE

    # CLOCK_OUT
    await create_time_clock_event(
        PointageCreate(type_evenement=TypeEvenementPointage.CLOCK_OUT),
        test_db,
        seed.ctx,
        seed.operator,
    )
    status_final = await get_operator_timeclock_status(test_db, seed.ctx, seed.operator)
    assert status_final.status == TimeclockStatus.CLOCKED_OUT


async def test_timeclock_invalid_transition_clock_in_while_active_raises_409(test_db: AsyncSession):
    seed = await make_base_seed(test_db)

    await create_time_clock_event(
        PointageCreate(type_evenement=TypeEvenementPointage.CLOCK_IN),
        test_db,
        seed.ctx,
        seed.operator,
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_time_clock_event(
            PointageCreate(type_evenement=TypeEvenementPointage.CLOCK_IN),
            test_db,
            seed.ctx,
            seed.operator,
        )
    assert exc_info.value.status_code == 409


async def test_timeclock_invalid_transition_break_end_when_clocked_out_raises_409(
    test_db: AsyncSession,
):
    seed = await make_base_seed(test_db)

    with pytest.raises(HTTPException) as exc_info:
        await create_time_clock_event(
            PointageCreate(type_evenement=TypeEvenementPointage.BREAK_END),
            test_db,
            seed.ctx,
            seed.operator,
        )
    assert exc_info.value.status_code == 409


async def test_timeclock_invalid_transition_clock_out_when_clocked_out_raises_409(
    test_db: AsyncSession,
):
    seed = await make_base_seed(test_db)

    with pytest.raises(HTTPException) as exc_info:
        await create_time_clock_event(
            PointageCreate(type_evenement=TypeEvenementPointage.CLOCK_OUT),
            test_db,
            seed.ctx,
            seed.operator,
        )
    assert exc_info.value.status_code == 409


async def test_get_establishment_operator_statuses_returns_all_operators(test_db: AsyncSession):
    seed = await make_base_seed(test_db)

    # Clock in the operator
    await create_time_clock_event(
        PointageCreate(type_evenement=TypeEvenementPointage.CLOCK_IN),
        test_db,
        seed.ctx,
        seed.operator,
    )

    result = await get_establishment_operator_statuses(test_db, seed.ctx)
    operator_ids = {item.operator_id for item in result.items}
    assert seed.operator.id in operator_ids
