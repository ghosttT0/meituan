from uuid import uuid4

from app.domain.eval_spec import EvalSpec
from app.domain.simulation import SimulationScenario


class ScenarioBuilder:
    def build(
        self,
        spec: EvalSpec,
        profile_id: str,
        primary_branch: str,
        max_turns: int = 8,
        secondary_branch: str | None = None,
    ) -> SimulationScenario:
        return SimulationScenario(
            scenario_id=f"scenario_{uuid4().hex[:8]}",
            spec_id=spec.spec_id,
            profile_id=profile_id,
            primary_branch=primary_branch,
            secondary_branch=secondary_branch,
            max_turns=max_turns,
            termination_policy="task_complete_or_user_exit",
        )
