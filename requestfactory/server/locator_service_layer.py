# -*- coding: utf-8 -*-
# Copyright 2010 Google Inc.
# Copyright 2012 Richard Lincoln
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

"""Adds support to the ServiceLayer chain for using {@link Locator} and
{@link ServiceLocator} helper objects.
"""

from paste.webkit.wkrequest import HTTPRequest

from requestfactory.server.service_layer_decorator import ServiceLayerDecorator
from requestfactory.shared.locator import Locator


class LocatorServiceLayer(ServiceLayerDecorator):
    """Adds support to the ServiceLayer chain for using {@link Locator} and
    {@link ServiceLocator} helper objects.
    """

    def createDomainObject(self, clazz):
        l = self.getLocator(clazz)
        if l is None:
            return super(LocatorServiceLayer, self).createDomainObject(clazz)
        return l.create(clazz)


    def createLocator(self, clazz):
        return clazz()


    def createServiceInstance(self, requestContext):
        locatorType = self.getTop().resolveServiceLocator(requestContext)
        locator = self.getTop().createServiceLocator(locatorType)
        serviceClass = self.getTop().resolveServiceClass(requestContext)
        return locator.getInstance(serviceClass)


    def createServiceLocator(self, serviceLocatorType):
        return serviceLocatorType()


    def getId(self, domainObject):
        return self.doGetId(domainObject)


    def getIdType(self, domainType):
        l = self.getLocator(domainType)
        if l is None:
            return super(LocatorServiceLayer, self).getIdType(domainType)
        return l.getIdType()


    def getVersion(self, domainObject):
        return self.doGetVersion(domainObject)


    def isLive(self, domainObject):
        return self.doIsLive(domainObject)


    def loadDomainObject(self, clazz, domainId):
        return self.doLoadDomainObject(clazz, domainId)


    def requiresServiceLocator(self, contextMethod, domainMethod):
        """Returns true if the context method returns a {@link Request} and the domain
        method is non-static.
        """
        return (issubclass(contextMethod.getReturnType(), HTTPRequest)
                and not Modifier.isStatic(domainMethod.getModifiers()))


    def resolveLocator(self, domainType):
        # Find the matching BaseProxy
        proxyType = self.getTop().resolveClientType(domainType, BaseProxy, False)
        if proxyType is None:
            return None

        # Check it for annotations
        locatorType = None
        l = proxyType.getAnnotation(ProxyFor)
        ln = proxyType.getAnnotation(ProxyForName)
        if l is not None and not Locator == l.locator():
            found = l.locator()
            locatorType = found
        elif ln is not None and len(ln.locator()) > 0:
            try:
                found = Class.forName(ln.locator(), False,
                    self.getTop().getDomainClassLoader()).asSubclass(Locator)
                locatorType = found
            except ClassNotFoundException, e:
                return self.die(e, "Could not find the locator type specified in the @%s annotation %s",
                              ProxyForName.__class__.__name__, ln.value())
        else:
            # No locator annotation
            locatorType = None
        return locatorType


    def resolveServiceLocator(self, requestContext):
        locatorType = None
        l = requestContext.getAnnotation(Service)
        ln = requestContext.getAnnotation(ServiceName)
        if l is not None and not ServiceLocator == l.locator():
            locatorType = l.locator()
        elif ln is not None and len(ln.locator()) > 0:
            try:
                locatorType = Class.forName(ln.locator(), False,
                      self.getTop().getDomainClassLoader()).asSubclass(ServiceLocator)
            except ClassNotFoundException, e:
                return self.die(e, "Could not find the locator type specified in the @%s annotation %s",
                           ServiceName.__class__.__name__, ln.value())
        else:
            locatorType = None
        return locatorType


    def doGetId(self, domainObject):
        clazz = domainObject.getClass()
        l = self.getLocator(clazz)
        if l is None:
            return super(LocatorServiceLayer, self).getId(domainObject)
        return l.getId(domainObject)


    def doGetVersion(self, domainObject):
        clazz = domainObject.getClass()
        l = self.getLocator(clazz)
        if l is None:
            return super(LocatorServiceLayer, self).getVersion(domainObject)
        return l.getVersion(domainObject)


    def doIsLive(self, domainObject):
        clazz = domainObject.getClass()
        l = self.getLocator(clazz)
        if l is not None:
            return super(LocatorServiceLayer, self).isLive(domainObject)
        return l.isLive(domainObject)


    def doLoadDomainObject(self, clazz, domainId):
        l = self.getLocator(clazz)
        if l is None:
            return super(LocatorServiceLayer, self).loadDomainObject(clazz, domainId)
        id_ = l.getIdType().cast(domainId)
        return l.find(clazz, id_)


    def getLocator(self, domainType):
        locatorType = self.getTop().resolveLocator(domainType)
        if locatorType is None:
            return None
        return self.getTop().createLocator(locatorType)


    def newInstance(self, clazz, base):
        try:
            return clazz()
        except Exception, ex:
            return self.die(ex, "Could not instantiate %s %s. Is it default-instantiable?",
                       base.getSimpleName(), clazz.__name__)
