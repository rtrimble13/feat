"""Application layer: use-cases that orchestrate domain logic over ports.

Services contain orchestration only — every formula lives in
``feat.domain``. Services receive their repositories and config by
injection and return ``Result`` values; they never print or exit.
"""
