import pyvisa
import numpy as np
import matplotlib.pyplot as plt

from pyvisa.resources.tcpip import TCPIPInstrument

RIGOL_IP = '192.168.128.25'
VISA_ADDRESS = f'TCPIP::{RIGOL_IP}::INSTR'
CHANNEL = 'CHAN1'

rm = pyvisa.ResourceManager('@py')
scope: TCPIPInstrument = rm.open_resource(VISA_ADDRESS)
scope.timeout = 5000

try:
    print(scope.query("*IDN?").strip())
    scope.write(':STOP')

    scope.write(f':WAV:SOUR {CHANNEL}')
    scope.write(':WAV:MODE RAW')
    scope.write(':WAV:FORM BYTE')

    state, _ = scope.query(':WAV:STAT?').split(',')
    print(state)

    data_parts = []

    scope.write(':WAV:STAR 1')
    scope.write(':WAV:STOP 1000')

    data_parts.append(scope.query_binary_values(':WAV:DATA?', datatype='B', container=np.ndarray))

    scope.write(':WAV:STAR 1001')
    scope.write(':WAV:STOP 2000')

    data_parts.append(scope.query_binary_values(':WAV:DATA?', datatype='B', container=np.ndarray))

    raw_data = np.concat(data_parts)

    volt_scale = float(scope.query(f':{CHANNEL}:SCAL?'))
    volt_offset = float(scope.query(f':{CHANNEL}:OFFS?'))
    y_reference = float(scope.query(':WAV:YREF?'))
    y_origin = float(scope.query(':WAV:YOR?'))
    y_increment = float(scope.query(':WAV:YINC?'))
    print(f"volt_scale: {volt_scale}\nvolt_offset: {volt_offset}\ny: {y_reference}")

    time_scale = float(scope.query(':TIM:SCAL?'))
    time_offset = float(scope.query(':TIM:OFFS?'))
    sample_rate = float(scope.query(':ACQ:SRAT?'))
    print(f"time_scale: {time_scale}\ntime_offset: {time_offset}\nsample_rate: {sample_rate}")

    scope.write(':RUN')

    voltages = (raw_data - y_reference - y_origin) * y_increment

    num_points = len(voltages)
    duration = num_points / sample_rate
    time_axis = np.linspace(0, duration, num_points)

    plt.figure(figsize=(12, 6))
    plt.plot(time_axis, voltages)
    plt.xlabel('t')
    plt.ylabel('U')
    plt.grid(True)
    plt.show()

except pyvisa.errors.VisaIOError as e:
    print(f"Exception: {e}")
finally:
    if 'scope' in locals():
        scope.close()
    print("Connection closed")
