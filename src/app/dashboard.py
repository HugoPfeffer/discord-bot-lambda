from config import MAP_POOL, SLUG_TO_NAME

IS_COMPONENTS_V2 = 1 << 15

_BUTTON_STYLE_SUCCESS = 3
_BUTTON_STYLE_SECONDARY = 2


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


def build_dashboard_components(state: dict) -> list[dict]:
    played = state.get("played") or set()
    cycle = state.get("cycle_number", 1)

    remaining_slugs = [m["slug"] for m in MAP_POOL if m["slug"] not in played]
    played_slugs = [m["slug"] for m in MAP_POOL if m["slug"] in played]

    num_played = len(played_slugs)
    total = len(MAP_POOL)

    components: list[dict] = [
        {"type": 10, "content": "\U0001f3af **CS2 Map Night**"},
        {"type": 10, "content": f"{num_played} of {total} played \u00b7 cycle #{cycle}"},
        {"type": 14, "divider": True, "spacing": 1},
    ]

    components.append({"type": 10, "content": f"**Remaining ({len(remaining_slugs)}):**"})
    if remaining_slugs:
        for row in _chunk(remaining_slugs):
            components.append({
                "type": 1,
                "components": [_map_button(s, False) for s in row],
            })
    else:
        components.append({"type": 10, "content": "*None -- all maps played!*"})

    components.append({"type": 14, "divider": True, "spacing": 1})

    components.append({"type": 10, "content": f"**Played ({len(played_slugs)}):**"})
    if played_slugs:
        for row in _chunk(played_slugs):
            components.append({
                "type": 1,
                "components": [_map_button(s, True) for s in row],
            })
    else:
        components.append({"type": 10, "content": "*None yet -- pick a map!*"})

    return components


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
