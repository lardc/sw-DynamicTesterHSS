import time
from fastapi import FastAPI, HTTPException
from src.config_loader import load_config, Config
from src.sampler import OscilloscopeHandler, OscilloscopeData
from src.logger import setup_logging, get_logger
from src.measure import find_min_max, serialize_curves
import numpy as np
from pydantic import BaseModel

from typing import List, Dict

from src.measure import Curves, perform_calculations, get_pivot_index

app = FastAPI(title="Oscilloscope Sampler")
scope_handler: OscilloscopeHandler
logger = get_logger(__name__)

g_t1 = 0.0

class ResponseModel(BaseModel):
    status: str = "ok"
    info: str = ""
    data: List[Dict[str, float|None]] = []

@app.on_event("startup")
def startup_event():
    global scope_handler
    try:
        config: Config = load_config()
        setup_logging(config.log_path)

        scope_handler = OscilloscopeHandler(config, '@py')

    except Exception as e:
        raise e


@app.get("/status")
def get_status():
    logger.info("Endpoint /status was called")
    return {"status": "stat"}


@app.get("/results", response_model=ResponseModel)
def get_results():
    global g_t1

    response = ResponseModel()

    logger.info("Endpoint /results was called")

    t2 = time.perf_counter()

    results_data = scope_handler.get_results()
    if not results_data:
        raise HTTPException(status_code=404, detail="No results available")

    try:
        pivot_index = get_pivot_index(results_data)
        list_curves = [
            serialize_curves(results_data, end_index=pivot_index),
            serialize_curves(results_data, start_index=pivot_index)
        ]
    except Exception as e:
        response.status = "failed"
        response.info = f"error serializing curves: {e}"
        return response

    try:
        for curves in list_curves:
            response.data.append(perform_calculations(curves))
    except Exception as e:
        response.status = "failed"
        response.info = "calculations failed: " + str(e)
        return response

    t2 = time.perf_counter() - t2

    logger.info(f"samplig and measuring estimated: {t2 + g_t1}")

    return response


@app.get("/test/ids")
def test_id_request():
    return {"ids": []}

@app.get("/test/config")
def test_get_config():
    return scope_handler.get_config()

@app.get("/test/curves")
def test_get_curves():
    pivot_index = get_pivot_index(scope_handler.get_results())

    list_curves = []
    list_curves.append(serialize_curves(scope_handler.get_results(), end_index=pivot_index))
    list_curves.append(serialize_curves(scope_handler.get_results(), start_index=pivot_index))
    #print(list_curves)
    return {"status": "ok"}


@app.post("/configure")
def configure(config_data: Config):
    logger.info("Endpoint /configure was called")

    current_config = load_config()
    update_data = config_data.model_dump(exclude_unset=True)
    updated_config = current_config.model_copy(update=update_data)
    scope_handler.set_config(updated_config)
    return {
        "status": "config updated",
        "updated_fields": list(update_data.keys())
    }


@app.post("/start")
def start_sampler():
    global g_t1
    logger.info("Endpoint /start was called")
    g_t1 = time.perf_counter()
    scope_handler.request_raw_data()
    g_t1 = time.perf_counter() - g_t1
    return {"status": "sampling started"}

@app.post("/stop")
def stop_sampler():
    logger.info("Endpoint /stop was called")
    return
