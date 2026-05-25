import base64
import json
import os

import functions_framework
from google.cloud import run_v2


@functions_framework.cloud_event
def rollback(cloud_event):
    """Pub/Sub-triggered: roll a Cloud Run canary back to the previous stable revision.

    The function is invoked by a Cloud Monitoring alert delivered through a
    Pub/Sub notification channel. It inspects the offending revision and, if
    it looks like a canary (small traffic share, or carrying the canary tag),
    rewrites the service's traffic so the largest non-offending revision
    receives 100% of requests.
    """
    project = os.environ["PROJECT_ID"]
    region = os.environ["REGION"]
    service_name = os.environ["SERVICE_NAME"]

    envelope = cloud_event.data["message"]["data"]
    payload = json.loads(base64.b64decode(envelope).decode())

    incident = payload.get("incident", {})
    if incident.get("state") != "open":
        print(f"Ignoring incident in state={incident.get('state')!r}")
        return

    labels = incident.get("resource", {}).get("labels", {})
    bad_rev = labels.get("revision_name")
    if not bad_rev:
        print("Alert payload had no revision_name; aborting.")
        return

    client = run_v2.ServicesClient()
    full_name = f"projects/{project}/locations/{region}/services/{service_name}"
    svc = client.get_service(name=full_name)

    bad_target = next((t for t in svc.traffic if t.revision == bad_rev), None)
    if bad_target is None:
        print(f"Revision {bad_rev} is not in the current traffic split; nothing to do.")
        return

    # Safety: never auto-revert the stable revision. If the alerting revision is
    # carrying the majority of traffic and has no canary tag, this is most likely
    # a real production incident, not a bad canary — leave it for a human.
    if bad_target.percent >= 50 and not bad_target.tag:
        print(
            f"Revision {bad_rev} carries {bad_target.percent}% with no canary tag; "
            "refusing to auto-roll-back the stable revision."
        )
        return

    rollback_target = max(
        (t for t in svc.traffic if t.revision and t.revision != bad_rev),
        key=lambda t: t.percent,
        default=None,
    )
    if rollback_target is None:
        print("No alternative revision in the traffic split; cannot roll back.")
        return

    print(
        f"Rolling back: {bad_rev} ({bad_target.percent}%) "
        f"-> {rollback_target.revision} (100%)"
    )
    svc.traffic = [
        run_v2.TrafficTarget(
            type_=run_v2.TrafficTargetAllocationType.TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION,
            revision=rollback_target.revision,
            percent=100,
        )
    ]
    op = client.update_service(service=svc)
    op.result(timeout=120)
    print("Rollback complete.")
