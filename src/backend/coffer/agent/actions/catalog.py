from coffer.agent.actions.base import Action
from coffer.agent.actions.budget_plan import BUDGET_PLAN
from coffer.agent.actions.company_research import COMPANY_RESEARCH
from coffer.agent.actions.investment_ideas import INVESTMENT_IDEAS
from coffer.agent.actions.portfolio_review import PORTFOLIO_REVIEW
from coffer.agent.actions.purchase_impact import PURCHASE_IMPACT
from coffer.agent.actions.savings_analysis import SAVINGS_ANALYSIS
from coffer.agent.tools.registry import ToolRegistry

ACTIONS: dict[str, Action] = {
    a.id: a
    for a in (
        PORTFOLIO_REVIEW,
        SAVINGS_ANALYSIS,
        PURCHASE_IMPACT,
        BUDGET_PLAN,
        INVESTMENT_IDEAS,
        COMPANY_RESEARCH,
    )
}


def get_action(action_id: str) -> Action | None:
    return ACTIONS.get(action_id)


def validate_catalog(registry: ToolRegistry) -> list[str]:
    """Consistency errors: unknown tools, and user-data tools in actions that claim not to use
    user data (`uses_user_data=False`); `uses_internet=False` must not list internet tools."""
    errors: list[str] = []
    for action in ACTIONS.values():
        for name in action.tools:
            tool = registry.get(name)
            if tool is None:
                errors.append(f"{action.id}: unknown tool {name}")
            elif tool.group == "user_data" and not action.uses_user_data:
                errors.append(f"{action.id}: user_data tool {name} but uses_user_data=False")
            elif tool.uses_internet and not action.uses_internet:
                errors.append(f"{action.id}: internet tool {name} but uses_internet=False")
    return errors
