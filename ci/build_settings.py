#!/usr/bin/env python3
"""Print validated Docker build inputs, one per line."""
import json
from image_key import ROOT, image_key

stack = json.loads((ROOT / "ci/stack.json").read_text())
for value in (image_key(), stack["bench_version"], stack["python_image"], stack["node_image"]):
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise ValueError("Invalid CI build setting.")
    print(value)
