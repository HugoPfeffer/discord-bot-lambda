import json
import logging
import os
import time

import requests as http_requests
from flask import Flask, jsonify, request
from mangum import Mangum
from asgiref.wsgi import WsgiToAsgi
from discord_interactions import verify_key_decorator

import db
from config import SLUG_TO_NAME, MAP_SLUGS
from dashboard import dashboard_response

DISCORD_PUBLIC_KEY = os.environ.get("DISCORD_PUBLIC_KEY")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

INTERACTION_CALLBACK_TYPE_PONG = 1
INTERACTION_CALLBACK_TYPE_MESSAGE = 4
INTERACTION_CALLBACK_TYPE_UPDATE = 7

EPHEMERAL = 64

logger = logging.getLogger("cs2-map-tracker")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_handler)

app = Flask(__name__)
asgi_app = WsgiToAsgi(app)
handler = Mangum(asgi_app)


def _log(action: str, interaction: dict, **extra):
    entry = {
        "action": action,
        "guild_id": interaction.get("guild_id"),
        "user_id": (interaction.get("member") or {}).get("user", {}).get("id"),
        "interaction_type": interaction.get("type"),
        **extra,
    }
    logger.info(json.dumps(entry))


def _ephemeral(content: str) -> dict:
    return {
        "type": INTERACTION_CALLBACK_TYPE_MESSAGE,
        "data": {"content": content, "flags": EPHEMERAL},
    }


def _public_message(content: str) -> dict:
    return {
        "type": INTERACTION_CALLBACK_TYPE_MESSAGE,
        "data": {"content": content},
    }


def _send_followup(interaction: dict, content: str):
    """Send a follow-up message via the interaction webhook."""
    app_id = interaction.get("application_id")
    token = interaction.get("token")
    url = f"https://discord.com/api/v10/webhooks/{app_id}/{token}"
    http_requests.post(url, json={"content": content}, timeout=5)


# -- Slash command handlers --------------------------------------------------

def _cmd_dashboard(interaction: dict) -> dict:
    guild_id = interaction["guild_id"]
    state = db.get_state(guild_id)
    _log("dashboard", interaction)
    return dashboard_response(state, INTERACTION_CALLBACK_TYPE_MESSAGE)


def _cmd_played(interaction: dict) -> dict:
    guild_id = interaction["guild_id"]
    slug = interaction["data"]["options"][0]["value"]
    name = SLUG_TO_NAME.get(slug, slug)

    state = db.get_state(guild_id)
    if slug in state["played"]:
        _log("played_noop", interaction, map=slug)
        return _ephemeral(f"**{name}** is already marked as played.")

    state = db.mark_played(guild_id, slug)
    _log("played", interaction, map=slug)

    if len(state["played"]) >= len(MAP_SLUGS):
        cycle_num = state["cycle_number"]
        db.reset_cycle(guild_id)
        _send_followup(
            interaction,
            f"\U0001f389 All {len(MAP_SLUGS)} maps played \u2014 new cycle started! (cycle #{cycle_num + 1})",
        )
        return _public_message(
            f"\u2705 **{name}** marked as played \u2014 that completes the cycle!"
        )

    return _public_message(f"\u2705 **{name}** marked as played.")


def _cmd_remaining(interaction: dict) -> dict:
    guild_id = interaction["guild_id"]
    state = db.get_state(guild_id)
    remaining = [SLUG_TO_NAME[s] for s in MAP_SLUGS if s not in state["played"]]
    _log("remaining", interaction)

    if not remaining:
        return _ephemeral("All maps have been played this cycle!")

    lines = "\n".join(f"\u2022 {m}" for m in remaining)
    return _ephemeral(f"**Remaining ({len(remaining)}):**\n{lines}")


def _cmd_history(interaction: dict) -> dict:
    guild_id = interaction["guild_id"]
    state = db.get_state(guild_id)
    order = state.get("played_order") or []
    _log("history", interaction)

    if not order:
        return _ephemeral("No maps played yet this cycle.")

    lines = "\n".join(f"{i+1}. {SLUG_TO_NAME.get(s, s)}" for i, s in enumerate(order))
    return _ephemeral(f"**Played this cycle ({len(order)}):**\n{lines}")


def _cmd_undo(interaction: dict) -> dict:
    guild_id = interaction["guild_id"]
    state, undone = db.undo_last(guild_id)
    _log("undo", interaction, map=undone)

    if undone is None:
        return _ephemeral("Nothing to undo \u2014 no maps have been played this cycle.")

    name = SLUG_TO_NAME.get(undone, undone)
    return _public_message(f"\u21a9\ufe0f **{name}** unmarked (undo).")


def _cmd_unmark(interaction: dict) -> dict:
    guild_id = interaction["guild_id"]
    slug = interaction["data"]["options"][0]["value"]
    name = SLUG_TO_NAME.get(slug, slug)

    state = db.get_state(guild_id)
    if slug not in state["played"]:
        _log("unmark_noop", interaction, map=slug)
        return _ephemeral(f"**{name}** is not marked as played.")

    db.unmark_map(guild_id, slug)
    _log("unmark", interaction, map=slug)
    return _public_message(f"\u21a9\ufe0f **{name}** unmarked.")


def _cmd_reset(interaction: dict) -> dict:
    guild_id = interaction["guild_id"]
    _log("reset_prompt", interaction)
    return {
        "type": INTERACTION_CALLBACK_TYPE_MESSAGE,
        "data": {
            "content": "Are you sure you want to reset the current cycle?",
            "flags": EPHEMERAL,
            "components": [
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 2,
                            "style": 4,
                            "label": "Confirm Reset",
                            "custom_id": "reset_confirm:yes",
                        },
                        {
                            "type": 2,
                            "style": 2,
                            "label": "Cancel",
                            "custom_id": "reset_confirm:no",
                        },
                    ],
                }
            ],
        },
    }


_COMMAND_HANDLERS = {
    "dashboard": _cmd_dashboard,
    "played": _cmd_played,
    "remaining": _cmd_remaining,
    "history": _cmd_history,
    "undo": _cmd_undo,
    "unmark": _cmd_unmark,
    "reset": _cmd_reset,
}


# -- Component interaction handlers ------------------------------------------

def _handle_map_toggle(interaction: dict, slug: str) -> dict:
    guild_id = interaction["guild_id"]
    state, cycle_completed = db.toggle_map(guild_id, slug)
    name = SLUG_TO_NAME.get(slug, slug)
    _log("map_toggle", interaction, map=slug, cycle_completed=cycle_completed)

    if cycle_completed:
        completed_cycle = state.get("_completed_cycle", "?")
        _send_followup(
            interaction,
            f"\U0001f389 All {len(MAP_SLUGS)} maps played \u2014 new cycle started! (cycle #{state['cycle_number']})",
        )

    return dashboard_response(state, INTERACTION_CALLBACK_TYPE_UPDATE)


def _handle_reset_confirm(interaction: dict, action: str) -> dict:
    if action == "no":
        _log("reset_cancel", interaction)
        return {
            "type": INTERACTION_CALLBACK_TYPE_UPDATE,
            "data": {"content": "Reset cancelled.", "components": []},
        }

    guild_id = interaction["guild_id"]
    state = db.reset_cycle(guild_id)
    _log("reset_confirmed", interaction)

    _send_followup(
        interaction,
        f"\U0001f504 Cycle manually reset \u2014 starting cycle #{state['cycle_number']}.",
    )

    return {
        "type": INTERACTION_CALLBACK_TYPE_UPDATE,
        "data": {"content": "Cycle reset.", "components": []},
    }


def _route_component(interaction: dict) -> dict:
    custom_id = interaction["data"]["custom_id"]

    if custom_id.startswith("map_toggle:"):
        slug = custom_id.split(":", 1)[1]
        if slug in MAP_SLUGS:
            return _handle_map_toggle(interaction, slug)

    if custom_id.startswith("reset_confirm:"):
        action = custom_id.split(":", 1)[1]
        return _handle_reset_confirm(interaction, action)

    return _ephemeral("Unknown interaction.")


# -- Main router --------------------------------------------------------------

@app.route("/", methods=["POST"])
async def interactions():
    raw_request = request.json
    return interact(raw_request)


@verify_key_decorator(DISCORD_PUBLIC_KEY)
def interact(raw_request):
    start = time.time()
    interaction_type = raw_request["type"]

    try:
        if interaction_type == 1:
            return jsonify({"type": INTERACTION_CALLBACK_TYPE_PONG})

        if interaction_type == 2:
            command_name = raw_request["data"]["name"]
            handler_fn = _COMMAND_HANDLERS.get(command_name)
            if handler_fn:
                result = handler_fn(raw_request)
            else:
                result = _ephemeral(f"Unknown command: {command_name}")

        elif interaction_type == 3:
            result = _route_component(raw_request)

        else:
            result = _ephemeral("Unsupported interaction type.")

    except Exception:
        logger.exception("Unhandled error in interaction handler")
        result = _ephemeral("Something went wrong. Please try again.")

    duration_ms = int((time.time() - start) * 1000)
    _log("response", raw_request, duration_ms=duration_ms)

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
