import time
from fastapi import FastAPI, HTTPException
from src.config_loader import load_config, Config
from src.sampler import OscilloscopeHandler, OscilloscopeData
from src.logger import setup_logging, get_logger
from src.measure import find_min_max, serialize_curves
import numpy as np

from typing import List

from src.measure import Curves, vi_rise_fall, calc_delay, recovery, calc_energy, is_high_element, on_mode, get_pivot_index

app = FastAPI(title="Oscilloscope Sampler")
scope_handler: OscilloscopeHandler
logger = get_logger(__name__)

g_t1 = 0.0


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


@app.get("/results")
def get_results():
    global g_t1

    logger.info("Endpoint /results was called")

    t2 = time.perf_counter()

    results_data = scope_handler.get_results()
    if not results_data:
        raise HTTPException(status_code=404, detail="No results available")

    pivot_index = get_pivot_index(results_data)

    list_curves = []
    list_curves.append(serialize_curves(results_data, end_index=pivot_index))
    list_curves.append(serialize_curves(results_data, start_index=pivot_index))

    results = []

    for curves in list_curves:
        high = is_high_element(curves)
        on = on_mode(curves)
        vi = vi_rise_fall(curves)
        rec = recovery(curves)
        energy = calc_energy(curves)
        delay = calc_delay(curves)

        result = {
            "Uce_amp": vi["V_points"].S_amp,
            "Uce_max": vi["V_points"].S_max,
            "Ice_amp": vi["I_points"].S_amp,
            "Ice_max": vi["I_points"].S_max,
            "dI_dt": vi["I_points"].S_rf,
            "tfi": vi["I_points"].t_rf if not on else None,
            "tri": vi["I_points"].t_rf if on else None,
            "Icpk": vi["I_points"].S_max if not on else None,
            "dU_dt": vi["V_points"].S_rf,
            "tfv": vi["V_points"].t_rf if on else None,
            "trv": vi["V_points"].t_rf if not on else None,
            "Eon": energy["Energy"] if on else None,
            "Eoff": energy["Energy"] if not on else None,
            "tdi_on": delay if on and not high else None,
            "tdi_off": delay if not on and not high else None,
            "Uce_100": vi["V_points"].S_amp if not on else None,
            "Irm": rec["Irrm"] if on else None,
            "trr": rec["trr"] if on else None,
            "trr1": rec["trr1"] if on else None,
            "trr2": rec["trr2"] if on else None,
            "Qrr": rec["Qrr"] if on else None,
            "Erec": rec["Energy"] if on else None,
        }
        results.append(result)

    t2 = time.perf_counter() - t2

    logger.info(f"samplig and measuring estimated: {t2 + g_t1}")

    return results


@app.get("/test/ids")
def test_id_request():
    return {"ids": []}

@app.get("/test/config")
def test_get_config():
    return load_config().model_dump()

@app.get("/test/curves")
def test_get_curves():
    pivot_index = get_pivot_index(scope_handler.get_results())

    list_curves = []
    list_curves.append(serialize_curves(scope_handler.get_results(), end_index=pivot_index))
    list_curves.append(serialize_curves(scope_handler.get_results(), start_index=pivot_index))
    #print(list_curves)
    return {"status": "ok"}


@app.post("/configure")
def configure():
    logger.info("Endpoint /configure was called")
    scope_handler.set_config(load_config())
    return {"status": "config reloaded"}

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
