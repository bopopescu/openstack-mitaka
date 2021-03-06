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

import testtools

from openstack.cluster.v1 import profile


FAKE_ID = '9b127538-a675-4271-ab9b-f24f54cfe173'
FAKE_NAME = 'test_profile'

FAKE = {
    'metadata': {},
    'name': FAKE_NAME,
    'id': FAKE_ID,
    'spec': {
        'type': 'os.nova.server',
        'version': 1.0,
        'properties': {
            'flavor': 1,
            'image': 'cirros-0.3.2-x86_64-uec',
            'key_name': 'oskey',
            'name': 'cirros_server'
        }
    },
    'type': 'os.nova.server'
}


class TestProfile(testtools.TestCase):

    def setUp(self):
        super(TestProfile, self).setUp()

    def test_basic(self):
        sot = profile.Profile()
        self.assertEqual('profile', sot.resource_key)
        self.assertEqual('profiles', sot.resources_key)
        self.assertEqual('/profiles', sot.base_path)
        self.assertEqual('clustering', sot.service.service_type)
        self.assertTrue(sot.allow_create)
        self.assertTrue(sot.allow_retrieve)
        self.assertTrue(sot.allow_update)
        self.assertTrue(sot.allow_delete)
        self.assertTrue(sot.allow_list)
        self.assertTrue(sot.patch_update)

    def test_instantiate(self):
        sot = profile.Profile(FAKE)
        self.assertEqual(FAKE['id'], sot.id)
        self.assertEqual(FAKE['name'], sot.name)
        self.assertEqual(FAKE['metadata'], sot.metadata)
        self.assertEqual(FAKE['spec'], sot.spec)
        self.assertEqual(FAKE['type'], sot.type_name)
