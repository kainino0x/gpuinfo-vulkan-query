#!/usr/bin/python3
# Format this file with python3 -m autopep8 -i query.py

from collections import defaultdict, namedtuple, OrderedDict
import glob
import json
import time
import re
import sys
import xml.etree.ElementTree as ET


class dotdict(dict):
    '''dot.notation access to dictionary attributes'''
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def load_vk_enums():
    '''Load useful enums from vk.xml'''
    tree = ET.parse('vk.xml')
    root = tree.getroot()
    vk = dotdict()
    vk.Format = dotdict()
    for e in root.findall("./enums[@name='VkFormat']/*"):
        name = e.attrib['name'][len('VK_FORMAT_'):]
        vk.Format[name] = int(e.attrib['value'])
    vk.FormatFeature = dotdict()
    for e in root.findall("./enums[@name='VkFormatFeatureFlagBits']/*"):
        name = e.attrib['name'][len('VK_FORMAT_FEATURE_'):-len('_BIT')]
        vk.FormatFeature[name] = 1 << int(e.attrib['bitpos'])
    vk.SampleCount = dotdict()
    for e in root.findall("./enums[@name='VkSampleCountFlagBits']/*"):
        # keep the leading underscore
        name = e.attrib['name'][len('VK_SAMPLE_COUNT'):-len('_BIT')]
        vk.SampleCount[name] = 1 << int(e.attrib['bitpos'])
    return vk


Rq = namedtuple('Rq', ['name', 'passes', 'passed_reports', 'failed_reports'])


def run(requirements):
    def extractFormatsMap(report):
        m = dotdict()
        for fmt in report['formats']:
            m[fmt[0]] = fmt[1]
        return m

    deviceName_values = set()
    supported_deviceName_values = set()
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

        info = dotdict()
        info.report = report
        info.fmts = extractFormatsMap(report)
        info.features = set([k for (k, v) in report['features'].items() if v])
        if 'core11' in report and 'features' in report['core11']:
            for k, v in report['core11']['features'].items():
                if v:
                    info.features.add(k)
        if 'core12' in report and 'features' in report['core12']:
            for k, v in report['core12']['features'].items():
                if v:
                    info.features.add(k)
        if 'extended' in report and 'devicefeatures2' in report['extended']:
            for v in report['extended']['devicefeatures2']:
                if v['supported']:
                    info.features.add(v['name'])
        info.limits = report['properties']['limits']

        # +  ' ' + report['properties']['driverVersionText']
        deviceName = report['properties']['deviceName']
        deviceName = re.sub(r' \((LLVM|ACO|Subzero).*?\)', '', deviceName)
        deviceName_values.add(deviceName)

        unsupported_because = None
        for rq in requirements:
            if rq.passes(info):
                rq.passed_reports[deviceName].append(report_id)
            else:
                rq.failed_reports[deviceName].append(report_id)
                unsupported_because = rq.name
                break

        if not unsupported_because:
            supported_deviceName_values.add(deviceName)

        # if unsupported_because:
        #    print('{}: "{}" failed "{}"'.format(
        #        report_id, deviceName, unsupported_because))

    result = 'Beginning with {} unique deviceNames in {} reports.\n\n'.format(
        len(deviceName_values), len(reports_filenames))
    for rq in requirements:
        failed_reports_sorted = OrderedDict(sorted(rq.failed_reports.items()))

        result_list_all = []
        result_list_some = []
        if len(failed_reports_sorted):
            for name, ids in failed_reports_sorted.items():
                passed_reports = rq.passed_reports[name]
                if len(passed_reports) == 0:
                    result_list_all.append('    x {}: {} ({})\n'.format(
                        name, len(ids), ' '.join(map(str, ids))))

            for name, ids in failed_reports_sorted.items():
                passed_reports = rq.passed_reports[name]
                if len(passed_reports) != 0:
                    result_list_some.append('    ~ {}: {} of {} ({}; ok: {})\n'.format(
                        name, len(ids), len(ids) + len(passed_reports),
                        ' '.join(map(str, ids)),
                        ' '.join(map(str, passed_reports))))

            result += 'Requirement "{}" loses {} (and partially loses {}) further deviceNames:\n'.format(
                rq.name, len(result_list_all), len(result_list_some))
            result += '  In ALL reports ({} deviceNames):\n{}'.format(
                len(result_list_all), ''.join(result_list_all))
            result += '  In SOME reports ({} deviceNames):\n{}'.format(
                len(result_list_some), ''.join(result_list_some))
        else:
            result += 'Requirement "{}" loses no further reports!\n'.format(rq.name)

    result += ('At least one of each of the following was still supported:\n  + ' +
               '\n  + '.join(sorted(supported_deviceName_values)))

    print()
    print(result)

    result_filename = 'result-{}.txt'.format(time.strftime("%Y%m%d-%H%M%S"))
    print('Result saved to {}'.format(result_filename))
    with open(result_filename, 'w') as f:
        f.write(result)


def format_supported_with_optimal_tiling_features(formats_map, format, flags):
    return format in formats_map and (formats_map[format]['optimalTilingFeatures'] & flags) == flags


if __name__ == '__main__':
    vk = load_vk_enums()
    requirements = []

    def add_rq(name, passes):
        requirements.append(Rq(name, passes, defaultdict(
            lambda: []), defaultdict(lambda: [])))

    def add_min_limit(name, value):
        add_rq('{} >= {}'.format(name, value),
               lambda info: info.limits[name] >= value)

    def add_max_limit(name, value):
        add_rq('{} <= {}'.format(name, value),
               lambda info: int(info.limits[name], 0) <= value)

    def add_bits_limit(name, bits):
        add_rq('{} has bits 0b{:b}'.format(name, bits),
               lambda info: (info.limits[name] & bits) == bits)

    # Known requirements

    add_rq('robustBufferAccess',
           lambda info: 'robustBufferAccess' in info.features)

    add_rq('maxImageDimension2D and related limits >= 8192',
           lambda info: min(
               info.limits['maxImageDimension2D'],
               info.limits['maxImageDimensionCube'],
               info.limits['maxFramebufferWidth'],
               info.limits['maxFramebufferHeight'],
               info.limits['maxViewportDimensions'][0],
               info.limits['maxViewportDimensions'][1],
               info.limits['viewportBoundsRange'][1],
           ) >= 8192)
    add_min_limit('maxImageDimension1D', 8192)
    add_min_limit('maxImageDimension3D', 2048)
    add_min_limit('maxImageArrayLayers', 256)

    add_min_limit('maxBoundDescriptorSets', 4)
    add_min_limit('maxDescriptorSetUniformBuffersDynamic', 8)
    add_min_limit('maxDescriptorSetStorageBuffersDynamic', 4)
    add_min_limit('maxPerStageDescriptorSampledImages', 16)
    add_min_limit('maxPerStageDescriptorSamplers', 16)
    add_min_limit('maxPerStageDescriptorStorageBuffers', 8)
    add_min_limit('maxPerStageDescriptorStorageImages', 4)
    add_min_limit('maxPerStageDescriptorUniformBuffers', 12)

    add_min_limit('maxUniformBufferRange', 65536)
    add_min_limit('maxStorageBufferRange', 134217728)

    add_max_limit('minUniformBufferOffsetAlignment', 256)
    add_max_limit('minStorageBufferOffsetAlignment', 256)

    add_min_limit('maxVertexInputBindings', 8)
    add_min_limit('maxVertexInputAttributes', 16)
    add_min_limit('maxVertexInputBindingStride', 2048)
    add_min_limit('maxVertexInputAttributeOffset', 2047)

    add_min_limit('maxVertexOutputComponents', 60)
    add_min_limit('maxFragmentInputComponents', 60)
    add_min_limit('maxComputeSharedMemorySize', 16384)
    add_min_limit('maxComputeWorkGroupInvocations', 256)
    add_rq('maxComputeWorkGroupSize >= [256,256,64]',
           lambda info:
           info.limits['maxComputeWorkGroupSize'][0] >= 256 and
           info.limits['maxComputeWorkGroupSize'][1] >= 256 and
           info.limits['maxComputeWorkGroupSize'][2] >= 64)
    add_rq('maxComputeWorkGroupCount >= [65535,65535,65535]',
           lambda info:
           info.limits['maxComputeWorkGroupCount'][0] >= 65535 and
           info.limits['maxComputeWorkGroupCount'][1] >= 65535 and
           info.limits['maxComputeWorkGroupCount'][2] >= 65535)

    add_min_limit('maxColorAttachments', 8)

    add_bits_limit('framebufferColorSampleCounts',
                   vk.SampleCount._1 | vk.SampleCount._4)
    add_bits_limit('framebufferDepthSampleCounts',
                   vk.SampleCount._1 | vk.SampleCount._4)

    add_rq('maxFragmentCombinedOutputResources >= 8+4+8, OR is intel/nvidia/amd',
           lambda info: info.limits['maxFragmentCombinedOutputResources'] >= 8 + 4 + 8 or
           info.report['properties']['vendorID'] in [0x8086, 0x10de, 0x1002])

    add_rq('fragmentStoresAndAtomics',
           lambda info: 'fragmentStoresAndAtomics' in info.features)
    add_rq('fullDrawIndexUint32',
           lambda info: 'fullDrawIndexUint32' in info.features)
    add_rq('depthBiasClamp', lambda info: 'depthBiasClamp' in info.features)
    add_rq('imageCubeArray', lambda info: 'imageCubeArray' in info.features)
    add_rq('independentBlend',
           lambda info: 'independentBlend' in info.features)
    add_rq('sampleRateShading',
           lambda info: 'sampleRateShading' in info.features)

    add_rq('has BC || (ETC2 && ASTC LDR 2D)',
           lambda info: 'textureCompressionBC' in info.features or
           ('textureCompressionETC2' in info.features and 'textureCompressionASTC_LDR' in info.features))

    add_rq('Vulkan 1.1 or "VK_KHR_maintenance1" or "VK_AMD_negative_viewport_height" for viewport Y-flip',
           lambda info: info.report['properties']['apiVersionText'].startswith('1.1') or
           any(map(lambda e:
                   e['extensionName'] == 'VK_KHR_maintenance1' or
                   e['extensionName'] == 'VK_AMD_negative_viewport_height',
                   info.report['extensions'])))

    add_rq('timestampValidBits != 0',
           lambda info: True in (queue['timestampValidBits'] != 0 for queue in info.report['queues']))

    # Texture formats

    ds_required_flags = vk.FormatFeature.SAMPLED_IMAGE | vk.FormatFeature.DEPTH_STENCIL_ATTACHMENT
    add_rq('depth16unorm', lambda info: format_supported_with_optimal_tiling_features(
        info.fmts, vk.Format.D16_UNORM, ds_required_flags))
    add_rq('depth32float', lambda info: format_supported_with_optimal_tiling_features(
        info.fmts, vk.Format.D32_SFLOAT, ds_required_flags))

    def depth24plus(info):
        return (format_supported_with_optimal_tiling_features(info.fmts, vk.Format.X8_D24_UNORM, ds_required_flags) or
                format_supported_with_optimal_tiling_features(info.fmts, vk.Format.D32_SFLOAT, ds_required_flags))
    add_rq('depth24plus', depth24plus)

    def depth24plus_stencil8(info):
        return (format_supported_with_optimal_tiling_features(info.fmts, vk.Format.D24_UNORM_S8_UINT, ds_required_flags) or
                format_supported_with_optimal_tiling_features(info.fmts, vk.Format.D32_SFLOAT_S8_UINT, ds_required_flags))
    add_rq('depth24plus-stencil8', depth24plus_stencil8)

    def any_s8(info):
        return (format_supported_with_optimal_tiling_features(info.fmts, vk.Format.D24_UNORM_S8_UINT, ds_required_flags) or
                format_supported_with_optimal_tiling_features(info.fmts, vk.Format.D16_UNORM_S8_UINT, ds_required_flags) or
                format_supported_with_optimal_tiling_features(info.fmts, vk.Format.D32_SFLOAT_S8_UINT, ds_required_flags) or
                format_supported_with_optimal_tiling_features(info.fmts, vk.Format.S8_UINT, ds_required_flags))
    add_rq('stencil8 any format', any_s8)

    def d24s8_or_s8(info):
        return (format_supported_with_optimal_tiling_features(info.fmts, vk.Format.D24_UNORM_S8_UINT, ds_required_flags) or
                format_supported_with_optimal_tiling_features(info.fmts, vk.Format.S8_UINT, ds_required_flags))
    add_rq('stencil8 <= 4 bytes', d24s8_or_s8)

    # Additional requirements?

    run(requirements)
