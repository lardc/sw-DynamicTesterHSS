import pyvisa
import numpy as np
import matplotlib.pyplot as plt
import time

from pyvisa.resources.tcpip import TCPIPInstrument

RIGOL_IP = '192.168.128.25'
VISA_ADDRESS = f'TCPIP::{RIGOL_IP}::INSTR'
CHANNEL = 'CHAN1'

rm = pyvisa.ResourceManager('@py')
g_scope: TCPIPInstrument = rm.open_resource(VISA_ADDRESS)
g_scope.timeout = 5000

if __name__ == '__main__':
    try:
        print(g_scope.query('*IDN?'))

        g_scope.write(':STOP')
        time.sleep(1.0)

        g_scope.write(':WAV:SOUR:CHAN1')
        g_scope.write(':WAV:MODE RAW')
        g_scope.write(':WAV:FORM BYTE')

        max_points = int(g_scope.query(':ACQ:MDEP?'))
        print(max_points)

        chunks = []

        step = 125000
        i = 0

        while i * step + step <= max_points:
            start = i * step + 1
            stop = i * step + step

            g_scope.write(f'WAV:STAR {start}')
            g_scope.write(f'WAV:STOP {stop}')
            g_scope.write('WAV:DATA?')

            print(g_scope.read_raw())
            print(f'Reading... {stop * 100 / max_points}%')

            i += 1

        data = np.concat(chunks)
        print(data)

        g_scope.write(':RUN')

        plt.plot(data)
        plt.grid()
        plt.show()

    except pyvisa.errors.VisaIOError as e:
        print(f"Exception: {e}")

