# -*- coding: utf-8 -*-
#
# Copyright 2014-2015 BigML
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
from __future__ import absolute_import


import os

from bigmler.tests.world import world

from bigml.api import HTTP_OK, HTTP_UNAUTHORIZED

def check_debug(command):
    """Adds verbosity level and command print.

    """
    debug = os.environ.get('BIGMLER_DEBUG', False)
    verbosity = 0
    extend_cmd = ''
    if debug == '1':
        verbosity = 1
    elif debug == '2':
        extend_cmd = ' --debug'
    command = "%s --verbosity %s%s" % (command, verbosity, extend_cmd)
    if debug:
        print command
    return command


def check_http_code(resources):
    """Checks the http code in the resource list

    """
    if resources['code'] == HTTP_OK:
        assert True
    else:
        assert False, "Response code: %s" % resources['code']


def store_init_resources():
    """Store the initial existing resources grouped by resource_type

    """
    world.count_resources('init')


def store_final_resources():
    """Store the final existing resources grouped by resource_type

    """
    world.count_resources('final')


def check_init_equals_final():
    """Checks that the number of resources grouped by type has not changed

    """
    world.check_init_equals_final()


#@step(r'I want to use api in DEV mode')
def i_want_api_dev_mode(step):
    world.api = world.api_dev_mode
    # Update counters of resources for DEV mode
    world.count_resources('init')
