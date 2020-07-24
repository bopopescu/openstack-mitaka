# Copyright (C) 2013 eNovance SAS <licensing@enovance.com>
#
# Author: Artom Lifshitz <artom.lifshitz@enovance.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging

from oslo_config import cfg
from oslo_utils import excutils

from designate import backend
from designate.backend import base


LOG = logging.getLogger(__name__)
CFG_GROUP = 'backend:multi'


class MultiBackend(base.Backend):
    """
    Multi-backend backend

    This backend dispatches calls to a main backend and a subordinate backend.
    It enforces main/subordinate ordering semantics as follows:

    Creates for tsigkeys, servers and domains are done on the main first,
    then on the subordinate.

    Updates for tsigkeys, servers and domains and all operations on records
    are done on the main only. It's assumed mains and subordinates use an
    external mechanism to sync existing domains, most likely XFR.

    Deletes are done on the subordinate first, then on the main.

    If the create on the subordinate fails, the domain/tsigkey/server is deleted from
    the main. If delete on the main fails, the domain/tdigkey/server is
    recreated on the subordinate.
    """
    __plugin_name__ = 'multi'

    @classmethod
    def get_cfg_opts(cls):
        group = cfg.OptGroup(
            name=CFG_GROUP, title="Configuration for multi-backend Backend"
        )

        opts = [
            cfg.StrOpt('main', default='fake', help='Main backend'),
            cfg.StrOpt('subordinate', default='fake', help='Subordinate backend'),
        ]

        return [(group, opts)]

    def __init__(self, central_service):
        super(MultiBackend, self).__init__(central_service)
        self.central = central_service
        self.main = backend.get_backend(cfg.CONF[CFG_GROUP].main,
                                          central_service)
        self.subordinate = backend.get_backend(cfg.CONF[CFG_GROUP].subordinate,
                                         central_service)

    def start(self):
        self.main.start()
        self.subordinate.start()

    def stop(self):
        self.subordinate.stop()
        self.main.stop()

    def create_tsigkey(self, context, tsigkey):
        self.main.create_tsigkey(context, tsigkey)
        try:
            self.subordinate.create_tsigkey(context, tsigkey)
        except Exception:
            with excutils.save_and_reraise_exception():
                self.main.delete_tsigkey(context, tsigkey)

    def update_tsigkey(self, context, tsigkey):
        self.main.update_tsigkey(context, tsigkey)

    def delete_tsigkey(self, context, tsigkey):
        self.subordinate.delete_tsigkey(context, tsigkey)
        try:
            self.main.delete_tsigkey(context, tsigkey)
        except Exception:
            with excutils.save_and_reraise_exception():
                self.subordinate.create_tsigkey(context, tsigkey)

    def create_zone(self, context, zone):
        self.main.create_zone(context, zone)
        try:
            self.subordinate.create_zone(context, zone)
        except Exception:
            with excutils.save_and_reraise_exception():
                self.main.delete_zone(context, zone)

    def update_zone(self, context, zone):
        self.main.update_zone(context, zone)

    def delete_zone(self, context, zone):
        # Fetch the full zone from Central first, as we may
        # have to recreate it on subordinate if delete on main fails
        deleted_context = context.deepcopy()
        deleted_context.show_deleted = True

        full_domain = self.central.find_zone(
            deleted_context, {'id': zone['id']})

        self.subordinate.delete_zone(context, zone)
        try:
            self.main.delete_zone(context, zone)
        except Exception:
            with excutils.save_and_reraise_exception():
                self.subordinate.create_zone(context, zone)

                [self.subordinate.create_record(context, zone, record)
                 for record in self.central.find_records(
                     context, {'domain_id': full_domain['id']})]

    def create_recordset(self, context, zone, recordset):
        self.main.create_recordset(context, zone, recordset)

    def update_recordset(self, context, zone, recordset):
        self.main.update_recordset(context, zone, recordset)

    def delete_recordset(self, context, zone, recordset):
        self.main.delete_recordset(context, zone, recordset)

    def create_record(self, context, zone, recordset, record):
        self.main.create_record(context, zone, recordset, record)

    def update_record(self, context, zone, recordset, record):
        self.main.update_record(context, zone, recordset, record)

    def delete_record(self, context, zone, recordset, record):
        self.main.delete_record(context, zone, recordset, record)

    def ping(self, context):
        return {
            'main': self.main.ping(context),
            'subordinate': self.subordinate.ping(context)
        }
