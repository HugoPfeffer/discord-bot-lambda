import json
import logging
import os
import time

from flask import Flask, jsonify, request
from mangum import Mangum
from asgiref.wsgi import WsgiToAsgi
from discord_interactions import verify_key_decorator

import db
import pago
from config import SLUG_TO_NAME, MAP_SLUGS
from dashboard import build_dashboard_components, dashboard_response, IS_COMPONENTS_V2

DISCORD_PUBLIC_KEY = os.environ.get("DISCORD_PUBLIC_KEY")

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
handler = Mangum(asgi_app, lifespan="off")


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
        state = db.reset_cycle(guild_id)
        return _public_message(
            f"\u2705 **{name}** marked as played \u2014 that completes the cycle!\n"
            f"\U0001f389 All {len(MAP_SLUGS)} maps played \u2014 new cycle started! (cycle #{state['cycle_number']})"
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


def _cmd_pago(interaction: dict) -> dict:
    guild_id = interaction["guild_id"]
    user = interaction["member"]["user"]
    user_id = user["id"]
    username = user.get("global_name") or user["username"]
    result = pago.record_pago(guild_id, user_id, username)
    _log("pago", interaction,
         days=result["days_count"], total=result["total_pagos"],
         streak=result["streak"], is_new_day=result["is_new_day"])
    streak = int(result["streak"])
    streak_suffix = f" \U0001f525 {streak}d" if streak >= 2 else ""
    return _public_message(
        f"✅ <@{user_id}> marcou treino — dia {result['days_count']}, "
        f"sessão {result['total_pagos']} no total.{streak_suffix}"
    )


def _cmd_despago(interaction: dict) -> dict:
    guild_id = interaction["guild_id"]
    user = interaction["member"]["user"]
    user_id = user["id"]
    result = pago.undo_pago(guild_id, user_id)
    _log("despago", interaction, undone=result is not None)
    if result is None:
        return _ephemeral("Nada para desfazer hoje.")
    return _public_message(
        f"↩️ <@{user_id}> desfez um /pago — "
        f"agora {result['days_count']} dias, {result['total_pagos']} sessões."
    )


def _cmd_placar(interaction: dict) -> dict:
    guild_id = interaction["guild_id"]
    rows = pago.get_leaderboard(guild_id, limit=10)
    _log("placar", interaction, count=len(rows))
    if not rows:
        return _public_message(
            "Ainda não há treinos registrados. Use /pago para começar!"
        )
    lines = [
        f"{i+1}. <@{r['user_id']}> — {r['days_count']} dias ({r['total_pagos']} sessões)"
        for i, r in enumerate(rows)
    ]
    return _public_message("\U0001f3c6 **Placar de Treino**\n" + "\n".join(lines))


def _cmd_meu_pago(interaction: dict) -> dict:
    guild_id = interaction["guild_id"]
    user = interaction["member"]["user"]
    user_id = user["id"]
    item, rank = pago.get_user_rank(guild_id, user_id)
    _log("meu_pago", interaction, rank=rank)
    if item is None:
        return _ephemeral("Você ainda não tem treinos registrados. Use /pago!")
    streak = int(item.get("streak", 0))
    streak_line = f"\n\U0001f525 Streak: {streak} dias" if streak >= 2 else ""
    return _ephemeral(
        f"**Sua posição:** #{rank}\n"
        f"Dias: {item['days_count']} · Sessões: {item['total_pagos']}"
        f"{streak_line}"
    )


def _cmd_pago_remove(interaction: dict) -> dict:
    guild_id = interaction["guild_id"]
    # Discord enforces the ADMINISTRATOR permission via default_member_permissions
    # on the command itself; no in-code permission check needed.
    target_user_id = interaction["data"]["options"][0]["value"]
    removed = pago.remove_user(guild_id, target_user_id)
    _log("pago_remove", interaction, target=target_user_id, removed=removed)
    if not removed:
        return _ephemeral(f"<@{target_user_id}> não estava no placar.")
    return _ephemeral(f"<@{target_user_id}> removido do placar.")


_COMMAND_HANDLERS = {
    "dashboard": _cmd_dashboard,
    "played": _cmd_played,
    "remaining": _cmd_remaining,
    "history": _cmd_history,
    "undo": _cmd_undo,
    "unmark": _cmd_unmark,
    "reset": _cmd_reset,
    "pago": _cmd_pago,
    "despago": _cmd_despago,
    "placar": _cmd_placar,
    "meu-pago": _cmd_meu_pago,
    "pago-remove": _cmd_pago_remove,
}


# -- Component interaction handlers ------------------------------------------

def _handle_map_toggle(interaction: dict, slug: str) -> dict:
    guild_id = interaction["guild_id"]
    state, cycle_completed = db.toggle_map(guild_id, slug)
    _log("map_toggle", interaction, map=slug, cycle_completed=cycle_completed)

    if cycle_completed:
        components = build_dashboard_components(state)
        celebration = {
            "type": 10,
            "content": (
                f"\U0001f389 All {len(MAP_SLUGS)} maps played \u2014 "
                f"new cycle started! (cycle #{state['cycle_number']})"
            ),
        }
        components[0]["components"].insert(0, celebration)
        return {
            "type": INTERACTION_CALLBACK_TYPE_UPDATE,
            "data": {"flags": IS_COMPONENTS_V2, "components": components},
        }

    return dashboard_response(state, INTERACTION_CALLBACK_TYPE_UPDATE)


def _handle_reset_confirm(interaction: dict, action: str) -> dict:
    if action == "no":
        _log("reset_cancel", interaction)
        return {
            "type": INTERACTION_CALLBACK_TYPE_UPDATE,
            "data": {"content": "Reset cancelled.", "components": []},
        }

    if action != "yes":
        return _ephemeral("Unknown action.")

    guild_id = interaction["guild_id"]
    state = db.reset_cycle(guild_id)
    _log("reset_confirmed", interaction)

    return {
        "type": INTERACTION_CALLBACK_TYPE_UPDATE,
        "data": {
            "content": f"\U0001f504 Cycle manually reset \u2014 starting cycle #{state['cycle_number']}.",
            "components": [],
        },
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
