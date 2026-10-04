"""Save machine-readable outputs of every MCP tool test (same inputs as the MCP Inspector runs).

Usage:  python export_tool_outputs.py   -> reports/hw05/raw/mcp_inspector_outputs.json
Talks to both servers over STDIO exactly like the Inspector does (meals needs internet).
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "reports" / "hw05" / "raw" / "mcp_inspector_outputs.json"

CALLS = {
    "meals_server.py": [
        ("search_meals_by_name", {"query": "Arrabiata", "limit": 5}),
        ("meals_by_ingredient", {"ingredient": "chicken", "limit": 5}),
        ("meal_details", {"id": "52771"}),
        ("random_meal", {}),
    ],
    "trials_server.py": [
        ("search_trials", {"query": "Mayo", "limit": 5}),
        ("search_trials", {"query": "a"}),
        ("get_trial", {"trial_id": 5}),
        ("get_trial", {"trial_id": 9999}),
        ("trial_stats", {"group_by": "status"}),
        ("trial_stats", {"group_by": "color"}),
    ],
}


async def run_server(server: str, calls: list) -> list:
    params = StdioServerParameters(command=sys.executable, args=[server], cwd=str(HERE))
    records = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for tool, args in calls:
                res = await session.call_tool(tool, args)
                text = res.content[0].text if res.content else ""
                try:
                    output = json.loads(text)
                except ValueError:
                    output = text
                records.append({"timestamp": datetime.now().isoformat(timespec="seconds"),
                                "server": server.replace(".py", ""), "tool": tool, "input": args,
                                "is_error": bool(res.isError), "output": output})
                print(f"[{records[-1]['timestamp']}] {server:<17} {tool:<22} {json.dumps(args)}"
                      f" -> {'ERROR' if res.isError else 'ok'}")
    return records


async def main():
    records = []
    for server, calls in CALLS.items():
        records += await run_server(server, calls)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(records, indent=2))
    print(f"saved {len(records)} tool results -> reports/hw05/raw/{OUT.name}")


if __name__ == "__main__":
    asyncio.run(main())
