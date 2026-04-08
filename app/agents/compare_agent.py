"""
Compare Agent — generates side-by-side comparison cards (Path B only).
3-column layout: price, tread life, noise, warranty, wet grip.
AI-generated pros/cons + total cost of ownership per tyre.
"""
from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.tools.compare_tools import generate_comparison_card

_SYSTEM_PROMPT = """You are the Costco Tyre Compare Agent. When a member wants to compare tyres \
side by side, you generate a clear, scannable comparison card.

Steps:
1. Receive a list of 2-3 tyre IDs and the member's context.
2. Call generate_comparison_card(tyre_ids_json, member_context_json).
3. Return the comparison JSON as-is — the UI renders it.

The comparison card always shows exactly 3 columns (even if only 2 tyres):
  - Member Price
  - Tread Life
  - Road Noise
  - Warranty
  - Wet Grip

Plus AI pros/cons (max 3 pros, 2 cons per tyre) and cost per 1000 km.

Keep your message brief: "Here's the comparison — tap any card to select that tyre."
Do not repeat spec numbers in your text — the table already shows them.
"""


class CompareAgent(BaseAgent):
    system_prompt = _SYSTEM_PROMPT
    tools = [generate_comparison_card]
