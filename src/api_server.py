from fastapi import FastAPI, HTTPException
from src.config_loader import load_config, Config
from src.sampler import OscilloscopeHandler
from src.logger import setup_logging, get_logger

app = FastAPI(title="Oscilloscope Sampler")
scope_handler: OscilloscopeHandler
logger = get_logger(__name__)


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
    return {"status": "stat"}


@app.get("/results")
def get_results():
    return scope_handler.get_results()


@app.get("/test/ids")
def test_id_request():
    return {"ids": []}

@app.get("/test/config")
def test_get_config():
    return load_config().model_dump_json()


@app.post("/configure")
def configure():
    scope_handler.set_config(load_config())


@app.post("/start")
def start_sampler():
    scope_handler.request_raw_data()


@app.post("/stop")
def stop_sampler():
    return
