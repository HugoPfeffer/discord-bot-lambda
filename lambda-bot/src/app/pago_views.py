"""Components V2 view builders for the pago (training presence) commands.

Visual language is CS2-flavored: orange/CT-blue/T-red accent colors, operative
rank tiers, fire-tier streak labels, and a header thumbnail re-using the
existing CS2 lobby icon (no fabricated asset URLs).
"""

from typing import Optional

IS_COMPONENTS_V2 = 1 << 15
EPHEMERAL = 64

INTERACTION_CALLBACK_TYPE_MESSAGE = 4

_HEADER_ICON = (
    "https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/"
    "main/images/lobby_mapveto.png"
)

_ACCENT_PAGO     = 0xDE9B35  # CS2 orange — successful op
_ACCENT_DESPAGO  = 0xFAA61A  # warning amber — undone
_ACCENT_PLACAR   = 0xFFC83D  # leaderboard gold
_ACCENT_DOSSIE   = 0x5887AB  # CT blue — personal dossier
_ACCENT_REMOVE   = 0xED4245  # T-side red — admin removal
_ACCENT_NEUTRAL  = 0x4F545C  # muted gray — empty/idle states


def _rank_tier(days: int) -> str:
    """CS-inspired Portuguese rank tier label for a given days_count."""
    if days <= 0:
        return "—"
    if days <= 2:
        return "🥈 Recruta"
    if days <= 6:
        return "🥇 Operativo"
    if days <= 14:
        return "🛡️ Veterano"
    if days <= 29:
        return "⚔️ Elite"
    if days <= 59:
        return "🦅 Comandante"
    return "🌟 Lendário"


def _streak_label(streak: int) -> Optional[str]:
    """Fire-tier badge for a streak. None when streak is too low to flex."""
    if streak < 2:
        return None
    if streak <= 4:
        return f"🔥 {streak}d · Aceso"
    if streak <= 9:
        return f"🔥🔥 {streak}d · Em chamas"
    if streak <= 19:
        return f"🔥🔥🔥 {streak}d · Inferno"
    return f"🔥🔥🔥🔥 {streak}d · Lendário"


def _header(title: str, subtitle: str) -> dict:
    return {
        "type": 9,
        "components": [
            {"type": 10, "content": f"# {title}"},
            {"type": 10, "content": subtitle},
        ],
        "accessory": {
            "type": 11,
            "media": {"url": _HEADER_ICON},
            "description": "CS2",
        },
    }


def _divider() -> dict:
    return {"type": 14, "divider": True, "spacing": 1}


def _container(accent: int, components: list[dict]) -> list[dict]:
    return [{"type": 17, "accent_color": accent, "components": components}]


def _placar_button() -> dict:
    return {
        "type": 1,
        "components": [
            {
                "type": 2,
                "style": 2,  # secondary
                "label": "Placar",
                "emoji": {"name": "🏆"},
                "custom_id": "pago:show_placar",
            }
        ],
    }


def _v2_response(components: list[dict], ephemeral: bool = False) -> dict:
    flags = IS_COMPONENTS_V2 | (EPHEMERAL if ephemeral else 0)
    return {
        "type": INTERACTION_CALLBACK_TYPE_MESSAGE,
        "data": {"flags": flags, "components": components},
    }


# -- Public response builders ------------------------------------------------

def pago_response(user_id: str, result: dict) -> dict:
    days   = int(result["days_count"])
    total  = int(result["total_pagos"])
    today  = int(result.get("today_sessions", 1))
    streak = int(result.get("streak", 0))
    is_new_day = bool(result.get("is_new_day"))

    title    = "✅ Treino Registrado" if is_new_day else "🎯 Sessão Extra"
    subtitle = (
        f"Operativo <@{user_id}> entrou em operação"
        if is_new_day
        else f"<@{user_id}> · sessão #{today} de hoje"
    )

    stats_lines = [
        f"📅 **Dia:** {days}",
        f"🎯 **Sessão total:** {total}",
        f"🎖️ **Patente:** {_rank_tier(days)}",
    ]
    streak_line = _streak_label(streak)
    if streak_line:
        stats_lines.append(streak_line)

    inner = [
        _header(title, subtitle),
        _divider(),
        {"type": 10, "content": "\n".join(stats_lines)},
        _divider(),
        _placar_button(),
    ]
    return _v2_response(_container(_ACCENT_PAGO, inner))


def despago_response(user_id: str, result: dict) -> dict:
    days  = int(result["days_count"])
    total = int(result["total_pagos"])
    today = int(result.get("today_sessions", 0))

    inner = [
        _header(
            "↩️ Operação Desfeita",
            f"<@{user_id}> reverteu o registro de hoje",
        ),
        _divider(),
        {"type": 10, "content": (
            f"📅 **Dias:** {days}\n"
            f"🎯 **Sessões totais:** {total}\n"
            f"📆 **Restantes hoje:** {today}"
        )},
    ]
    return _v2_response(_container(_ACCENT_DESPAGO, inner))


def despago_empty_response() -> dict:
    inner = [{"type": 10, "content": "ℹ️ Nada para desfazer hoje."}]
    return _v2_response(_container(_ACCENT_NEUTRAL, inner), ephemeral=True)


def placar_response(rows: list[dict], ephemeral: bool = False) -> dict:
    if not rows:
        inner = [
            _header(
                "🏆 Placar de Operativos",
                "Ainda não há treinos registrados.",
            ),
            _divider(),
            {"type": 10, "content": "Use **/pago** para entrar em operação."},
        ]
        return _v2_response(
            _container(_ACCENT_NEUTRAL, inner),
            ephemeral=ephemeral,
        )

    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    lines: list[str] = []
    for i, r in enumerate(rows):
        prefix  = medals.get(i, f"`#{i + 1:>2}`")
        days    = int(r.get("days_count", 0))
        total   = int(r.get("total_pagos", 0))
        streak  = int(r.get("streak", 0))
        streak_badge = f" · 🔥{streak}d" if streak >= 2 else ""
        lines.append(
            f"{prefix} <@{r['user_id']}> — **{days}** dias · "
            f"{total} sessões{streak_badge}"
        )

    inner = [
        _header(
            "🏆 Placar de Operativos",
            f"Top {len(rows)} · ranking por dias treinados",
        ),
        _divider(),
        {"type": 10, "content": "\n".join(lines)},
    ]
    return _v2_response(
        _container(_ACCENT_PLACAR, inner),
        ephemeral=ephemeral,
    )


def meu_pago_response(item: dict, rank: int) -> dict:
    days   = int(item.get("days_count", 0))
    total  = int(item.get("total_pagos", 0))
    today  = int(item.get("today_sessions", 0))
    streak = int(item.get("streak", 0))
    last   = item.get("last_pago_date") or "—"

    streak_line = _streak_label(streak) or f"🔥 Streak: {streak}d"

    inner = [
        _header(
            "📋 Seu Dossiê",
            f"Ranking **#{rank}** · {_rank_tier(days)}",
        ),
        _divider(),
        {"type": 10, "content": (
            f"📅 **Dias treinados:** {days}\n"
            f"🎯 **Sessões totais:** {total}\n"
            f"📆 **Sessões hoje:** {today}\n"
            f"🗓️ **Último treino:** {last}\n"
            f"{streak_line}"
        )},
        _divider(),
        _placar_button(),
    ]
    return _v2_response(
        _container(_ACCENT_DOSSIE, inner),
        ephemeral=True,
    )


def meu_pago_empty_response() -> dict:
    inner = [
        _header(
            "📋 Seu Dossiê",
            "Você ainda não tem treinos registrados.",
        ),
        _divider(),
        {"type": 10, "content": "Use **/pago** para entrar em operação."},
    ]
    return _v2_response(
        _container(_ACCENT_NEUTRAL, inner),
        ephemeral=True,
    )


def pago_remove_response(user_id: str, removed: bool) -> dict:
    if not removed:
        inner = [{"type": 10, "content": (
            f"ℹ️ <@{user_id}> não estava no placar."
        )}]
        return _v2_response(
            _container(_ACCENT_NEUTRAL, inner),
            ephemeral=True,
        )

    inner = [
        _header(
            "🚫 Operativo Removido",
            f"<@{user_id}> foi retirado do placar.",
        ),
    ]
    return _v2_response(
        _container(_ACCENT_REMOVE, inner),
        ephemeral=True,
    )
