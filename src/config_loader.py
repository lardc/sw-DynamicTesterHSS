import json
from typing import List, Dict, Optional
from pydantic import BaseModel, ValidationError


class DeviceConfig(BaseModel):
    id: str

    channel1: Optional[str] = None
    channel2: Optional[str] = None
    channel1_div: int = 1
    channel2_div: int = 1


class Config(BaseModel):
    log_path: str
    api_port: int = 8000
    oscilloscopes: List[DeviceConfig]
    
    emulation: Optional[bool] = False
    csv_path: Optional[str] = None
    sample_rate: float = 0


def load_config(path: str = 'config.json') -> Config:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    try:
        config = Config(**data)
    except ValidationError as e:
        raise ValidationError(f"Config validation error: {e}")

    return config
