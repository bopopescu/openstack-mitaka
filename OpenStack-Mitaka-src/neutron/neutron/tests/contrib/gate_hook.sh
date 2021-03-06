#!/usr/bin/env bash

set -ex

VENV=${1:-"dsvm-functional"}

GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack

if [ "$VENV" == "dsvm-functional" ] || [ "$VENV" == "dsvm-fullstack" ]
then
    # The following need to be set before sourcing
    # configure_for_func_testing.
    GATE_STACK_USER=stack
    NEUTRON_PATH=$GATE_DEST/neutron
    PROJECT_NAME=neutron
    IS_GATE=True

    source $DEVSTACK_PATH/functions
    source $NEUTRON_PATH/devstack/lib/ovs

    source $NEUTRON_PATH/tools/configure_for_func_testing.sh

    configure_host_for_func_testing

    # Make the workspace owned by the stack user
    sudo chown -R $STACK_USER:$STACK_USER $BASE

elif [ "$VENV" == "api" -o "$VENV" == "api-pecan" -o "$VENV" == "full-pecan" ]
then
    if [ "$VENV" == "api-pecan" -o "$VENV" == "full-pecan" ]
    then
        cat >> $DEVSTACK_PATH/local.conf <<EOF
[[post-config|/etc/neutron/neutron.conf]]

[DEFAULT]
web_framework=pecan

EOF
    fi

    export DEVSTACK_LOCAL_CONFIG+="
enable_plugin neutron git://git.openstack.org/openstack/neutron
enable_service q-qos
enable_service q-bgp
"
# TODO(armax): figure out a cleaner way to maintain this
# gate hook and expose API extensions.

    $BASE/new/devstack-gate/devstack-vm-gate.sh
elif [ "$VENV" == "dsvm-plus" ]
then
    # We need the qos service enabled to add corresponding scenario tests to tempest
    export DEVSTACK_LOCAL_CONFIG+="
enable_plugin neutron git://git.openstack.org/openstack/neutron
enable_service q-qos
enable_service q-bgp
"

    $BASE/new/devstack-gate/devstack-vm-gate.sh
elif [ "$VENV" == "rally" ]
then
    # NOTE(yamamoto): This is a no-op placeholder to allow
    # further changes.
    $BASE/new/devstack-gate/devstack-vm-gate.sh
fi
