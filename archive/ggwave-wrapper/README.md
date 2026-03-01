# ggwave_simple Wrapper DLL

A simple wrapper DLL for the ggwave library, designed for easy integration with AutoHotkey V2.

## Building

### Prerequisites

- Visual Studio 2022 (or 2019) with C++ support
- CMake 3.10 or higher

### Build Steps

1. Open a Developer Command Prompt for Visual Studio
2. Navigate to this folder: `cd ggwave-wrapper`
3. Run the build script: `build.bat`

The script will:
- Create a build directory
- Configure with CMake
- Build the Release version
- Copy `ggwave_simple.dll` and `SDL2.dll` to the `AHK` folder

### Manual Build

```cmd
mkdir build
cd build
cmake .. -G "Visual Studio 17 2022" -A x64
cmake --build . --config Release
```

## API Reference

### Initialization

```c
// Initialize with audio device indices and protocol
// Returns 0 on success, negative on error
int ggwave_simple_init(int playbackDeviceId, int captureDeviceId, int protocolId);
```

### Device Enumeration

```c
int ggwave_simple_get_playback_device_count(void);
int ggwave_simple_get_capture_device_count(void);
const char* ggwave_simple_get_playback_device_name(int deviceId);
const char* ggwave_simple_get_capture_device_name(int deviceId);
```

### Send/Receive

```c
// Send a message via audio
int ggwave_simple_send(const char* message, int volume);

// Check if transmitting
int ggwave_simple_is_transmitting(void);

// Process audio (call regularly in a loop)
int ggwave_simple_process(void);

// Receive a message (returns length, 0 if none)
int ggwave_simple_receive(char* buffer, int bufferSize);
```

### Protocol Selection

```c
// Set transmission protocol
// 0 = AUDIBLE_NORMAL, 1 = AUDIBLE_FAST, 2 = AUDIBLE_FASTEST
// 3 = ULTRASOUND_NORMAL, 4 = ULTRASOUND_FAST, 5 = ULTRASOUND_FASTEST
int ggwave_simple_set_protocol(int protocolId);
```

### Cleanup

```c
void ggwave_simple_cleanup(void);
const char* ggwave_simple_get_error(void);
```

## Usage from AHK

See `AHK/main_dll.ahk` for a complete example.

Basic usage:

```ahk
; Load DLL
DllCall("LoadLibrary", "Str", "ggwave_simple.dll", "Ptr")

; Initialize (device 0 for both, protocol 1 = AUDIBLE_FAST)
DllCall("ggwave_simple\ggwave_simple_init", "Int", 0, "Int", 0, "Int", 1, "Int")

; Send a message
DllCall("ggwave_simple\ggwave_simple_send", "AStr", "Hello World", "Int", 50, "Int")

; Process and receive (call in a timer)
DllCall("ggwave_simple\ggwave_simple_process", "Int")
buffer := Buffer(256, 0)
len := DllCall("ggwave_simple\ggwave_simple_receive", "Ptr", buffer.Ptr, "Int", 256, "Int")
if (len > 0) {
    message := StrGet(buffer, len, "UTF-8")
}

; Cleanup
DllCall("ggwave_simple\ggwave_simple_cleanup")
```
