#!/usr/bin/env python3
"""Display and record a USB camera feed with a simple GUI."""

from __future__ import annotations

import datetime as dt
import re
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import cv2
from PIL import Image, ImageTk


CAMERA_INDEX = 0
FRAME_INTERVAL_MS = 15
OUTPUT_DIR = Path("recordings")


def safe_filename(value: str) -> str:
    """Return a filesystem-friendly filename stem."""
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return name.strip("._") or "usb_cam_recording"


class UsbCamRecorder(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("USB Camera Recorder")
        self.geometry("920x680")
        self.minsize(720, 520)

        self.capture = cv2.VideoCapture(CAMERA_INDEX)
        if not self.capture.isOpened():
            messagebox.showerror(
                "Camera error",
                f"Could not open USB camera at index {CAMERA_INDEX}.",
            )
            self.destroy()
            return

        self.writer: cv2.VideoWriter | None = None
        self.recording_path: Path | None = None
        self.current_frame = None
        self.photo = None

        self.name_var = tk.StringVar(value="USB Camera")
        self.status_var = tk.StringVar(value="Previewing camera")
        self.recording_var = tk.StringVar(value="Not recording")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(FRAME_INTERVAL_MS, self.update_frame)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.Frame(self, padding=12)
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Name text").grid(row=0, column=0, sticky="w")
        name_entry = ttk.Entry(controls, textvariable=self.name_var)
        name_entry.grid(row=0, column=1, sticky="ew", padx=8)

        ttk.Button(controls, text="Change Name Text", command=self.change_name_text).grid(
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
        self.status_var.set(f"Name text set to: {name or 'USB Camera'}")

    def start_recording(self) -> None:
        if self.writer is not None:
            return

        width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        fps = self.capture.get(cv2.CAP_PROP_FPS)
        if fps <= 1 or fps > 120:
            fps = 30

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

        self.recording_var.set(f"Recording: {self.recording_path}")

    def stop_recording(self) -> None:
        if self.writer is None:
            return

        self.writer.release()
        self.writer = None
        saved_path = self.recording_path
        self.recording_path = None
        self.recording_var.set(f"Saved: {saved_path}")

    def update_frame(self) -> None:
        ok, frame = self.capture.read()
        if not ok:
            self.status_var.set("Could not read frame from camera")
            self.after(FRAME_INTERVAL_MS, self.update_frame)
            return

        self.current_frame = frame
        display_frame = frame.copy()
        label = self.name_var.get().strip() or "USB Camera"
        cv2.putText(
            display_frame,
            label,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

        if self.writer is not None:
            self.writer.write(display_frame)

        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb_frame)
        image.thumbnail((self.preview.winfo_width() or 900, self.preview.winfo_height() or 560))
        self.photo = ImageTk.PhotoImage(image=image)
        self.preview.configure(image=self.photo)
        self.status_var.set("Previewing camera")
        self.after(FRAME_INTERVAL_MS, self.update_frame)

    def close(self) -> None:
        self.stop_recording()
        if self.capture.isOpened():
            self.capture.release()
        self.destroy()


if __name__ == "__main__":
    app = UsbCamRecorder()
    if app.winfo_exists():
        app.mainloop()
