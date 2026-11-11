"""Token and cost meter, per agent and per run, plus a daily budget for the whole app."""
import datetime as dt
import threading
from dataclasses import dataclass, field

from .settings import DAILY_TOKEN_BUDGET, PRICES_PER_1M


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES_PER_1M.get(model, (0.0, 0.0))
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


@dataclass
class CostMeter:
    rows: dict = field(default_factory=dict)          # agent -> {model, calls, input, output, usd}
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, agent: str, model: str, input_tokens: int, output_tokens: int):
        with self._lock:
            r = self.rows.setdefault(agent, dict(model=model, calls=0, input_tokens=0, output_tokens=0, usd=0.0))
            r["calls"] += 1
            r["input_tokens"] += input_tokens
            r["output_tokens"] += output_tokens
            r["usd"] += cost_usd(model, input_tokens, output_tokens)
        DAILY_BUDGET.spend(input_tokens + output_tokens)

    @property
    def total_tokens(self) -> int:
        return sum(r["input_tokens"] + r["output_tokens"] for r in self.rows.values())

    @property
    def total_usd(self) -> float:
        return sum(r["usd"] for r in self.rows.values())

    def table(self) -> list:
        out = [dict(agent=a, **r) for a, r in self.rows.items()]
        out.append(dict(agent="TOTAL", model="", calls=sum(r["calls"] for r in self.rows.values()),
                        input_tokens=sum(r["input_tokens"] for r in self.rows.values()),
                        output_tokens=sum(r["output_tokens"] for r in self.rows.values()), usd=self.total_usd))
        return out


class _DailyBudget:
    """Process-wide token budget; resets each UTC day. Stops runaway spend if the app is abused."""

    def __init__(self, limit: int):
        self.limit, self.used, self.day = limit, 0, dt.datetime.now(dt.timezone.utc).date()
        self._lock = threading.Lock()

    def _roll(self):
        today = dt.datetime.now(dt.timezone.utc).date()
        if today != self.day:
            self.day, self.used = today, 0

    def spend(self, tokens: int):
        with self._lock:
            self._roll()
            self.used += tokens

    def remaining(self) -> int:
        with self._lock:
            self._roll()
            return max(self.limit - self.used, 0)


DAILY_BUDGET = _DailyBudget(DAILY_TOKEN_BUDGET)
