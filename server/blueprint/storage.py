"""Run storage.

* Default: in-memory plus a JSON file per run under ``server/runs/``.
* With ``COSMOS_ENDPOINT`` set: Azure Cosmos DB (container partitioned by ``/run_id``).
  Authenticates with ``COSMOS_KEY`` or, if absent, ``DefaultAzureCredential``
  (managed identity when deployed on Azure Container Apps).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from loguru import logger

from blueprint.models import BlueprintRun


class RunStore:
    def __init__(self) -> None:
        self._mem: dict[str, BlueprintRun] = {}
        self._dir = Path(os.getenv("RUNS_DIR", Path(__file__).resolve().parent.parent / "runs"))
        self._container = None
        endpoint = os.getenv("COSMOS_ENDPOINT")
        if endpoint:
            try:
                from azure.cosmos.aio import CosmosClient  # optional dependency

                key = os.getenv("COSMOS_KEY")
                if key:
                    credential = key
                else:
                    from azure.identity.aio import DefaultAzureCredential

                    credential = DefaultAzureCredential()
                client = CosmosClient(endpoint, credential=credential)
                db = client.get_database_client(os.getenv("COSMOS_DATABASE", "blueprint"))
                self._container = db.get_container_client(os.getenv("COSMOS_CONTAINER", "runs"))
                logger.info("RunStore: using Azure Cosmos DB")
            except ImportError:
                logger.warning("COSMOS_ENDPOINT set but azure-cosmos not installed; using files")

    async def save(self, run: BlueprintRun) -> None:
        self._mem[run.run_id] = run
        doc = run.model_dump(mode="json")
        if self._container is not None:
            try:
                await self._container.upsert_item({"id": run.run_id, **doc})
                return
            except Exception as e:  # keep the demo running if Cosmos is misconfigured
                logger.error(f"Cosmos upsert failed, falling back to file: {e}")
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / f"{run.run_id}.json").write_text(json.dumps(doc, indent=2))

    async def get(self, run_id: str) -> BlueprintRun | None:
        if run_id in self._mem:
            return self._mem[run_id]
        path = self._dir / f"{run_id}.json"
        if path.exists():
            return BlueprintRun.model_validate_json(path.read_text())
        if self._container is not None:
            try:
                item = await self._container.read_item(run_id, partition_key=run_id)
                return BlueprintRun.model_validate(item)
            except Exception:
                return None
        return None
