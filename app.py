"""Desktop interface for recording a voice reference and generating an MP3."""

from __future__ import annotations

import shutil
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk

from audio_player import AudioPlayer
from audio_recorder import MicrophoneRecorder
from voice_engine import GenerationResult, VoiceEngine


ROOT = Path(__file__).resolve().parent
REFERENCE_PATH = ROOT / "data" / "reference.wav"
OUTPUT_DIRECTORY = ROOT / "outputs"


class VoiceCloneApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Voice Clone")

        self.recorder = MicrophoneRecorder()
        self.player = AudioPlayer()
        self.engine = VoiceEngine()
        self.devices: list[tuple[int, str]] = []
        self.latest_output: Path | None = None
        self.latest_audio: GenerationResult | None = None
        self.record_started_at: datetime | None = None

        self.status = tk.StringVar(value="Record or import a voice sample.")
        self.model_status = tk.StringVar(value="MODEL LOADING")
        self.timer = tk.StringVar(value="00:00")
        self.character_count = tk.StringVar(value="0 / 1000 characters")
        self.device_name = tk.StringVar()
        self.exaggeration = tk.DoubleVar(value=0.5)
        self.cfg_weight = tk.DoubleVar(value=0.5)
        self.temperature = tk.DoubleVar(value=0.8)

        self._build_ui()
        self._set_initial_window_size()
        self._refresh_devices()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(200, self._start_model_load)

    def _set_initial_window_size(self) -> None:
        """Fit the complete interface on the current display and center it."""
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        available_width = max(640, screen_width - 80)
        available_height = max(620, screen_height - 100)
        width = min(max(720, self.root.winfo_reqwidth()), available_width)
        height = min(max(650, self.root.winfo_reqheight()), available_height)
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2 - 12)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(min(660, width), min(620, height))

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=(22, 16))
        frame.pack(fill="both", expand=True)

        header = ttk.Frame(frame)
        header.pack(fill="x", pady=(0, 12))
        heading = ttk.Frame(header)
        heading.pack(side="left", fill="x", expand=True)
        ttk.Label(heading, text="Voice Clone", font=("Segoe UI", 21, "bold")).pack(anchor="w")
        ttk.Label(
            heading,
            text="Create natural speech from a short voice reference.",
            bootstyle="secondary",
        ).pack(anchor="w", pady=(2, 0))
        self.model_badge = ttk.Label(
            header,
            textvariable=self.model_status,
            bootstyle="warning",
            font=("Segoe UI", 9, "bold"),
        )
        self.model_badge.pack(side="right", anchor="n", pady=5)

        reference_section = ttk.Labelframe(frame, text="1  Voice reference", padding=12)
        reference_section.pack(fill="x", pady=(0, 8))
        device_row = ttk.Frame(reference_section)
        device_row.pack(fill="x", pady=(0, 10))
        self.device_box = ttk.Combobox(device_row, textvariable=self.device_name, state="readonly")
        self.device_box.pack(side="left", fill="x", expand=True)
        ttk.Button(
            device_row,
            text="Refresh",
            command=self._refresh_devices,
            bootstyle="secondary-outline",
        ).pack(side="left", padx=(8, 0))

        reference_row = ttk.Frame(reference_section)
        reference_row.pack(fill="x")
        self.record_button = ttk.Button(
            reference_row,
            text="Record",
            command=self._toggle_recording,
            bootstyle="danger-outline",
        )
        self.record_button.pack(side="left")
        ttk.Button(
            reference_row,
            text="Import WAV",
            command=self._import_reference,
            bootstyle="secondary",
        ).pack(side="left", padx=8)
        ttk.Button(
            reference_row,
            text="Play",
            command=self._play_reference,
            bootstyle="info-outline",
        ).pack(side="left")
        ttk.Button(
            reference_row,
            text="Stop",
            command=self._stop_reference,
            bootstyle="secondary-outline",
        ).pack(side="left", padx=(8, 0))
        ttk.Label(reference_row, textvariable=self.timer).pack(side="right")

        text_section = ttk.Labelframe(frame, text="2  Text to speak", padding=12)
        text_section.pack(fill="x", pady=(0, 8))
        self.text_box = tk.Text(
            text_section,
            height=3,
            wrap="word",
            font=("Segoe UI", 11),
            background="#202428",
            foreground="#f1f3f5",
            insertbackground="#f1f3f5",
            selectbackground="#375a7f",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#454b50",
            highlightcolor="#0d6efd",
            padx=10,
            pady=10,
        )
        self.text_box.pack(fill="x")
        self.text_box.bind("<<Modified>>", self._update_character_count)
        ttk.Label(
            text_section,
            textvariable=self.character_count,
            bootstyle="secondary",
        ).pack(anchor="e", pady=(6, 0))

        controls = ttk.Labelframe(frame, text="3  Voice style", padding=12)
        controls.pack(fill="x", pady=(0, 8))
        preset_row = ttk.Frame(controls)
        preset_row.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(preset_row, text="Presets", bootstyle="secondary").pack(side="left", padx=(0, 8))
        ttk.Button(
            preset_row,
            text="Natural",
            command=lambda: self._set_preset(0.5, 0.5, 0.8, "Natural"),
            bootstyle="info-outline",
        ).pack(side="left")
        ttk.Button(
            preset_row,
            text="Expressive",
            command=lambda: self._set_preset(0.8, 0.35, 0.9, "Expressive"),
            bootstyle="info-outline",
        ).pack(side="left", padx=6)
        ttk.Button(
            preset_row,
            text="Calm",
            command=lambda: self._set_preset(0.35, 0.55, 0.7, "Calm"),
            bootstyle="info-outline",
        ).pack(side="left")
        self._add_parameter_slider(
            controls,
            row=1,
            label="Expressiveness",
            variable=self.exaggeration,
            minimum=0.25,
            maximum=1.5,
        )
        self._add_parameter_slider(
            controls,
            row=2,
            label="Guidance / pacing",
            variable=self.cfg_weight,
            minimum=0.0,
            maximum=1.0,
        )
        self._add_parameter_slider(
            controls,
            row=3,
            label="Temperature",
            variable=self.temperature,
            minimum=0.1,
            maximum=1.5,
        )
        ttk.Button(
            controls,
            text="Reset defaults",
            command=self._reset_parameters,
            bootstyle="secondary-outline",
        ).grid(
            row=4, column=1, sticky="e", pady=(8, 0)
        )
        controls.columnconfigure(1, weight=1)

        self.generate_button = ttk.Button(
            frame,
            text="Generate MP3",
            command=self._start_generation,
            bootstyle="success",
        )
        self.generate_button.pack(fill="x", ipady=5, pady=(0, 8))

        output_section = ttk.Labelframe(frame, text="4  Generated audio", padding=12)
        output_section.pack(fill="x")
        self.play_button = ttk.Button(
            output_section,
            text="Play result",
            command=self._play_result,
            state="disabled",
            bootstyle="info",
        )
        self.play_button.pack(side="left")
        ttk.Button(
            output_section,
            text="Stop",
            command=self._stop_audio,
            bootstyle="secondary-outline",
        ).pack(side="left", padx=8)
        self.save_button = ttk.Button(
            output_section,
            text="Save as...",
            command=self._save_as,
            state="disabled",
            bootstyle="success-outline",
        )
        self.save_button.pack(side="right")

        self.progress = ttk.Progressbar(frame, mode="indeterminate", bootstyle="success")
        self.progress.pack(fill="x", pady=(14, 8))
        ttk.Label(frame, textvariable=self.status, wraplength=680, bootstyle="secondary").pack(anchor="w")

    @staticmethod
    def _add_parameter_slider(
        parent: ttk.Labelframe,
        row: int,
        label: str,
        variable: tk.DoubleVar,
        minimum: float,
        maximum: float,
    ) -> None:
        value_text = tk.StringVar(value=f"{variable.get():.2f}")
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
        scale = ttk.Scale(parent, from_=minimum, to=maximum, variable=variable, bootstyle="info")
        scale.grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Label(parent, textvariable=value_text, width=5).grid(row=row, column=2, sticky="e", padx=(10, 0))
        variable.trace_add("write", lambda *_: value_text.set(f"{variable.get():.2f}"))

    def _reset_parameters(self) -> None:
        self._set_preset(0.5, 0.5, 0.8, "Natural")

    def _set_preset(
        self,
        exaggeration: float,
        cfg_weight: float,
        temperature: float,
        name: str,
    ) -> None:
        self.exaggeration.set(exaggeration)
        self.cfg_weight.set(cfg_weight)
        self.temperature.set(temperature)
        self.status.set(f"{name} voice preset selected.")

    def _update_character_count(self, _event=None) -> None:
        if not self.text_box.edit_modified():
            return
        count = len(self.text_box.get("1.0", "end-1c"))
        self.character_count.set(f"{count} / 1000 characters")
        self.text_box.edit_modified(False)

    def _refresh_devices(self) -> None:
        try:
            self.devices = self.recorder.input_devices()
        except Exception as exc:
            messagebox.showerror("Microphone error", str(exc))
            return

        names = [name for _, name in self.devices]
        self.device_box["values"] = names
        if names:
            self.device_box.current(0)
        else:
            self.device_name.set("No microphone found")

    def _start_model_load(self) -> None:
        self.generate_button.configure(state="disabled")
        self.progress.start(10)
        self.status.set("Loading the local Chatterbox model on the GPU...")
        threading.Thread(target=self._model_load_worker, daemon=True).start()

    def _model_load_worker(self) -> None:
        try:
            device = self.engine.load()
        except Exception as exc:
            self.root.after(0, self._model_load_failed, str(exc))
        else:
            self.root.after(0, self._model_load_finished, device)

    def _model_load_failed(self, error: str) -> None:
        self.progress.stop()
        self.generate_button.configure(state="normal")
        self.model_status.set("MODEL ERROR")
        self.model_badge.configure(bootstyle="danger")
        self.status.set("The model could not be loaded. Generation will retry when requested.")
        messagebox.showerror("Model loading error", error)

    def _model_load_finished(self, device: str) -> None:
        self.progress.stop()
        self.generate_button.configure(state="normal")
        self.model_status.set(f"{device.upper()} READY")
        self.model_badge.configure(bootstyle="success")
        self.status.set(f"Local model ready on {device.upper()}. Record or import a voice sample.")

    def _selected_device(self) -> int | None:
        index = self.device_box.current()
        return self.devices[index][0] if 0 <= index < len(self.devices) else None

    def _toggle_recording(self) -> None:
        if self.recorder.is_recording:
            self._stop_recording()
            return

        self.player.stop()
        try:
            self.recorder.start(self._selected_device())
        except Exception as exc:
            messagebox.showerror("Recording error", str(exc))
            return

        self.record_started_at = datetime.now()
        self.record_button.configure(text="Stop recording", bootstyle="danger")
        self.status.set("Recording... Speak naturally for about 10-20 seconds.")
        self._update_timer()

    def _stop_recording(self) -> None:
        try:
            duration = self.recorder.stop_and_save(REFERENCE_PATH)
        except Exception as exc:
            messagebox.showerror("Recording error", str(exc))
            self.status.set("Recording was not saved.")
        else:
            self.status.set(f"Reference saved locally ({duration:.1f} seconds).")
        finally:
            self.record_started_at = None
            self.record_button.configure(text="Record", bootstyle="danger-outline")

    def _update_timer(self) -> None:
        if not self.recorder.is_recording or self.record_started_at is None:
            return
        elapsed = int((datetime.now() - self.record_started_at).total_seconds())
        self.timer.set(f"{elapsed // 60:02d}:{elapsed % 60:02d}")
        if elapsed >= 30:
            self._stop_recording()
            return
        self.root.after(250, self._update_timer)

    def _import_reference(self) -> None:
        source = filedialog.askopenfilename(filetypes=[("WAV audio", "*.wav")])
        if not source:
            return
        REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, REFERENCE_PATH)
        self.status.set("Reference WAV imported and stored locally.")

    def _play_reference(self) -> None:
        try:
            duration = self.player.play_file(REFERENCE_PATH)
        except Exception as exc:
            messagebox.showerror("Playback error", str(exc))
        else:
            self.status.set(f"Playing reference in the app ({duration:.1f} seconds).")

    def _stop_audio(self) -> None:
        self.player.stop()
        self.status.set("Playback stopped.")

    def _stop_reference(self) -> None:
        self.player.stop()
        self.status.set("Reference playback stopped.")

    def _start_generation(self) -> None:
        text = self.text_box.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Text required", "Enter the text you want to generate.")
            return
        if not REFERENCE_PATH.exists():
            messagebox.showwarning("Reference required", "Record or import a reference voice first.")
            return

        self.generate_button.configure(state="disabled")
        self.progress.start(10)
        first_load = not self.engine.is_loaded
        self.status.set(
            "Loading the model and downloading its files for the first run..."
            if first_load
            else "Generating speech..."
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = OUTPUT_DIRECTORY / f"generated_{timestamp}.mp3"
        threading.Thread(
            target=self._generate_worker,
            args=(
                text,
                destination,
                self.exaggeration.get(),
                self.cfg_weight.get(),
                self.temperature.get(),
            ),
            daemon=True,
        ).start()

    def _generate_worker(
        self,
        text: str,
        destination: Path,
        exaggeration: float,
        cfg_weight: float,
        temperature: float,
    ) -> None:
        try:
            result = self.engine.generate_mp3(
                text,
                REFERENCE_PATH,
                destination,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                temperature=temperature,
            )
        except Exception as exc:
            self.root.after(0, self._generation_failed, str(exc))
        else:
            self.root.after(0, self._generation_finished, result)

    def _generation_failed(self, error: str) -> None:
        self.progress.stop()
        self.generate_button.configure(state="normal")
        self.status.set("Generation failed.")
        messagebox.showerror("Generation error", error)

    def _generation_finished(self, result: GenerationResult) -> None:
        self.latest_output = result.path
        self.latest_audio = result
        self.progress.stop()
        self.generate_button.configure(state="normal")
        self.play_button.configure(state="normal")
        self.save_button.configure(state="normal")
        device = self.engine.device.upper() if self.engine.device else "UNKNOWN"
        self.status.set(f"MP3 generated using {device}: {result.path.name}")

    def _play_result(self) -> None:
        if self.latest_audio is None:
            return
        try:
            duration = self.player.play_samples(
                self.latest_audio.samples,
                self.latest_audio.sample_rate,
            )
        except Exception as exc:
            messagebox.showerror("Playback error", str(exc))
        else:
            self.status.set(f"Playing generated speech in the app ({duration:.1f} seconds).")

    def _save_as(self) -> None:
        if self.latest_output is None:
            return
        destination = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("MP3 audio", "*.mp3")],
            initialfile=self.latest_output.name,
        )
        if destination:
            shutil.copy2(self.latest_output, destination)
            self.status.set(f"Saved: {destination}")

    def _close(self) -> None:
        self.player.stop()
        self.recorder.cancel()
        self.root.destroy()


def main() -> None:
    root = ttk.Window(themename="darkly")
    VoiceCloneApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
