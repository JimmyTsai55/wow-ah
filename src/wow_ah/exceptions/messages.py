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
    INVALID_TIMESTAMP = "Invalid timestamp format: {timestamp}"
    STORAGE_ERROR = "Database error during {operation}: {error}"
    ZERO_TOTAL_QUANTITY = "Cannot aggregate listings for item {item_id}: total quantity is 0"
    ZERO_MATERIAL_COST = "Recipe {recipe_name} has zero material cost — reagent prices are likely stale or zero"


class AgentErrorMessages:
    MISSING_API_KEY = "OPENAI_API_KEY is not set. Add it to your .env file."
    OPENAI_ERROR = "OpenAI API call failed: {error}"
    MAX_ROUNDS_EXCEEDED = (
        "Agent '{agent}' exceeded the maximum of {limit} tool-call rounds"
    )
    UNKNOWN_TOOL = "Agent '{agent}' requested an unknown tool: {tool}"
