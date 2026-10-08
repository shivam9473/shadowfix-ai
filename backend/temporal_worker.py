"""Temporal worker. The workflow waits on an admin signal before any deploy activity.

Start a Temporal server, then from backend/: python temporal_worker.py
The API does not require Temporal. This module is the durable human-approval wait.
"""

from __future__ import annotations


def main() -> None:
    import asyncio
    import os
    from datetime import timedelta

    from temporalio import activity, workflow
    from temporalio.client import Client
    from temporalio.worker import Worker

    @activity.defn
    async def diagnose(incident: dict) -> dict:
        from knowledge.mem0_rules import TenantMemory
        from pipeline import IncidentStore, index_demo, run_incident
        from main import build_knowledge

        kb = build_knowledge()
        index_demo(kb)
        store = IncidentStore()
        created = store.create(incident["tenant_id"], incident["target"])
        finished = run_incident(store, kb, TenantMemory(), created["id"], halted=False)
        return {"incident_id": finished["id"], "status": finished["status"]}

    @activity.defn
    async def deploy(incident_id: str) -> dict:
        return {
            "incident_id": incident_id,
            "note": "Deploy runs in the API approve handler, which mints the 15-minute STS session.",
        }

    @workflow.defn
    class ShadowFixWorkflow:
        def __init__(self) -> None:
            self.approved = False

        @workflow.signal
        def approve(self) -> None:
            self.approved = True

        @workflow.run
        async def run(self, incident: dict) -> dict:
            diagnosed = await workflow.execute_activity(
                diagnose,
                incident,
                start_to_close_timeout=timedelta(minutes=5),
            )
            await workflow.wait_condition(lambda: self.approved)
            deployed = await workflow.execute_activity(
                deploy,
                diagnosed["incident_id"],
                start_to_close_timeout=timedelta(minutes=5),
            )
            return {"diagnosed": diagnosed, "deployed": deployed}

    async def serve() -> None:
        address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
        namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
        queue = os.getenv("TEMPORAL_TASK_QUEUE", "shadowfix")
        client = await Client.connect(address, namespace=namespace)
        worker = Worker(
            client,
            task_queue=queue,
            workflows=[ShadowFixWorkflow],
            activities=[diagnose, deploy],
        )
        await worker.run()

    asyncio.run(serve())


if __name__ == "__main__":
    main()
