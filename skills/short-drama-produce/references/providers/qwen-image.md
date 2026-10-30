# Qwen Image adapter

Adapter command:

```json
{"command": ["python3", "/absolute/path/provider_adapters.py", "qwen-image"], "timeout_seconds": 1200}
```

The same adapter has two explicitly selectable transports:

- ComfyUI: set `COMFY_URL`; plain HTTP is accepted only for loopback addresses. `COMFY_USER`
  and `COMFY_PASS` optionally enable HTTP Basic auth.
- APIMart/OpenAI-compatible Qwen API: set `QWEN_IMAGE_API_KEY` and optionally
  `QWEN_IMAGE_BASE_URL` (default `https://api.apimart.ai/v1`) and `QWEN_IMAGE_MODEL`
  (default `qwen-image-3.0`).

`QWEN_IMAGE_TRANSPORT=api|comfy` resolves the route explicitly. Without it, a configured
`QWEN_IMAGE_API_KEY` selects the API and otherwise ComfyUI is used. This makes a cost-bearing
remote route visible in environment configuration rather than silently falling back between the
two. Credentials stay in the environment and never enter the project or adapter config.

The adapter implements the Qwen Image 2.1 ComfyUI workflow used by the migrated character-reference
skill:

- no references: `CLIPTextEncode` text-to-image;
- one to three references: `TextEncodeQwenImageEditPlus`;
- `ModelSamplingAuraFlow` shift 3.1, `KSampler` euler/simple, 20 steps, CFG 2.5 by default;
- references are uploaded through `POST /upload/image`;
- the workflow is submitted through `POST /prompt`, polled through `GET /history/<id>`, and fetched
  through `GET /view`.

ComfyUI job parameters:

- `ratio`: `2:3`, `4:5`, or `1:1`;
- or both `width` and `height`, multiples of 16 up to 2048;
- `seed`, `steps`, `cfg`, `shift`;
- `negative_prompt`;
- `prompt_language` for reference-contract text.

Optional model filenames are read from `COMFY_UNET`, `COMFY_CLIP`, and `COMFY_VAE`. Defaults match
the tested Qwen Image 2.1 workflow and can be overridden for another ComfyUI installation.

API job parameters are `ratio` (`2:3`, `4:5`, `1:1`) or `width` and `height` from 512 to 2048,
plus optional `negative_prompt` and `prompt_language`. Sampler-only fields (`seed`, `steps`,
`cfg`, `shift`) fail closed on the API route instead of being silently ignored. Up to three local
references are sent as `image_urls` data URIs.

The API joins `POST /images/generations`; the submission task id is written before polling and
`GET /v1/tasks/{task_id}` is read until `result.images[0].url[]` is ready. Polling uses
`IMAGE_TASK_POLL_INTERVAL` and `IMAGE_TASK_TIMEOUT_SECONDS`. Collect retrieves an existing task
without submitting a new generation.

Protocol surface: ComfyUI HTTP API (`/upload/image`, `/prompt`, `/history/<id>`, `/view`) or
[APIMart Qwen Image 3.0](https://docs.apimart.ai/en/api-reference/images/qwen-image-3.0/generation)
plus [task status](https://docs.apimart.ai/en/api-reference/tasks/status).
