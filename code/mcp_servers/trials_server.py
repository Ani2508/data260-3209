"""HW5 Part 2B - domain MCP server over the s3209_rel MySQL data (STDIO).

Run with the MCP Inspector:   mcp dev trials_server.py --with "mcp[cli]<2"
Three tools, one envelope: {"ok": bool, "data": ..., "error": str | None}.
Logs go to stderr only.
"""
import logging
import sys

from mcp.server.fastmcp import FastMCP

import trials_core as core

logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="%(asctime)s [s3209_trials] %(levelname)s %(message)s")
log = logging.getLogger("s3209_trials")

mcp = FastMCP("s3209_trials")
store = core.SQLTrialStore()


def _run(name: str, inputs: dict) -> dict:
    # drop arguments the client left empty so defaults apply
    inputs = {k: v for k, v in inputs.items() if v is not None}
    log.info("tool=%s inputs=%s", name, inputs)
    try:
        result = core.TOOLS[name](store, inputs)
    except Exception as exc:  # DB down etc. -> clean envelope, never a crash
        log.exception("tool %s failed", name)
        result = core.fail(f"{type(exc).__name__}: {exc}")
    log.info("tool=%s ok=%s", name, result["ok"])
    return result


@mcp.tool()
def search_trials(query: str, status: str | None = None, limit: int = 10) -> dict:
    """Search trials by title or sponsor name. status (optional): Recruiting,
    Active - Not Recruiting, Completed, Terminated. limit: 1-25."""
    return _run("search_trials", {"query": query, "status": status, "limit": limit})


@mcp.tool()
def get_trial(trial_id: int) -> dict:
    """Get one trial's full record by numeric id."""
    return _run("get_trial", {"trial_id": trial_id})


@mcp.tool()
def trial_stats(group_by: str = "status") -> dict:
    """Aggregate: trial count and total open enrollment slots grouped by 'status' or 'sponsor'."""
    return _run("trial_stats", {"group_by": group_by})


if __name__ == "__main__":
    log.info("starting s3209_trials MCP server (stdio)")
    mcp.run()
