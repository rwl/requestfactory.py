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

from requestfactory.server.service_layer_decorator import ServiceLayerDecorator

from requestfactory.vm.impl.deobfuscator import Deobfuscator, Builder


class ResolverServiceLayer(ServiceLayerDecorator):
    """Implements all of the resolution methods in ServiceLayer."""

    deobfuscator = None

    @classmethod
    def updateDeobfuscator(cls, clazz, resolveClassesWith):
        builder = Builder.load(clazz, resolveClassesWith)
        if cls.deobfuscator is None:
            builder.merge(cls.deobfuscator)
        cls.deobfuscator = builder.build()


    def resolveClass(self, typeToken):
        deobfuscated = self.deobfuscator.getTypeFromToken(typeToken)
        if deobfuscated is None:
            self.die(None, "No type for token %s", typeToken)
        return self.forName(deobfuscated).asSubclass(BaseProxy.__class__)


    def resolveClientType(self, domainClass, clientClass, required):
        if list.__class__.isAssignableFrom(domainClass):
            return list.__class__.asSubclass(clientClass)

        if set.__class__.isAssignableFrom(domainClass):
            return set.__class__.asSubclass(clientClass)

        if TypeUtils.isValueType(domainClass):
            return domainClass.asSubclass(clientClass)

        toSearch = domainClass
        while toSearch != None:
            clientTypes = self.deobfuscator.getClientProxies(toSearch.getName())
            if clientTypes is not None:
                for clientType in clientTypes:
                    proxy = self.forName(clientType)
                    if clientClass.isAssignableFrom(proxy):
                        return proxy.asSubclass(clientClass)
            toSearch = toSearch.getSuperclass()

        if required:
            self.die(None, "The domain type %s cannot be sent to the client",
                     domainClass.__class__.__name__)
        return None


    def resolveDomainClass(self, clazz):
        if list.__class__.equals(clazz):
            return list.__class__
        elif set.__class__.equals(clazz):
            return set.__class__
        elif BaseProxy.__class__.isAssignableFrom(clazz):
            pf = clazz.getAnnotation(ProxyFor.__class__)
            if pf is not None:
                return pf.value()
            pfn = clazz.getAnnotation(ProxyForName.__class__)
            if pfn is not None:
                toReturn = self.forName(pfn.value())
                return toReturn;
        return self.die(None, "Could not resolve a domain type for client type %s",
                   clazz.__class__.__name__)


    def resolveDomainMethod(self, operation):
        """The validator has already determined the mapping from the RequsetContext
        method to a domain method signature. We'll reuse this calculation instead
        of iterating over all methods.
        """
        domainDescriptor = self.deobfuscator.getDomainMethodDescriptor(operation)

        if domainDescriptor == None:
            return self.die(None,
                    "No domain method descriptor is mapped to operation %s",
                    operation)


        domainArgs = self.getArgumentTypes(domainDescriptor)
        requestContext = self.getTop().resolveRequestContext(operation)
        serviceImplementation = self.getTop().resolveServiceClass(requestContext)

        # Request<FooProxy> someMethod(int a, double b, FooProxy c);
        requestContextMethod = self.getTop().resolveRequestContextMethod(operation)

        ex = None
        try:
            return serviceImplementation.getMethod(requestContextMethod.getName(), domainArgs)
        except SecurityException, e:
            ex = e
        except NoSuchMethodException, e:
            ex = e

        return self.die(ex,
                "Could not find method in implementation %s matching descriptor %s for operation %s",
                serviceImplementation.getCanonicalName(), domainDescriptor, operation)


    def resolveRequestContext(self, operation):
        requestContextClass = self.deobfuscator.getRequestContext(operation)
        if requestContextClass is None:
            self.die(None, "No RequestContext for operation %s", operation)
        return self.forName(requestContextClass).asSubclass(RequestContext.__class__)


    def resolveRequestContextMethod(self, operation):
        searchIn = self.getTop().resolveRequestContext(operation)
        methodName = self.deobfuscator.getRequestContextMethodName(operation)
        descriptor = self.deobfuscator.getRequestContextMethodDescriptor(operation)
        params = self.getArgumentTypes(descriptor)
        try:
            return searchIn.getMethod(methodName, params)
        except NoSuchMethodException, ex:
            return self.report("Could not locate %s operation %s",
                    RequestContext.__class__.__name__, operation)


    def resolveRequestFactory(self, binaryName):
        toReturn = self.forName(binaryName).asSubclass(RequestFactory.__class__)
        self.updateDeobfuscator(toReturn, self.getTop().getDomainClassLoader())
        return toReturn


    def resolveServiceClass(self, requestContextClass):
        searchIn = None
        s = requestContextClass.getAnnotation(Service.__class__)
        if s is not None:
            searchIn = s.domainType
        sn = requestContextClass.getAnnotation(ServiceName.__class__)
        if sn is not None:
            searchIn = self.forName(sn.domainType)
        if searchIn is None:
            self.die(None, "The %s type %s did not specify a service type",
                     RequestContext.__class__.__name__,
                     requestContextClass.__class__.__name__)
        return searchIn


    def resolveTypeToken(self, clazz):
        return OperationKey.hash(clazz.getName())


    def forName(self, name):
        """Call {@link Class#forName(String)} and report any errors through
        {@link #die()}.
        """
        try:
            return Class.forName(name, False, self.getTop().getDomainClassLoader())
        except ClassNotFoundException, e:
            return self.die(e, "Could not locate class %s", name)


    def getArgumentTypes(self, descriptor):
        types = Type.getArgumentTypes(descriptor)
        params = list()
        for i in range(len(types)):
            params[i] = self.getClass(types[i])
        return params


    def getClass(self, type):
        if type.__class__ == bool:
            return boolean.__class__
        elif type.__class__ == float:
            return float.__class__
        elif type.__class__ == int:
            return int.__class__
        elif type.__class__ == long:
            return long.__class__
        elif type.__class__ == object:
            return forName(type.getClassName())
        elif type.__class__ == None:
            return None
        elif type.__class__ == list:
            return self.die(None,
                    "Unsupported Type used in operation descriptor %s",
                    type.getDescriptor());
        else:
            # Error in this switch statement
            return self.die(None, "Unhandled Type: %s", type.getDescriptor())
