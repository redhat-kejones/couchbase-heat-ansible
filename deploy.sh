#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o xtrace
set -o pipefail

display_usage() { 
  echo "Use this program to deploy or update a Couchbase NoSQL DB Cluster using Python, Heat and Ansible" 
  echo -e "Usage: $0 stackname [--num-data-nodes=3] [--update] \n" 
}

# if less than two arguments supplied, display usage 
if [  $# -le 0 ] 
then 
  display_usage
  exit 1
fi 
 
# set default values for arguments
STACK_NAME=${1:-couchbase}
NUM_DATA_NODES=3
UPDATE=false

# read the options
TEMP=`getopt -o h --long help,num-data-nodes:,update -n $0 -- "$@"`
eval set -- "$TEMP"

# extract options and their arguments into variables.
while true ; do
    case "$1" in
        -h|--help) echo $2; display_usage; exit 0 ;;
        --num-data-nodes)
            case "$2" in
              "") shift 2 ;;
              *) NUM_DATA_NODES=$2 ; shift 2 ;;
            esac ;;
        --update) UPDATE=true ; shift ;;
        --) shift ; break ;;
        *) echo "Internal error!" ; exit 1 ;;
    esac
done

# do something with the variables -- in this case the lamest possible one :-)
echo "NUM_DATA_NODES = $NUM_DATA_NODES"
echo "UPDATE = $UPDATE"

if [  "${UPDATE}" = true ]
then
  echo "Stack update initiated for ${STACK_NAME}"
  exit 0
else
  echo "Stack create initiated for ${STACK_NAME}"
fi
