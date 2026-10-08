from blueprint.agents.base import AgentProcessor
from blueprint.domain_classifier import classify_domain
from blueprint.models import BlueprintRun


class DomainClassifier(AgentProcessor):
    """Classifies the requirement into a reference domain before any other agent runs."""

    agent_id = "dom"
    title = "Domain Classifier"
    service = "Rules engine · weighted keywords"

    async def run(self, run: BlueprintRun) -> str:
        await self.mock_pause()
        match = classify_domain(run.request.requirement)
        run.domain = match
        if match.fallback:
            await self.log(run, f"No domain rule matched; using default: {match.name}")
        else:
            await self.log(
                run,
                f"Matched {', '.join(match.matched)} → score {match.score} "
                f"({match.confidence:.0%} of all domain points)",
            )
        await self.log(
            run, f"Redirect → screenshots/{match.domain}/, reference set {match.reference_set}"
        )
        await self.log(run, "Hand-off → Requirements Analyst")
        return f"{match.name} · set {match.reference_set}"
