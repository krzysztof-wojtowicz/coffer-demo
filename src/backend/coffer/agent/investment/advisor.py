"""Investment advisor: tool calling over market data with a deterministic fallback.

Tool calling is done through structured output so that it works with any `LLMClient`:
each step the model returns either
`{"action": "call_tool", "tool": ..., "args": {...}}` or `{"action": "final", "answer": {...}}`.
Only aggregates reach the model: asset-class shares, symbols and the risk profile.
"""

import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from coffer.agent import service as agent_service
from coffer.agent.investment.schemas import AdviceOut, HoldingIn, TipOut, TopPickOut
from coffer.agent.llm import (
    LLMClient,
    LLMMessage,
    LLMTimeout,
    LLMUnavailable,
    llm_deadline,
    remaining_s,
)
from coffer.analytics.portfolio import HoldingInput, portfolio_summary
from coffer.core.config import get_settings
from coffer.market import service as market
from coffer.market.tools import MARKET_TOOLS, ToolError, call_tool

log = logging.getLogger(__name__)

MAX_STEPS = 4
TASK = "advisor"  # agent_runs.task; matches the planned CHECK list in docs/data-model.md 2.8
PROMPT_VERSION = "advisor_v1"
PICKS = 3
TIPS = 3

CLASS_ALIASES = {
    "stock": "stock",
    "stocks": "stock",
    "akcje": "stock",
    "etf": "etf",
    "bond": "bond",
    "bonds": "bond",
    "obligacje": "bond",
    "cash": "cash",
    "deposit": "cash",
    "lokata": "cash",
    "gotowka": "cash",
    "gotówka": "cash",
    "real_estate": "real_estate",
    "reit": "real_estate",
    "nieruchomosci": "real_estate",
    "nieruchomości": "real_estate",
    "commodity": "commodity",
    "commodities": "commodity",
    "gold": "commodity",
    "zloto": "commodity",
    "złoto": "commodity",
    "crypto": "crypto",
}

MAX_RISK = {"low": 2, "medium": 3, "high": 5}
TARGET_RISK = {"low": Decimal("1.5"), "medium": Decimal("3"), "high": Decimal("4")}
RISK_PL = {"low": "niski", "medium": "umiarkowany", "high": "wysoki"}
CLASS_PL = {
    "stock": "akcje",
    "etf": "ETF",
    "bond": "obligacje",
    "real_estate": "nieruchomości",
    "commodity": "surowce",
    "crypto": "kryptowaluty",
    "cash": "gotówka/lokaty",
}


@dataclass(frozen=True)
class RiskProfile:
    risk: str = "medium"
    horizon: str = "medium"
    preferred_classes: tuple[str, ...] = ()
    from_user: bool = False

    @property
    def max_risk(self) -> int:
        cap = MAX_RISK.get(self.risk, 3)
        return min(cap, 2) if self.horizon == "short" else cap


@dataclass(frozen=True)
class PortfolioContext:
    """Aggregated, anonymous view of the holdings."""

    class_shares: dict[str, Decimal | None]
    symbols: tuple[str, ...]


@dataclass
class _Trace:
    """What one advisor run sent and received; persisted as an `agent_runs` row."""

    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    seen_urls: set[str] = field(default_factory=set)
    messages: list[dict[str, str]] = field(default_factory=list)
    raw_outputs: list[str] = field(default_factory=list)
    attempts: int = 0
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    status: str = "unavailable"  # ok | invalid | unavailable | limited | timeout
    error: str | None = None


def normalize_class(value: str) -> str:
    return CLASS_ALIASES.get(value.strip().lower(), "other")


def to_risk_profile(risk: str, horizon: str, preferred_classes: Sequence[str]) -> RiskProfile:
    preferred = tuple(dict.fromkeys(normalize_class(c) for c in preferred_classes))
    return RiskProfile(
        risk=risk if risk in MAX_RISK else "medium",
        horizon=horizon,
        preferred_classes=preferred,
        from_user=True,
    )


def portfolio_context(holdings: Sequence[HoldingIn]) -> PortfolioContext:
    items = [
        HoldingInput(
            id=i,
            name=h.symbol or h.asset_class,
            symbol=h.symbol,
            asset_class=normalize_class(h.asset_class),
            quantity=h.quantity,
            purchase_price=Decimal("0"),
            manual_value=h.current_value,
        )
        for i, h in enumerate(holdings)
    ]
    summary = portfolio_summary(items)
    known_total = summary.total_value > 0
    shares: dict[str, Decimal | None] = {
        a.asset_class: (a.share_pct if known_total else None) for a in summary.allocation
    }
    symbols = tuple(dict.fromkeys(h.symbol.strip().upper() for h in holdings if h.symbol))
    return PortfolioContext(class_shares=shares, symbols=symbols)


def yahoo_url(symbol: str | None) -> str | None:
    return f"https://finance.yahoo.com/quote/{symbol}" if symbol else None


# --- deterministic fallback -------------------------------------------------------------


def _score(inst: market.Instrument, profile: RiskProfile, ctx: PortfolioContext) -> Decimal:
    score = -abs(Decimal(inst.risk_level) - TARGET_RISK.get(profile.risk, Decimal(3))) * 2
    if inst.asset_class in profile.preferred_classes:
        score += 2
    if inst.asset_class not in ctx.class_shares:
        score += 3
    else:
        share = ctx.class_shares[inst.asset_class]
        score -= (share / 25) if share is not None else 1
    if inst.symbol and inst.symbol in ctx.symbols:
        score -= 3
    return score


def _fallback_rationale(
    inst: market.Instrument, profile: RiskProfile, ctx: PortfolioContext
) -> str:
    parts = [inst.description]
    cls = CLASS_PL[inst.asset_class]
    if inst.asset_class not in ctx.class_shares:
        parts.append(f"Twój portfel nie zawiera jeszcze klasy „{cls}”, więc to dywersyfikacja.")
    else:
        share = ctx.class_shares[inst.asset_class]
        if share is not None:
            parts.append(f"Klasa „{cls}” stanowi obecnie {share}% portfela.")
    if inst.asset_class in profile.preferred_classes:
        parts.append("To jedna z preferowanych przez Ciebie klas aktywów.")
    parts.append(
        f"Ryzyko {inst.risk_level}/5 pasuje do profilu: {RISK_PL.get(profile.risk, 'umiarkowany')}."
    )
    return " ".join(parts)


def fallback_picks(profile: RiskProfile, ctx: PortfolioContext) -> list[TopPickOut]:
    universe = market.get_instrument_universe()
    allowed = [i for i in universe if i.risk_level <= profile.max_risk] or universe
    ranked = sorted(allowed, key=lambda i: _score(i, profile, ctx), reverse=True)
    chosen: list[market.Instrument] = []
    for inst in ranked:  # first pass: distinct asset classes
        if inst.asset_class not in {c.asset_class for c in chosen}:
            chosen.append(inst)
        if len(chosen) == PICKS:
            break
    for inst in ranked:  # second pass: fill up if not enough classes
        if len(chosen) == PICKS:
            break
        if inst not in chosen:
            chosen.append(inst)
    return [
        TopPickOut(
            name=i.name,
            asset_class=i.asset_class,
            symbol=i.symbol,
            rationale=_fallback_rationale(i, profile, ctx),
            risk_level=i.risk_level,
            source_url=yahoo_url(i.symbol),
        )
        for i in chosen
    ]


# --- LLM tool-calling loop --------------------------------------------------------------

_TOOL_NAMES = [t.name for t in MARKET_TOOLS]

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["call_tool", "final"]},
        "tool": {"type": "string", "enum": _TOOL_NAMES},
        "args": {
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer"},
            },
        },
        "answer": {
            "type": "object",
            "properties": {
                "top_picks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "asset_class": {"type": "string", "enum": list(market.ASSET_CLASSES)},
                            "symbol": {"type": "string"},
                            "rationale": {"type": "string"},
                            "risk_level": {"type": "integer"},
                            "source_url": {"type": "string"},
                        },
                        "required": ["name", "asset_class", "rationale", "risk_level"],
                    },
                }
            },
            "required": ["top_picks"],
        },
    },
    "required": ["action"],
}


def _system_prompt(profile: RiskProfile) -> str:
    tools = "\n".join(
        f"- {t.name}: {t.description} Argumenty (JSON Schema): "
        f"{json.dumps(t.parameters, ensure_ascii=False)}"
        for t in MARKET_TOOLS
    )
    return (
        "Jesteś doradcą inwestycyjnym aplikacji Coffer. Odpowiadasz wyłącznie JSON-em.\n"
        "Masz dostęp do narzędzi z danymi rynkowymi:\n"
        f"{tools}\n\n"
        'Aby wywołać narzędzie, zwróć {"action":"call_tool","tool":"<nazwa>","args":{...}}. '
        "Wynik dostaniesz w kolejnej wiadomości.\n"
        'Gdy masz wystarczające dane, zwróć {"action":"final","answer":{"top_picks":[...]}} '
        f"z dokładnie {PICKS} propozycjami (name, asset_class, symbol, rationale, risk_level 1-5, "
        "source_url). Wybieraj instrumenty z get_instrument_universe, dywersyfikuj względem "
        "obecnego portfela i nie przekraczaj maksymalnego poziomu ryzyka "
        f"{profile.max_risk}/5. Uzasadnienia pisz po polsku, zwięźle, bez obietnic zysku. "
        f"Masz maksymalnie {MAX_STEPS} kroki."
    )


def _context_message(profile: RiskProfile, ctx: PortfolioContext) -> str:
    data = {
        "profil_ryzyka": {
            "ryzyko": profile.risk,
            "horyzont": profile.horizon,
            "preferowane_klasy": list(profile.preferred_classes),
            "maks_poziom_ryzyka": profile.max_risk,
            "profil_domyslny": not profile.from_user,
        },
        "portfel": {
            "udzialy_klas_pct": {
                k: (str(v) if v is not None else None) for k, v in ctx.class_shares.items()
            },
            "symbole": list(ctx.symbols),
        },
    }
    return "Kontekst użytkownika:\n" + json.dumps(data, ensure_ascii=False)


def _collect_urls(output: Any, trace: _Trace) -> None:
    if isinstance(output, dict):
        for k, v in output.items():
            if k == "url" and isinstance(v, str):
                trace.seen_urls.add(v)
            else:
                _collect_urls(v, trace)
    elif isinstance(output, list):
        for v in output:
            _collect_urls(v, trace)


def _validate_answer(answer: Any, profile: RiskProfile, trace: _Trace) -> list[TopPickOut] | None:
    if not isinstance(answer, dict):
        return None
    raw = answer.get("top_picks")
    if not isinstance(raw, list) or len(raw) < PICKS:
        return None
    by_symbol = {i.symbol: i for i in market.get_instrument_universe() if i.symbol}
    picks: list[TopPickOut] = []
    for item in raw[:PICKS]:
        if not isinstance(item, dict):
            return None
        name = str(item.get("name") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        symbol = str(item.get("symbol") or "").strip().upper() or None
        asset_class = item.get("asset_class")
        risk = item.get("risk_level")
        known = by_symbol.get(symbol) if symbol else None
        if known is not None:  # trust our universe over the model
            asset_class, risk = known.asset_class, known.risk_level
        if (
            not name
            or not rationale
            or asset_class not in market.ASSET_CLASSES
            or not isinstance(risk, int)
            or isinstance(risk, bool)
            or not 1 <= risk <= 5
            or risk > profile.max_risk
        ):
            return None
        url = str(item.get("source_url") or "").strip() or None
        if url not in trace.seen_urls:
            url = yahoo_url(symbol)
        picks.append(
            TopPickOut(
                name=name[:200],
                asset_class=asset_class,
                symbol=symbol,
                rationale=rationale[:1000],
                risk_level=risk,
                source_url=url,
            )
        )
    return picks


def run_tool_loop(
    llm: LLMClient, profile: RiskProfile, ctx: PortfolioContext, trace: _Trace | None = None
) -> list[TopPickOut] | None:
    """Return validated picks from the model, or None when the loop fails."""
    system = _system_prompt(profile)
    messages = [LLMMessage("user", _context_message(profile, ctx))]
    trace = trace if trace is not None else _Trace()
    trace.messages.append({"role": "system", "content": system})
    trace.messages.append({"role": "user", "content": messages[0].content})
    for step in range(MAX_STEPS):
        left = remaining_s()
        if left is not None and left <= 0:
            raise LLMTimeout("Przekroczono limit czasu doradcy")
        trace.attempts += 1
        resp = llm.complete(system=system, messages=messages, response_schema=RESPONSE_SCHEMA)
        trace.model = resp.model
        if resp.input_tokens is not None:
            trace.input_tokens = (trace.input_tokens or 0) + resp.input_tokens
        if resp.output_tokens is not None:
            trace.output_tokens = (trace.output_tokens or 0) + resp.output_tokens
        trace.raw_outputs.append(resp.content)
        trace.messages.append({"role": "assistant", "content": resp.content})
        try:
            data = json.loads(resp.content)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        action = data.get("action")
        if action == "final":
            return _validate_answer(data.get("answer"), profile, trace)
        if action != "call_tool":
            return None
        tool = str(data.get("tool") or "")
        raw_args = data.get("args")
        args: dict[str, Any] = raw_args if isinstance(raw_args, dict) else {}
        started = time.perf_counter()
        try:
            output: Any = call_tool(tool, args)
            _collect_urls(output, trace)
        except ToolError as exc:
            output = {"error": str(exc)}
        trace.tool_calls.append(
            {
                "name": tool,
                "arguments": args,
                "output": output if isinstance(output, dict) else {"result": output},
                "duration_ms": int((time.perf_counter() - started) * 1000),
            }
        )
        last = step == MAX_STEPS - 2
        hint = '\nTo ostatni krok: zwróć {"action":"final", ...}.' if last else ""
        messages.append(LLMMessage("assistant", resp.content))
        result_msg = f"Wynik narzędzia {tool}:\n{json.dumps(output, ensure_ascii=False)}{hint}"
        messages.append(LLMMessage("user", result_msg))
        trace.messages.append({"role": "user", "content": result_msg})
    return None


def _tips() -> list[TipOut]:
    return [
        TipOut(title=t.title, summary=t.summary, source=t.source, url=t.url)
        for t in market.get_market_tips(TIPS)
    ]


def advise(
    holdings: Sequence[HoldingIn],
    risk_profile: RiskProfile,
    llm: LLMClient | None,
    trace: _Trace | None = None,
) -> AdviceOut:
    """Top picks for the user's risk profile (RiskProfile() = default moderate profile)."""
    ctx = portfolio_context(holdings)
    trace = trace if trace is not None else _Trace()
    picks: list[TopPickOut] | None = None
    if llm is not None:
        try:
            # One budget for every step and model call: the request must finish well before
            # the 120 s Vercel proxy limit (each call gets min(its timeout, time left)).
            with llm_deadline(get_settings().advisor_timeout_s):
                try:
                    picks = run_tool_loop(llm, risk_profile, ctx, trace)
                except LLMUnavailable as exc:
                    left = remaining_s()
                    if isinstance(exc, LLMTimeout) or (left is not None and left <= 0):
                        raise LLMTimeout(str(exc)) from exc
                    raise
            trace.status = "ok" if picks is not None else "invalid"
        except LLMTimeout as exc:
            trace.status, trace.error = "timeout", str(exc)
        except LLMUnavailable as exc:
            trace.status, trace.error = "unavailable", str(exc)
        except Exception as exc:
            log.warning("Investment advisor LLM loop failed", exc_info=True)
            trace.status, trace.error = "invalid", type(exc).__name__
    llm_used = picks is not None
    if picks is None:
        picks = fallback_picks(risk_profile, ctx)
    return AdviceOut(
        top_picks=picks,
        tips=_tips(),
        llm_used=llm_used,
        ai_status="ok" if llm_used else ("timeout" if trace.status == "timeout" else "unavailable"),
    )


def advise_for_user(
    db: Session,
    user_id: int,
    holdings: Sequence[HoldingIn],
    risk_profile: RiskProfile,
    llm: LLMClient | None,
) -> AdviceOut:
    """`advise` with the shared daily LLM limit and an `agent_runs` trace (decision (f)).

    Over the limit the model is not called and the deterministic picks are returned
    (llm_used=False, ai_status="limited"): the advisor stays useful, only the AI part is off.
    Without a configured LLM nothing is recorded (no model call, no cost).
    """
    if llm is None:
        return advise(holdings, risk_profile, None)
    started = time.perf_counter()
    trace = _Trace()
    # TODO(0007_agent_usage): COUNT-then-call races (two parallel requests can both pass);
    # replace with the atomic reserve_run on llm_usage_daily, docs/data-model.md 2.8 (f).
    if agent_service.count_runs_today(db, user_id) >= get_settings().agent_daily_limit:
        out = advise(holdings, risk_profile, None)
        out.ai_status = "limited"
        trace.status = "limited"
    else:
        # The model loop can take tens of seconds; give the connection back to the pool (N08).
        db.commit()
        db.close()
        out = advise(holdings, risk_profile, llm, trace)
    agent_service.record_run(
        db,
        user_id=user_id,
        task=TASK,
        prompt_version=PROMPT_VERSION,
        model=trace.model,
        status=trace.status,
        tool_calls=trace.tool_calls,
        messages=trace.messages,
        raw_outputs=trace.raw_outputs,
        error=trace.error,
        attempts=trace.attempts,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return out
