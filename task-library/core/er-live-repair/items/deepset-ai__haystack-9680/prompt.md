## Issue (deepset-ai/haystack)

Image support in `HuggingFaceAPIChatGenerator`
We want to make this component support multimodal user messages.

Relevant info: https://huggingface.co/docs/inference-providers/en/tasks/chat-completion#code-snippet-example-for-conversational-vlms

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.

## Names the tests use

The project's tests for this issue use these names; give them exactly as listed:

- `convert_message_to_hf_format` (the existing helper) turns a user `ChatMessage` with text and `ImageContent` parts into `{"role": "user", "content": [{"type": "text", "text": <text>}, {"type": "image_url", "image_url": {"url": "data:<mime type>;base64,<base64 image>"}}, ...]}`, the parts in the message's order (the Hugging Face chat-completion format for images).
