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

        g_scope.write(':WAV:STAR 1')
        g_scope.write(f':WAV:STOP {max_points}')

        g_scope.write(':WAV:RES')
        g_scope.write(':WAV:BEG')

        chunks = []

        state, points = g_scope.query(':WAV:STAT?').split(',')
        print(f"Started... State = {state}, Points = {points}")

        while state == 'READ':
            g_scope.write(':WAV:DATA?')

            #chunks.append(list(g_scope.read_raw()[11:]))
            print(g_scope.read_raw())

            state, points  = g_scope.query(':WAV:STAT?').split(',')
            print(f"Reading... State = {state}, Points = {points}")


        g_scope.write(':WAV:DATA?')
        #chunks.append(list(g_scope.read_raw()[11:]))
        print(g_scope.read_raw())

        g_scope.write(':WAV:END')

        data = np.concat(chunks)
        print(data)

        g_scope.write(':RUN')

        plt.plot(data)
        plt.grid()
        plt.show()



    except pyvisa.errors.VisaIOError as e:
        print(f"Exception: {e}")

