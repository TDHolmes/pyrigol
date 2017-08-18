# /usr/local/env python3
# -*- coding: utf-8 -*-
"""
Adapted from: http://juluribk.com/2015/05/08/controlling-rigol-dp832-with-python/
Uses Pyvisa for communication
"""
import visa
import numpy
import time


class BaseVisaDevice:
    def __init__(self):
        try:
            self.rm = visa.ResourceManager()
            instrument_list = self.rm.list_resources()
            self.usb_devices = []
            for dev in instrument_list:
                if "USB" in dev:
                    self.usb_devices.append(dev)
        except visa.VisaIOError:
            print("Pyvisa is not able to find the connections")

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.close_instrument()

    def write(self, message):
        self.device.write(message)
        time.sleep(0.1)
        error = self.device.ask('SYST:ERR?')
        if error[0]:
            print('`{}` recieved. No error occured'.format(message))
            return 0
        else:
            print('`{}` recieved. An Error occured: {}'.format(message, error))
            return error[0]

    def reset(self):
        """ resets the instrument, registers, & buffers. """
        self.write("*RST")
        time.sleep(0.2)

    def close_instrument(self):
        self.device.close()


class RigolDP832(BaseVisaDevice):
    def __init__(self):
        super().__init__()
        success = False
        for dev in self.usb_devices:
            if "DP8" in dev:
                success = True
                self.device = self.rm.open_resource(dev)
                self.device_name = dev
                print("Connected device! {} as {}".format(dev, self.device))
                break
        if success is False:
            raise RuntimeError("Failed to find a DP832!")

    def turn_off(self, channel):
        if channel <= 0 or channel > 3:
            raise RuntimeError("Invalid channel!")
        self.write(':OUTP CH{},OFF'.format(channel))

    def turn_on(self, channel):
        if channel <= 0 or channel > 3:
            raise RuntimeError("Invalid channel!")
        self.write(':OUTP CH{},ON'.format(channel))

    def measure_voltage(self, channel, dc=False):
        dc_command = ":DC"
        cmd = ":MEAS:VOLT{}? CH{}".format(dc_command if dc else "", channel)
        return self.device.query_ascii_values(cmd, container=numpy.array)[0]

    def measure_current(self, channel, dc=False):
        dc_command = ":DC"
        cmd = ":MEAS:CURR{}? CH{}".format(dc_command if dc else "", channel)
        return self.device.query_ascii_values(cmd, container=numpy.array)[0]

    def measure_power(self, channel, dc=False):
        dc_command = ":DC"
        cmd = ":MEAS:ALL{}? CH{}".format(dc_command if dc else "", channel)
        return self.device.query_ascii_values(cmd, container=numpy.array)[0]


class Rigol1054Z(BaseVisaDevice):
    DIVS_VERTICAL = 8
    DIVS_HORIZONTAL = 12

    def __init__(self):
        super().__init__()
        success = False
        for dev in self.usb_devices:
            if "DS1Z" in dev:
                self.device = self.rm.open_resource(dev)
                self.device_name = dev
                print("Connected device! {} as {}".format(dev, self.device))
                success = True
                break
        if success is False:
            raise RuntimeError("Failed to find a DS1054Z!")

    def turn_on(self, channel):
        if channel <= 0 or channel > 4:
            raise RuntimeError("Invalid channel!")
        self.write(':CHAN{}:DISP ON'.format(channel))

    def turn_off(self, channel):
        if channel <= 0 or channel > 4:
            raise RuntimeError("Invalid channel!")
        self.write(':CHAN{}:DISP OFF'.format(channel))

    def channel_scale_set(self, channel, scale_factor):
        """ Sets channel scale in volts. """
        self.write(':CHAN{}:SCAL {}'.format(channel, scale_factor))

    def channel_scale_get(self, channel):
        """ Gets channel scale in volts. """
        return self.device.query_ascii_values(':CHAN{}:SCAL?'.format(channel))[0]

    def channel_offset_set(self, channel, offset):
        """ Sets channel offset in volts. """
        self.write(':CHAN{}:OFFS {}'.format(channel, offset))

    def channel_offset_get(self, channel):
        """ Gets channel offset in volts. """
        # return self.device.query_ascii_values(':CHAN{}:OFFS?'.format(channel))[0]
        return self.device.query_ascii_values(":WAV:YOR?")[0]

    def timescale(self, timescale):
        """ Sets the scope's timescale in seconds. """
        self.write(':TIM:SCAL {}'.format(timescale))

    def trigger_offset(self, time_offset):
        """ Sets the time offset in seconds. """
        self.write(':TIM:OFFS {}'.format(time_offset))

    def capture_start(self):
        self.write(":START")

    def capture_stop(self):
        self.write(":STOP")

    def trigger_edge_config(self, channel, level, trig_type="single", coupling="DC", slope="falling"):
        type_lookup = {"single": "SING"}
        slope_lookup = {"falling": "NEG", "rising": "POS"}
        coupling = coupling.strip().upper()
        if coupling != "DC" and coupling != "AC":
            raise RuntimeError("Invalid coupling type!")
        slope = slope_lookup[slope.strip().lower()]
        trig_type = type_lookup[trig_type.strip().lower()]
        self.write(':TRIG:EDGE:SOUR CHAN{}'.format(channel))
        self.write(':TRIG:EDGE:SWE {}'.format(trig_type))
        self.write(':TRIG:EDGE:COUP {}'.format(coupling))
        self.write(':TRIG:EDGE:SLOP {}'.format(slope))
        self.write(':TRIG:EDGE:LEV {.5f}'.format(float(level)))

    def get_samples(self, channel):
        def conv_string(string):
            if len(string.strip()) != 0:
                if string[0] == "#":
                    string = string[11:]
                # fix some common issues I've seen
                string.replace("ee", "e")
                try:
                    data = float(string)
                    return data
                except:
                    pass
            print("WARNING: Dropped packet!")
            return None

        self.write(":WAV:FORM ASCII")
        self.device.write(":WAV:POIN:MODE RAW")
        data = self.device.query_ascii_values(":WAV:DATA? CHAN1", converter=conv_string)
        return data

    def samplerate_get(self):
        return self.device.query_ascii_values(':ACQ:SAMP?')[0]


"""
# Grab the raw data from channel 1
scope.write(":STOP")

# Get the timescale
timescale = scope.ask_for_values(":TIM:SCAL?")[0]

# Get the timescale offset
timeoffset = scope.ask_for_values(":TIM:OFFS?")[0]
voltscale = scope.ask_for_values(':CHAN1:SCAL?')[0]

# And the voltage offset
voltoffset = scope.ask_for_values(":CHAN1:OFFS?")[0]

scope.write(":WAV:POIN:MODE RAW")
rawdata = scope.ask(":WAV:DATA? CHAN1")[10:]
data_size = len(rawdata)
sample_rate = scope.ask_for_values(':ACQ:SAMP?')[0]
print 'Data size:', data_size, "Sample rate:", sample_rate

scope.write(":KEY:FORCE")
"""


if __name__ == "__main__":
    # with RigolDP832() as r:
    #     while True:
    #         v = r.measure_voltage(channel=3)
    #         i = r.measure_current(channel=3)
    #         p = v * i
    #         print("V: {:.4f}\tI: {:.4f}\tP: {:.4f}\t".format(v, i, p))

    with Rigol1054Z() as r:
        # r.capture_start()
        # time.sleep(5)
        r.capture_stop()
        vals = r.get_samples(1)
        for v in vals:
            print(v)
