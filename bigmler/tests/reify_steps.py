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
import time
import re

from bigmler.tests.world import world, res_filename
from subprocess import check_call, CalledProcessError
from bigmler.checkpoint import file_number_of_lines
from bigmler.utils import SYSTEM_ENCODING, PYTHON3, open_mode
from bigml.api import check_resource
from bigmler.tests.common_steps import check_debug


def python3_contents(filename, prior_contents):
    """Check for a file that has alternative contents for Python3 and return
       its contents

    """
    directory = os.path.dirname(filename)
    basename = os.path.basename(filename)
    basename_name, basename_ext = basename.split(".")
    filename = os.path.join(directory, "%s_py3.%s" % ( \
        basename_name, basename_ext))
    try:
        with open(filename, open_mode("r")) as file_handler:
            return file_handler.read()
    except IOError:
        return prior_contents


#@step(r'I create a reify output for the resource in "(.*)" for "(.*)')
def i_create_output(step, output=None, language=None, resource_type='source',
                    add_fields=False):
    if output is None and language is None:
        assert False
    world.directory = os.path.dirname(output)
    world.folders.append(world.directory)
    resource_id = getattr(world, resource_type)['resource']
    try:
        command = (u"bigmler reify --id " + resource_id +
                   u" --store --output " + output)
        if add_fields:
            command += u' --add-fields'
        command = check_debug(command)
        if not PYTHON3:
            command.encode(SYSTEM_ENCODING)
        retcode = check_call(command, shell=True)
        if retcode < 0:
            assert False
        else:
            world.output = world.directory
            assert True
    except (OSError, CalledProcessError, IOError) as exc:
        assert False, str(exc)


#@step(r'the "(.*)" file is like "(.*)"')
def i_check_output_file(step, output=None, check_file=None):
    if check_file is None or output is None:
        assert False
    check_file = res_filename(check_file)
    try:
        output_file = os.path.join(world.directory, "reify.py")
        with open(check_file, open_mode("r")) as check_file_handler:
            check_contents = check_file_handler.read().strip("\n")
        # remove unicode mark for strings if Python3
        if PYTHON3:
            check_contents = check_contents.replace( \
                " u'", " '").replace("{u'", "{'")
        with open(output_file, open_mode("r")) as output_file:
            output_file_contents = output_file.read()
        #strip comments at the beginning of the file
        output_file_contents = re.sub(r'""".*"""', '', output_file_contents,
                                      flags=re.S).strip("\n")
        if check_contents == output_file_contents:
            assert True
        else:
            if PYTHON3:
                # look for an alternative in PYTHON3
                check_contents = python3_contents(check_file, check_contents)
            if check_contents == output_file_contents:
                assert True
            else:
                assert False, ("File contents:\n%s\nExpected contents:\n%s" %
                               (output_file_contents, check_contents))
    except Exception, exc:
        assert False, str(exc)


#@step(r'I create a BigML source with data "(.*)" and params "(.*)"')
def create_source(filename, output=None, args=None):
    source = world.api.create_source(res_filename(filename), args)
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])


#@step(r'I create a BigML dataset from a source with data "(.*)" and params "(.*)"')
def create_dataset(filename, output=None, args=None):
    source = world.api.create_source(res_filename(filename))
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])
    world.dataset = world.api.create_dataset(source, args)
    world.api.ok(world.dataset)
    world.datasets.append(world.dataset['resource'])


#@step(r'I create a BigML model from a dataset with data "(.*)" and params "(.*)"')
def create_model(filename, output=None, args=None):
    source = world.api.create_source(res_filename(filename))
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])
    world.dataset = world.api.create_dataset(source)
    world.api.ok(world.dataset)
    world.datasets.append(world.dataset['resource'])
    world.model = world.api.create_model(world.dataset, args)
    world.api.ok(world.model)
    world.models.append(world.model['resource'])

#@step(r'I create a BigML prediction for (.*) from a model with data "(.*)" and params "(.*)"')
def create_prediction(filename, input_data= None, output=None, args=None):
    source = world.api.create_source(res_filename(filename))
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])
    world.dataset = world.api.create_dataset(source)
    world.api.ok(world.dataset)
    world.datasets.append(world.dataset['resource'])
    world.model = world.api.create_model(world.dataset)
    world.api.ok(world.model)
    world.models.append(world.model['resource'])
    world.prediction = world.api.create_prediction(world.model, input_data, args)
    world.api.ok(world.prediction)
    world.predictions.append(world.prediction['resource'])

#@step(r'I create a BigML cluster from a dataset with data "(.*)" and params "(.*)"')
def create_cluster(filename, output=None, args=None):
    source = world.api.create_source(res_filename(filename))
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])
    world.dataset = world.api.create_dataset(source)
    world.api.ok(world.dataset)
    world.datasets.append(world.dataset['resource'])
    world.cluster = world.api.create_cluster(world.dataset, args)
    world.api.ok(world.cluster)
    world.clusters.append(world.cluster['resource'])

#@step(r'I create a BigML anomaly from a dataset with data "(.*)" and params "(.*)"')
def create_anomaly(filename, output=None, args=None):
    source = world.api.create_source(res_filename(filename))
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])
    world.dataset = world.api.create_dataset(source)
    world.api.ok(world.dataset)
    world.datasets.append(world.dataset['resource'])
    world.anomaly = world.api.create_anomaly(world.dataset, args)
    world.api.ok(world.anomaly)
    world.anomalies.append(world.anomaly['resource'])

#@step(r'I create a BigML centroid for (.*) from a cluster with data "(.*)" and params "(.*)"')
def create_centroid(filename, input_data=None, output=None, args=None):
    source = world.api.create_source(res_filename(filename))
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])
    world.dataset = world.api.create_dataset(source)
    world.api.ok(world.dataset)
    world.datasets.append(world.dataset['resource'])
    world.cluster = world.api.create_cluster(world.dataset)
    world.api.ok(world.cluster)
    world.clusters.append(world.cluster['resource'])
    world.centroid = world.api.create_centroid(world.cluster, input_data, args)
    world.api.ok(world.centroid)
    world.centroids.append(world.centroid['resource'])

#@step(r'I create a BigML anomaly score for (.*) from an anomaly detector with data "(.*)" and params "(.*)"')
def create_anomaly_score(filename, input_data=None, output=None, args=None):
    source = world.api.create_source(res_filename(filename))
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])
    world.dataset = world.api.create_dataset(source)
    world.api.ok(world.dataset)
    world.datasets.append(world.dataset['resource'])
    world.anomaly = world.api.create_anomaly(world.dataset)
    world.api.ok(world.anomaly)
    world.anomalies.append(world.anomaly['resource'])
    world.anomaly_score = world.api.create_anomaly_score(world.anomaly, input_data, args)
    world.api.ok(world.anomaly_score)
    world.anomaly_scores.append(world.anomaly_score['resource'])

#@step(r'I create a BigML batch prediction from a model with data "(.*)" and params "(.*)"')
def create_batch_prediction(filename, output=None, args=None):
    source = world.api.create_source(res_filename(filename))
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])
    world.dataset = world.api.create_dataset(source)
    world.api.ok(world.dataset)
    world.datasets.append(world.dataset['resource'])
    world.model = world.api.create_model(world.dataset)
    world.api.ok(world.model)
    world.models.append(world.model['resource'])
    world.batch_prediction = world.api.create_batch_prediction(world.model, world.dataset, args)
    world.api.ok(world.batch_prediction)
    world.batch_predictions.append(world.batch_prediction['resource'])

#@step(r'I create a BigML batch centroid from a cluster with data "(.*)" and params "(.*)"')
def create_batch_centroid(filename, output=None, args=None):
    source = world.api.create_source(res_filename(filename))
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])
    world.dataset = world.api.create_dataset(source)
    world.api.ok(world.dataset)
    world.datasets.append(world.dataset['resource'])
    world.cluster = world.api.create_cluster(world.dataset)
    world.api.ok(world.cluster)
    world.clusters.append(world.cluster['resource'])
    world.batch_centroid = world.api.create_batch_centroid(world.cluster, world.dataset, args)
    world.api.ok(world.batch_centroid)
    world.batch_centroids.append(world.batch_centroid['resource'])

#@step(r'I create a BigML batch anomaly score from an anomaly detector with data "(.*)" and params "(.*)"')
def create_batch_anomaly_score(filename, output=None, args=None):
    source = world.api.create_source(res_filename(filename))
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])
    world.dataset = world.api.create_dataset(source)
    world.api.ok(world.dataset)
    world.datasets.append(world.dataset['resource'])
    world.anomaly = world.api.create_anomaly(world.dataset)
    world.api.ok(world.anomaly)
    world.anomalies.append(world.anomaly['resource'])
    world.batch_anomaly_score = world.api.create_batch_anomaly_score(world.anomaly, world.dataset, args)
    world.api.ok(world.batch_anomaly_score)
    world.batch_anomaly_scores.append(world.batch_anomaly_score['resource'])

#@step(r'I create a BigML evaluation with data "(.*)" and params "(.*)"')
def create_evaluation(filename, output=None, args=None):
    source = world.api.create_source(res_filename(filename))
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])
    world.dataset = world.api.create_dataset(source)
    world.api.ok(world.dataset)
    world.datasets.append(world.dataset['resource'])
    world.model = world.api.create_model(world.dataset)
    world.api.ok(world.model)
    world.models.append(world.model['resource'])
    world.evaluation = world.api.create_evaluation(world.model, world.dataset, args)
    world.api.ok(world.evaluation)
    world.evaluations.append(world.evaluation['resource'])


#@step(r'I create a BigML ensemble from a dataset with data "(.*)" and params "(.*)"')
def create_ensemble(filename, output=None, args=None):
    source = world.api.create_source(res_filename(filename))
    world.source = source
    world.directory = os.path.dirname(output)
    world.output = output
    world.api.ok(world.source)
    world.sources.append(source['resource'])
    world.dataset = world.api.create_dataset(source)
    world.api.ok(world.dataset)
    world.datasets.append(world.dataset['resource'])
    world.ensemble = world.api.create_ensemble(world.dataset, args)
    world.api.ok(world.ensemble)
    world.ensembles.append(world.ensemble['resource'])
