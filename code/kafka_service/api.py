"""HW8 Part 1 FastAPI wrapper on PORT_BASE 8509. It never touches the trial dict;
every call becomes a Kafka request/response through TrialKafkaClient.

A caller may send its own X-Correlation-ID; the API passes it through unchanged.
"""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse

from config import PORT_BASE, PREFIX, RUN_BY, get_logger
from kafka_client import TrialKafkaClient

log = get_logger("api")
client: TrialKafkaClient | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global client
    client = TrialKafkaClient(role="api")
    log.info("Run by: %s (%s)", RUN_BY, PREFIX)
    log.info("Server started at http://127.0.0.1:%d", PORT_BASE)
    yield
    client.close()


app = FastAPI(title=f"{PREFIX} trial service (Kafka)", lifespan=lifespan)


def reply(response: dict) -> JSONResponse:
    if response["success"]:
        code = 200
    elif response.get("error") == "Trial not found":
        code = 404
    elif str(response.get("error", "")).startswith("No response"):
        code = 504
    else:
        code = 422
    return JSONResponse(response, status_code=code,
                        headers={"X-Correlation-ID": str(response.get("correlation_id"))})


@app.post("/trials")
def create_trial(data: dict, x_correlation_id: str | None = Header(default=None)):
    cid = x_correlation_id or str(uuid.uuid4())
    log.info("HTTP POST /trials cid=%s", cid)
    return reply(client.request("CREATE_TRIAL", data, correlation_id=cid))


@app.get("/trials/{trial_id}")
def get_trial(trial_id: str, x_correlation_id: str | None = Header(default=None)):
    cid = x_correlation_id or str(uuid.uuid4())
    log.info("HTTP GET /trials/%s cid=%s", trial_id, cid)
    return reply(client.request("GET_TRIAL", {"trial_id": trial_id}, correlation_id=cid))
