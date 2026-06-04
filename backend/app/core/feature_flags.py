from fastapi import Depends, HTTPException, status

from app.core.dependencies import CurrentEstablishment, get_current_establishment
from app.core.features import Feature


def require_feature(feature: Feature):
    """Return a FastAPI dependency that rejects (403) when the feature is disabled for the site.

    Usage at router level:
        router = APIRouter(dependencies=[Depends(require_feature(Feature.CLEANING))])

    Usage at endpoint level:
        @router.post("/endpoint", dependencies=[Depends(require_feature(Feature.TIMECLOCK))])
    """

    async def _guard(
        establishment: CurrentEstablishment = Depends(get_current_establishment),
    ) -> None:
        from app.modules.tenant.schemas import EstablishmentSettings

        settings = EstablishmentSettings.from_raw(establishment.settings)
        if not settings.is_enabled(feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"La fonctionnalité '{feature.value}' est désactivée pour cet établissement.",
            )

    return _guard
