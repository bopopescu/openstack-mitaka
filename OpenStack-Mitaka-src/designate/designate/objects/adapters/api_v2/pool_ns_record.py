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

from designate.objects.adapters.api_v2 import base
from designate import objects
LOG = logging.getLogger(__name__)


class PoolNsRecordAPIv2Adapter(base.APIv2Adapter):

    ADAPTER_OBJECT = objects.PoolNsRecord

    MODIFICATIONS = {
        'fields': {
            'priority': {
                'read_only': False
            },
            'hostname': {
                'read_only': False
            },
        },
        'options': {
            'links': False,
            'resource_name': 'ns_record',
            'collection_name': 'ns_records',
        }
    }


class PoolNsRecordListAPIv2Adapter(base.APIv2Adapter):

    ADAPTER_OBJECT = objects.PoolNsRecordList

    MODIFICATIONS = {
        'options': {
            'links': False,
            'resource_name': 'ns_record',
            'collection_name': 'ns_records',
        }
    }

    @classmethod
    def _render_list(cls, list_object, *args, **kwargs):

        r_list = super(PoolNsRecordListAPIv2Adapter, cls)._render_list(
            list_object, *args, **kwargs)

        return r_list[cls.MODIFICATIONS['options']['collection_name']]
