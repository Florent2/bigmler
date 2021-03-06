# -*- coding: utf-8 -*-
#
# Copyright 2015 BigML
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

"""RESTChain class that reifies the chain of REST API calls needed to build
   a resource

"""

from __future__ import absolute_import

import sys
import math
import os

import bigmler.reify.restutils as u

from bigml.resourcehandler import get_resource_id, get_resource_type
from bigml.fields import Fields
from bigml.basemodel import retrieve_resource

from bigmler.reify.reify_defaults import COMMON_DEFAULTS, DEFAULTS

GET_QS = 'limit=-1;exclude=root,trees'
PREFIXES = {
    "python": ('"""Python code to reify %s\n\n"""\n\n'
               'from bigml.api import BigML\napi = BigML()\n\n')
}


def uniquify(resource_ids):
    """Ensure the list of objects has unique resource ids maintaining the
       priority order found by reify

    """
    unique_objects = []
    for resource_id in reversed(resource_ids):
        if not resource_id in unique_objects:
            unique_objects.append(resource_id)
    return unique_objects


class RESTChain(object):

    """List of REST calls in reverse order leading to the resource creation

    """


    def __init__(self, api, resource_id, add_fields,
                 logger=None, storage=None):
        """Constructor: empty list of objects and REST calls

        """

        def silent(message):
            """No logging

            """
            pass

        self.calls = {}
        self.objects = [resource_id]
        self.api = api
        self.delete = not self.api.storage
        if self.delete:
            self.api.storage = storage or os.getcwd()
        self.add_fields = add_fields
        self.logger = logger or silent
        self.reify_resource(resource_id)
        self.objects = uniquify(self.objects)
        if self.delete:
            self.api.storage = None

    def get_resource(self, resource_id):
        """Auxiliar method to retrieve resources. The query string ensures
           low bandwith usage and full fields structure.

        """
        if (resource_id and not isinstance(resource_id, basestring) and
                isinstance(resource_id, list)):
            resource_id = resource_id[0]
        try:
            resource = retrieve_resource(self.api, resource_id,
                                      query_string=GET_QS).get('object')
            return resource
        except ValueError:
            sys.exit("We could not reify the resource. Failed to find"
                     " information for %s in the"
                     " creation chain." % resource_id)

    def delete_stored_resource(self, resource_id):
        """Deletes the copy of the resource stored to fasten the analysis

        """
        if self.api.storage is not None:
            try:
                stored_resource = "%s%s%s" % (self.api.storage, os.sep,
                                              resource_id.replace("/", "_"))
                os.remove(stored_resource)
            except IOError:
                pass

    def add(self, resource_id, calls):
        """Extend the list of calls and objects

        """
        if not resource_id in self.calls:
            self.calls[resource_id] = calls
        for call in calls:
            for origins in call.origins:
                if isinstance(origins, basestring):
                    origins = [origins]
                for origin in origins:
                    if not origin in self.objects:
                        message = "New origin found for %s: %s\n" % \
                            (resource_id, origin)
                        self.logger(message)
                    self.objects.append(origin)
                    if not origin in self.calls:
                        self.reify_resource(origin)
                    else:
                        new_origins = []
                        calls = self.calls[origin]
                        for call in calls:
                            # only create calls will introduce new origins
                            if call.action == "create":
                                new_origins.extend(call.origins)
                        self.objects.extend(new_origins)

    def reify(self, language=None):
        """Prints the chain of commands in the user-given language

        """
        prefix = PREFIXES.get(language, "") % self.objects[-1]
        out = prefix
        counts = {}
        alias = {}
        for resource_id in self.objects:
            for call in self.calls.get(resource_id, []):
                u.get_resource_alias(resource_id, counts, alias)
                out += call.reify(language, alias=alias)
        return out

    def reify_resource(self, resource_id):
        """Redirects to the reify method according to the resource type

        """
        # first check if this is a valid id
        resource_id = get_resource_id(resource_id)

        if resource_id is not None:
            resource_type = get_resource_type(resource_id)

            reify_handler = getattr(self, 'reify_%s' % resource_type)
            message = "Analyzing %s.\n" % resource_id
            self.logger(message)
            reify_handler(resource_id)
            if self.delete:
                self.delete_stored_resource(resource_id)

    def reify_source(self, resource_id):
        """Extracts the REST API arguments from the source JSON structure

        """
        resource_type = get_resource_type(resource_id)
        child = self.get_resource(resource_id)

        opts = {"create": {}, "update": {}}

        # create options
        source_defaults = DEFAULTS[resource_type].get("create", {})
        source_defaults.update(COMMON_DEFAULTS.get("create", {}))
        # special case, souces can be named like uploaded files
        name_as_file = [child.get('file_name')]
        name_as_file.extend(source_defaults["name"])
        source_defaults["name"] = name_as_file

        for attribute, default_value in source_defaults.items():
            opts["create"].update(
                u.default_setting(child, attribute, *default_value))

        # data
        if child.get('remote') is not None:
            data = child['remote']
        elif child.get('file_name') is not None:
            data = child['file_name']
        else:
            data = "UNKNOWN-INLINE-DATA"

        # update options
        source_defaults = DEFAULTS[resource_type].get("update", {})

        for attribute, default_value in source_defaults.items():
            opts["update"].update(
                u.default_setting(child, attribute, *default_value))

        # We add the information for the updatable fields only when requested.
        if self.add_fields:
            opts["update"].update({"fields": u.get_fields_changes(child)})

        calls = u.build_calls(resource_id, [data], opts)
        self.add(resource_id, calls)


    def reify_dataset(self, resource_id):
        """Extracts the REST API arguments from the dataset JSON structure

        """
        child = self.get_resource(resource_id)
        origin, parent_id = u.get_origin_info(child)
        parent = self.get_resource(parent_id)

        opts = {"create": {}, "update": {}}

        # as two-steps result from a cluster or batch prediction, centroid
        # or anomaly score
        if origin in ['origin_batch_resource', 'cluster']:
            if origin == "cluster":
                opts['create'].update({"centroid": child['centroid']})
            _, grandparent = u.get_origin_info(parent)
            grandparent = self.get_resource(grandparent)
        else:
            grandparent = parent

        # options common to all model types
        u.common_dataset_opts(child, grandparent, opts)

        # update options
        dataset_defaults = DEFAULTS["dataset"].get("update", {})
        dataset_defaults.update(COMMON_DEFAULTS.get("update", {}))

        for attribute, default_value in dataset_defaults.items():
            opts["update"].update(
                u.default_setting(child, attribute, *default_value))

        # name, exclude automatic naming alternatives
        autonames = [u'']
        suffixes = [u"filtered", u"sampled", u"dataset", u"extended",
                    u"- batchprediction", u"- batchanomalyscore",
                    u"- batchcentroid", u"- merged"]
        autonames.extend([u'%s %s' % (grandparent.get('name', ''), suffix)
                          for suffix in suffixes])
        autonames.append(
            u"%s's dataset" % '.'.join(parent['name'].split('.')[0:-1]))
        autonames.append(
            u"%s' dataset" % '.'.join(parent['name'].split('.')[0:-1]))
        autonames.append(
            u"Cluster %s - %s" % (int(child.get('centroid', "0"), base=16),
                                  parent['name']))
        autonames.append(
            u"Dataset from %s model - segment" % parent['name'])
        u.non_automatic_name(child, opts, autonames=autonames)

        # objective field
        resource_fields = Fields(
            {'resource': child['resource'], 'object': child})
        objective_id = child['objective_field']['id']
        preferred_fields = resource_fields.preferred_fields()
        max_column = sorted([field['column_number']
                             for _, field in preferred_fields.items()],
                            reverse=True)[0]
        objective_column = resource_fields.fields[objective_id][ \
            'column_number']
        if objective_column != max_column:
            opts['create'].update({"objective_field": {"id": objective_id}})

        # resize
        if (child['size'] != grandparent['size'] and
                get_resource_type(parent) == 'source'):
            opts['create'].update({"size": child['size']})

        # generated fields
        if child.get('new_fields', None):
            new_fields = child['new_fields']
            for new_field in new_fields:
                new_field['field'] = new_field['generator']
                del new_field['generator']

            opts['create'].update({"new_fields": new_fields})

        u.range_opts(child, grandparent, opts)

        calls = u.build_calls(resource_id, [parent_id], opts)
        self.add(resource_id, calls)

    def reify_model(self, resource_id):
        """Extracts the REST API arguments from the model JSON structure

        """
        parent_id, opts = self._inspect_model(resource_id)

        calls = u.build_calls(resource_id, [parent_id], opts)
        self.add(resource_id, calls)

    def _inspect_model(self, resource_id):
        """Auxliliary function to use model JSON structure to define ensembles
           and models

        """
        child = self.get_resource(resource_id)
        origin, parent_id = u.get_origin_info(child)
        parent = self.get_resource(parent_id)
        opts = {"create": {}, "update": {}}
        # as two-steps result from a cluster
        if origin == 'cluster':
            opts['create'].update({"centroid": child['centroid']})
            _, grandparent = u.get_origin_info(parent)
            grandparent = self.get_resource(grandparent)
        elif origin == 'datasets':
            grandparent = parent
            if child.get('objective_field') != \
                    grandparent.get('objective_field').get('id'):
                opts['create'].update(
                    {"objective_field": child.get('objective_field')})
        else:
            grandparent = parent
            if child.get('objective_field') != \
                    grandparent.get('objective_field').get('id'):
                opts['create'].update(
                    {"objective_field": child.get('objective_field')})

        # the objective field name is automatically added to tags
        objective_field_name = child.get('objective_field_name','')
        if objective_field_name in child.get('tags'):
            child['tags'].remove(objective_field_name)
        # options common to all model types
        u.common_model_opts(child, grandparent, opts)

        # name, exclude automatic naming alternatives
        autonames = [u'']
        autonames.append(
            u"%s model" % grandparent.get('name', ''))
        autonames.append(
            u"Cluster %s - %s" % (int(child.get('centroid', "0"), base=16),
                                  parent['name']))

        u.non_automatic_name(child, opts, autonames=autonames)

        if child.get('randomize') == True:
            default_random_candidates = int(
                math.floor(math.sqrt(len(child['input_fields']))))
            opts['create'].update(
                u.default_setting( \
                    child, 'random_candidates', [default_random_candidates]))
        return parent_id, opts

    def reify_ensemble(self, resource_id):
        """Extracts the REST API arguments from the ensemble JSON structure

        """
        child = self.get_resource(resource_id)
        _, parent_id = u.get_origin_info(child)
        # add options defined at model level
        _, opts = self._inspect_model(child['models'][0])
        # the default value for replacement in models is the oposite, so
        # it will be added afterwards
        if 'replacement' in opts['create']:
            del opts['create']['replacement']
        # create options
        u.non_default_opts(child, opts)

        calls = u.build_calls(resource_id, [parent_id], opts)
        self.add(resource_id, calls)

    def reify_cluster(self, resource_id):
        """Extracts the REST API arguments from the cluster JSON structure

        """
        child = self.get_resource(resource_id)
        _, parent_id = u.get_origin_info(child)
        parent = self.get_resource(parent_id)

        opts = {"create": {}, "update": {}}

        # options common to all model types
        u.common_model_opts(child, parent, opts)

        if child.get('critical_value') is None and  'k' in child:
            opts['create'].update({"k": child['k']})

        # name, exclude automatic naming alternatives
        u.non_automatic_name( \
            child, opts, autoname=u'%s cluster' % parent.get('name', ''))

        calls = u.build_calls(resource_id, [parent_id], opts)
        self.add(resource_id, calls)

    def reify_anomaly(self, resource_id):
        """Extracts the REST API arguments from the anomaly JSON structure

        """

        child = self.get_resource(resource_id)
        _, parent_id = u.get_origin_info(child)
        parent = self.get_resource(parent_id)

        opts = {"create": {}, "update": {}}

        # options common to all model types
        u.common_model_opts(child, parent, opts)

        # name, exclude automatic naming alternatives
        u.non_automatic_name(
            child, opts,
            autoname=u'%s anomaly detector' % parent.get('name', ''))

        calls = u.build_calls(resource_id, [parent_id], opts)
        self.add(resource_id, calls)

    def reify_prediction(self, resource_id):
        """ Extracts the REST API arguments from the prediction JSON structure:

        """
        child = self.get_resource(resource_id)
        origin, parent = u.get_origin_info(child)
        if origin == 'models':
            model = self.get_resource(parent[0])
            parent = self.get_resource('ensemble/%s' % model['ensemble_id'])
        else:
            parent = self.get_resource(parent)

        opts = {"create": {}, "update": {}}

        # non-inherited create options
        u.non_inherited_opts(child, parent, opts)

        # non-default create options
        u.non_default_opts(child, opts)

        opts['create'].update({'input_data': child['input_data']})

        # name, exclude automatic naming alternatives
        u.non_automatic_name(
            child, opts,
            autoname=u'Prediction for %s' % child['objective_field_name'])

        calls = u.build_calls(resource_id, [parent['resource']], opts)
        self.add(resource_id, calls)

    def reify_centroid(self, resource_id):
        """ Extracts the REST API arguments from the centroid JSON structure:

        """
        child = self.get_resource(resource_id)
        _, parent = u.get_origin_info(child)
        parent = self.get_resource(parent)

        opts = {"create": {}, "update": {}}

        # non-inherited create options
        u.non_inherited_opts(child, parent, opts)

        # non-default create options
        u.non_default_opts(child, opts)

        opts['create'].update({'input_data': child['input_data']})

        # name, exclude automatic naming alternatives
        u.non_automatic_name(
            child, opts,
            autoname=u'Centroid for %s' % parent['name'])
        # non-default update options
        u.non_default_opts(child, opts, call="update")

        calls = u.build_calls(resource_id, [parent['resource']], opts)
        self.add(resource_id, calls)

    def reify_anomalyscore(self, resource_id):
        """ Extracts the REST API arguments from the anomaly score
            JSON structure:

        """
        child = self.get_resource(resource_id)
        _, parent = u.get_origin_info(child)
        parent = self.get_resource(parent)

        opts = {"create": {}, "update": {}}

        # non-inherited create options
        u.non_inherited_opts(child, parent, opts)

        opts['create'].update({'input_data': child['input_data']})

        # name, exclude automatic naming alternatives
        u.non_automatic_name(
            child, opts,
            autoname=u'Score for %s' % parent['name'])

        calls = u.build_calls(resource_id, [parent['resource']], opts)
        self.add(resource_id, calls)

    def reify_evaluation(self, resource_id):
        """ Extracts the REST API arguments from the evaluation JSON structure:
            model/ensemble, dataset and args

        """

        child = self.get_resource(resource_id)
        # evalutations have 2 different origins as arguments
        [(_, parent1),
         (_, parent2)] = u.get_origin_info(child)
        parent1 = self.get_resource(parent1)
        parent2 = self.get_resource(parent2)


        opts = {"create": {}, "update": {}}

        # non-inherited create options
        u.non_inherited_opts(child, parent1, opts)

        # non-default create options
        u.non_default_opts(child, opts)

        # model/ensemble to dataset mapping
        fields = parent2['fields'].keys()
        default_map = dict(zip(fields, fields))
        opts['create'].update(
            u.default_setting(child, 'fields_map', default_map))

        # name, exclude automatic naming alternatives
        u.non_automatic_name(
            child, opts,
            autoname=u'Evaluation of %s with %s' % \
                (parent1.get('name', ''),
                 parent2.get('name', '')))

        # range in dataset
        if not child.get('range', []) in [[], [1, parent2.get('rows', None)]]:
            opts['create'].update({"range": child['range']})

        calls = u.build_calls(
            resource_id, [parent1['resource'], parent2['resource']], opts)
        self.add(resource_id, calls)

    def reify_batchprediction(self, resource_id):
        """ Extracts the REST API arguments from the batch prediction
            JSON structure:
            model/ensemble, dataset and args

        """
        child = self.get_resource(resource_id)
        # evalutations have 2 different origins as arguments
        [(_, parent1),
         (_, parent2)] = u.get_origin_info(child)
        parent1 = self.get_resource(parent1)
        parent2 = self.get_resource(parent2)

        opts = {"create": {}, "update": {}}

        # common create options for batch resources
        u.common_batch_options(child, parent1, parent2, opts)

        if child.get('header', True):
            opts['create'].update(
                u.default_setting(child, 'prediction_name', [None, '']))
            opts['create'].update(
                u.default_setting(child, 'centroid_name', [None, '']))

        # name, exclude automatic naming alternatives
        u.non_automatic_name(
            child, opts,
            autoname=u'Batch Prediction of %s with %s' % \
                (parent1.get('name', ''),
                 parent2.get('name', '')))

        calls = u.build_calls(
            resource_id, [parent1['resource'], parent2['resource']], opts)
        self.add(resource_id, calls)

    def reify_batchcentroid(self, resource_id):
        """ Extracts the REST API arguments from the batch centroid
            JSON structure:
            cluster, dataset and args

        """
        child = self.get_resource(resource_id)
        # batch resources have 2 different origins as arguments
        [(_, parent1),
         (_, parent2)] = u.get_origin_info(child)
        parent1 = self.get_resource(parent1)
        parent2 = self.get_resource(parent2)

        opts = {"create": {}, "update": {}}

        # common create options for batch resources
        u.common_batch_options(child, parent1, parent2, opts)

        if child.get('header', True):
            opts['create'].update(
                u.default_setting(child, 'distance_name', [None, '']))

        # name, exclude automatic naming alternatives
        u.non_automatic_name(
            child, opts,
            autoname=u'Batch Centroid of %s with %s' % \
                (parent1.get('name', ''),
                 parent2.get('name', '')))

        calls = u.build_calls(
            resource_id, [parent1['resource'], parent2['resource']], opts)
        self.add(resource_id, calls)

    def reify_batchanomalyscore(self, resource_id):
        """ Extracts the REST API arguments from the batch anomaly score
            JSON structure:
            anomaly detector, dataset and args

        """
        child = self.get_resource(resource_id)
        # batch resources have 2 different origins as arguments
        [(_, parent1),
         (_, parent2)] = u.get_origin_info(child)
        parent1 = self.get_resource(parent1)
        parent2 = self.get_resource(parent2)

        opts = {"create": {}, "update": {}}

        # common create options for batch resources
        u.common_batch_options(child, parent1, parent2, opts)

        # name, exclude automatic naming alternatives
        u.non_automatic_name(
            child, opts,
            autoname=u'Batch Anomaly Score of %s with %s' % \
                (parent1.get('name', ''),
                 parent2.get('name', '')))

        calls = u.build_calls(
            resource_id, [parent1['resource'], parent2['resource']], opts)
        self.add(resource_id, calls)
