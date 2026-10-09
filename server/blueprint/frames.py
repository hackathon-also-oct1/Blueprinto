"""Custom Pipecat frames for the blueprint pipeline."""

from dataclasses import dataclass

from pipecat.frames.frames import DataFrame

from blueprint.models import BlueprintRun, RunRequest


@dataclass
class StartBlueprintFrame(DataFrame):
    """Asks the Orchestrator to start a run (pushed by the voice agent's tool)."""

    request: RunRequest


@dataclass
class BlueprintRunFrame(DataFrame):
    """Carries one run through the agent processors, in order."""

    run: BlueprintRun

