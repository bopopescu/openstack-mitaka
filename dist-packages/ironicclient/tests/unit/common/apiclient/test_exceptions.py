# Copyright 2012 OpenStack Foundation
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

from oslotest import base as test_base
import six
from six.moves import http_client

from ironicclient.common.apiclient import exceptions


class FakeResponse(object):
    json_data = {}

    def __init__(self, **kwargs):
        for key, value in six.iteritems(kwargs):
            setattr(self, key, value)

    def json(self):
        return self.json_data


class ExceptionsArgsTest(test_base.BaseTestCase):

    def assert_exception(self, ex_cls, method, url, status_code, json_data,
                         error_msg=None, error_details=None,
                         check_description=True):
        ex = exceptions.from_response(
            FakeResponse(status_code=status_code,
                         headers={"Content-Type": "application/json"},
                         json_data=json_data),
            method,
            url)
        self.assertIsInstance(ex, ex_cls)
        if check_description:
            expected_msg = error_msg or json_data["error"]["message"]
            expected_details = error_details or json_data["error"]["details"]
            self.assertEqual(expected_msg, ex.message)
            self.assertEqual(expected_details, ex.details)
        self.assertEqual(method, ex.method)
        self.assertEqual(url, ex.url)
        self.assertEqual(status_code, ex.http_status)

    def test_from_response_known(self):
        method = "GET"
        url = "/fake"
        status_code = http_client.BAD_REQUEST
        json_data = {"error": {"message": "fake message",
                               "details": "fake details"}}
        self.assert_exception(
            exceptions.BadRequest, method, url, status_code, json_data)

    def test_from_response_unknown(self):
        method = "POST"
        url = "/fake-unknown"
        status_code = 499
        json_data = {"error": {"message": "fake unknown message",
                               "details": "fake unknown details"}}
        self.assert_exception(
            exceptions.HTTPClientError, method, url, status_code, json_data)
        status_code = 600
        self.assert_exception(
            exceptions.HttpError, method, url, status_code, json_data)

    def test_from_response_non_openstack(self):
        method = "POST"
        url = "/fake-unknown"
        status_code = http_client.BAD_REQUEST
        json_data = {"alien": 123}
        self.assert_exception(
            exceptions.BadRequest, method, url, status_code, json_data,
            check_description=False)

    def test_from_response_with_different_response_format(self):
        method = "GET"
        url = "/fake-wsme"
        status_code = http_client.BAD_REQUEST
        json_data1 = {"error_message": {"debuginfo": None,
                                        "faultcode": "Client",
                                        "faultstring": "fake message"}}
        message = six.text_type(
            json_data1["error_message"]["faultstring"])
        details = six.text_type(json_data1)
        self.assert_exception(
            exceptions.BadRequest, method, url, status_code, json_data1,
            message, details)

        json_data2 = {"badRequest": {"message": "fake message",
                                     "code": http_client.BAD_REQUEST}}
        message = six.text_type(json_data2["badRequest"]["message"])
        details = six.text_type(json_data2)
        self.assert_exception(
            exceptions.BadRequest, method, url, status_code, json_data2,
            message, details)

    def test_from_response_with_text_response_format(self):
        method = "GET"
        url = "/fake-wsme"
        status_code = http_client.BAD_REQUEST
        text_data1 = "error_message: fake message"

        ex = exceptions.from_response(
            FakeResponse(status_code=status_code,
                         headers={"Content-Type": "text/html"},
                         text=text_data1),
            method,
            url)
        self.assertIsInstance(ex, exceptions.BadRequest)
        self.assertEqual(text_data1, ex.details)
        self.assertEqual(method, ex.method)
        self.assertEqual(url, ex.url)
        self.assertEqual(status_code, ex.http_status)

    def test_from_response_with_text_response_format_with_no_body(self):
        method = "GET"
        url = "/fake-wsme"
        status_code = http_client.UNAUTHORIZED

        ex = exceptions.from_response(
            FakeResponse(status_code=status_code,
                         headers={"Content-Type": "text/html"}),
            method,
            url)
        self.assertIsInstance(ex, exceptions.Unauthorized)
        self.assertEqual('', ex.details)
        self.assertEqual(method, ex.method)
        self.assertEqual(url, ex.url)
        self.assertEqual(status_code, ex.http_status)
