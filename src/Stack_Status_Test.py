import sys
import os
import time
import json
import paramiko
import socket

from heatclient.client import Client as Heat_Client
from heatclient.v1.stacks import StackManager as Stack_Manager
from keystoneclient.v2_0 import Client as Keystone_Client

from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.playbook.play import Play
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase


def check_server_available(ip_address, username, private_key_file, command):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    available = False
    while available == False:
        try:
           private_key = paramiko.RSAKey.from_private_key_file(private_key_file)
           ssh.connect(ip_address, username=username, pkey = private_key)
           available = True
           break
        except paramiko.AuthenticationException:
           #print "check_server_available: Double check username and private_key_file"
           continue
        except socket.error:
           #print "check_server_available: Server %s is not available yet" % ip_address
           continue
        else:
           break

    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)
    for line in ssh_stdout:
        print line


def get_keystone_creds():
    d = {}
    d['username'] = os.environ['OS_USERNAME']
    d['password'] = os.environ['OS_PASSWORD']
    d['auth_url'] = os.environ['OS_AUTH_URL']
    d['tenant_name'] = os.environ['OS_TENANT_NAME']
    return d


cred = get_keystone_creds()
ks_client = Keystone_Client(**cred)
heat_endpoint = ks_client.service_catalog.url_for(service_type='orchestration', endpoint_type='publicURL')
heatclient = Heat_Client('1', heat_endpoint, token=ks_client.auth_token)

start_time = time.time()

stacklist = heatclient.stacks.list()

print "Stack get for couchbase\n\n"
stack_get = heatclient.stacks.get('couchbase')

print "stack_get = %s" % stack_get
print "couchbase.description = %s" % stack_get.description
print "couchbase.stack_name = %s" % stack_get.stack_name

#while True:
print "stack_get.stack_status = %s" % stack_get.stack_status
print "stack_get = %s" % stack_get
#    time.sleep(5)
#    if stack_get.stack_status == "UPDATE_COMPLETE":
#        break

couchbase_floating_ips = [None, None, None, None]

#print "Stack status %s" % stack.status
#print "Stack2 status %s" % stack2.status

stack_outputs = stack_get.outputs
for item in stack_outputs:
  output = item
  dump_out = json.dumps(output)
  parsed_json = json.loads(dump_out)
  if 'Floating_IP' in (parsed_json['output_key']):
    print (parsed_json['output_key'])
    key_string = parsed_json['output_key']
    key_string = key_string.replace("Couchbase", "")
    key_string = key_string.replace("_Floating_IP", "")
    #print "key_string = %s" % key_string
    position = int(key_string) - 1
    couchbase_floating_ips[position] = parsed_json['output_value']

print "couchbase_floating_ips = ", couchbase_floating_ips
print [x.encode('ascii') for x in couchbase_floating_ips] 

couchbase_private_ips = [None, None, None, None]

stack_outputs = stack_get.outputs
for item in stack_outputs:
  output = item
  dump_out = json.dumps(output)
  parsed_json = json.loads(dump_out)
  if 'Private_IP' in (parsed_json['output_key']):
    print (parsed_json['output_key'])
    key_string = parsed_json['output_key']
    key_string = key_string.replace("Couchbase", "")
    key_string = key_string.replace("_Private_IP", "")
    #print "key_string = %s" % key_string
    position = int(key_string) - 1
    couchbase_private_ips[position] = parsed_json['output_value']

print "couchbase_private_ips = ", couchbase_private_ips
print [x.encode('ascii') for x in couchbase_private_ips] 

