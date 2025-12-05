import json
from typing import List, Dict, Optional
from pydantic import BaseModel, ValidationError


class DeviceConfig(BaseModel):
    id: str
    channel1: str
    channel2: str
    emulation: bool
    csv_path: Optional[str] = None


class Config(BaseModel):
    log_path: str
    api_port: int = 8000
    oscilloscopes: List[DeviceConfig]


def load_config(path: str = 'config.json') -> Config:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    try:
        config = Config(**data)
    except ValidationError as e:
        raise ValidationError(f"Config validation error: {e}")

    return config
