import numpy as np

from numpy.typing import NDArray
from typing import Tuple, Dict, List
from src.sampler import OscilloscopeData
from dataclasses import dataclass

from src.logger import get_logger

logger = get_logger(__name__)

@dataclass
class Curves:
    Vge: NDArray[np.float32]
    Vce: NDArray[np.float32]
    Ice: NDArray[np.float32]
    time_step: float

@dataclass
class RiseFallResult:
    S_max: float
    S_amp: float
    S_rf: float
    t_rf: float
    t_min: float
    t_max: float


def find_min_max(array: NDArray) -> Tuple[float, float]:
    return (array.min(), array.max())

def get_pivot_index(data: List[OscilloscopeData]) -> int:
    vge_data = np.array([])
    for d in data:
        if 'Vge' in d.raw_data:
            vge_data = d.raw_data['Vge']
            break

    if len(vge_data) == 0:
        logger.warning("No Vge data found, returning 0 as pivot index.")
        return 0

    first_zero_idx = 0
    second_zero_idx = 0
    for i in range(len(vge_data)-1):
        if vge_data[i] <= 0 and vge_data[i+1] > 0:
            if first_zero_idx == 0:
                first_zero_idx = i+1
            else:
                second_zero_idx = i+1
                break

    if second_zero_idx == 0:
        logger.warning(f"Found only {1 if first_zero_idx > 0 else 0} zero crossing(s). Using fallback pivot.")
        return len(vge_data) // 2 if first_zero_idx == 0 else first_zero_idx

    pivot_idx = (first_zero_idx + second_zero_idx) // 2

    logger.info(f"Data split at index {pivot_idx}.")

    return pivot_idx

def serialize_curves(data: List[OscilloscopeData], start_index: int = 0, end_index: int = -1) -> Curves:
    logger.info("Serializing curves from oscilloscope data.")
    curves = Curves(
        Vge = np.array([]),
        Vce =  np.array([]),
        Ice =  np.array([]),
        time_step = 0.0
    )

    for d in data:
        keys = list(d.raw_data.keys())
        curves.time_step = d.time_step
        for k in keys:
            if k == 'Vge':
                curves.Vge = np.array(d.raw_data[k])[start_index:end_index]
            elif k == 'Vce':
                curves.Vce = np.array(d.raw_data[k])[start_index:end_index]
            elif k == 'Ice':
                curves.Ice = np.array(d.raw_data[k])[start_index:end_index]

    return curves

def signal_rise_fall(signal: np.ndarray, time_step: float, low_point: float = 0.1) -> RiseFallResult:
    max_zone = 50
    rise_mode = signal[0] < signal[-1]
    if rise_mode:
        s_amp: float = np.mean(signal[-max_zone:])
    else:
        s_amp: float = np.mean(signal[:max_zone])
    s_max = np.max(signal)

    t_min = t_max = None
    base_value = s_amp if rise_mode else s_max

    for i in range(len(signal)):
        idx = i if rise_mode else len(signal) - 1 - i
        if t_min is None and signal[idx] >= base_value * low_point:
            t_min = idx
        if t_max is None and signal[idx] >= base_value * 0.9:
            t_max = idx
        if t_min is not None and t_max is not None:
            break

    if t_min is None or t_max is None:
        t_min = t_max = 0

    t_rf = abs(t_max - t_min) * time_step * 1e9  # ns
    s_rf = abs((signal[t_max] - signal[t_min]) / (t_rf if t_rf != 0 else 1)) * 1e3  # per us

    return RiseFallResult(
        S_max=s_max,
        S_amp=s_amp,
        S_rf=s_rf,
        t_rf=t_rf,
        t_min=t_min,
        t_max=t_max
    )

def vi_rise_fall(curves: Curves, is_diode: bool) -> Dict[str, RiseFallResult]:
    vce = -curves.Vce if is_diode else curves.Vce
    v_points = signal_rise_fall(vce, curves.time_step)
    i_points = signal_rise_fall(curves.Ice, curves.time_step)

    return {"V_points": v_points, "I_points": i_points}

def calc_delay(curves: Curves) -> float:
    vge_pivot = signal_rise_fall(curves.Vge, curves.time_step)
    ice_pivot = signal_rise_fall(curves.Ice, curves.time_step)

    on_mode = curves.Vce[0] > curves.Vce[-1]
    delay = (ice_pivot.t_min - vge_pivot.t_min) if on_mode else (ice_pivot.t_max - vge_pivot.t_max)

    return delay * curves.time_step * 1e9  # ns

def integrate(data: np.ndarray, time_step: float, start_index: int, end_index: int) -> float:
    if end_index < start_index:
        return 0.0

    result = np.sum(data[start_index:end_index+1])
    result -= 0.5 * (data[start_index] + data[end_index])

    return result * time_step

def find_aux_point(data: np.ndarray, start_index: int, threshold: float):
    x = y = None
    for i in range(start_index, len(data)):
        if data[i] <= threshold:
            x = i
            y = data[i]
            break

    return {"X": x, "Y": y}

def recovery_get_xy(data: np.ndarray, magic_a=20, magic_b=12, magic_c=2):
    max_point_idx = np.argmax(data)
    fraction = round((len(data) - max_point_idx) / magic_a)

    start_index = max_point_idx + fraction * magic_b
    end_index = len(data) - fraction * magic_c

    if start_index >= len(data) or end_index >= len(data):
        start_index = min(start_index, len(data)-1)
        end_index = min(end_index, len(data)-1)

    k = (data[start_index] - data[end_index]) / (start_index - end_index)
    b = data[start_index] - k * start_index

    return {"k": k, "b": b}

def recovery(curves: Curves, is_diode: bool):
    current = curves.Ice
    voltage = -curves.Vce if is_diode else curves.Vce
    time_step = curves.time_step

    line_i = recovery_get_xy(current)
    i_point_min = np.argmin(current)
    i_point_max = np.argmax(current)

    ir0 = tr0 = None
    for i in range(i_point_min, i_point_max):
        if current[i] > (i * line_i["k"] + line_i["b"]):
            ir0 = current[i]
            tr0 = i
            break
    if tr0 is None:
        tr0 = i_point_min

    current_trim = []
    current_cut = []
    for i in range(tr0, len(current)):
        current_trim.append(current[i] - (i * line_i["k"] + line_i["b"]))
        current_cut.append(current[i])
    current_trim = np.array(current_trim)

    irrm_idx = np.argmax(current_trim)
    irrm = current_trim[irrm_idx]

    aux_090 = find_aux_point(current_trim, irrm_idx, irrm * 0.9)
    aux_025 = find_aux_point(current_trim, irrm_idx, irrm * 0.25)
    aux_002 = find_aux_point(current_trim, irrm_idx, irrm * 0.02)

    k_r = (aux_090["Y"] - aux_025["Y"]) / (aux_090["X"] - aux_025["X"]) if (aux_090["X"] != aux_025["X"]) else 1e-9
    b_r = aux_090["Y"] - k_r * aux_090["X"]

    trr_index = int(round(-b_r / k_r))
    if trr_index >= len(current_trim):
        trr_index = len(current_trim) - 1
    trr = -b_r / k_r * time_step * 1e9
    qrr = integrate(current_trim, time_step, 0, trr_index - 1) * 1e6

    trr2 = (trr_index - irrm_idx) * time_step * 1e9
    trr1 = trr - trr2

    power = []
    max_voltage = np.max(voltage)
    for i in range(tr0, tr0 + (aux_002["X"] or 0)):
        volt = voltage[i] if is_diode else (max_voltage - voltage[i])
        curr = current[i] - (i * line_i["k"] + line_i["b"])
        power.append(volt * curr)
    power = np.array(power)
    energy = integrate(power, time_step, 0, len(power) - 1) * 1e3

    return {
        "trr": trr,
        "trr1": trr1,
        "trr2": trr2,
        "Irrm": irrm,
        "Qrr": qrr,
        "Energy": energy
    }

def calc_energy(curves: Curves):
    _vge = curves.Vge
    _vce = curves.Vce
    _ice = curves.Ice
    time_step = curves.time_step

    if len(_vce) != len(_ice):
        raise ValueError("Energy calc: arrays of different lengths.")

    on_mode = _vce[0] > _vce[-1]

    vce_pivot = signal_rise_fall(_vce, time_step, 0.02)
    ice_pivot = signal_rise_fall(_ice, time_step, 0.02)

    start_time = 0
    if len(_vge) != 0:
        vge_pivot = signal_rise_fall(_vge, time_step)
        start_time = vge_pivot.t_min if on_mode else vge_pivot.t_max
    stop_time = vce_pivot.t_min if on_mode else ice_pivot.t_min

    power = _vce[start_time:stop_time] * _ice[start_time:stop_time]

    if len(_vge) == 0 and len(power) > 0:
        pmax_idx = np.argmax(power)
        initial_shift = np.mean(power[:pmax_idx // 2]) if pmax_idx > 0 else 0
        power = power - initial_shift

    energy = integrate(power, time_step, 0, len(power) - 1) * 1e3 if len(power) > 0 else 0

    return {"Power": power, "Energy": energy}

def is_diode(curves: Curves) -> bool:
    return bool(np.mean(curves.Vce) < 0)

def is_high_element(curves: Curves) -> bool:
    return len(curves.Vge) == 0

def on_mode(curves: Curves) -> bool:
    return curves.Vce[0] > curves.Vce[-1]


