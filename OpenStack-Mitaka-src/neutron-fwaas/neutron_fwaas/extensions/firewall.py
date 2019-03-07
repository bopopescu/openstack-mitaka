# Copyright 2013 Big Switch Networks, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import abc

from neutron.api import extensions
from neutron.api.v2 import attributes as attr
from neutron.api.v2 import resource_helper
from neutron.common import exceptions as nexception
from neutron.plugins.common import constants as p_const
from neutron.services import service_base
from neutron_lib import constants
from oslo_config import cfg
from oslo_log import log as logging
import six

from neutron_fwaas._i18n import _


LOG = logging.getLogger(__name__)

# Firewall rule action
FWAAS_ALLOW = "allow"
FWAAS_DENY = "deny"
FWAAS_REJECT = "reject"

# Firewall resource path prefix
FIREWALL_PREFIX = "/fw"


# Firewall Exceptions
class FirewallNotFound(nexception.NotFound):
    message = _("Firewall %(firewall_id)s could not be found.")


class FirewallInUse(nexception.InUse):
    message = _("Firewall %(firewall_id)s is still active.")


class FirewallInPendingState(nexception.Conflict):
    message = _("Operation cannot be performed since associated Firewall "
                "%(firewall_id)s is in %(pending_state)s.")


class FirewallPolicyNotFound(nexception.NotFound):
    message = _("Firewall Policy %(firewall_policy_id)s could not be found.")


class FirewallPolicyInUse(nexception.InUse):
    message = _("Firewall Policy %(firewall_policy_id)s is being used.")


class FirewallPolicyConflict(nexception.Conflict):
    """FWaaS exception for firewall policy

    Occurs when admin policy tries to use another tenant's unshared
    policy.
    """
    message = _("Operation cannot be performed since Firewall Policy "
                "%(firewall_policy_id)s is not shared and does not belong to "
                "your tenant.")


class FirewallRuleSharingConflict(nexception.Conflict):

    """FWaaS exception for firewall rules

    When a shared policy is created or updated with unshared rules,
    this exception will be raised.
    """
    message = _("Operation cannot be performed since Firewall Policy "
                "%(firewall_policy_id)s is shared but Firewall Rule "
                "%(firewall_rule_id)s is not shared")


class FirewallPolicySharingConflict(nexception.Conflict):

    """FWaaS exception for firewall policy

    When a policy is shared without sharing its associated rules,
    this exception will be raised.
    """
    message = _("Operation cannot be performed. Before sharing Firewall "
                "Policy %(firewall_policy_id)s, share associated Firewall "
                "Rule %(firewall_rule_id)s")


class FirewallRuleNotFound(nexception.NotFound):
    message = _("Firewall Rule %(firewall_rule_id)s could not be found.")


class FirewallRuleInUse(nexception.InUse):
    message = _("Firewall Rule %(firewall_rule_id)s is being used.")


class FirewallRuleNotAssociatedWithPolicy(nexception.InvalidInput):
    message = _("Firewall Rule %(firewall_rule_id)s is not associated "
                " with Firewall Policy %(firewall_policy_id)s.")


class FirewallRuleInvalidProtocol(nexception.InvalidInput):
    message = _("Firewall Rule protocol %(protocol)s is not supported. "
                "Only protocol values %(values)s and their integer "
                "representation (0 to 255) are supported.")


class FirewallRuleInvalidAction(nexception.InvalidInput):
    message = _("Firewall rule action %(action)s is not supported. "
                "Only action values %(values)s are supported.")


class FirewallRuleInvalidICMPParameter(nexception.InvalidInput):
    message = _("%(param)s are not allowed when protocol "
                "is set to ICMP.")


class FirewallRuleWithPortWithoutProtocolInvalid(nexception.InvalidInput):
    message = _("Source/destination port requires a protocol")


class FirewallRuleInvalidPortValue(nexception.InvalidInput):
    message = _("Invalid value for port %(port)s.")


class FirewallRuleInfoMissing(nexception.InvalidInput):
    message = _("Missing rule info argument for insert/remove "
                "rule operation.")


class FirewallIpAddressConflict(nexception.InvalidInput):
    message = _("Invalid input - IP addresses do not agree with IP Version")

# TODO(dougwig) - once this exception is out of neutron, restore this
#class FirewallInternalDriverError(nexception.NeutronException):
#    """Fwaas exception for all driver errors.
#
#    On any failure or exception in the driver, driver should log it and
#    raise this exception to the agent
#    """
#    message = _("%(driver)s: Internal driver error.")
FirewallInternalDriverError = nexception.FirewallInternalDriverError


class FirewallRuleConflict(nexception.Conflict):

    """Firewall rule conflict exception.

    Occurs when admin policy tries to use another tenant's unshared
    rule.
    """

    message = _("Operation cannot be performed since Firewall Rule "
                "%(firewall_rule_id)s is not shared and belongs to "
                "another tenant %(tenant_id)s")


fw_valid_protocol_values = [None, constants.PROTO_NAME_TCP,
                            constants.PROTO_NAME_UDP,
                            constants.PROTO_NAME_ICMP]
fw_valid_action_values = [FWAAS_ALLOW, FWAAS_DENY, FWAAS_REJECT]


def convert_protocol(value):
    if value is None:
        return
    if value.isdigit():
        val = int(value)
        if 0 <= val <= 255:
            return val
        else:
            raise FirewallRuleInvalidProtocol(
                protocol=value,
                values=fw_valid_protocol_values)
    elif value.lower() in fw_valid_protocol_values:
        return value.lower()
    else:
        raise FirewallRuleInvalidProtocol(
            protocol=value,
            values=fw_valid_protocol_values)


def convert_action_to_case_insensitive(value):
    if value is None:
        return
    else:
        return value.lower()


def convert_port_to_string(value):
    if value is None:
        return
    else:
        return str(value)


def _validate_port_range(data, key_specs=None):
    if data is None:
        return
    data = str(data)
    ports = data.split(':')
    for p in ports:
        try:
            val = int(p)
        except (ValueError, TypeError):
            msg = _("Port '%s' is not a valid number") % p
            LOG.debug(msg)
            return msg
        if val <= 0 or val > 65535:
            msg = _("Invalid port '%s'") % p
            LOG.debug(msg)
            return msg


def _validate_ip_or_subnet_or_none(data, valid_values=None):
    if data is None:
        return None
    msg_ip = attr._validate_ip_address(data, valid_values)
    if not msg_ip:
        return
    msg_subnet = attr._validate_subnet(data, valid_values)
    if not msg_subnet:
        return
    return _("%(msg_ip)s and %(msg_subnet)s") % {'msg_ip': msg_ip,
                                                 'msg_subnet': msg_subnet}


attr.validators['type:port_range'] = _validate_port_range
attr.validators['type:ip_or_subnet_or_none'] = _validate_ip_or_subnet_or_none


RESOURCE_ATTRIBUTE_MAP = {
    'firewall_rules': {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True, 'primary_key': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True,
                      'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': attr.NAME_MAX_LEN},
                 'is_visible': True, 'default': ''},
        'description': {'allow_post': True, 'allow_put': True,
                        'validate': {'type:string':
                                     attr.DESCRIPTION_MAX_LEN},
                        'is_visible': True, 'default': ''},
        'firewall_policy_id': {'allow_post': False, 'allow_put': False,
                               'validate': {'type:uuid_or_none': None},
                               'is_visible': True},
        'shared': {'allow_post': True, 'allow_put': True,
                   'default': False, 'convert_to': attr.convert_to_boolean,
                   'is_visible': True, 'required_by_policy': True,
                   'enforce_policy': True},
        'protocol': {'allow_post': True, 'allow_put': True,
                     'is_visible': True, 'default': None,
                     'convert_to': convert_protocol,
                     'validate': {'type:values': fw_valid_protocol_values}},
        'ip_version': {'allow_post': True, 'allow_put': True,
                       'default': 4, 'convert_to': attr.convert_to_int,
                       'validate': {'type:values': [4, 6]},
                       'is_visible': True},
        'source_ip_address': {'allow_post': True, 'allow_put': True,
                              'validate': {'type:ip_or_subnet_or_none': None},
                              'is_visible': True, 'default': None},
        'destination_ip_address': {'allow_post': True, 'allow_put': True,
                                   'validate': {'type:ip_or_subnet_or_none':
                                                None},
                                   'is_visible': True, 'default': None},
        'source_port': {'allow_post': True, 'allow_put': True,
                        'validate': {'type:port_range': None},
                        'convert_to': convert_port_to_string,
                        'default': None, 'is_visible': True},
        'destination_port': {'allow_post': True, 'allow_put': True,
                             'validate': {'type:port_range': None},
                             'convert_to': convert_port_to_string,
                             'default': None, 'is_visible': True},
        'position': {'allow_post': False, 'allow_put': False,
                     'default': None, 'is_visible': True},
        'action': {'allow_post': True, 'allow_put': True,
                   'convert_to': convert_action_to_case_insensitive,
                   'validate': {'type:values': fw_valid_action_values},
                   'is_visible': True, 'default': 'deny'},
        'enabled': {'allow_post': True, 'allow_put': True,
                    'default': True, 'convert_to': attr.convert_to_boolean,
                    'is_visible': True},
    },
    'firewall_policies': {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True,
               'primary_key': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True,
                      'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': attr.NAME_MAX_LEN},
                 'is_visible': True, 'default': ''},
        'description': {'allow_post': True, 'allow_put': True,
                        'validate': {'type:string':
                                     attr.DESCRIPTION_MAX_LEN},
                        'is_visible': True, 'default': ''},
        'shared': {'allow_post': True, 'allow_put': True,
                   'default': False, 'convert_to': attr.convert_to_boolean,
                   'is_visible': True, 'required_by_policy': True,
                   'enforce_policy': True},
        'firewall_rules': {'allow_post': True, 'allow_put': True,
                           'validate': {'type:uuid_list': None},
                           'convert_to': attr.convert_none_to_empty_list,
                           'default': None, 'is_visible': True},
        'audited': {'allow_post': True, 'allow_put': True,
                    'default': False, 'convert_to': attr.convert_to_boolean,
                    'is_visible': True},
    },
    'firewalls': {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True,
               'primary_key': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True,
                      'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': attr.NAME_MAX_LEN},
                 'is_visible': True, 'default': ''},
        'description': {'allow_post': True, 'allow_put': True,
                        'validate': {'type:string':
                                     attr.DESCRIPTION_MAX_LEN},
                        'is_visible': True, 'default': ''},
        'admin_state_up': {'allow_post': True, 'allow_put': True,
                           'default': True,
                           'convert_to': attr.convert_to_boolean,
                           'is_visible': True},
        'status': {'allow_post': False, 'allow_put': False,
                   'is_visible': True},
        'shared': {'allow_post': True, 'allow_put': True,
                   'default': False, 'convert_to': attr.convert_to_boolean,
                   'is_visible': False, 'required_by_policy': True,
                   'enforce_policy': True},
        'firewall_policy_id': {'allow_post': True, 'allow_put': True,
                               'validate': {'type:uuid_or_none': None},
                               'is_visible': True},
    },
}

# A tenant may have a unique firewall and policy for each router
# when router insertion is used.
# Set default quotas to align with default l3 quota_router of 10
# though keep as separately controllable.

firewall_quota_opts = [
    cfg.IntOpt('quota_firewall',
               default=10,
               help=_('Number of firewalls allowed per tenant. '
                      'A negative value means unlimited.')),
    cfg.IntOpt('quota_firewall_policy',
               default=10,
               help=_('Number of firewall policies allowed per tenant. '
                      'A negative value means unlimited.')),
    cfg.IntOpt('quota_firewall_rule',
               default=100,
               help=_('Number of firewall rules allowed per tenant. '
                      'A negative value means unlimited.')),
]
cfg.CONF.register_opts(firewall_quota_opts, 'QUOTAS')


class Firewall(extensions.ExtensionDescriptor):

    @classmethod
    def get_name(cls):
        return "Firewall service"

    @classmethod
    def get_alias(cls):
        return "fwaas"

    @classmethod
    def get_description(cls):
        return "Extension for Firewall service"

    @classmethod
    def get_namespace(cls):
        return "http://wiki.openstack.org/Neutron/FWaaS/API_1.0"

    @classmethod
    def get_updated(cls):
        return "2013-02-25T10:00:00-00:00"

    @classmethod
    def get_resources(cls):
        special_mappings = {'firewall_policies': 'firewall_policy'}
        plural_mappings = resource_helper.build_plural_mappings(
            special_mappings, RESOURCE_ATTRIBUTE_MAP)
        attr.PLURALS.update(plural_mappings)
        action_map = {'firewall_policy': {'insert_rule': 'PUT',
                                          'remove_rule': 'PUT'}}
        return resource_helper.build_resource_info(plural_mappings,
                                                   RESOURCE_ATTRIBUTE_MAP,
                                                   p_const.FIREWALL,
                                                   action_map=action_map,
                                                   register_quota=True)

    @classmethod
    def get_plugin_interface(cls):
        return FirewallPluginBase

    def update_attributes_map(self, attributes):
        super(Firewall, self).update_attributes_map(
            attributes, extension_attrs_map=RESOURCE_ATTRIBUTE_MAP)

    def get_extended_resources(self, version):
        if version == "2.0":
            return RESOURCE_ATTRIBUTE_MAP
        else:
            return {}


@six.add_metaclass(abc.ABCMeta)
class FirewallPluginBase(service_base.ServicePluginBase):

    def get_plugin_name(self):
        return p_const.FIREWALL

    def get_plugin_type(self):
        return p_const.FIREWALL

    def get_plugin_description(self):
        return 'Firewall service plugin'

    @abc.abstractmethod
    def get_firewalls(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_firewall(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def create_firewall(self, context, firewall):
        pass

    @abc.abstractmethod
    def update_firewall(self, context, id, firewall):
        pass

    @abc.abstractmethod
    def delete_firewall(self, context, id):
        pass

    @abc.abstractmethod
    def get_firewall_rules(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_firewall_rule(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def create_firewall_rule(self, context, firewall_rule):
        pass

    @abc.abstractmethod
    def update_firewall_rule(self, context, id, firewall_rule):
        pass

    @abc.abstractmethod
    def delete_firewall_rule(self, context, id):
        pass

    @abc.abstractmethod
    def get_firewall_policy(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def get_firewall_policies(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def create_firewall_policy(self, context, firewall_policy):
        pass

    @abc.abstractmethod
    def update_firewall_policy(self, context, id, firewall_policy):
        pass

    @abc.abstractmethod
    def delete_firewall_policy(self, context, id):
        pass

    @abc.abstractmethod
    def insert_rule(self, context, id, rule_info):
        pass

    @abc.abstractmethod
    def remove_rule(self, context, id, rule_info):
        pass
