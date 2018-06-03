#!/usr/bin/env python3

import os
import re
import stat
import json
import pathlib
import tabulate
import subprocess

def run_cmd(*args):
    result = subprocess.run(args = args, stdout = subprocess.PIPE)
    if result.returncode != 0:
        raise Exception(('subprocess returned %d...' % ( result.returncode ), result.stdout.decode('ASCII')))
    return result.stdout.decode('ASCII')

def get_majno(name):
    with open('/proc/devices', 'r') as f:
        for line in [ _.rstrip('\n') for _ in f.readlines() ]:
            m = re.match('^ *(?P<majno>[0-9]+) %s$' % ( name ), line)
            if m is None:
                continue

            return int(m.groupdict()['majno'])

    raise Exception('cannot get major number for %s...' % ( name ))

def get_disk_info(disk):
    in_info_section = False

    info_fields = {
        'Device Model':     { 'name': 'model'          },
        'Serial Number':    { 'name': 'serial'         },
        'Firmware Version': { 'name': 'firmware'       },
        'User Capacity':    { 'name': 'capacity',      'formatter': lambda v: int(re.match('^(?P<capacity>[0-9,]+) bytes \[[0-9\.]+ (G|T|E)B\]$', v).groupdict()['capacity'].replace(',','')) },
        'Sector Sizes':     { 'name': 'sectors',       'formatter': lambda v: { _[1]: int(_[0]) for _ in re.findall('(?:([0-9]+) bytes (logical|physical))', v) } },
        'Rotation Rate':    { 'name': 'spindle_speed', 'formatter': lambda v: int(re.match('^(?P<rpm>[0-9]+) rpm$', v).groupdict()['rpm']) },
        'Form Factor':      { 'name': 'form_factor'    },
        'SATA Version is':  { 'name': 'sata_version',  'formatter': lambda v: re.match('^SATA [0-9\.]+, (?P<rating>[0-9\.]+ (?:G|T)b/s) \(current: (?P<current>[0-9\.]+ (?:G|T)b/s)\)$', v).groupdict() },
        'SMART support is': { 'name': 'smart_enabled', 'formatter': lambda v: True if v == 'Enabled' else False if v == 'Disabled' else None },
    }

    info = {
        'path': disk,
    }

    for line in run_cmd('sudo', 'smartctl', '-i', disk).split('\n'):
        if not in_info_section:
            if line == '=== START OF INFORMATION SECTION ===':
                in_info_section = True
            continue

        m = re.match('^(?P<key>[^:]+): +(?P<value>.*)$', line)
        if m is None:
            continue

        d = m.groupdict()
        key = d['key']
        value = d['value']

        if key not in info_fields:
            continue

        field = info_fields[key]

        if 'formatter' in field:
            value = field['formatter'](value)
            if value is None:
                continue

        if field['name'] in info:
            if type(info[field['name']]) is not list:
                info[field['name']] = [ info[field['name']], value ]
            else:
                info[field['name']].append(value)
        else:
            info[field['name']] = value

    info['smart_attributes'] = get_disk_smart_attrs(disk)

    return info

def get_disk_smart_attrs(disk):
    in_info_section = False

    info_fields = {
        '0x09': { 'raw_value': lambda v: ( 'py_value', int(re.match('^(?P<hrs>[0-9]+)(?: \([0-9]+ [0-9]+ [0-9]+\))?$', v).groupdict()['hrs'])        ) },
        '0xbe': { 'raw_value': lambda v: ( 'py_value', { k: int(v) for k,v in re.match('^(?P<cur>[0-9]+) \(Min/Max (?P<min>[0-9]+)/(?P<max>[0-9]+)\)$', v).groupdict().items() } ) },
        '0xf0': { 'raw_value': lambda v: ( 'py_value', int(re.match('^(?P<hrs>[0-9]+)(?: \([0-9]+ [0-9]+ [0-9]+\))?$', v).groupdict()['hrs'])        ) },
    }

    info = {}
    for line in run_cmd('sudo', 'smartctl', '-A', '-fhex,id', disk).split('\n'):
        if not in_info_section:
            if line == '=== START OF READ SMART DATA SECTION ===':
                in_info_section = True
            continue

        m = re.match(
            '^'
            '(?P<id>0x[0-9a-f]{2}) +'
            '(?P<name>[^ ]+) +'
            '(?P<flag>0x[0-9a-f]{4}) +'
            '(?P<value>[0-9]{1,3}) +'
            '(?P<worst>[0-9]{1,3}) +'
            '(?P<threshold>[0-9]{1,3}) +'
            '(?P<type>(Pre-fail|Old_age)) +'
            '(?P<updated>(Always|Offline)) +'
            '(?P<when_failed>(-|FAILING_NOW|In_the_past)) +'
            '(?P<raw_value>.*)'
            '$',
            line
        )
        if m is None:
            continue

        d = m.groupdict()

        if d['id'] in info_fields:
            for k, v in info_fields[d['id']].items():
                nk, nd = v(d[k])
                d[nk] = nd

        info[d['id']] = d

    return info

def bytes_to_si(n):
    for o, u in [
        ( 1000 ** 5, 'EB' ),
        ( 1000 ** 4, 'TB' ),
        ( 1000 ** 3, 'GB' ),
        ( 1000 ** 2, 'MB' ),
        ( 1000 ** 1, 'kB' ),
        ( 1000 ** 0, 'B' ),
    ]:
        if n < o:
            continue
        return '%.1f %s' % ( n / o, u )

skip_majno = [
    get_majno('loop'),
    get_majno('zvol'),
    get_majno('nvme'),
    get_majno('blkext'),
]

devices = {}

x = json.loads(run_cmd('lsblk', '-Jp'))
for blkdev in x['blockdevices']:
    if not pathlib.Path(blkdev['name']).is_block_device():
        continue

    majmin = [ int(_) for _ in blkdev['maj:min'].split(':') ]
    if majmin[0] in skip_majno:
        continue

    device = get_disk_info(blkdev['name'])
    identifier = device['model'] + ':' + device['serial']
    devices[identifier] = device

def get_table(devices):
    columns = [
        { 'text': 'Path',          'data': lambda k, v: v['path']                                                      },
        { 'text': 'Model',         'data': lambda k, v: v['model']                                                     },
        { 'text': 'Serial',        'data': lambda k, v: v['serial']                                                    },
        { 'text': 'Firmware',      'data': lambda k, v: v['firmware']                                                  },
        { 'text': 'Capacity',      'data': lambda k, v: bytes_to_si(v['capacity'])                                     },
        { 'text': 'Flying (h)',    'data': lambda k, v: v['smart_attributes']['0xf0']['py_value']                      },
        { 'text': 'Powered (h)',   'data': lambda k, v: v['smart_attributes']['0x09']['py_value']                      },
        { 'text': 'Power Cycles',  'data': lambda k, v: v['smart_attributes']['0x0c']['raw_value']                     },
        { 'text': 'Reallocated',   'data': lambda k, v: re.sub('^0$', '-', v['smart_attributes']['0x05']['raw_value']) },
        { 'text': 'Temperature',   'data': lambda k, v: ' / '.join([ str(_) for _ in [
                                                            v['smart_attributes']['0xbe']['py_value']['min'],
                                                            v['smart_attributes']['0xbe']['py_value']['cur'],
                                                            v['smart_attributes']['0xbe']['py_value']['max']
                                                        ]])},
    ]

    headers = [ _['text'] for _ in columns ]
    data = sorted(get_table_data(devices, columns), key=lambda v: v[2])
    return tabulate.tabulate(data, headers = headers)

def get_table_data(devices, columns):
    for device_key, device_data in devices.items():
        yield [ *get_table_row(device_key, device_data, columns) ]

def get_table_row(device_key, device_data, columns):
    for column in columns:
        yield column['data'](device_key, device_data)

#print(json.dumps(devices))
print(get_table(devices))

exit(0)
