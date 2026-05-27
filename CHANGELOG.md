# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.4] - 2026-05-27

### Fixed

- CI lint fixes; PyPI publish workflow with manual trigger.

## [0.1.3] - 2026-05-27

### Added

- Initial public open-source release extracted from the Repana LLM observability monorepo.
- `ObservabilityClient` with batch HTTP ingest, PII redaction, and `auto_instrument()`.
- Provider wrappers: OpenAI, Anthropic, Gemini, Bedrock.
- Unified `stream_chat`, endpoint discovery, and cost estimation.

[0.1.4]: https://github.com/repanareddysekhar/llm-obs/releases/tag/v0.1.4
[0.1.3]: https://github.com/repanareddysekhar/llm-obs/releases/tag/v0.1.3
