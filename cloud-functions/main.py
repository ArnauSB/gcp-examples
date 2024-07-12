import os
import logging
import base64
from google.cloud import pubsub_v1
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

# Configure Pub/Sub client
PROJECT = os.environ.get('PROJECT')
SUBSCRIPTION = os.environ.get('SUBSCRIPTION')
subscriber = pubsub_v1.SubscriberClient()
subscription_path = pubsub_v1.SubscriberClient().subscription_path(PROJECT, SUBSCRIPTION)

# Configure Compute Engine client
compute = discovery.build('compute', 'v1', credentials=GoogleCredentials.get_application_default())

# Configure logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def start_stop_vm(event, context):
    # Get the event message (base64)
    message_bytes = base64.b64decode(event['data'])
    message = message_bytes.decode('utf-8')

    # Get the ID of the message
    message_id = context.event_id

    # Split the message to get the VM name, the zone and the action
    try:
        vm_name, zone, action = message.split(':')
    except ValueError:
        logger.error('Invalid message format. Expected: zone:vm_name:action')
        return

    # Choose action to perform
    if action == 'start':
        action_func = start_vm
    elif action == 'stop':
        action_func = stop_vm
    elif action == 'create':
        action_func = create_vm
    else:
        logger.error(f'Non valid action: {action}')
        return

    # Execute the action to the VM
    action_func(vm_name, zone)
    logger.info(f'Action "{action}" done to VM "{vm_name}" in zone "{zone}"')

    # Ack reception of the message
    subscriber.modify_ack_deadline(
        request={
            'subscription': subscription_path,
            'ack_ids': [message_id],
            'ack_deadline_seconds': 0
        }
    )

def start_vm(vm_name, zone):
    # Send request to start the VM
    try:
        compute.instances().start(
            project=PROJECT,
            zone=zone,
            instance=vm_name
        ).execute()
        logger.info(f'VM "{vm_name}" started in zone "{zone}"')
    except Exception as e:
        logger.error(f'Error starting VM "{vm_name}": {e}')

def stop_vm(vm_name, zone):
    # Send request to stop the VM
    try:
        compute.instances().stop(
            project=PROJECT,
            zone=zone,
            instance=vm_name
        ).execute()
        logger.info(f'VM "{vm_name}" stopped in zone "{zone}"')
    except Exception as e:
        logger.error(f'Error stopping VM "{vm_name}": {e}')

def create_vm(vm_name, zone):
    # Send request to create the VM
    try:
        image_response = compute.images().getFromFamily(
            project='debian-cloud', family='debian-11').execute()
        source_disk_image = image_response['selfLink']

        machine_type = f"zones/{zone}/machineTypes/e2-small"
        config = {
            'name': vm_name,
            'machineType': machine_type,
            'disks': [
                {
                    'boot': True,
                    'autoDelete': True,
                    'initializeParams': {
                        'sourceImage': source_disk_image,
                    }
                }
            ],
            'networkInterfaces': [{
                'network': 'global/networks/default',
                'accessConfigs': [
                    {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
                ]
            }],
            'serviceAccounts': [{
                'email': 'default',
                'scopes': [
                    'https://www.googleapis.com/auth/devstorage.read_write',
                    'https://www.googleapis.com/auth/logging.write'
                ]
            }]
        }
        compute.instances().insert(
            project=PROJECT,
            zone=zone,
            body=config).execute()
        logger.info(f'VM "{vm_name}" created in zone "{zone}"')
    except Exception as e:
       logger.error(f'Error creating VM "{vm_name}": {e}') 
    