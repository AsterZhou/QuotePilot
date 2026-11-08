# QuotePilot 180-second product cut

`storyboard.json` is the source of truth for ten contiguous scenes and Chinese narration. All business examples are synthetic; UI footage/screenshots come from the real local service. Platform cards read the actual P0 receipts. No public deployment or native workflow execution is claimed.

## Reproduce

1. Install optional `media/requirements-video.txt`, existing project requirements, FFmpeg with libx264/libass, and Playwright Chromium. These are media dependencies, not production service dependencies.
2. Obtain an open-licensed Chinese font such as Noto Sans SC from its official distribution. Keep its license when redistributing. Convert the variable font with `python scripts/prepare_video_font.py SOURCE.ttf /absolute/path/QuotePilotSans.ttf`. Set `QUOTEPILOT_VIDEO_FONT` to this static font. The family name is significant to libass.
3. Run the existing isolated acceptance server and `scripts/independent_browser.cjs` with `QUOTEPILOT_RECORD_VIDEO` pointing at `tmp/product-video/raw`, and browser evidence output at `evidence/sprint-p2/browser`. Use temporary synthetic SQLite and local test credentials; never use production data. The script needs Playwright's FFmpeg executable for recording.
4. Preserve both actual page recordings (admin first, reviewer second) and the five PNG screenshots plus approved.pdf/xlsx. Raw videos can be restored from the accompanying demo-materials ZIP.
5. From the repository root, run `python scripts/build_product_video.py`, then `python scripts/verify_product_video.py`. Inspect the decoded Chinese subtitles and monetary labels visually before delivery.

Output: `tmp/product-video/QuotePilot_180s_subtitled.mp4`, 1920×1080, 24fps, exactly180 seconds, burned Chinese subtitles. The background tones are generated mathematically by the script. This cut has no voiceover: the no-key voice endpoint failed certificate validation. Full narration and SRT/ASS are included for later recording.

The edit contains short slowed real screencasts and pans across actual screenshots. It is an edited product presentation, not an uninterrupted 180-second screen recording. Do not describe the standalone Genesis probe and MatrixOne mirror as a completed native orchestration workflow.

Large recordings, screenshots and media outputs are delivered separately, not added to Git. P0/P1/P2 evidence JSON and regression logs are versioned.
