"""HW5 Part 2A - "meals" MCP server over TheMealDB (test key 1), run over STDIO.

Run with the MCP Inspector:   mcp dev meals_server.py
Logs go to stderr only - stdout is reserved for the JSON-RPC stream.
"""
import logging
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="%(asctime)s [meals] %(levelname)s %(message)s")
log = logging.getLogger("meals")

API_BASE = "https://www.themealdb.com/api/json/v1/1"
TIMEOUT_S = 10.0

mcp = FastMCP("meals")


def _get(endpoint: str, params: dict | None = None) -> list[dict] | None:
    """Call TheMealDB and return the "meals" list (None when the API says no results).

    Network / HTTP / JSON problems raise RuntimeError with a short message, which
    the MCP client (Inspector) shows as a clean tool error.
    """
    url = f"{API_BASE}/{endpoint}"
    log.info("GET %s params=%s", url, params)
    try:
        resp = httpx.get(url, params=params, timeout=TIMEOUT_S)
        resp.raise_for_status()
        payload = resp.json()
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"TheMealDB timed out after {TIMEOUT_S}s") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"TheMealDB returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Network error calling TheMealDB: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError("TheMealDB returned invalid JSON") from exc
    return payload.get("meals")


def _ingredients(meal: dict) -> list[dict]:
    items = []
    for i in range(1, 21):
        name = (meal.get(f"strIngredient{i}") or "").strip()
        if name:
            items.append({"name": name, "measure": (meal.get(f"strMeasure{i}") or "").strip()})
    return items


def _details(meal: dict) -> dict[str, Any]:
    return {
        "id": meal.get("idMeal"),
        "name": meal.get("strMeal"),
        "category": meal.get("strCategory"),
        "area": meal.get("strArea"),
        "instructions": meal.get("strInstructions"),
        "image": meal.get("strMealThumb"),
        "source": meal.get("strSource"),
        "youtube": meal.get("strYoutube"),
        "ingredients": _ingredients(meal),
    }


@mcp.tool()
def search_meals_by_name(query: str, limit: int = 5) -> dict:
    """Search meals by name. Returns up to `limit` (1-25) meals with id, name, area, category, thumb."""
    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= limit <= 25:
        raise ValueError("limit must be between 1 and 25")
    meals = _get("search.php", {"s": query.strip()})
    if not meals:
        return {"results": [], "message": f"no matches for '{query}'"}
    return {"results": [{"id": m["idMeal"], "name": m["strMeal"], "area": m.get("strArea"),
                         "category": m.get("strCategory"), "thumb": m.get("strMealThumb")}
                        for m in meals[:limit]]}


@mcp.tool()
def meals_by_ingredient(ingredient: str, limit: int = 12) -> dict:
    """List meals whose main ingredient matches. Returns small cards: id, name, thumb."""
    if not ingredient.strip():
        raise ValueError("ingredient must not be empty")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    meals = _get("filter.php", {"i": ingredient.strip()})
    if not meals:
        return {"results": [], "message": f"no matches for ingredient '{ingredient}'"}
    return {"results": [{"id": m["idMeal"], "name": m["strMeal"], "thumb": m.get("strMealThumb")}
                        for m in meals[:limit]]}


@mcp.tool()
def meal_details(id: str | int) -> dict:
    """Full recipe for one meal id: name, category, area, instructions, image, source, youtube, ingredients."""
    meal_id = str(id).strip()
    if not meal_id.isdigit():
        raise ValueError("id must be a numeric meal id, e.g. 52771")
    meals = _get("lookup.php", {"i": meal_id})
    if not meals:
        return {"result": None, "message": f"no meal found with id {meal_id}"}
    return _details(meals[0])


@mcp.tool()
def random_meal() -> dict:
    """One random meal, same shape as meal_details."""
    meals = _get("random.php")
    if not meals:
        return {"result": None, "message": "no matches"}
    return _details(meals[0])


if __name__ == "__main__":
    log.info("starting meals MCP server (stdio)")
    mcp.run()
