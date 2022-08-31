# Dutch SmartMeter MQTT to DBus
**This project currently only works for Dutch smart meters**

This software takes the Dutch smart meter values on the VenusOS MQTT and translates it to the correct D-Bus values.
It involves the Smartstuff P1 Pro Dongle, which sends the Dutch smart meter values from the P1 port to the VenusOS local MQTT broker.

## Dutch Smart Meter P1 module
This project uses the [Smartstuff P1 Pro Dongle](https://smart-stuff.nl/product/p1-dongel-slimme-meter-esp32/), which contains the ESP32C3.
This module can be configured to send the smart meter data to a MQTT broker. In this case: the Victron GX local MQTT broker.

## Smartstuff P1 Pro Dongle configuration
Sending the smart meter P1 data to the MQTT is quite simple:
1. Get the Smartstuff P1 Pro Dongle **with DSMR-API preinstalled**.
2. Connect via WiFi to this module and place it on the same network as the Victron GX. When on the same network, open the [P1 Dongle Pro configuration page](http://p1-dongle-pro/)
3. Go to Settings. Enter the Victron GX IP at MQTT Broker IP. Set MQTT Top Topic to "SmartMeter/"
4. Enable the MQTT broker on the Victron GX: go to Settings->Services and enable "MQTT on LAN (SSL)". Also enable "MQTT on LAN (Plaintext)"

## Software intallation
To use this software, you need to install kwindrem's [PackageManager](https://github.com/kwindrem/SetupHelper).
If you use the 123\SmartBMS to USB on your Victron GX, then PackageManager was already installed together with the [123\SmartBMS VenusOS](https://123electric.eu/products/123smartbms-to-usb/) software.

From PackageManager, add a new package.
Github username: 123electric
Repository: SmartMeter-DBus
Branch: latest

After activation of this software, the software will get the MQTT values from the Victron GX broker and send it to the DBus.
If you want to use this meter for ESS, go to Settings->ESS->Grid metering and select "External meter".

The Victron remote should now show your smart meter values and if activated, use the values for ESS grid compensation.
