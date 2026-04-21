# Meeting Sentinel

A tiny macOS CLI that records your meetings — mic + other participants'
voices mixed together — and transcribes them automatically.

Turn it on, leave it in a terminal tab, and it will:
- watch for Zoom / Teams / WeChat / FaceTime,
- offer to record when a meeting starts,
- offer to stop-and-transcribe when the meeting ends,
- drop an audio file and a text transcript into folders you picked.

Works with **Soniox**, **ElevenLabs**, or **local Whisper** — you choose
during setup, and you can switch later.

---

## Install with Claude Code (one line)

Open [Claude Code](https://claude.com/claude-code) in any terminal and paste
this prompt — it will clone, install, and walk you through setup:

```
Install Meeting Sentinel from https://github.com/tristanmcinnis/meeting-sentinel into ~/tools/meeting-sentinel. Run its install.sh, then run `meet setup` and answer the prompts with me (it will ask where to save audio, where to save transcripts, and which transcription provider to use — Soniox, ElevenLabs, or local Whisper). Check prerequisites (ffmpeg via Homebrew, BlackHole 2ch via Homebrew cask) and install whatever is missing. When done, show me how to run `meet watch`.
```

Claude will run every step, prompt you for the two folders and the provider,
handle `brew install` for `ffmpeg` and `blackhole-2ch`, and make sure `meet`
is on your `PATH`.

---

## Manual install

```bash
# 1. Prerequisites (macOS)
brew install ffmpeg
brew install --cask blackhole-2ch
# reboot — BlackHole is a kernel audio driver

# 2. Audio routing
#   Open  Audio MIDI Setup
#   +  →  Create Multi-Output Device
#   check  Built-in Output  +  BlackHole 2ch
#   Right-click  →  Use This Device For Sound Output

# 3. Clone & install
git clone https://github.com/tristanmcinnis/meeting-sentinel.git ~/tools/meeting-sentinel
cd ~/tools/meeting-sentinel
./install.sh

# 4. Configure (asks you where to save audio + transcripts + provider)
meet setup

# 5. Verify and run
meet devices          # BlackHole should be detected
meet watch            # or: meet start / meet stop
```

---

## Commands

```
meet setup                   First-run config — paths + provider
meet config                  Show active config
meet start [-n NAME]         Start recording manually
meet stop                    Stop and transcribe
meet stop --no-transcribe    Stop without transcribing
meet watch                   Auto-prompt when a meeting app opens/closes
meet transcribe FILE.m4a     Transcribe an existing audio file
meet status                  Show active recording info
meet devices                 List audio devices
meet unprocessed             List all raw transcripts
```

## Output

- **Audio:** `<your recordings dir>/<name>.m4a`
- **Transcript:** `<your transcripts dir>/<name>-transcript.txt`

Both paths are chosen during `meet setup`. Defaults are `~/Meetings/recordings`
and `~/Meetings/transcripts`.

---

## Transcription providers

Pick one during `meet setup` — you can re-run the wizard any time to switch.

| Provider | Cost | Speed | Notes |
|---|---|---|---|
| **Soniox** | cloud, paid | fast | strong multilingual (en + zh, etc.), speaker diarization, timestamps. Needs `SONIOX_API_KEY` |
| **ElevenLabs** | cloud, paid | fast | Scribe v1; good English + diarization. Needs `ELEVENLABS_API_KEY` |
| **whisper-local** | free | slower | runs fully on your Mac, no API key, no network. Needs `pip install openai-whisper` |
| **none** | — | — | record only, transcribe later elsewhere |

API keys go in your shell rc file:

```bash
# ~/.zshrc
export SONIOX_API_KEY='sk-...'
export ELEVENLABS_API_KEY='el-...'
```

---

## How it works

```
meet start/stop  →  ffmpeg captures  mic + BlackHole  →  .m4a
                                                           ↓
                                        transcriber (Soniox / ElevenLabs / Whisper)
                                                           ↓
                                                       -transcript.txt
```

- **ffmpeg** records two inputs (your mic + BlackHole loopback) and mixes them into a single `.m4a`.
- **BlackHole** is a virtual audio driver that duplicates your system's audio output — that's how we capture the other people on the call without asking them for permission or installing anything on their side.
- The `.m4a` is then passed to whichever transcription backend you configured.

Config lives at `~/.config/meeting-sentinel/config.json`. Recording state
(active PID) lives at `~/.config/meeting-sentinel/state.json`.

---

## Troubleshooting

**`meet devices` doesn't show BlackHole.** Install it and reboot — it's a
kernel driver: `brew install --cask blackhole-2ch`, then restart.

**Recording has my voice but nothing from the other side.** You haven't
routed system output through BlackHole. Open **Audio MIDI Setup**, create a
Multi-Output Device with Built-in Output + BlackHole 2ch, then set it as your
system output. BlackHole is silent on its own; you want audio to go *to* it.

**Soniox / ElevenLabs says "API key not set".** Export the key in the same
shell where you run `meet`. Add it to `~/.zshrc` to make it permanent.

**`whisper-local` is slow.** Pick a smaller model in `meet setup` (`tiny` or
`base`), or switch to a cloud provider for long calls.

---

## License

MIT. See [LICENSE](./LICENSE).
