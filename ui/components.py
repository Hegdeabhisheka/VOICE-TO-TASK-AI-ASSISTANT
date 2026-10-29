"""Reusable Streamlit components: gauge, task cards, KPIs, banners, charts, transcript bubbles."""
from __future__ import annotations

import html
from collections import Counter
from datetime import datetime, timedelta

import plotly.graph_objects as go
import streamlit as st

from core import config
from core.automation import format_deadline

PRIORITY_COLORS = {"low": "#3b82f6", "medium": "#00e5ff", "high": "#ffb300", "urgent": "#ff3b5c"}
CATEGORY_COLORS = {"work": "#3b82f6", "personal": "#ff3df2", "study": "#8b5cf6", "health": "#39ff14",
                   "shopping": "#ffb300", "finance": "#00e5ff", "other": "#64748b"}
CATEGORY_ICONS = {"work": "💼", "personal": "🏠", "study": "📚", "health": "💪",
                  "shopping": "🛒", "finance": "💳", "other": "📌"}
_MIC_LABELS = {"idle": "Ready", "listening": "Listening", "processing": "Thinking",
               "success": "Done", "error": "Try again"}


def _esc(text: object) -> str:
    """HTML-escape any value; newlines become <br>."""
    return html.escape("" if text is None else str(text)).replace("\n", "<br>")


def _style(fig: go.Figure, height: int, top: int = 40) -> go.Figure:
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#e2e8f0"), margin=dict(l=10, r=10, t=top, b=10), height=height,
                      transition={"duration": 800, "easing": "cubic-in-out"})
    fig.update_xaxes(gridcolor="rgba(255,255,255,.08)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,.08)", zeroline=False)
    return fig


def _empty_figure(message: str, height: int = 300) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(size=15, color="#93a0c8"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _style(fig, height)


def show_plot(fig: go.Figure, key: str | None = None) -> None:
    """Render a Plotly figure full-width. Keep `key` stable so the gauge animates between reruns."""
    config_ = {"displayModeBar": False}
    try:
        st.plotly_chart(fig, use_container_width=True, config=config_, key=key)
    except TypeError:  # newer Streamlit versions replaced use_container_width
        st.plotly_chart(fig, width="stretch", config=config_, key=key)


def score_gauge(score_dict: dict) -> go.Figure:
    """Plotly gauge for the Interaction Score (eases to new values when re-rendered with a stable key)."""
    score = int(score_dict.get("score", 0) or 0)
    color = score_dict.get("color", "#00e5ff")
    title = (f"{_esc(score_dict.get('level', 'Dormant'))}<br>"
             f"<span style='font-size:0.75em;color:#93a0c8'>{_esc(score_dict.get('label', ''))}</span>")
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        number={"font": {"size": 56, "color": color}},
        title={"text": title, "font": {"size": 18, "color": "#e6ebff"}},
        gauge={"axis": {"range": [0, 100], "tickcolor": "#64748b", "tickvals": [0, 25, 50, 75, 100]},
               "bar": {"color": color, "thickness": 0.32}, "bgcolor": "rgba(255,255,255,.05)", "borderwidth": 0,
               "steps": [{"range": [0, 25], "color": "rgba(139,92,246,.20)"},
                         {"range": [25, 50], "color": "rgba(0,229,255,.16)"},
                         {"range": [50, 75], "color": "rgba(255,179,0,.16)"},
                         {"range": [75, 100], "color": "rgba(57,255,20,.18)"}],
               "threshold": {"line": {"color": color, "width": 3}, "thickness": 0.8, "value": score}}))
    return _style(fig, 270, top=80)


def task_card(task: dict) -> str:
    """HTML card for one task: priority chip, category, due badge, overdue/done styling."""
    priority = task.get("priority", "medium")
    if priority not in config.PRIORITIES:
        priority = "medium"
    classes = ["task-card", f"pr-{priority}"]
    if task.get("overdue"):
        classes.append("overdue")
    if task.get("status") == "done":
        classes.append("done")
    category = task.get("category", "other")
    chips = [f'<span class="chip pr-{priority}">{_esc(priority)}</span>',
             f'<span class="chip">{CATEGORY_ICONS.get(category, "📌")} {_esc(category)}</span>']
    deadline = task.get("deadline")
    if task.get("status") == "done":
        chips.append('<span class="chip done">✓ done</span>')
    elif isinstance(deadline, datetime):
        late = task.get("overdue")
        text = ("Overdue · " if late else "⏰ ") + format_deadline(deadline)
        chips.append(f'<span class="chip{" due-late" if late else ""}">{_esc(text)}</span>')
    return (f'<div class="{" ".join(classes)}"><div class="task-title">{_esc(task.get("title", ""))}</div>'
            f'<div class="task-meta">{"".join(chips)}</div></div>')


def kpi_row(stats: dict) -> None:
    """Render five KPI cards: pending, due today, overdue, done, streak."""
    overdue = int(stats.get("overdue", 0) or 0)
    items = [("📋", stats.get("pending", 0), "Pending", ""),
             ("📅", stats.get("due_today", 0), "Due today", ""),
             ("⚠️", overdue, "Overdue", "late" if overdue else ""),
             ("✅", stats.get("done", 0), "Done", ""),
             ("🔥", f"{int(stats.get('streak_days', 0) or 0)}d", "Streak", "")]
    for col, (icon, value, label, cls) in zip(st.columns(len(items)), items):
        col.markdown(f'<div class="kpi {cls}"><div class="kpi-icon">{icon}</div>'
                     f'<div class="kpi-value">{_esc(value)}</div><div class="kpi-label">{label}</div></div>',
                     unsafe_allow_html=True)


def command_result_banner(result: object) -> None:
    """Render a green (ok) or red (not ok) banner from an executor.Result (any object with ok/message)."""
    ok = bool(getattr(result, "ok", False))
    message = getattr(result, "message", "") or ("Done." if ok else "That didn't work.")
    st.markdown(f'<div class="banner {"ok" if ok else "err"}"><span class="icon">{"✅" if ok else "⚠️"}</span>'
                f'<span>{_esc(message)}</span></div>', unsafe_allow_html=True)


def timeline_chart(tasks: list[dict]) -> go.Figure:
    """Upcoming deadlines of pending tasks on a time axis (one lane per category, coloured by priority)."""
    rows = sorted((t for t in tasks if isinstance(t.get("deadline"), datetime) and t.get("status") != "done"),
                  key=lambda t: t["deadline"])[:40]
    if not rows:
        return _empty_figure("No scheduled tasks yet. Add one with a deadline!", 360)
    fig = go.Figure()
    for priority in config.PRIORITIES:
        subset = [t for t in rows if t.get("priority") == priority]
        if not subset:
            continue
        fig.add_trace(go.Scatter(
            x=[t["deadline"] for t in subset], y=[t.get("category", "other") for t in subset],
            mode="markers", name=priority.title(), text=[t["title"] for t in subset],
            customdata=[format_deadline(t["deadline"]) for t in subset],
            hovertemplate="<b>%{text}</b><br>%{customdata}<extra></extra>",
            marker=dict(size=17, symbol="diamond", color=PRIORITY_COLORS[priority],
                        line=dict(width=1, color="#0b1030"))))
    now = datetime.now()
    first, last = min(now, rows[0]["deadline"]), max(now, rows[-1]["deadline"])
    pad = max(timedelta(hours=2), (last - first) * 0.08)
    fig.update_xaxes(range=[first - pad, last + pad])
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(config.CATEGORIES)))
    fig.add_shape(type="line", x0=now, x1=now, y0=0, y1=1, xref="x", yref="paper",
                  line=dict(color="#f8fafc", width=1, dash="dot"))
    fig.add_annotation(x=now, y=1, yref="paper", text="now", showarrow=False, yshift=10,
                       font=dict(color="#f8fafc"))
    fig.update_layout(legend=dict(orientation="h", y=-0.15), title="Upcoming deadlines")
    return _style(fig, 380, top=50)


def category_donut(tasks: list[dict]) -> go.Figure:
    """Donut chart of tasks per category."""
    counts = Counter(t.get("category", "other") for t in tasks)
    if not counts:
        return _empty_figure("No tasks yet")
    names = [c for c in config.CATEGORIES if c in counts] + [c for c in counts if c not in config.CATEGORIES]
    fig = go.Figure(go.Pie(labels=[n.title() for n in names], values=[counts[n] for n in names], hole=0.58,
                           marker=dict(colors=[CATEGORY_COLORS.get(n, "#64748b") for n in names],
                                       line=dict(color="#0b1030", width=2)),
                           textinfo="label+value", sort=False))
    fig.update_layout(title="Tasks by category", showlegend=False)
    return _style(fig, 320)


def transcript_bubble(text: str, confidence: float) -> str:
    """HTML bubble showing what was heard, with a confidence meter (green / amber / red)."""
    try:
        conf = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        conf = 0.0
    color = "#39ff14" if conf >= 0.8 else "#ffb300" if conf >= config.MIN_COMMAND_CONFIDENCE else "#ff3b5c"
    return (f'<div class="bubble">🗣️ {_esc(text) or "<i>(nothing heard)</i>"}'
            f'<div class="meta"><span class="meter"><span style="width:{conf * 100:.0f}%;background:{color}"></span></span>'
            f'<span>{conf:.0%} confident</span></div></div>')


def mic_badge(state: str = "idle") -> str:
    """HTML for the pulsing mic badge; `state` is idle | listening | processing | success | error."""
    state = state if state in _MIC_LABELS else "idle"
    return (f'<div class="mic-row"><div class="mic-badge {state}">🎙️</div>'
            f'<span class="mic-label">{_MIC_LABELS[state]}</span></div>')