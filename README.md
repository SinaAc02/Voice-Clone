# Voice Clone

Voice Clone is a Windows desktop app that generates speech from text and a
reference voice recording. It uses the pretrained Chatterbox model and saves
results as MP3 files.

## Features

- Record from a selected microphone or import a WAV file
- Trim quiet edges and normalize recorded audio
- Generate English speech with Chatterbox 500M
- Adjust expressiveness, guidance and temperature
- Play reference recordings and generated speech in the app
- Export audio as 192 kbps MP3

## Setup

The dependencies target Windows, Python 3.12 and CUDA 12.4. The engine selects
CUDA when available and falls back to CPU inference. A microphone is needed
for recording; existing WAV files can be imported instead.

```powershell
git clone https://github.com/SinaAc02/Voice-Clone.git
cd Voice-Clone
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

The first launch downloads model weights into `models/huggingface/`. Later
launches reuse that cache and load the model into memory.

## Using the app

1. Select a microphone and record a reference, or import a WAV file.
2. Play the reference to check its level and clarity.
3. Enter up to 1,000 characters of text and adjust the voice settings.
4. Choose **Generate MP3**, then play the result.

The recorder keeps up to 30 seconds of audio and trims quiet edges. A clear
10-20 second sample with one speaker is a useful starting point. Voice quality
varies with the recording and generated text.

The current reference is saved to `data/reference.wav`; generated MP3 files go
to `outputs/`. These folders and the model cache are ignored by Git.

## Project structure

- `app.py`: Tkinter interface and background workers
- `audio_recorder.py`: microphone capture and recording cleanup
- `voice_engine.py`: Chatterbox loading, generation and MP3 encoding
- `audio_player.py`: playback through the default audio output
