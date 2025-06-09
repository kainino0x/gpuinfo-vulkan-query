#!/usr/bin/python3
# Format this file with python3 -m autopep8 -i query.py

# Gathers devices and groups them by Device ID and Vendor

# Pass the path to Dawn's gpu_info.json file to match devices against the known
# patterns in that file and output devices which don't have a match. Useful for
# updating the architecture mappings as described in
# https://dawn.googlesource.com/dawn/+/refs/heads/main/src/dawn/updating_gpu_info.md

from collections import defaultdict, namedtuple, OrderedDict
import glob
import json
import time
import re
import sys
import getopt

class DeviceGroup:
    def __init__(self, devices, mask):
        self.mask = mask
        self.deviceIds = []
        for device in devices:
            self.deviceIds.append(int(device, 0))

    def matchDeviceId(self, testId):
        for deviceId in self.deviceIds:
            if testId & self.mask == deviceId:
                return True

        return False

class Architecture:
    def __init__(self, name):
        self.name = name
        self.deviceGroups = []

    def addDeviceGroup(self, devices, mask):
        self.deviceGroups.append(DeviceGroup(devices, mask))

    def matchDeviceId(self, testId):
        for deviceGroup in self.deviceGroups:
            if deviceGroup.matchDeviceId(testId):
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

    def addArchitecture(self, name, devices, mask):
        if name in self.architectures:
            arch = self.architectures[name]
        else:
            arch = Architecture(name)
            self.architectures[name] = arch

        arch.addDeviceGroup(devices, mask)

def collectDevices(vendors):
    reports_filenames = glob.glob('data/reports/*.json')
    reports_entries = sorted(map(lambda f: (
        int(f[len('data/reports/'):-len('.json')]), f), reports_filenames))

    print('Collecting device information from {} records...'.format(len(reports_entries)))

    i = 0;
    for report_id, filename in reports_entries:
        i = i + 1
        if (i % 1000 == 0):
            print('Reading record {} of {} ({:.2f}%)'.format(i, len(reports_entries), (i / len(reports_entries)) * 100), end='\r')

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
            if vendorName[0] == '_':
                continue

            id = int(vendorJson['id'], 0)

            if not id in vendors:
                vendors[id] = Vendor(id)

            vendor = vendors[id]
            vendor.name = vendorName

            if not 'devices' in vendorJson:
                continue;

            for deviceGroup in vendorJson['devices']:
                deviceMask = 0xFFFF
                if 'mask' in deviceGroup:
                    deviceMask = int(deviceGroup['mask'] , 0)

                if 'architecture' in deviceGroup:
                    archJson = deviceGroup['architecture']
                    for archName, archDevices in archJson.items():
                        if archName[0] == '_':
                            continue

                        vendor.addArchitecture(archName, archDevices, deviceMask)


if __name__ == '__main__':
    vendors = {}
    useGpuInfo = False

    opts, args = getopt.getopt(sys.argv[1:], 'a')

    showAll = False
    for o, a in opts:
        if o == "-a":
            showAll = True

    if (len(args) > 0):
        collectGpuInfo(vendors, args[0])
        useGpuInfo = True

    collectDevices(vendors)

    filteredEntries = 0
    totalEntries = 0

    filteredDevices = 0
    totalDevices = 0

    if useGpuInfo:
        print('\n=== The following devices have a corresponding entry in GPUInfo ===')

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
        print('\n=== The following devices had no corresponding entry in GPUInfo ===')

    entriesSkipped = False
    for (vendorId, vendor) in vendors.items():
        # Filter out vendorId of 0x0000 if -a is not specified
        if vendorId == 0 and not showAll:
            entriesSkipped = True
            continue

        # Filter out Apple devices if -a is not specified,
        # because we don't handle them in the GPUInfo JSON
        if vendorId == 0x106b and not showAll:
            entriesSkipped = True
            continue

        if len(vendor.devices):
            print('\n{} VendorId: 0x{:04x}, {} Devices'.format(vendor.name, vendorId, len(vendor.devices)))

            totalDevices += len(vendor.devices)

            for (deviceId, device) in vendor.devices.items():
                # Filter out deviceId of 0x0000 if -a is not specified
                if deviceId == 0 and not showAll:
                    entriesSkipped = True
                    continue

                totalEntries += device.count
                print(' - DeviceId: 0x{:04x}, {} Entries'.format(deviceId, device.count))

                for name in device.names:
                    print('  {}'.format(name))

    print('\n{} entries, {} unique devices, {} vendors'.format(totalEntries, totalDevices, len(vendors)))
    if useGpuInfo:
        print('{} entries categorized ({:.2f}%)'.format(filteredEntries, (filteredEntries/totalEntries) * 100))
        print('{} devices categorized ({:.2f}%)'.format(filteredDevices, (filteredDevices/totalDevices) * 100))
    if entriesSkipped:
        print('Some devices or vendors were skipped due to not being applicable to GPUInfo. To view all devices use the -a command line option')
