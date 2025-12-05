import uvicorn
import os
from src.api_server import app
from src.config_loader import load_config, Config


def main() -> None:
    try:
        local_config = load_config()
        port = local_config.api_port
    except Exception:
        port = int(os.environ.get("API_PORT", 8000))

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    main()
