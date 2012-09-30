# -*- coding: utf-8 -*-
# Copyright 2011 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

from requestfactory.shared.impl.constants import Constants
from requestfactory.server.service_layer_decorator import ServiceLayerDecorator
from requestfactory.shared.entity_proxy_id import EntityProxyId
from requestfactory.shared.impl.find_request import FindRequest
from requestfactory.server.impl.find_service import FindService


class FindServiceLayer(ServiceLayerDecorator):
    """Allows the use of a very short operation name for the find method. This
    also avoids the need to introduce special-case code for FindRequest into
    RequestFactoryInterfaceValidator.
    """

    def resolveDomainMethod(self, operation):
        if Constants.FIND_METHOD_OPERATION == operation:
            try:
                return getattr(FindService, 'find')
            except self.SecurityException, e:
                ex = e
            except self.NoSuchMethodException, e:
                ex = e
            self.die(ex, 'Could not retrieve %s.find() method',
                     FindService.__class__.__name__)
        return super(FindServiceLayer, self).resolveDomainMethod(operation)


    def resolveRequestContext(self, operation):
        if Constants.FIND_METHOD_OPERATION == operation:
            return FindRequest
        return super(FindServiceLayer, self).resolveRequestContext(operation)


    def resolveRequestContextMethod(self, operation):
        if Constants.FIND_METHOD_OPERATION == operation:
            try:
                return getattr(FindRequest, 'find')#, EntityProxyId)
            except self.SecurityException, e:
                ex = e
            except self.NoSuchMethodException, e:
                ex = e
            self.die(ex, 'Could not retrieve %s.find() method',
                     FindRequest.__class__.__name__)
        return super(FindServiceLayer, self).resolveRequestContextMethod(operation)
