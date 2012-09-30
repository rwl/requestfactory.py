# -*- coding: utf-8 -*-
# Copyright 2010 Google Inc.
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

import logging

from requestfactory.server.exceptions import UnexpectedException, ReportableException
from requestfactory.server.service_layer import ServiceLayer


LOGGER = logging.getLogger(ServiceLayer.__class__.__name__)


class ServiceLayerDecorator(ServiceLayer):
    """Users that intend to alter how RequestFactory interacts with the domain
    environment can extend this type and provide it to
    {@link ServiceLayer#create(ServiceLayerDecorator...)}. The methods defined in
    this type will automatically delegate to the next decorator or the root
    service object after being processed by{@code create()}.
    """

    def __init__(self):
        # A pointer to the next deepest layer.
        self._next = None

    def createDomainObject(self, clazz):
        return self.getNext().createDomainObject(clazz)

    def createLocator(self, clazz):
        return self.getNext().createLocator(clazz)

    def createServiceInstance(self, requestContext):
        return self.getNext().createServiceInstance(requestContext)

    def createServiceLocator(self, clazz):
        return self.getNext().createServiceLocator(clazz)

    def getDomainClassLoader(self):
        return self.getNext().getDomainClassLoader()

    def getGetter(self, domainType, property_):
        return self.getNext().getGetter(domainType, property_)

    def getId(self, domainObject):
        return self.getNext().getId(domainObject)

    def getIdType(self, domainType):
        return self.getNext().getIdType(domainType)

    def getProperty(self, domainObject, property_):
        return self.getNext().getProperty(domainObject, property_)

    def getRequestReturnType(self, contextMethod):
        return self.getNext().getRequestReturnType(contextMethod)

    def getSetter(self, domainType, property_):
        return self.getNext().getSetter(domainType, property_)

    def getVersion(self, domainObject):
        return self.getNext().getVersion(domainObject)

    def invoke(self, domainMethod, *args):
        return self.getNext().invoke(domainMethod, args)

    def isLive(self, domainObject):
        return self.getNext().isLive(domainObject)

    def loadDomainObject(self, clazz, domainId):
        return self.getNext().loadDomainObject(clazz, domainId)

    def loadDomainObjects(self, classes, domainIds):
        return self.getNext().loadDomainObjects(classes, domainIds)

    def requiresServiceLocator(self, contextMethod, domainMethod):
        return self.getNext().requiresServiceLocator(contextMethod, domainMethod)

    def resolveClass(self, typeToken):
        return self.getNext().resolveClass(typeToken)

    def resolveClientType(self, domainClass, clientType, required):
        return self.getNext().resolveClientType(domainClass, clientType, required)

    def resolveDomainClass(self, clazz):
        return self.getNext().resolveDomainClass(clazz)

    def resolveDomainMethod(self, operation):
        return self.getNext().resolveDomainMethod(operation)

    def resolveLocator(self, domainType):
        return self.getNext().resolveLocator(domainType)

    def resolveRequestContext(self, operation):
        return self.getNext().resolveRequestContext(operation)

    def resolveRequestContextMethod(self, operation):
        return self.getNext().resolveRequestContextMethod(operation)

    def resolveRequestFactory(self, binaryName):
        return self.getNext().resolveRequestFactory(binaryName)

    def resolveServiceClass(self, requestContextClass):
        return self.getNext().resolveServiceClass(requestContextClass)

    def resolveServiceLocator(self, requestContext):
        return self.getNext().resolveServiceLocator(requestContext)

    def resolveTypeToken(self, proxyType):
        return self.getNext().resolveTypeToken(proxyType)

    def setProperty(self, domainObject, property_, expectedType, value):
        self.getNext().setProperty(domainObject, property_, expectedType, value)

    def validate(self, domainObject):
        return self.getNext().validate(domainObject)

    def die(self, e, message, *args):
        """Throw a fatal error up into the top-level processing code. This method
        should be used to provide diagnostic information that will help the
        end-developer track down problems when that data would expose
        implementation details of the server to the client.

        @param e a throwable with more data, may be {@code null}
        @param message a printf-style format string
        @param args arguments for the message
        @throws UnexpectedException this method never returns normally
        @see #report(String, Object...)
        """
        msg = message % args
        LOGGER.log(logging.CRITICAL, msg, e)
        raise UnexpectedException(msg, e)

    def getTop(self):
        """Returns the top-most service layer. General-purpose ServiceLayer decorators
        should use the instance provided by {@code getTop()} when calling public
        methods on the ServiceLayer API to allow higher-level decorators to
        override behaviors built into lower-level decorators.

        @return the ServiceLayer returned by
                {@link #create(ServiceLayerDecorator...)}
        """
        return self.top

    def report(self, msgOrUserGeneratedException, *args):
        """Report an exception thrown by code that is under the control of the
        end-developer.

        @param userGeneratedException an {@link InvocationTargetException} thrown
                 by an invocation of user-provided code
        @throws ReportableException this method never returns normally
        ---
        Return a message to the client. This method should not include any data
        that was not sent to the server by the client to avoid leaking data.

        @param msg a printf-style format string
        @param args arguments for the message
        @throws ReportableException this method never returns normally
        @see #die(Throwable, String, Object...)
        """
        if len(args) == 0:
            raise ReportableException(msgOrUserGeneratedException.getCause())
        else:
            raise ReportableException(msgOrUserGeneratedException % args)


    def getNext(self):
        """Retrieves the next service layer. Used only by the server-package code and
        accessed by used code via {@code super.doSomething()}.
        """
        if self._next is None:
            # Unexpected, all methods should be implemented by some layer
            raise NotImplementedError
        return self._next
