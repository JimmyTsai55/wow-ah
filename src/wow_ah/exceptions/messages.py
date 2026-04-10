class APIErrorMessages:
    AUTH_FAILED = "Blizzard OAuth2 authentication failed: {error}"
    FETCH_FAILED = "Commodity data fetch failed: HTTP {status_code}"
    RATE_LIMITED = "API rate limited, please try again later"


class DataErrorMessages:
    NO_SNAPSHOTS = "No price snapshots found for {item_name}. Run 'wow-ah fetch' first."
    INSUFFICIENT_HISTORY = (
        "{item_name} has only {actual}h of history, need at least {required}h"
    )
    RECIPE_NOT_FOUND = "Recipe not found: {recipe_name}"
    RECIPE_FILE_INVALID = "Recipe file is invalid: {error}"
