# USB Camera Recorder

Simple Python GUI app to preview and record video from a USB camera.

## Setup

Install Tkinter if it is missing:

```bash
sudo apt install python3-tk
```

Create and activate the virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python usb_cam_recorder.py
```

## Notes

- Use the text box to set the recording file name prefix.
- Click **Start Recording** and **Stop Recording** to save video.
- Recordings are saved in the `recordings/` folder.
- Recording uses the measured capture FPS when you press **Start Recording**.
- The camera device is selected by `CAMERA_INDEX` in `usb_cam_recorder.py`.
- Resolution is selected by `CAMERA_PROFILE`.
- Use `CAMERA_PROFILE = "1080p"` for `1920x1080 30 FPS`.
- Use `CAMERA_PROFILE = "720p"` for `1280x720 30 FPS`.
- Auto exposure is enabled.
- To inspect camera modes, install `v4l-utils` and run:

```bash
sudo apt install v4l-utils
v4l2-ctl --device=/dev/video4 --list-formats-ext
```
