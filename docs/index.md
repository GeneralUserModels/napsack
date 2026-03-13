---
hide:
  - navigation
  - toc
---

# NAPsack

<div style="text-align: center;">
<img src="https://github.com/user-attachments/assets/85922c5a-f3c0-40a5-8273-ae9d60214711" alt="NAPsack" width="80%" />
</div>

**NAPsack** records and structures your computer use by generating natural language captions from screenshots and input events (click, keypress, scroll, cursor move).

## Installation

!!! info "Install NAPsack"

    === "pip"

        ```shell
        pip install napsack
        ```

    === "From source"

        ```shell
        git clone https://github.com/generalusermodels/napsack.git
        cd napsack
        pip install --editable .
        ```

> Requires Python 3.11+ and `ffmpeg` for video generation.

## Quickstart

**Record** a session (press CTRL+C to stop):

```shell
napsack-record --monitor
```

**Label** the recorded session:

```shell
# Gemini (default)
napsack-label --session logs/session_name --model gemini/gemini-2.5-flash

# OpenAI
napsack-label --session logs/session_name --model openai/gpt-4o

# Anthropic
napsack-label --session logs/session_name --model anthropic/claude-3-5-sonnet-20241022

# Self-hosted vLLM
napsack-label --session logs/session_name --model hosted_vllm/Qwen3-VL-8B --api-base http://localhost:8000/v1
```

NAPsack uses [litellm](https://github.com/BerriAI/litellm), so any provider litellm supports works out of the box. Set the appropriate API key in your environment:

| Provider | Environment variable |
|----------|----------------------|
| Gemini | `GEMINI_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| vLLM | _(none required)_ |

## Output

```
logs/session_name
├── screenshots         # Recorded screenshots
├── aggregations.jsonl  # Recorded event bursts
├── captions.jsonl      # All VLM-generated captions
├── annotated.mp4       # Final video showing generated captions and input events
└── data.jsonl          # Final data containing raw input events and LLM generated captions
```

## How it works

### Record

NAPsack groups temporally adjacent input events of the same type into **event bursts**. An event is assigned to the current burst if the time since the preceding event of that type does not exceed the corresponding **gap** threshold and the elapsed time since the burst start remains within the **max** duration.

- If the **gap** threshold is exceeded, a new burst is started.
- If the **max** duration is exceeded, the first half of the current burst is finalized and saved, while the second half becomes the active burst.

A burst is force-restarted when the active monitor changes.

### Label

The `label` module:

- Loads sessions or raw screenshots and chunks them.
- Uses prompts to instruct the VLM to generate captions describing the user's actions and context.
- Produces `captions.jsonl` and `data.jsonl` (captions aligned to screenshots and events).
- Optionally renders an annotated video (`annotated.mp4`) showing captions and event visualizations overlaid on frames.

The label step performs a second layer of aggregation: it uses the bursts detected at recording time and further refines and annotates them with VLM outputs to create final human-readable summaries.
