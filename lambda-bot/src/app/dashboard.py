from config import MAP_POOL, SLUG_TO_NAME, SLUG_TO_THUMB

IS_COMPONENTS_V2 = 1 << 15

_BUTTON_STYLE_SUCCESS = 3
_BUTTON_STYLE_SECONDARY = 2

_ACCENT_COLOR = 0xDE9B35
_HEADER_ICON = "https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/lobby_mapveto.png"


def _chunk(items, size=5):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _map_button(slug: str, played: bool) -> dict:
    name = SLUG_TO_NAME[slug]
    return {
        "type": 2,
        "style": _BUTTON_STYLE_SECONDARY if played else _BUTTON_STYLE_SUCCESS,
        "label": f"\u2713 {name}" if played else name,
        "custom_id": f"map_toggle:{slug}",
    }


def _map_gallery(slugs: list[str]) -> dict:
    """Media Gallery showing map thumbnails. Items don't count toward the 40-component cap."""
    return {
        "type": 12,
        "items": [
            {
                "media": {"url": SLUG_TO_THUMB[slug]},
                "description": SLUG_TO_NAME[slug],
            }
            for slug in slugs
        ],
    }


def build_dashboard_components(state: dict) -> list[dict]:
    played = state.get("played") or set()
    cycle = state.get("cycle_number", 1)

    remaining_slugs = [m["slug"] for m in MAP_POOL if m["slug"] not in played]
    played_slugs = [m["slug"] for m in MAP_POOL if m["slug"] in played]

    num_played = len(played_slugs)
    total = len(MAP_POOL)

    inner: list[dict] = []

    inner.append({
        "type": 9,
        "components": [
            {"type": 10, "content": "# CS2 Map Night"},
            {"type": 10, "content": f"{num_played} of {total} played \u00b7 cycle #{cycle}"},
        ],
        "accessory": {
            "type": 11,
            "media": {"url": _HEADER_ICON},
            "description": "CS2",
        },
    })

    inner.append({"type": 14, "divider": True, "spacing": 1})

    inner.append({"type": 10, "content": f"**Remaining ({len(remaining_slugs)}):**"})
    if remaining_slugs:
        inner.append(_map_gallery(remaining_slugs))
        for row in _chunk(remaining_slugs):
            inner.append({
                "type": 1,
                "components": [_map_button(s, False) for s in row],
            })
    else:
        inner.append({"type": 10, "content": "*None \u2014 all maps played!*"})

    inner.append({"type": 14, "divider": True, "spacing": 1})

    inner.append({"type": 10, "content": f"**Played ({len(played_slugs)}):**"})
    if played_slugs:
        for row in _chunk(played_slugs):
            inner.append({
                "type": 1,
                "components": [_map_button(s, True) for s in row],
            })
    else:
        inner.append({"type": 10, "content": "*None yet \u2014 pick a map!*"})

    return [{
        "type": 17,
        "accent_color": _ACCENT_COLOR,
        "components": inner,
    }]


def dashboard_response(state: dict, response_type: int = 4) -> dict:
    """Build a full interaction response containing the dashboard.

    response_type 4 = CHANNEL_MESSAGE_WITH_SOURCE (new message)
    response_type 7 = UPDATE_MESSAGE (edit in place)
    """
    return {
        "type": response_type,
        "data": {
            "flags": IS_COMPONENTS_V2,
            "components": build_dashboard_components(state),
        },
    }
