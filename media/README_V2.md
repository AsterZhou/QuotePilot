# Product video v2

175-second full-frame real browser footage; actual synthetic RFQ version100→500 and repeated cost/approval workflow. First create/review the18-second opening sample, then build the complete cut. Current voice is synthesized Mandarin Chinese, not a human voice actor.

- Source: media/final_storyboard.json, docs/final/P2_VIDEO_V2_SHOTLIST.md.
- Real user operation footage: scripts/final_browser.cjs, record_final_demo.cjs, verify_final_user_path.cjs. Never run them against production. Live credentials arrive only through hidden stdin to final_live_server.py, and only synthetic local SQLite paths are allowed.
- Generate voice with final_voice.py (edge-tts optional media dependency); default TLS verification uses the system environment trust root. No TLS bypass or paid API key.
- Install media/requirements-video.txt and system FFmpeg/libx264/libass; prepare QuotePilot Sans static Chinese font with scripts/prepare_video_font.py.
- Restore the materials ZIP's raw/, take4/, voice/ into tmp/final-video; role mappings/timeline are in evidence/final-p1/capture. Absolute paths from the original recorder fall back to restored take4 filenames. Keep synthetic approved PDF/XLSX separate from production files.
- Build with `python scripts/build_final_video.py --opening` then `python scripts/build_final_video.py`. `--reuse-unchanged-scenes` is only for an explicitly identified one-scene correction with existing verified intermediates; use the default full rebuild after any other input change.
- Decode the full file and check subtitles, real amounts, voice levels, and actual browser playback from0 to ended. Technical decoding and sampled frames alone do not certify editorial quality or subjective listening.

Large recordings, voices and MP4s are delivered separately. No screenshots/pans are used as product-video backgrounds; editorial title/subtitle overlays are clearly separate from actual UI. Reopening a saved platform receipt is not a new model/SQL call and is labeled accordingly.
