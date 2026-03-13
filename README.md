# NAPsack

**NAPsack** records and structures your computer use by generating natural language caption from screenshots and input events (click, keypress, scroll, cursor move).

<img width="1808" height="784" alt="github_fig" src="https://github.com/user-attachments/assets/85922c5a-f3c0-40a5-8273-ae9d60214711" />

---
# Quickstart

> Requires Python 3.11+

Install NAPsack from PyPI:

```shell
pip install napsack
```

Or, if you prefer not to install it, use `uv` to run the module commands shown below.

## API Keys

NAPsack uses a VLM to generate captions. Create a `.env` file in the project root (or export variables in your shell):

```shell
cp .env.example .env
```

NAPsack uses [litellm](https://github.com/BerriAI/litellm), so pass a full provider-prefixed model string via `--model`:

| Provider | `--model` example | API key variable |
|----------|-------------------|-----------------|
| Gemini (default) | `gemini/gemini-2.5-flash` | `GEMINI_API_KEY` |
| OpenAI | `openai/gpt-4.1-mini` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/claude-4.6-sonnet` | `ANTHROPIC_API_KEY` |
| vLLM (self-hosted) | `hosted_vllm/Qwen3-VL-8B` + `--api-base http://host/v1` | _(none required)_ |
| Tinfoil (confidential inference) | _(pass `--client tinfoil`)_ | `TINFOIL_API_KEY` |
| BigQuery | _(pass `--client bigquery`)_ | Application Default Credentials — `gcloud auth application-default login` |

**Record** a session (press CTRL+C to stop)
```shell
napsack-record --session-dir ./logs/session_name --monitor
# or without installing:
uv run -m napsack.record --session-dir ./logs/session_name --monitor
```
**Label** the recorded session
```shell
napsack-label --session-dir ./logs/session_name # default model is Gemini 3.0 flash
# or without instaling
uv run -m napsack.label --session-dir ./logs/session_name 
```

> NAPsack uses [litellm](https://github.com/BerriAI/litellm) as its labeling backend, supporting Gemini, vLLM/self-hosted models, and any OpenAI-compatible API (OpenAI, Together, Groq, etc.). It also supports [Tinfoil](https://tinfoil.sh) for confidential inference (your data never leaves a verified TEE), and integrates with BigQuery (if you're on Screenomics, this is for you :D).

To use Tinfoil, pass `--client tinfoil --model <model>`, e.g.:
```shell
napsack-label --session-dir ./logs/session_name --client tinfoil --model meta-llama/Llama-3.2-11B-Vision-Instruct
```

# Output

```shell
./logs/session_name
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


