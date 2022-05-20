#!/usr/bin/python3
# Format this file with python3 -m autopep8 -i query.py

from collections import defaultdict, namedtuple, OrderedDict
import glob
import json
import time
import re
import sys
import getopt

class Architecture:
    def __init__(self, name, devices, mask):
        self.name = name
        self.mask = mask
        self.deviceIds = []
        for device in devices:
            self.deviceIds.append(int(device, 0))

    def matchDeviceId(self, testId):
        for deviceId in self.deviceIds:
            if testId & self.mask == deviceId:
                return True

        return False

class Device:
    def __init__(self, deviceId, name):
        self.deviceId = deviceId;
        self.names = { name }
        self.count = 1

    def addName(self, name):
        self.names.add(name)
        self.count += 1

class Vendor:
    def __init__(self, vendorId):
        self.vendorId = vendorId;
        self.name = ''
        self.devices = {}
        self.architectures = {}

    def addDevice(self, deviceId, deviceName):
        if deviceId in self.devices:
            self.devices[deviceId].addName(deviceName)
        else:
            self.devices[deviceId] = Device(deviceId, deviceName)

    def addArchitecture(self, architecture):
        self.architectures[architecture.name] = architecture

def collectDevices(vendors):
    reports_filenames = glob.glob('data/reports/*.json')
    reports_entries = sorted(map(lambda f: (
        int(f[len('data/reports/'):-len('.json')]), f), reports_filenames))

    for report_id, filename in reports_entries:
        report = None
        with open(filename) as f:
            try:
                report = json.load(f)
            except KeyboardInterrupt:
                sys.exit(1)
            except:
                print('error parsing {}'.format(filename))
                continue

        properties = report['properties']

        vendorId = 0
        if 'vendorID' in properties:
            vendorId = properties['vendorID']

        deviceId = 0
        if 'deviceID' in properties:
            deviceId = properties['deviceID']

        deviceName = '[unknown]'
        if 'deviceName' in properties:
            deviceName = properties['deviceName']

        if not vendorId in vendors:
            vendors[vendorId] = Vendor(vendorId)

        vendors[vendorId].addDevice(deviceId, deviceName)

def collectGpuInfo(vendors, gpuInfoPath):
    gpuInfoJson = None
    with open(gpuInfoPath) as f:
        try:
            gpuInfoJson = json.load(f)
        except KeyboardInterrupt:
            sys.exit(1)
        except:
            print('error parsing {}'.format(gpuInfoPath))

        for vendorName, vendorJson in gpuInfoJson['vendors'].items():
            id = int(vendorJson['id'], 0)

            if not id in vendors:
                vendors[id] = Vendor(id)

            vendor = vendors[id]
            vendor.name = vendorName

            deviceMask = 0xFFFF
            if 'deviceMask' in vendorJson:
                deviceMask = int(vendorJson['deviceMask'] , 0)

            if 'architecture' in vendorJson:
                archJson = vendorJson['architecture']
                for archName, archDevices in archJson.items():
                    if archName[0] == '_':
                        continue

                    vendor.addArchitecture(Architecture(archName, archDevices, deviceMask))


if __name__ == '__main__':
    vendors = {}
    useGpuInfo = False

    if (len(sys.argv) > 1):
        collectGpuInfo(vendors, sys.argv[1])
        useGpuInfo = True

    collectDevices(vendors)

    filteredEntries = 0
    totalEntries = 0

    filteredDevices = 0
    totalDevices = 0

    if useGpuInfo:
        print('\n\=== The following devices have a corresponding entry in GPUInfo ===')

        for (vendorId, vendor) in vendors.items():
            if not vendor.name:
                continue

            print('\n{} VendorId: 0x{:04x}'.format(vendor.name, vendorId))

            for (archName, arch) in vendor.architectures.items():
                archMatches = [deviceId for deviceId in vendor.devices if arch.matchDeviceId(deviceId)]
                archMatches.sort()
                filteredDevices += len(archMatches)

                print(' - {}'.format(archName))

                for deviceId in archMatches:
                    device = vendor.devices[deviceId]
                    filteredEntries += device.count
                    for name in device.names:
                        print('     + DeviceId: 0x{:04x}, {}'.format(deviceId, name))
                    del vendor.devices[deviceId]

        totalDevices += filteredDevices
        totalEntries += filteredEntries
        print('\n\=== The following devices had no corresponding entry in GPUInfo ===')

    for (vendorId, vendor) in vendors.items():
        if len(vendor.devices):
            print('\n{} VendorId: 0x{:04x}, {} Devices'.format(vendor.name, vendorId, len(vendor.devices)))

            totalDevices += len(vendor.devices)

            for (deviceId, device) in vendor.devices.items():
                totalEntries += device.count
                print(' - DeviceId: 0x{:04x}, {} Entries'.format(deviceId, device.count))

                for name in device.names:
                    print('  {}'.format(name))

    print('\n{} entries, {} unique devices, {} vendors'.format(totalEntries, totalDevices, len(vendors)))
    if useGpuInfo:
        print('{} entries categorized ({:.2f}%)'.format(filteredEntries, (filteredEntries/totalEntries) * 100))
        print('{} devices categorized ({:.2f}%)'.format(filteredDevices, (filteredDevices/totalDevices) * 100))
