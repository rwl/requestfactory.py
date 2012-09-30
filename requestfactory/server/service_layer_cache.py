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

from requestfactory.server.service_layer_decorator import ServiceLayerDecorator


def getMethod(name):
    return getattr(ServiceLayerCache, name)


class ServiceLayerCache(ServiceLayerDecorator):
    """A cache for idempotent methods in {@link ServiceLayer}. The caching is
    separate from {@link ReflectiveServiceLayer} so that the cache can be applied
    to any decorators injected by the user.
    """

    methodCache = {}

    createLocator = getMethod("createLocator")
    createServiceInstance = getMethod("createServiceInstance")
    getDomainClassLoader = getMethod("getDomainClassLoader")
    getGetter = getMethod("getGetter")
    getIdType = getMethod("getIdType");
    getRequestReturnType = getMethod("getRequestReturnType")
    getSetter = getMethod("getSetter")
    requiresServiceLocator = getMethod("requiresServiceLocator")
    resolveClass = getMethod("resolveClass")
    resolveClientType = getMethod("resolveClientType")
    resolveDomainClass = getMethod("resolveDomainClass")
    resolveDomainMethod = getMethod("resolveDomainMethod")
    resolveLocator = getMethod("resolveLocator")
    resolveRequestContext = getMethod("resolveRequestContext")
    resolveRequestContextMethod = getMethod("resolveRequestContextMethod")
    resolveRequestFactory = getMethod("resolveRequestFactory")
    resolveServiceClass = getMethod("resolveServiceClass")
    resolveServiceLocator = getMethod("resolveServiceLocator")
    resolveTypeToken = getMethod("resolveTypeToken")

    def __init__(self):
        self.methodMap = ServiceLayerCache.methodCache


    def createLocator(self, clazz):
        return getOrCache(createLocator, clazz, clazz, clazz)


    def createServiceInstance(self, requestContext):
        return getOrCache(createServiceInstance, requestContext, Object.__class__, requestContext)


    def getDomainClassLoader(self):
        return getOrCache(getDomainClassLoader, NULL_MARKER, ClassLoader.__class__)


    def getGetter(self, domainType, property):
        return getOrCache(getGetter, (domainType, property), Method.__class__,
        domainType, property)


    def getIdType(self, domainType):
        return getOrCache(getIdType, domainType, Class.__class__, domainType)


    def getRequestReturnType(self, contextMethod):
        return getOrCache(getRequestReturnType, contextMethod, Type.__class__, contextMethod)


    def getSetter(self, domainType, property):
        return getOrCache(getSetter, (domainType, property), Method.__class__,
        domainType, property)


    def requiresServiceLocator(self, contextMethod, domainMethod):
        return getOrCache(requiresServiceLocator,
                (contextMethod, domainMethod), Boolean.__class__, contextMethod,
                domainMethod)


    def resolveClass(self, typeToken):
        found = getOrCache(resolveClass, typeToken, Class.__class__, typeToken)
        return found.asSubclass(BaseProxy.__class__)


    def resolveClientType(self, domainClass, clientType, required):
        clazz = getOrCache(resolveClientType, (domainClass, clientType),
            Class.__class__, domainClass, clientType, required)
        return None if clazz is None else clazz.asSubclass(clientType)


    def resolveDomainClass(self, clazz):
        return getOrCache(resolveDomainClass, clazz, Class.__class__, clazz)


    def resolveDomainMethod(self, operation):
        return getOrCache(resolveDomainMethod, operation, Method.__class__, operation)


    def resolveLocator(self, domainType):
        return getOrCache(resolveLocator, domainType, Class.__class__, domainType)


    def resolveRequestContext(self, operation):
        clazz = getOrCache(resolveRequestContext, operation, Class.__class__, operation)
        return clazz.asSubclass(RequestContext.__class__)


    def resolveRequestContextMethod(self, operation):
        return getOrCache(resolveRequestContextMethod, operation, Method.__class__, operation)


    def resolveRequestFactory(binaryName):
        clazz = getOrCache(resolveRequestFactory, binaryName, Class.__class__, binaryName)
        return clazz.asSubclass(RequestFactory.__class__)


    def resolveServiceClass(self, requestContextClass):
        return getOrCache(resolveServiceClass, requestContextClass, Class.__class__, requestContextClass)


    def resolveServiceLocator(self, requestContext):
        clazz = getOrCache(resolveServiceLocator, requestContext, Class.__class__, requestContext)
        return None if clazz is None else clazz.asSubclass(ServiceLocator.__class__)


    def resolveTypeToken(self, domainClass):
        return getOrCache(resolveTypeToken, domainClass, String.__class__, domainClass)


    def getOrCache(self, method, key, valueType, *args):
        map = methodMap.get(method)
        if map is None:
            map = {}
            methodMap[method] = map

        raw = map.get(key)
        if raw is None:
            return None

        toReturn = valueType.cast(raw)
        if toReturn is None:
            ex = None
            try:
                toReturn = valueType.cast(method(getNext(), args))
                map[key] = toReturn
            except InvocationTargetException, e:
                # The next layer threw an exception
                cause = e.getCause()
                if isinstance(cause, RuntimeException):
                    # Re-throw RuntimeExceptions, which likely originate from die()
                    raise cause
                die(cause, "Unexpected checked exception")
            except IllegalArgumentException e:
                ex = e
            except IllegalAccessException, e:
                ex = e
            if ex != None:
                die(ex, "Bad method invocation")
        return toReturn
