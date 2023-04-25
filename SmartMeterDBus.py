#!/usr/bin/env python3
import os
from os import _exit as os_exit
import sys
import time
import ssl
from paho.mqtt.client import Client
from collections import deque
from datetime import datetime
from traceback import print_exc
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

# Victron packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
import dbus.service
import ve_utils
from vedbus import VeDbusService

class SmartMeterDBus():
    LAST_RECEIVED_TIMEOUT = 30

    def __init__(self, mqtt_broker, mqtt_username, mqtt_password, mqtt_topic):
        self._info = {
            'name'      : "SmartMeter",
            'servicename' : "smartmeter",
            'id'          : 0,
            'version'    : "1.02"
        }
        self._device_instance = 30

        self._mqtt_topic = mqtt_topic
        self._mqtt_client = Client('SmartMeterDBus')
        self._mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
        self._mqtt_client.tls_insecure_set(True)
        self._mqtt_client.username_pw_set(mqtt_username, password=mqtt_password)
        self._mqtt_client.connect(mqtt_broker, port=8883)
        self._mqtt_client.on_connect = self._mqtt_on_connect
        self._mqtt_client.on_message = self._mqtt_on_message
        self._mqtt_client.loop_start()
        self._meter_data = {}
        self._new_data_received = False
        self._last_received = None

        self._dbusservice = VeDbusService("com.victronenergy.grid.smartmeter")
        
        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', self._info['version'])
        self._dbusservice.add_path('/Mgmt/Connection', '(API)')

        # Create the basic objects
        self._dbusservice.add_path('/DeviceInstance', self._device_instance)
        self._dbusservice.add_path('/ProductId',     self._info['id'])
        self._dbusservice.add_path('/ProductName',     self._info['name'])
        self._dbusservice.add_path('/FirmwareVersion', self._info['version'], self._info['version'], gettextcallback=lambda p, v: "v"+v)
        self._dbusservice.add_path('/HardwareVersion', None)
        self._dbusservice.add_path('/Serial', None)
        self._dbusservice.add_path('/Connected', 1)

        # Create device list
        self._dbusservice.add_path('/Devices/0/DeviceInstance',  self._device_instance)
        self._dbusservice.add_path('/Devices/0/FirmwareVersion', self._info['version'])
        self._dbusservice.add_path('/Devices/0/ProductId',       self._info['id'])
        self._dbusservice.add_path('/Devices/0/ProductName',   self._info['name'])
        self._dbusservice.add_path('/Devices/0/ServiceName',   self._info['servicename'])
        self._dbusservice.add_path('/Devices/0/VregLink',     "(API)")

        # Create the meter paths
        self._dbusservice.add_path('/Ac/Power', None, gettextcallback=lambda p, v: "{:d}W".format(v))
        self._dbusservice.add_path('/Ac/Current', None, gettextcallback=lambda p, v: "{:.2f}A".format(v))
        self._dbusservice.add_path('/Ac/Energy/Forward', None, gettextcallback=lambda p, v: "{:.1f}kWh".format(v))
        self._dbusservice.add_path('/Ac/L1/Power', None, gettextcallback=lambda p, v: "{:d}W".format(v))
        self._dbusservice.add_path('/Ac/L2/Power', None, gettextcallback=lambda p, v: "{:d}W".format(v))
        self._dbusservice.add_path('/Ac/L3/Power', None, gettextcallback=lambda p, v: "{:d}W".format(v))
        self._dbusservice.add_path('/Ac/L1/Voltage', None, gettextcallback=lambda p, v: "{:.1f}V".format(v))
        self._dbusservice.add_path('/Ac/L2/Voltage', None, gettextcallback=lambda p, v: "{:.1f}V".format(v))
        self._dbusservice.add_path('/Ac/L3/Voltage', None, gettextcallback=lambda p, v: "{:.1f}V".format(v))
        self._dbusservice.add_path('/Ac/L1/Current', None, gettextcallback=lambda p, v: "{:.2f}A".format(v))
        self._dbusservice.add_path('/Ac/L2/Current', None, gettextcallback=lambda p, v: "{:.2f}A".format(v))
        self._dbusservice.add_path('/Ac/L3/Current', None, gettextcallback=lambda p, v: "{:.2f}A".format(v))

    def update(self):
        if self._new_data_received and time.time() > self._last_received + 0.01: # After 10ms of no incoming data, process data
            power_l1 = int(self._meter_data['power_returned_l1']*-1000) if round(self._meter_data['power_returned_l1'], 3) > 0.000 else int(self._meter_data['power_delivered_l1']*1000)
            power_l2 = int(self._meter_data['power_returned_l2']*-1000) if round(self._meter_data['power_returned_l2'], 3) > 0.000 else int(self._meter_data['power_delivered_l2']*1000)
            power_l3 = int(self._meter_data['power_returned_l3']*-1000) if round(self._meter_data['power_returned_l3'], 3) > 0.000 else int(self._meter_data['power_delivered_l3']*1000)
            voltage_l1 = self._meter_data['voltage_l1']
            voltage_l2 = self._meter_data['voltage_l2']
            voltage_l3 = self._meter_data['voltage_l3']
            current_l1 = round(power_l1/voltage_l1, 2)
            current_l2 = round(power_l2/voltage_l2, 2)
            current_l3 = round(power_l3/voltage_l3, 2)
            self._dbusservice['/Ac/Power'] = power_l1+power_l2+power_l3
            self._dbusservice['/Ac/Current'] = current_l1+current_l2+current_l3
            self._dbusservice['/Ac/Energy/Forward'] = round(self._meter_data['energy_delivered_tariff1']+self._meter_data['energy_delivered_tariff2'], 2)
            self._dbusservice['/Ac/L1/Power'] = power_l1
            self._dbusservice['/Ac/L2/Power'] = power_l2
            self._dbusservice['/Ac/L3/Power'] = power_l3
            self._dbusservice['/Ac/L1/Voltage'] = self._meter_data['voltage_l1']
            self._dbusservice['/Ac/L2/Voltage'] = self._meter_data['voltage_l2']
            self._dbusservice['/Ac/L3/Voltage'] = self._meter_data['voltage_l3']
            self._dbusservice['/Ac/L1/Current'] = current_l1
            self._dbusservice['/Ac/L2/Current'] = current_l2
            self._dbusservice['/Ac/L3/Current'] = current_l3

            self._new_data_received = False
        elif time.time() > self._last_received + self.LAST_RECEIVED_TIMEOUT:
            self._dbusservice['/Ac/Power'] = None
            self._dbusservice['/Ac/Current'] = None
            self._dbusservice['/Ac/Energy/Forward'] = None
            self._dbusservice['/Ac/L1/Power'] = None
            self._dbusservice['/Ac/L2/Power'] = None
            self._dbusservice['/Ac/L3/Power'] = None
            self._dbusservice['/Ac/L1/Voltage'] = None
            self._dbusservice['/Ac/L2/Voltage'] = None
            self._dbusservice['/Ac/L3/Voltage'] = None
            self._dbusservice['/Ac/L1/Current'] = None
            self._dbusservice['/Ac/L2/Current'] = None
            self._dbusservice['/Ac/L3/Current'] = None


    def close(self):
        self._mqtt_client.loop_stop()

    def _mqtt_on_message(self, client, userdata, message):
        self._last_received = time.time()
        self._new_data_received = True
        # Get sub topic from whole topic path
        topic = message.topic[len(self._mqtt_topic)+1:]
        try:
            # If value contains point, then try to convert to float. Otherwise to integer. If conversions fails, convert to string
            if '.' in str(message.payload):
                val = float(message.payload)
            else:
                val = int(message.payload)
        except ValueError:
            val = str(message.payload)
        self._meter_data[topic] = val
 
    def _mqtt_on_connect(self, client, userdata, rc, *args): 
        print('Succesfully connected to MQTT broker')
        client.subscribe(self._mqtt_topic + "/#")
 
def exit_on_error(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except:
        try:
            print ('exit_on_error: there was an exception. Printing stacktrace will be tried and then exit')
            print_exc()
        except:
            pass
        # sys.exit() is not used, since that throws an exception, which does not lead to a program
        # halt when used in a dbus callback, see connection.py in the Python/Dbus libraries, line 230.
        smartmeter_dbus.close()
        os_exit(1)

# Called on a one second timer
def handle_timer_tick():
    smartmeter_dbus.update()
    return True  # keep timer running

if __name__ == "__main__":  
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    print('SmartMeter to DBus started')
    DBusGMainLoop(set_as_default=True)
    mainloop = GLib.MainLoop()
    GLib.timeout_add(10, lambda: exit_on_error(handle_timer_tick))
    smartmeter_dbus = SmartMeterDBus('127.0.0.1', '', '', 'SmartMeter')
    # Give some time to receive MQTT data
    time.sleep(3)
    mainloop.run()
