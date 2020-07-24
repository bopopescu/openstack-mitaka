# Copyright 2014 Hewlett-Packard Development Company, L.P.
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
from oslo_log import log as logging

from designate.objects.adapters.yaml import base
from designate import objects
LOG = logging.getLogger(__name__)


class PoolTargetYAMLAdapter(base.YAMLAdapter):

    ADAPTER_OBJECT = objects.PoolTarget

    MODIFICATIONS = {
        'fields': {
            'type': {
                'read_only': False
            },
            'tsigkey_id': {
                'read_only': False
            },
            'description': {
                'read_only': False
            },
            'mains': {
                'read_only': False
            },
            'options': {
                'read_only': False
            }
        }
    }


class PoolTargetListYAMLAdapter(base.YAMLAdapter):

    ADAPTER_OBJECT = objects.PoolTargetList

    MODIFICATIONS = {}
