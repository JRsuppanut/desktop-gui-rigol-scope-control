# Desktop GUI Rigol Scope Control

This project provides a simple desktop GUI for controlling a Rigol oscilloscope over USB using Python, Tkinter, and PyVISA.

## Overview

The application allows you to:
- Detect and select available Rigol instruments connected via USB
- Connect and disconnect from the scope
- Send SCPI commands to the instrument
- Start and stop acquisition with Run/Stop controls
- Adjust basic trigger settings
- Configure channels 1–4, including coupling, probe, vertical/horizontal scaling, position, bandwidth, and inversion

## Requirements

- Python 3.8 or later
- A Rigol oscilloscope connected via USB
- A working VISA backend

## Installation

Install the required Python packages:

```bash
pip install pyvisa pyvisa-py
```

If your system uses a specific VISA implementation such as NI-VISA, make sure it is installed and available in your environment.

## Running the Program

Run the application with:

```bash
python main.py
```

## Basic Usage

1. Launch the program.
2. Click Refresh to detect USB devices.
3. Select a detected device and click Connect.
4. Once connected, you can:
   - Send SCPI commands from the Command field
   - Press Run or Stop
   - Apply trigger settings
   - Configure channel settings

## Example Commands

You can try basic SCPI commands such as:

```text
*IDN?
:RUN
:STOP
```

## Notes

- This program uses SCPI commands, which may vary depending on the oscilloscope model and firmware.
- Some commands may not be supported by your specific Rigol device.
- If no device is detected, check that:
  - the USB cable is connected properly
  - the oscilloscope is powered on
  - the VISA backend and drivers are installed correctly

## Project Files

```text
.
├── main.py
└── README.md
```

## Disclaimer

This project is intended for learning and experimental control of a Rigol oscilloscope. Please refer to the official instrument manual for full command support and safe operation.