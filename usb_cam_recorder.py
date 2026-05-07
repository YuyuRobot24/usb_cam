#!/usr/bin/env python3
"""Display and record a USB camera feed with a simple GUI."""

from __future__ import annotations

import datetime as dt
import re
import sys
import threading
import time
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ModuleNotFoundError:
    print(
        "Tkinter is not installed for this Python.\n"
        "On Ubuntu, install it with:\n"
        "  sudo apt install python3-tk\n"
        "Then recreate the virtual environment if needed:\n"
        "  rm -rf .venv\n"
        "  python3 -m venv .venv\n"
        "  source .venv/bin/activate\n"
        "  pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(1) from None

import cv2
from PIL import Image, ImageTk


CAMERA_INDEX = 4
CAMERA_PROFILE = "720p"
CAMERA_PROFILES = {
    "1080p": {
        "name": "1080p USB camera",
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "fourcc": "MJPG",
    },
    "720p": {
        "name": "720p USB camera",
        "width": 1280,
        "height": 720,
        "fps": 30,
        "fourcc": "MJPG",
    },
}
DEFAULT_CAMERA_CONFIG = {
    "name": "USB camera",
    "width": 1280,
    "height": 720,
    "fps": 30,
    "fourcc": "MJPG",
}
FRAME_INTERVAL_MS = 1
OUTPUT_DIR = Path("recordings")
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 950
WINDOW_MIN_WIDTH = 960
WINDOW_MIN_HEIGHT = 600


def safe_filename(value: str) -> str:
    """Return a filesystem-friendly filename stem."""
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return name.strip("._") or "usb_cam_recording"


def camera_config(profile: str) -> dict[str, int | str]:
    return CAMERA_PROFILES.get(profile, DEFAULT_CAMERA_CONFIG)


class UsbCamRecorder(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("USB Camera Recorder")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        self.name_var = tk.StringVar(value="USB Camera")
        self.configured_camera = camera_config(CAMERA_PROFILE)
        self.capture = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
        if not self.capture.isOpened():
            messagebox.showerror(
                "Camera error",
                f"Could not open USB camera at index {CAMERA_INDEX}.",
            )
            self.destroy()
            return
        self.capture.set(
            cv2.CAP_PROP_FOURCC,
            cv2.VideoWriter_fourcc(*str(self.configured_camera["fourcc"])),
        )
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.configured_camera["width"]))
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.configured_camera["height"]))
        self.capture.set(cv2.CAP_PROP_FPS, int(self.configured_camera["fps"]))
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)
        actual_width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.capture.get(cv2.CAP_PROP_FPS)
        actual_fourcc = int(self.capture.get(cv2.CAP_PROP_FOURCC))
        actual_format = "".join(chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4))

        self.writer: cv2.VideoWriter | None = None
        self.recording_path: Path | None = None
        self.latest_frame = None
        self.latest_frame_id = 0
        self.frame_lock = threading.Lock()
        self.writer_lock = threading.Lock()
        self.stats_lock = threading.Lock()
        self.running = True
        self.photo = None
        self.gui_frame_count = 0
        self.gui_fps_started_at = time.monotonic()
        self.camera_fps = 0.0
        self.gui_fps = 0.0
        self.last_displayed_frame_id = 0

        self.camera_status = (
            f"{self.configured_camera['name']} profile '{CAMERA_PROFILE}' on /dev/video{CAMERA_INDEX}: "
            f"{actual_width}x{actual_height} {actual_fps:.0f} FPS {actual_format}"
        )
        self.status_var = tk.StringVar(value=f"Previewing camera at {self.camera_status}")
        self.recording_var = tk.StringVar(value="Not recording")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.capture_thread.start()
        self.after(FRAME_INTERVAL_MS, self.update_frame)

    def maximize_window(self) -> None:
        try:
            self.attributes("-zoomed", True)
        except tk.TclError:
            try:
                self.state("zoomed")
            except tk.TclError:
                pass

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.Frame(self, padding=12)
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="File name").grid(row=0, column=0, sticky="w")
        name_entry = ttk.Entry(controls, textvariable=self.name_var)
        name_entry.grid(row=0, column=1, sticky="ew", padx=8)

        ttk.Button(controls, text="Set File Name", command=self.change_name_text).grid(
            row=0, column=2, padx=(0, 8)
        )
        ttk.Button(controls, text="Start Recording", command=self.start_recording).grid(
            row=0, column=3, padx=(0, 8)
        )
        ttk.Button(controls, text="Stop Recording", command=self.stop_recording).grid(
            row=0, column=4
        )

        self.preview = ttk.Label(self, anchor="center")
        self.preview.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        footer = ttk.Frame(self, padding=(12, 0, 12, 12))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        footer.columnconfigure(1, weight=1)

        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(footer, textvariable=self.recording_var).grid(row=0, column=1, sticky="e")

    def change_name_text(self) -> None:
        name = self.name_var.get().strip()
        self.status_var.set(f"Recording file name set to: {name or 'usb_cam_recording'}")

    def recording_fps(self) -> float:
        with self.stats_lock:
            measured_fps = self.camera_fps
        if 1 <= measured_fps <= 120:
            return measured_fps

        camera_fps = self.capture.get(cv2.CAP_PROP_FPS)
        if 1 <= camera_fps <= 120:
            return camera_fps

        return float(self.configured_camera["fps"])

    def start_recording(self) -> None:
        with self.writer_lock:
            if self.writer is not None:
                return

            width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
            height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
            fps = self.recording_fps()

            OUTPUT_DIR.mkdir(exist_ok=True)
            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_filename(self.name_var.get())}_{timestamp}.avi"
            self.recording_path = OUTPUT_DIR / filename

            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            self.writer = cv2.VideoWriter(str(self.recording_path), fourcc, fps, (width, height))
            if not self.writer.isOpened():
                self.writer = None
                self.recording_path = None
                messagebox.showerror("Recording error", "Could not create the output video file.")
                return

        self.recording_var.set(f"Recording: {self.recording_path} at {fps:.1f} FPS")

    def stop_recording(self) -> None:
        with self.writer_lock:
            if self.writer is None:
                return

            self.writer.release()
            self.writer = None
            saved_path = self.recording_path
            self.recording_path = None
        self.recording_var.set(f"Saved: {saved_path}")

    def capture_loop(self) -> None:
        frame_count = 0
        started_at = time.monotonic()

        while self.running:
            ok, frame = self.capture.read()
            if not ok:
                time.sleep(0.01)
                continue

            with self.frame_lock:
                self.latest_frame_id += 1
                self.latest_frame = frame

            with self.writer_lock:
                if self.writer is not None:
                    self.writer.write(frame)

            frame_count += 1
            elapsed = time.monotonic() - started_at
            if elapsed >= 1.0:
                with self.stats_lock:
                    self.camera_fps = frame_count / elapsed
                frame_count = 0
                started_at = time.monotonic()

    def update_frame(self) -> None:
        with self.frame_lock:
            frame = None if self.latest_frame is None else self.latest_frame.copy()
            frame_id = self.latest_frame_id

        if frame is None:
            self.status_var.set("Waiting for camera frame")
            self.after(FRAME_INTERVAL_MS, self.update_frame)
            return
        if frame_id == self.last_displayed_frame_id:
            self.after(FRAME_INTERVAL_MS, self.update_frame)
            return
        self.last_displayed_frame_id = frame_id

        display_frame = frame

        preview_width = self.preview.winfo_width()
        preview_height = self.preview.winfo_height()
        if preview_width < 50:
            preview_width = 900
        if preview_height < 50:
            preview_height = 560
        frame_height, frame_width = display_frame.shape[:2]
        scale = min(preview_width / frame_width, preview_height / frame_height, 1.0)
        resized_width = max(int(frame_width * scale), 1)
        resized_height = max(int(frame_height * scale), 1)
        preview_frame = cv2.resize(
            display_frame,
            (resized_width, resized_height),
            interpolation=cv2.INTER_AREA,
        )
        rgb_frame = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb_frame)
        self.photo = ImageTk.PhotoImage(image=image)
        self.preview.configure(image=self.photo)

        self.gui_frame_count += 1
        elapsed = time.monotonic() - self.gui_fps_started_at
        if elapsed >= 1.0:
            self.gui_fps = self.gui_frame_count / elapsed
            self.gui_frame_count = 0
            self.gui_fps_started_at = time.monotonic()
            with self.stats_lock:
                camera_fps = self.camera_fps
            self.status_var.set(
                f"Previewing {self.camera_status} | Capture {camera_fps:.1f} FPS | Display {self.gui_fps:.1f} FPS"
            )
        self.after(FRAME_INTERVAL_MS, self.update_frame)

    def close(self) -> None:
        self.running = False
        if hasattr(self, "capture_thread"):
            self.capture_thread.join(timeout=1.0)
        self.stop_recording()
        if self.capture.isOpened():
            self.capture.release()
        self.destroy()


if __name__ == "__main__":
    app = UsbCamRecorder()
    if app.winfo_exists():
        app.mainloop()
