from blueprint.agents.base import AgentProcessor
from blueprint.catalog import heuristic_spec
from blueprint.models import BlueprintRun, RequirementSpec

SYSTEM = """You are a senior business analyst. Turn a short product requirement into a
structured specification: a one-sentence summary, the user personas, the features
(each with name, description and MoSCoW priority: must/should/could) and the
non-functional requirements (security, privacy, accessibility, performance).
Be concrete and do not invent features the requirement does not imply."""


class RequirementsAnalyst(AgentProcessor):
    agent_id = "req"
    title = "Requirements Analyst"
    service = "Azure OpenAI · structured output"

    async def run(self, run: BlueprintRun) -> str:
        req = run.request
        if self.llm.mock:
            await self.mock_pause()
            spec = heuristic_spec(req.requirement)
        else:
            user = f"Platform: {req.platform}\nRequirement:\n{req.requirement}"
            spec, tokens = await self.llm.structured(SYSTEM, user, RequirementSpec)
            run.tokens += tokens
        run.spec = spec
        await self.log(
            run,
            f"Extracted {len(spec.features)} features; personas: {', '.join(spec.personas)}",
        )
        if spec.non_functional:
            await self.log(run, "Non-functional: " + "; ".join(spec.non_functional[:3]))
        await self.log(run, "Hand-off → UX Architect")
        return f"{len(spec.features)} features · {len(spec.personas)} personas"
