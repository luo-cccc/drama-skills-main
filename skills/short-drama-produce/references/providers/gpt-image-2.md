# GPT Image 2 adapter

Adapter command:

```json
{"command": ["python3", "/absolute/path/provider_adapters.py", "gpt-image-2"], "timeout_seconds": 600}
```

Required environment: `OPENAI_API_KEY`. `OPENAI_BASE_URL` optionally overrides the default
`https://api.openai.com/v1` and must remain HTTPS. `OPENAI_IMAGE_MODEL` optionally selects
another OpenAI-compatible image model available on that endpoint; it defaults to `gpt-image-2`.
For APIMart, set `OPENAI_BASE_URL=https://api.apimart.ai/v1`; the key still comes from
`OPENAI_API_KEY` and must never enter adapter config or project files.

The job must use modality `image` and have exactly one output. With no references, the adapter sends JSON to
`POST /images/generations`. With one to sixteen references, direct OpenAI sends an `image[]`
multipart edit to `POST /images/edits`; APIMart sends JSON `image_urls` with local files encoded as
data URIs to `POST /images/generations`. `OPENAI_IMAGE_REFERENCE_MODE=multipart|json_urls`
overrides the detected transport. `n` is always one.

The response may be a synchronous `data[0].b64_json`, a synchronous HTTPS `data[0].url`, or an
asynchronous `data[0].task_id`. APIMart uses the last form. The adapter records that id in
`handle_path` before polling, calls `GET /v1/tasks/{task_id}`, and downloads exactly one URL from
`data.result.images[0].url[]`. Polling uses `IMAGE_TASK_POLL_INTERVAL` and
`IMAGE_TASK_TIMEOUT_SECONDS`; collect polls an existing task without submitting another one.
The default model is `gpt-image-2`.

Supported public parameters are `width` plus `height` (compiled to `size`), or `size`, and `quality`, `background`, and
`moderation`. References use GPT Image 2's high-fidelity behavior without sending the older `input_fidelity` field.
Transparent backgrounds are rejected because GPT Image 2 does not support them. The output extension selects `png`,
`jpeg`, or `webp`.

Protocol references: [APIMart GPT Image 2](https://docs.apimart.ai/en/api-reference/images/gpt-image-2/generation),
[APIMart task status](https://docs.apimart.ai/en/api-reference/tasks/status),
[GPT Image 2 model](https://developers.openai.com/api/docs/models/gpt-image-2),
[image generation](https://developers.openai.com/api/reference/resources/images/methods/generate), and
[image edits](https://developers.openai.com/api/reference/resources/images/methods/edit).
