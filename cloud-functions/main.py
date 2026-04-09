import functions_framework
import base64
import logging

from google.api_core import exceptions
from google.auth import default
from google.cloud import compute_v1
import google.cloud.logging

# Integrate Python logging with Cloud Logging for proper severity mapping and structured metadata
google.cloud.logging.Client().setup_logging()
logger = logging.getLogger(__name__)

@functions_framework.cloud_event
def start_stop_vm(cloud_event):
    vm_name = zone = action = message_bytes = None
    try:
        data = cloud_event.data
        message_bytes = base64.b64decode(data["message"]["data"]).decode("utf-8")
        vm_name, zone, action = message_bytes.split(":")

        credentials, project = default()
        compute_client = compute_v1.InstancesClient(credentials=credentials)

        if action == "start":
            request = compute_v1.StartInstanceRequest(project=project, zone=zone, instance=vm_name)
            compute_client.start(request=request).result()
            logger.info(f"Started VM {vm_name} in {zone}")
        elif action == "stop":
            request = compute_v1.StopInstanceRequest(project=project, zone=zone, instance=vm_name)
            compute_client.stop(request=request).result()
            logger.info(f"Stopped VM {vm_name} in {zone}")
        elif action == "create":
            create_vm(compute_client, project, zone, vm_name)
        else:
            logger.error(f"Invalid action {action!r} for VM {vm_name} in {zone}")
            return

    except ValueError:
        logger.error(f"Invalid message format. Expected 'vm_name:zone:action', got: {message_bytes!r}")
    except exceptions.NotFound:
        logger.error(f"VM {vm_name!r} not found in zone {zone!r}")
    except exceptions.PermissionDenied:
        logger.error(f"Permission denied performing {action!r} on VM {vm_name!r} in {zone!r}")
    except Exception:
        logger.exception(f"Unexpected error performing {action!r} on VM {vm_name!r} in {zone!r}")
        raise  # NACK: let Pub/Sub retry on transient failures

def create_vm(compute_client, project, zone, vm_name):
    try:
        image_client = compute_v1.ImagesClient()
        image = image_client.get_from_family(project="debian-cloud", family="debian-11")
        source_disk_image = image.self_link

        machine_type = f"zones/{zone}/machineTypes/e2-small"
        config = compute_v1.Instance(
            name=vm_name,
            machine_type=machine_type,
            disks=[
                compute_v1.AttachedDisk(
                    boot=True,
                    auto_delete=True,
                    initialize_params=compute_v1.AttachedDiskInitializeParams(source_image=source_disk_image),
                )
            ],
            network_interfaces=[
                compute_v1.NetworkInterface(
                    network="global/networks/default",
                    access_configs=[compute_v1.AccessConfig(name="External NAT")],
                )
            ],
            service_accounts=[compute_v1.ServiceAccount(
                email="default",
                scopes=[
                    "https://www.googleapis.com/auth/devstorage.read_write",
                    "https://www.googleapis.com/auth/logging.write",
                ],
            )],
        )

        request = compute_v1.InsertInstanceRequest(project=project, zone=zone, instance_resource=config)
        compute_client.insert(request=request).result()
        logger.info(f"Created VM {vm_name} in {zone}")
    except exceptions.NotFound:
        logger.error(f"Debian-11 base image not found in 'debian-cloud' project")
    except Exception:
        logger.exception(f"Failed to create VM {vm_name!r} in zone {zone!r}")
        raise
