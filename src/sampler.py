from time import sleep
from datetime import datetime
from typing import List, Dict, Any, Tuple, Callable
import numpy as np
from numpy.typing import NDArray
from src.config_loader import Config, DeviceConfig
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, ValidationError

import pyvisa
from pyvisa import ResourceManager
from pyvisa.resources.tcpip import TCPIPInstrument

from src.logger import get_logger

logger = get_logger(__name__)


class OscilloscopeData(BaseModel):
    id: str
    raw_data: Dict[str, NDArray[np.float32]]

    class Config:
        arbitrary_types_allowed = True


class Preamble(BaseModel):
    xincrement: float = 0.0
    xorigin: float = 0.0
    xreference: int = 0
    yincrement: float = 0.0
    yorigin: int = 0
    yreference: int = 0
    sample_rate: float = 0.0


class Oscilloscope:
    def __init__(self, config: DeviceConfig, resource_manager: ResourceManager) -> None:
        self.__id: str = config.id
        self.__channel1: str = config.channel1
        self.__channel2: str = config.channel2
        self.__scope: TCPIPInstrument = resource_manager.open_resource(self.__id)
        self.__preamble: Preamble
        self.__state: str = ''

    def get_id(self) -> str:
        return self.__id

    def get_raw_data(self) -> Dict[str, NDArray[np.float32]]:
        data: Dict[str, NDArray[np.float32]] = {}

        self.__scope.write(':STOP')
        if self.__channel1 != 'None':
            data[self.__channel1] = self.__get_raw_data_channel(self.__channel1)
        if self.__channel2 != 'None':
            data[self.__channel2] = self.__get_raw_data_channel(self.__channel2)
        self.__scope.write(':RUN')

        return data

    def get_norm_data(self) -> Dict[str, NDArray[np.float32]]:
        data: Dict[str, NDArray[np.float32]] = {}

        self.__scope.write(':STOP')
        if self.__channel1 != 'None':
            data[self.__channel1] = self.__get_norm_data_channel(self.__channel1)
        if self.__channel2 != 'None':
            data[self.__channel2] = self.__get_norm_data_channel(self.__channel2)
        self.__scope.write(':RUN')

        return data

    def __get_raw_data_channel(self, channel: str) -> NDArray[np.float32]:
        t: datetime = datetime.now()

        self.__scope.write(f':WAV:SOUR:{channel}')
        self.__scope.write(':WAV:MODE RAW')
        self.__scope.write(':WAV:FORM BYTE')

        max_points = int(self.__scope.query(':ACQ:MDEP?'))
        logger.info(f"Max points: {max_points}")

        self.__scope.write(':WAV:STAR 1')
        self.__scope.write(f':WAV:STOP {max_points}')

        self.__scope.write(':WAV:RES')
        self.__scope.write(':WAV:BEG')

        data = []
        while True:
            self.__state, points = self.__scope.query(':WAV:STAT?').replace('\n', '').split(',')
            if self.__state == 'READ' and int(points) == 0:
                sleep(0.05)
                continue

            logger.info(f"Processed state = {self.__state}, points = {points}")

            data += self.__scope.query_binary_values(':WAV:DATA?', datatype='B')

            if self.__state == 'IDLE':
                self.__scope.write(':WAV:END')
                break

        logger.info(f't1: f{datetime.now() - t}')

        t = datetime.now()

        np_data: NDArray[np.float32] = np.array(data, dtype=np.float32)

        preamble: Preamble = self.get_preamble()
        np_data = (np_data - preamble.yorigin - preamble.yreference) * preamble.yincrement

        logger.info(f't2: {datetime.now() - t}')

        return np_data

    def __get_norm_data_channel(self, channel: str) -> NDArray[np.float32]:
        t: datetime = datetime.now()

        self.__scope.write(f':WAV:SOUR:{channel}')
        self.__scope.write(':WAV:MODE NORM')
        self.__scope.write(':WAV:FORM BYTE')

        data = self.__scope.query_binary_values(':WAV:DATA?', datatype='B')

        logger.info(f't1: {datetime.now() - t}')

        t = datetime.now()

        np_data: NDArray[np.float32] = np.array(data, dtype=np.float32)

        preamble: Preamble = self.get_preamble()
        np_data = (np_data - preamble.yorigin - preamble.yreference) * preamble.yincrement

        logger.info(f't2: {datetime.now() - t}')

        return np_data

    def get_preamble(self) -> Preamble:
        preamble_values: List[str] = self.__scope.query(':WAV:PRE?').split(',')

        if len(preamble_values) < 10:
            raise ValueError('Preamble incorrect')

        self.__preamble = Preamble(
            xincrement=float(preamble_values[4]),
            xorigin=float(preamble_values[5]),
            xreference=int(preamble_values[6]),
            yincrement=float(preamble_values[7]),
            yorigin=int(preamble_values[8]),
            yreference=int(preamble_values[9]),
            sample_rate=float(self.__scope.query(':ACQ:SRAT?'))
        )

        return self.__preamble

    def get_channel_settings(self, channel: str) -> Tuple[float, float]:
        vscale: float = float(self.__scope.query(f':{channel}:SCAL?'))
        voffset: float = float(self.__scope.query(f':{channel}:OFFS?'))
        return vscale, voffset

    def get_state(self) -> str:
        return self.__state


class OscilloscopeEmulation(Oscilloscope):
    def __init__(self, config: DeviceConfig, resource_manager: ResourceManager) -> None:
        self._id: str = config.id
        self._channel1: str = config.channel1
        self._channel2: str = config.channel2
        self._csv_path: str = config.csv_path
        self._preamble: Preamble = Preamble(
            xincrement=1.0e-6,
            yincrement=0.1,
            sample_rate=1000000.0
        )
        logger.info(f"Initialized OscilloscopeEmulation: {self._id}")

    def get_raw_data(self) -> Dict[str, NDArray[np.float32]]:
        data: Dict[str, NDArray[np.float32]] = {}
        return data

    def get_norm_data(self) -> Dict[str, NDArray[np.float32]]:
        data: Dict[str, NDArray[np.float32]] = {}
        return data

    def get_preamble(self) -> Preamble:
        return self._preamble


class OscilloscopeHandler:
    def __init__(self, config: Config, visa_path='') -> None:
        self.__resource_manager = ResourceManager(visa_path)
        self.__oscilloscopes: List[Oscilloscope] = []

        for device_config in config.oscilloscopes:
            try:
                scope_object = self.__create_scope_instance(device_config)
                self.__oscilloscopes.append(scope_object)
            except Exception as e:
                logger.error(f"Unable to create oscilloscope instance {device_config.id}: {e}")

    def __create_scope_instance(self, device_config: DeviceConfig) -> Oscilloscope:
        if device_config.emulation:
            return OscilloscopeEmulation(device_config, self.__resource_manager)
        return Oscilloscope(device_config, self.__resource_manager)

    def _worker_get_raw_data(self, scope: Oscilloscope) -> OscilloscopeData:
        try:
            return OscilloscopeData(id=scope.get_id(), raw_data=scope.get_raw_data())
        except Exception as e:
            return OscilloscopeData(id=scope.get_id(), raw_data={})

    def _worker_get_norm_data(self, scope: Oscilloscope) -> OscilloscopeData:
        try:
            return OscilloscopeData(id=scope.get_id(), raw_data=scope.get_norm_data())
        except Exception as e:
            return OscilloscopeData(id=scope.get_id(), raw_data={})

    def __request_data(self, worker_func: Callable[[Oscilloscope], OscilloscopeData]) -> List[OscilloscopeData]:
        results: List[OscilloscopeData] = []

        with ThreadPoolExecutor(max_workers=len(self.__oscilloscopes) or 1) as executor:
            future_to_scope = {
                executor.submit(worker_func, scope): scope.get_id()
                for scope in self.__oscilloscopes
            }

            for future in as_completed(future_to_scope):
                result = future.result()
                results.append(result)

        return results

    def request_raw_data(self) -> List[OscilloscopeData]:
        return self.__request_data(self._worker_get_raw_data)

    def request_norm_data(self) -> List[OscilloscopeData]:
        return self.__request_data(self._worker_get_norm_data)

    def request_ids(self) -> List[str]:
        ids: List[str] = []
        return ids
