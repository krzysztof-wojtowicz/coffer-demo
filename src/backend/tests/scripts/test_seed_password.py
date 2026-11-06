from coffer.accounts.policy import password_problems
from coffer.scripts import seed_demo


def test_demo_password_satisfies_policy() -> None:
    assert password_problems(seed_demo.DEMO_PASSWORD, seed_demo.DEMO_EMAIL) == []
