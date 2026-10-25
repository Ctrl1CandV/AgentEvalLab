`drop_unused_requests` not respecting `filter_headers`

Where `Cassette.play_response` appends to its interactions: https://github.com/kevin1024/vcrpy/blob/v8.1.0/vcr/cassette.py#L266

Is not taking into account filtered headers. This leads to authorization headers leaking into the cassette.

Here is a minimal reproducer with `aiohttp==3.13.2`, `vcrpy==8.1.0`, `pytest==9`, `pyyaml==6.0.3`:

```python
import pathlib

import aiohttp
import pytest
import vcr
import yaml

BASE_URL = "https://api.github.com/"


@pytest.mark.asyncio
async def test_drop_unused_requests_leaks_filtered_headers(tmpdir) -> None:
    cassette_path = pathlib.Path(tmpdir / "test.yaml")
    vcr_instance = vcr.VCR(
        record_mode="new_episodes", match_on=["method", "host", "path"]
    )

    # Step 1: Record a cassette with multiple interactions with auth headers
    with vcr_instance.use_cassette(
        cassette_path, filter_headers=[("authorization", None)]
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                BASE_URL, headers={"Authorization": "Bearer SECRET_TOKEN_12345"}
            ) as response:
                await response.text()
            async with session.get(
                f"{BASE_URL}/zen",
                headers={"Authorization": "Bearer SECRET_TOKEN_12345"},
            ) as response:
                await response.text()

    # Verify step 1: Cassette was created with 2 interactions and auth was filtered
    with cassette_path.open(encoding="utf-8") as f:
        cassette_data = yaml.safe_load(f)
    assert len(cassette_data["interactions"]) == 2
    for i, interaction in enumerate(cassette_data["interactions"]):
        assert "authorization" not in str(interaction["request"]["headers"]).lower(), (
            f"Authorization should be filtered during recording (interaction {i})"
        )

    # Step 2: Play back one interaction with drop_unused_requests=True,
    # dropping an unused request
    with vcr_instance.use_cassette(
        cassette_path,
        filter_headers=[("authorization", None)],
        drop_unused_requests=True,  # This triggers the bug!
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                BASE_URL, headers={"Authorization": "Bearer SECRET_TOKEN_12345"}
            ) as response:
                await response.text()

    # Verify step 2: One request was dropped, was auth filtered?
    with cassette_path.open(encoding="utf-8") as f:
        cassette_data = yaml.safe_load(f)
    # This assertion will fail due to the bug
    assert (
        "authorization"
        not in str(cassette_data["interactions"][0]["request"]["headers"]).lower()
    ), (
        "BUG: Authorization header leaked into cassette after playback "
        "with drop_unused_requests=True"
    )
```
