# USB Camera Recorder

Simple Python GUI app to preview and record video from a USB camera.

## Setup

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

- Use the text box to change the name shown on the video.
- Click **Start Recording** and **Stop Recording** to save video.
- Recordings are saved in the `recordings/` folder.
