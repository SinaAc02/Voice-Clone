# Voice Clone

Voice Clone is a local Windows desktop app for experimenting with zero-shot text-to-speech. It records a short voice sample, uses it as a reference for Chatterbox, and saves the generated speech as an MP3.

I built this project to learn how a speech model fits into a complete desktop workflow: microphone input, basic signal cleanup, GPU inference and playback in one interface. The recordings, generated audio and downloaded model weights remain on the user's computer.

## Features

- Record a reference directly from a selected microphone or import a WAV file
- Trim quiet edges and normalize the recorded sample
- Generate English speech with the Chatterbox 500M model
- Adjust expressiveness, guidance and temperature
- Play both the reference and generated result inside the app
- Export each result as a 192 kbps MP3

## Requirements

- Windows 10 or 11
- Python 3.12
- NVIDIA GPU recommended (CPU inference is possible but slow)
- Microphone
- About 3 GB for the model, plus the PyTorch environment

The project was developed and tested with an NVIDIA RTX 4070 Ti.

## Setup

```powershell
git clone https://github.com/SinaAc02/Voice-Clone.git
cd Voice-Clone
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

On the first start, Chatterbox downloads into `models/huggingface/`. Later starts use the local copy. Loading still takes a little time because the model must be transferred into GPU memory.

## How it works

1. `audio_recorder.py` captures mono audio, removes long quiet edges and normalizes the level.
2. `voice_engine.py` loads Chatterbox on CUDA when available and performs inference from the text and reference WAV.
3. The generated waveform is encoded as MP3 with `lameenc`.
4. `audio_player.py` sends reference or generated samples to the Windows audio output.
5. `app.py` connects those parts to the Tkinter interface without blocking its main thread.

Reference recordings are limited to 30 seconds. In practice, a clean 10-20 second sample with one speaker gives a better result than a noisy or heavily processed recording.
