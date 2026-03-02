# NAPsack

**NAPsack** records and structures your computer use by generating natural language caption from screenshots and input events (click, keypress, scroll, cursor move).

<img alt="napsack_overview" src="https://github.com/user-attachments/assets/dd9ca2c5-288c-4977-8dc9-10ca343e56db" />

---
# Quickstart

> Requires Python 3.11+ and `ffmpeg` for video generation. Use `uv` to run the commands below.

**Record** a session (press CTRL+C to stop)
```shell
uv run -m record --monitor
```
**Label** the recorded session
```shell
uv run -m label --session logs/session_name --client gemini
```

> NAPsack supports `gemini` and `vllm` for data labeling and integrates with `big query`

# Output

```shell
logs/session_name
├── screenshots         # Recorded screenshots
├── aggregations.jsonl  # Recorded event bursts
├── captions.jsonl	    # All VLM-generated captions
├── annotated.mp4       # Final video showing generated captions and input events
└── data.jsonl          # Final data containing raw input events and LLM generated captions
```

# Method

## Record

NAPsack groups temporally adjacent input events of the same type into **event bursts**. An event is assigned to the current burst if the time since the preceding event of that type does not exceed the corresponding **gap** threshold and the elapsed time since the burst start remains within the **max** duration.
* If the **gap** threshold is exceeded, a new burst is started.
* If the **max** duration is exceeded, the first half of the current burst is finalized and saved, while the second half becomes the active burst.
A burst is force-restarted when the active monitor changes.

## Label

The `label` module:

* Loads sessions or raw screenshots and chunks.
* Uses prompts (in `label/prompts`) to instruct the VLM to generate captions that describe the user's actions and context.
* Produces `captions.jsonl` and `data.jsonl` (captions aligned to screenshots and events).
* Optionally renders an annotated video (`annotated.mp4`) showing captions and event visualizations overlayed on frames.

The label step performs a second layer of aggregation: it uses the bursts detected at recording time and further refines and annotates them with VLM outputs to create final human-readable summaries.


