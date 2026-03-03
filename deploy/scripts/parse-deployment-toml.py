#!/usr/bin/env python3
"""Parse a Posit deployment TOML file and output configuration for GitHub Actions."""

import os
import toml

deployment_file = os.environ["DEPLOYMENT_FILE"]

with open(deployment_file) as f:
    data = toml.load(f)

server_url = data.get("server_url", "")
content_guid = data.get("id", "")

config = data.get("configuration", {})
entrypoint = config.get("entrypoint", "")

print(f"connect_server={server_url}")
print(f"content_guid={content_guid}")
print(f"entrypoint={entrypoint}")
