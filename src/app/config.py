import os
import yaml

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "maps.yaml")

with open(_CONFIG_PATH, "r") as f:
    _raw = yaml.safe_load(f)

MAP_POOL = _raw["active_duty"]
MAP_SLUGS = [m["slug"] for m in MAP_POOL]
SLUG_TO_NAME = {m["slug"]: m["name"] for m in MAP_POOL}
NAME_TO_SLUG = {m["name"]: m["slug"] for m in MAP_POOL}
