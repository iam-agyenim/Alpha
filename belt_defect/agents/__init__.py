"""Multi-agent layer on top of the trained belt-defect model.

Specialist agents (OpenAI models) call read-only tools that return the trained model's predictions and
training-data statistics; a lead agent merges their findings into one action plan.
"""
from .team import SPECIALISTS, LEAD, answer_question, make_client, run_briefing  # noqa: F401
