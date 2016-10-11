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

print "\n\n Updating couchbase stack"

template_file = '/home/kejones/heat/couchbase/Couchbase_Add_RHEL_Server.yaml'

template = open(template_file, 'r')
read_template = template.read()
stack = heatclient.stacks.update('couchbase', template=read_template,parameters={},poll=5)

stacklist = heatclient.stacks.list()

print "Stack get for couchbase\n\n"
stack_get = heatclient.stacks.get('couchbase')

#print "stack_get = %s" % stack_get
#print "couchbase.description = %s" % stack_get.description
#print "couchbase.stack_name = %s" % stack_get.stack_name

while True:
    stack_get = heatclient.stacks.get('couchbase')
    #print "stack_get.stack_status = %s" % stack_get.stack_status
    time.sleep(5)
    if stack_get.stack_status == "UPDATE_COMPLETE":
        break

couchbase_floating_ips = [None, None, None]

stack_outputs = stack_get.outputs
for item in stack_outputs:
  output = item
  dump_out = json.dumps(output)
  parsed_json = json.loads(dump_out)
  if 'Floating_IP' in (parsed_json['output_key']):
    #print (parsed_json['output_key'])
    key_string = parsed_json['output_key']
    key_string = key_string.replace("Couchbase", "")
    key_string = key_string.replace("_Floating_IP", "")
    #print "key_string = %s" % key_string
    position = int(key_string) - 1
    couchbase_floating_ips[position] = parsed_json['output_value']

print "couchbase_floating_ips = ", couchbase_floating_ips
print [x.encode('ascii') for x in couchbase_floating_ips] 

couchbase_private_ips = [None, None, None]

stack_outputs = stack_get.outputs
for item in stack_outputs:
  output = item
  dump_out = json.dumps(output)
  parsed_json = json.loads(dump_out)
  if 'Private_IP' in (parsed_json['output_key']):
    #print (parsed_json['output_key'])
    key_string = parsed_json['output_key']
    key_string = key_string.replace("Couchbase", "")
    key_string = key_string.replace("_Private_IP", "")
    #print "key_string = %s" % key_string
    position = int(key_string) - 1
    couchbase_private_ips[position] = parsed_json['output_value']

print "couchbase_private_ips = ", couchbase_private_ips
print [x.encode('ascii') for x in couchbase_private_ips] 

print "Waiting for instances to become available - checking for password-less ssh access"

for x in couchbase_floating_ips:
    check_server_available(x, 'cloud-user', '/home/kejones/kdj.pem', 'hostname')

print "Wait 30 seconds for all instances to become ready before playbook run"
time.sleep(30)

# initialize needed objects
variable_manager = VariableManager()
loader = DataLoader()

inventory = Inventory(loader=loader, variable_manager=variable_manager, host_list=couchbase_floating_ips)
playbook_path = '/home/kejones/heat/couchbase/couchbase_install_OpenStack.yml'

if not os.path.exists(playbook_path):
    print '[INFO] The playbook does not exist'
    sys.exit()

Options = namedtuple('Options', ['listtags', 'listtasks', 'listhosts', 'syntax', 'connection','module_path', 'forks', 'remote_user', 'private_key_file', 'ssh_common_args', 'ssh_extra_args', 'sftp_extra_args', 'scp_extra_args', 'become', 'become_method', 'become_user', 'verbosity', 'check'])

# the "private_key_file" will be taken from the "ansible.cfg" file
# The ansible.cfg file contains "host_key_checking = False" so that
# newly created OpenStack instances do not prompt for ssh permission.
options = Options(listtags=False, listtasks=False, listhosts=False, syntax=False, connection='ssh', module_path="", forks=100, remote_user='cloud-user', private_key_file=None, ssh_common_args=None, ssh_extra_args=None, sftp_extra_args=None, scp_extra_args=None, become=True, become_method='sudo', become_user='root', verbosity=None, check=False)

passwords = {}

pbex = PlaybookExecutor(playbooks=[playbook_path], inventory=inventory, variable_manager=variable_manager, loader=loader, options=options, passwords=passwords)

results = pbex.run()

print "\n Waiting before adding node to cluster"
time.sleep(30)

# Add Nodes
variable_manager3 = VariableManager()
loader3 = DataLoader()

playbook_path3 = '/home/kejones/heat/couchbase/couchbase_config_cluster_add_node.yml'

if not os.path.exists(playbook_path3):
    print '[INFO] The playbook does not exist'
    sys.exit()

variable_manager3.extra_vars = {'cluster_main_ip' : couchbase_floating_ips[0],
                                'cluster_node_ips' : [ couchbase_private_ips[2] ],
                                'admin_user' : 'Administrator',
                                'admin_password' : 'Vinson#12',
                                'cluster_ram_quota' : '2048',
                                'server_port' : '8091'
                                }

inventory3 = Inventory(loader=loader3, variable_manager=variable_manager3, host_list=[couchbase_floating_ips[0]])
pbex3 = PlaybookExecutor(playbooks=[playbook_path3], inventory=inventory3, variable_manager=variable_manager3, loader=loader3, options=options, passwords=passwords)

results = pbex3.run()

elapsed_time = time.time() - start_time
m, s = divmod(elapsed_time, 60)
h, m = divmod(m, 60)

print "Message from Couchbase Configuration ..."
print "  Successfully added additional Couchbase node to correct the warning"
print "  All systems operational to save the world!!!" 
print "  Couchbase Stack completed in: %d:%02d:%02d" % (h, m, s)
print "  Couchbase console can be accessed at %s:8091\n\n" % couchbase_floating_ips[0]
