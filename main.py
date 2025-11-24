from time import sleep
from datetime import datetime
import numpy as np
from numpy.typing import NDArray
import pyvisa
from pyvisa.resources.tcpip import TCPIPInstrument

RIGOL_IP = '192.168.128.25'
VISA_ADDRESS = f'TCPIP::{RIGOL_IP}::INSTR'
CHANNEL = 'CHAN1'


def get_norm_data(scope: TCPIPInstrument, channel='CHAN1', verbose=False) -> NDArray[np.float32]:
    t: datetime = datetime.now()

    scope.write(f':WAV:SOUR:{channel}')
    scope.write(':WAV:MODE NORM')
    scope.write(':WAV:FORM BYTE')

    data = scope.query_binary_values(':WAV:DATA?', datatype='b')

    if verbose:
        print('t1', datetime.now() - t)

    t = datetime.now()

    np_data: NDArray[np.float32] = np.array(data, dtype=np.float32)

    if verbose:
        print('t2', datetime.now() - t)

    return np_data


def get_raw_data(scope: TCPIPInstrument, channel='CHAN1', verbose=False) -> NDArray[np.float32]:
    t: datetime = datetime.now()

    scope.write(f':WAV:SOUR:{channel}')
    scope.write(':WAV:MODE RAW')
    scope.write(':WAV:FORM BYTE')

    max_points = int(scope.query(':ACQ:MDEP?'))
    if verbose:
        print("Max points: ", max_points)

    scope.write(':WAV:STAR 1')
    scope.write(f':WAV:STOP {max_points}')

    scope.write(':WAV:RES')
    scope.write(':WAV:BEG')

    data = []
    while True:
        state, points = scope.query(':WAV:STAT?').replace('\n', '').split(',')
        if state == 'READ' and int(points) == 0:
            sleep(0.05)
            continue

        if verbose:
            print(f"Processed state = {state}, points = {points}")

        data += scope.query_binary_values(':WAV:DATA?', datatype='b')

        if state == 'IDLE':
            scope.write(':WAV:END')
            break

    if verbose:
        print('t1', datetime.now() - t)

    t = datetime.now()

    np_data: NDArray[np.float32] = np.array(data, dtype=np.float32)

    if verbose:
        print('t2', datetime.now() - t)

    return np_data


if __name__ == '__main__':
    rm = pyvisa.ResourceManager('@py')
    instr_scope: TCPIPInstrument = rm.open_resource(VISA_ADDRESS)
    instr_scope.timeout = 5000

    print(instr_scope.query("*IDN?").strip())
