# Overview

## What is it?

This utility is designed to provide quick and easy access to important
information about your storage devices.

It can provide two forms of output, see below:
 - Tabular (default)
 - JSON

## What does it need? / Limitations

Currently it is in a nasty hacky form (it even calls `sudo` for you)...

It will probably break if your system isn't similar to mine, e.g:
 - has ZFS
 - has NVMe device(s)

It will skip the following device classes, as retrieved from `/proc/devices`:
 - `loop`
 - `zvol`
 - `nvme`
 - `blkext` (NVMe too??)

It depends on the following system utilities:
 - `sudo`
 - `lsblk`
 - `smartctl`

It depends on the following (exotic-ish) python modules:
 - `tabulate`

## Tabular Output

When run from a fresh checkout, the output looks like this:

```bash
$ ./storage_info.py
Path      Model                 Serial    Firmware    Capacity      Flying (h)    Powered (h)    Power Cycles  Reallocated    Temperature
--------  --------------------  --------  ----------  ----------  ------------  -------------  --------------  -------------  -------------
/dev/sdg  ST10000VN0004-1ZD101  ????????  SC60        10.0 TB             5438           7444              35  -              16 / 28 / 39
/dev/sdc  ST10000VN0004-1ZD101  ????????  SC60        10.0 TB             6696           7712              43  8              17 / 24 / 35
/dev/sde  ST10000VN0004-1ZD101  ????????  SC60        10.0 TB             6696           7712              43  -              17 / 25 / 36
/dev/sdd  ST10000VN0004-1ZD101  ????????  SC60        10.0 TB             6697           7712              43  -              16 / 24 / 35
/dev/sdf  ST10000VN0004-1ZD101  ????????  SC60        10.0 TB             6667           7681              38  -              18 / 26 / 37
/dev/sda  ST12000VN0007-2GS116  ????????  SC60        12.0 TB             1402           1414              12  -              18 / 24 / 35
/dev/sdb  ST12000VN0007-2GS116  ????????  SC60        12.0 TB              686            693               3  -              18 / 24 / 35
```

## JSON Output 

By altering the last calls to `print()`, the output can look like this:

```json
{
  "${MODEL}:${SERIAL}": {
    "path": "${DEVICE_PATH}",
    "model": "${MODEL}",
    "serial": "${SERIAL}",
    "firmware": "${FIRMWARE}",
    "capacity": "${CAPACITY}",
    "sectors": {
      "logical": "${LOGICAL_SECTOR_SIZE}",
      "physical": "${PHYSICAL_SECTOR_SIZE}"
    }
    "spindle_speed": ${SPINDLE_SPEED},
    "form_factor": "${FORM_FACTOR}",
    "sata_version": {
      "rating": "${SATA_RATING}",
      "current": "${SATA_CURRENT}"
    },
    "smart_enabled": ${SMART_ENABLED},
    "smart_attributes": {
      "${ID}": {
        "id": "${ID}",
        "name": "${NAME}",
        "flag": "${FLAG}",
        "value": "${VALUE}",
        "worst": "${WORST}",
        "threshold": "${THRESHOLD}",
        "type": "${TYPE}",
        "updated": "${UPDATED}",
        "when_failed": "${WHEN_FAILED}",
        "raw_value": "${RAW_VALUE}"
      },
      ...
    }
  },
  ...
}
```

Some SMART attributes also have a `py_value`:

 - `0x09` / Power_On_Hours
 - `0xb3` / Airflow_Temperature_Cel
 - `0xf0` / Head_Flying_Hours
