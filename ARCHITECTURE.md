# LoRaShell Project Architecture

## 1. Project Goal
Provide a Python Tkinter GUI tool for dual DTDS-622 modules connected over USB-TTL. The app performs:
- Serial port management (connect/disconnect)
- AT initialization and configuration per module
- Continuous RX logging with timestamps
- Frame parser for LoRa `+RX:` messages including broken split lines
- Parsed table view (`time`, `type`, `source`, `destination`, `data`)

## 2. Main Components

### 2.1 loraTest.py (Main Application)
- `SerialModule` class
  - Manages a serial port, receiver thread, and line display
  - `open`, `close`, `read_loop` for asynchronous reads
  - `send_at` for AT command send + response read
  - `append_line` writes to GUI text area and log file
- `App` class
  - Builds UI panels for both modules and parsed tables
  - Handles connect/disconnect events
  - Runs AT initialization in background thread to keep GUI responsive
  - Parses `+RX:` frames and populates parsed Treeview

### 2.2 UI Layout
- Top section: two module settings groups (port, baud, freq, recv mode, etc.)
- Middle toolbar: Connect, Disconnect, Refresh ports, Send AT now
- Bottom section: dual panes per module with raw RX text and parsed frame table
- Treeview columns: Time, Type, Source MAC, Destination MAC, Data

### 2.3 Parsing and Frame Handling
- `parse_rx_frame` handles raw `+RX:` string from module replies
  - Supports frame: `AA ... 55` with 8-byte source and destination MAC
  - Uses message ID mapping from your enums
  - Leaves data blank if no payload
- `on_parse_line` buffers partial `+RX:` fragments
  - Detects split lines and assembles complete packet text
  - Extracts full packet using regex pattern and parses

## 3. Code Flow
1. App starts with `main()` and builds Tkinter window
2. User selects serial ports/baud and clicks Connect
3. For each module:
   - `SerialModule.open()` opens port and starts `read_loop`
   - `initialize_dtds_module()` sends AT init sequence in a worker thread
4. `read_loop` receives bytes continuously and sends text to `append_line`
5. `append_line` logs and triggers `on_parse_line` callback
6. `on_parse_line` identifies +RX data, reassembles broken lines, calls `parse_rx_frame`
7. Parsed frame row inserted in the Treeview table

## 4. Key AT Commands Used
- `AT`, `AT+RESET`, `ATE0`, `ATV1`, `AT+MODEM=1`
- `AT+FREQ=<hz>` (converted from MHz)
- `AT+LMCFG=7,0,1`, `AT+LPCFG=8,0,1,0,0`, `AT+LBT=1,-80,10,0`
- `AT+TXPWR=22`
- `AT+RECV=<mode>,<verbose>` (choose 0 or 1)

## 5. Logging
- Each module writes logs to `module1_rx.log` and `module2_rx.log`
- Messages include timestamped raw lines and AT responses
- Parsed data table is for quick inspection and not currently persisted (can be added)

## 6. Extension Points
- Add UDP export or CSV parser output
- Save parsed table to file or database
- Add explicit command sequence editor and module-specific persistent setup
- Add support for binary frames with escaped payload or CRC checks

## 7. Architecture Diagram (Conceptual)
```
[User GUI] -> [App.connect_all] -> [SerialModule.open] -> [read_loop]
                |                                |
                |-- background AT init thread --> [SerialModule.send_at]

[read_loop] -> [append_line] -> [on_parse_line] -> [parse_rx_frame] -> [Treeview]
```

## 8. Notes
- The parser is robust to broken split lines by buffering partial +RX text and matching complete capture regex.
- MACs are 8 bytes pre-defined from your frame format.
- This tool is for real-time debugging and logging; further modularization into separate modules can improve testability.
