import httpx

from wow_ah.core.auth import TokenManager
from wow_ah.exceptions.base import APIError
from wow_ah.exceptions.messages import APIErrorMessages
from wow_ah.schemas.prices import CommodityListing, ItemInfo


def parse_commodities(
    raw: dict, watchlist: set[int] | None = None
) -> list[CommodityListing]:
    """Parse raw Blizzard API response into CommodityListing objects."""
    listings = []
    for auction in raw.get("auctions", []):
        item_id = auction["item"]["id"]
        if watchlist and item_id not in watchlist:
            continue
        listings.append(
            CommodityListing(
                item_id=item_id,
                unit_price=auction["unit_price"],
                quantity=auction["quantity"],
            )
        )
    return listings


class BlizzardAdapter:
    """Fetches market data from Blizzard Game Data API."""

    def __init__(self, token_manager: TokenManager, region: str = "us") -> None:
        self._token_manager = token_manager
        self._region = region
        self._base_url = f"https://{region}.api.blizzard.com"
        self._last_modified: str | None = None

    def fetch_commodities(self) -> list[CommodityListing]:
        token = self._token_manager.get_token()
        try:
            resp = httpx.get(
                f"{self._base_url}/data/wow/auctions/commodities",
                params={
                    "namespace": f"dynamic-{self._region}",
                    "locale": "en_US",
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise APIError(
                APIErrorMessages.FETCH_FAILED.format(status_code=e.response.status_code)
            ) from e
        except httpx.HTTPError as e:
            raise APIError(
                APIErrorMessages.FETCH_FAILED.format(status_code="connection_error")
            ) from e

        self._last_modified = resp.headers.get("Last-Modified")
        return parse_commodities(resp.json())

    def get_item(self, item_id: int) -> ItemInfo:
        token = self._token_manager.get_token()
        try:
            resp = httpx.get(
                f"{self._base_url}/data/wow/item/{item_id}",
                params={
                    "namespace": f"static-{self._region}",
                    "locale": "en_US",
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise APIError(
                APIErrorMessages.FETCH_FAILED.format(status_code=e.response.status_code)
            ) from e
        except httpx.HTTPError as e:
            raise APIError(
                APIErrorMessages.FETCH_FAILED.format(status_code="connection_error")
            ) from e
        data = resp.json()
        return ItemInfo(
            item_id=data["id"],
            name=data["name"],
            quality=data.get("quality", {}).get("name"),
            item_class=data.get("item_class", {}).get("name"),
            item_subclass=data.get("item_subclass", {}).get("name"),
        )

    @property
    def last_modified(self) -> str | None:
        return self._last_modified
