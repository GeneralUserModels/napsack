# NAPsack

**NAPsack** records and structures your computer use by generating natural language caption from screenshots and input events (click, keypress, scroll, cursor move).

<img width="1808" height="784" alt="github_fig" src="https://github.com/user-attachments/assets/85922c5a-f3c0-40a5-8273-ae9d60214711" />

---
# Quickstart

> Requires Python 3.11+ and `ffmpeg` for video generation. Use `uv` to run the commands below.

## API Keys

NAPsack uses a VLM to generate captions. Create a `.env` file in the project root (or export variables in your shell):

```shell
cp .env.example .env
```

Then fill in the key for your chosen client:

| Client | Variable | Where to get it |
|--------|----------|-----------------|
| `gemini` (default) | `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) |
| `vllm` | _(none — pass `--vllm-url`)_ | Self-hosted vLLM server |
| `bigquery` | _(uses Application Default Credentials)_ | `gcloud auth application-default login` |

For Gemini, your `.env` should contain:

```
GEMINI_API_KEY=your_key_here
```

**Record** a session (press CTRL+C to stop)
```shell
napsack-record --monitor
# or without installing:
uv run -m napsack.record --monitor
```
**Label** the recorded session
```shell
napsack-label --session logs/session_name --client gemini
# or without installing:
uv run -m napsack.label --session logs/session_name --client gemini
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


