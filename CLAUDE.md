# Claude Code — Meeting Sentinel install guide

You are helping a user install Meeting Sentinel, a macOS meeting recorder
and transcriber. Follow these steps in order. Ask the user the questions
marked **ask:** and wait for a real answer before moving on.

## 1. Check and install prerequisites

- Confirm `python3 --version` returns 3.9 or newer.
- Run `which ffmpeg`. If missing, run `brew install ffmpeg`.
- Run `system_profiler SPAudioDataType | grep -i blackhole`. If no match,
  run `brew install --cask blackhole-2ch` and warn the user they must
  reboot before `meet` can record other participants — BlackHole is a
  kernel audio driver.

## 2. Clone the repo

Default location is `~/tools/meeting-sentinel`. If the user already has a
preferred place for tools, use that instead.

```bash
mkdir -p ~/tools
git clone https://github.com/tristanmcinnis/meeting-sentinel.git ~/tools/meeting-sentinel
```

## 3. Run the installer

```bash
cd ~/tools/meeting-sentinel
./install.sh
```

Check that `~/.local/bin` is on the user's PATH. If not, append
`export PATH="$HOME/.local/bin:$PATH"` to the appropriate shell rc file
(`~/.zshrc` on modern macOS).

## 4. Run the interactive setup wizard

```bash
meet setup
```

It asks four things:

- **ask:** Where should audio files be saved? (Default: `~/Meetings/recordings`)
- **ask:** Where should transcripts be saved? (Default: `~/Meetings/transcripts`)
- **ask:** Which transcription provider? (`soniox`, `elevenlabs`, `whisper-local`, or `none`)
- Provider-specific follow-ups (languages, model, etc.)

For whichever provider they pick:
- **soniox** → remind them to export `SONIOX_API_KEY` in `~/.zshrc`.
- **elevenlabs** → remind them to export `ELEVENLABS_API_KEY` in `~/.zshrc`.
- **whisper-local** → run `pip install openai-whisper` (use `--user` if they're not in a venv). Warn that the first transcription downloads model weights.

## 5. Configure macOS audio routing

Meeting Sentinel captures the other side of the call by pulling from
BlackHole, which is a virtual output device. For that to work, the user's
system output must actually be sent to BlackHole.

Tell the user to do this manually — it's a GUI step:

1. Open **Audio MIDI Setup** (built-in macOS app).
2. Click the **+** in the bottom-left → **Create Multi-Output Device**.
3. Check both **Built-in Output** (or their current speakers/headphones) and **BlackHole 2ch**.
4. Right-click the Multi-Output Device → **Use This Device For Sound Output**.

Without this step recordings will only contain the user's own voice.

## 6. Verify

```bash
meet devices       # should list BlackHole 2ch with an index
meet config        # should show the paths and provider they picked
```

## 7. Tell the user how to use it

```
meet watch                    # passive — prompts when a meeting app opens
meet start -n client-call     # manual — start by name
meet stop                     # stops and transcribes using their provider
```

## Notes

- Config lives at `~/.config/meeting-sentinel/config.json`. They can re-run `meet setup` any time to change provider or folders.
- The repo is self-contained — no other Tristan-vault-specific code is pulled in.
- Do NOT upload or commit any `.m4a`, `.wav`, or transcript files to git — they contain user audio.
