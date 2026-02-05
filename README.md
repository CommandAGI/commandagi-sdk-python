# commandAGI Python SDK

Official Python SDK for [commandAGI](https://commandagi.com) — Command the AGI with taste.

## Installation

```bash
pip install git+https://github.com/commandAGI/commandagi-python.git
```

## Quick Start

```python
import os
from commandagi import CommandAGI, ProfileCreateParams, EvalParams

client = CommandAGI(api_key=os.environ["COMMANDAGI_API_KEY"])

# Create a profile
profile = client.profiles.create(ProfileCreateParams(
    project_id="your-project-id",
    name="my-taste-profile",
    seed="minimalist design with warm tones",
))

# Evaluate content against the profile
result = client.profiles.eval(profile.id, EvalParams(
    frame_url="https://example.com/image.jpg",
))

print(f"Score: {result.score}, Confidence: {result.confidence}")
```

## API Reference

### Client

```python
from commandagi import CommandAGI

client = CommandAGI(
    api_key="cagi_xxx...",                    # Required
    base_url="https://commandagi.com",        # Optional (default)
    timeout=30.0,                             # Optional (default: 30s)
)

# Use as context manager for automatic cleanup
with CommandAGI(api_key="cagi_xxx...") as client:
    profiles = client.profiles.list()
```

### Profiles

```python
from commandagi import (
    ProfileCreateParams,
    ProfileUpdateParams,
    EvalParams,
)

# Create a profile
profile = client.profiles.create(ProfileCreateParams(
    project_id="project-id",
    name="profile-name",
    seed="optional initial description",
))

# Get a profile (includes constraints, exemplars, comparisons)
profile = client.profiles.get("profile-id")

# Update a profile (partial update)
updated = client.profiles.update("profile-id", ProfileUpdateParams(
    name="new-name",
))

# Delete a profile
client.profiles.delete("profile-id")

# List all profiles (optionally filter by project)
all_profiles = client.profiles.list()
project_profiles = client.profiles.list("project-id")

# Evaluate content
result = client.profiles.eval("profile-id", EvalParams(
    frame_url="https://example.com/image.jpg",
))
# result.score (0-1), result.confidence (0-1), result.details

# Export profile (full)
full_export = client.profiles.export("profile-id")

# Export profile (minimal — for inference)
minimal_export = client.profiles.export_minimal("profile-id")
```

## License

MIT
