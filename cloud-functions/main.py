import os
import logging
import base64
from google.cloud import pubsub_v1
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

# Configurar el cliente de Pub/Sub
subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path('${PROJECT}', '${SUBSCRIPTION}')

# Configurar el cliente de Compute Engine
compute = discovery.build('compute', 'v1', credentials=GoogleCredentials.get_application_default())

def start_stop_vm(event, context):
    # Obtener el mensaje del evento (en formato base64)
    message_bytes = base64.b64decode(event['data'])
    message = message_bytes.decode('utf-8')

    # Obtener el ID del mensaje
    message_id = context.event_id

    # Obtener el nombre de la VM y la acción a realizar
    vm_name, action = message.split(':')

    # Determinar la acción a realizar
    if action == 'start':
        action_func = start_vm
    elif action == 'stop':
        action_func = stop_vm
    else:
        print(f'Error: Acción no válida recibida en el mensaje: {action}')
        return

    # Ejecutar la acción en la VM
    action_func(vm_name)
    print(f'Acción "{action}" realizada en la VM "{vm_name}"')

    # Confirmar la recepción del mensaje
    subscriber.modify_ack_deadline(
        request={
            'subscription': subscription_path,
            'ack_ids': [message_id],
            'ack_deadline_seconds': 0
        }
    )

def start_vm(vm_name):
    # Enviar la solicitud para iniciar la VM
    compute.instances().start(
        project='${PROJECT}',
        zone='europe-southwest1-a',
        instance=vm_name
    ).execute()

def stop_vm(vm_name):
    # Enviar la solicitud para detener la VM
    compute.instances().stop(
        project='${PROJECT}',
        zone='europe-southwest1-a',
        instance=vm_name
    ).execute()
