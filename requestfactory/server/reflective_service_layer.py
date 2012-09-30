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

import logging

from requestfactory.server.service_layer_decorator import ServiceLayerDecorator


LOGGER = logging.getLogger(__name__)


class ReflectiveServiceLayer(ServiceLayerDecorator):
    """Implements all methods that interact with domain objects."""

    # NB: All calls that ReflectiveServiceLayer makes to public APIs inherited
    # from ServiceLayer should be made to use the instance returned from
    # getTop().

    @classmethod
    def getBeanMethod(self, methodType, domainType, property_):
        """Linear search, but we want to handle getFoo, isFoo, and hasFoo. The
        result of this method will be cached by the ServiceLayerCache.
        """
        pass


    def createDomainObject(self, clazz):
        try:
            return clazz()
        except Exception, ex:
            return self.die(ex, "Could not create a new instance of domain type %s",
                    clazz.__name__)


    def getGetter(self, domainType, property_):
        return self.getBeanMethod(BeanMethod.GET, domainType, property_)


    def getId(self, domainObject):
        return self.getTop().getProperty(domainObject, "id")


    def getIdType(self, domainType):
        return self.getFind(domainType).getParameterTypes()[0]


    def getProperty(self, domainObject, property_):
        try:
            getter = self.getTop().getGetter(domainObject.getClass(), property_)
            if getter is None:
                self.die(None, "Could not determine getter for property %s on type %s",
                        property_, domainObject.__class__.__name__)
            value = getter(domainObject)
            return value
        except Exception, e:
            return self.die(e, "Could not retrieve property %s", property_)


    def getRequestReturnType(self, contextMethod):
        returnClass = contextMethod.getReturnType()
        if issubclass(returnClass, InstanceRequest):
            params = TypeUtils.getParameterization(InstanceRequest.__class__,
                    contextMethod.getGenericReturnType())
            assert len(params) == 2
            return params[1]
        elif issubclass(returnClass, Request):
            param = TypeUtils.getSingleParameterization(Request.__class__,
                    contextMethod.getGenericReturnType())
            return param
        else:
            return self.die(None, "Unknown RequestContext return type %s",
                    returnClass.__name__)


    def getSetter(self, domainType, property_):
        setter = self.getBeanMethod(BeanMethod.SET, domainType, property_)
        if setter is None:
            setter = self.getBeanMethod(BeanMethod.SET_BUILDER, domainType, property_)
        return setter


    def getVersion(self, domainObject):
        return self.getTop().getProperty(domainObject, "version")


    def invoke(self, domainMethod, *args):
        try:
            if Modifier.isStatic(domainMethod.getModifiers()):
                return domainMethod.invoke(None, args)
            else:
                realArgs = list()
                System.arraycopy(args, 1, realArgs, 0, realArgs.length)
                return domainMethod(args[0], realArgs)
        except Exception, ex:
            return self.die(ex, "Could not invoke method %s", domainMethod.getName())


    def isLive(self, domainObject):
        """This implementation attempts to re-load the object from the backing
        store.
        """
        id_ = self.getTop().getId(domainObject)
        return self.getTop().invoke(self.getFind(domainObject.getClass()), id_) != None


    def loadDomainObject(self, clazz, id_):
        if id_ is None:
            self.die(None, "Cannot invoke find method with a None id")
        return clazz.cast(self.getTop().invoke(self.getFind(clazz), id_))


    def loadDomainObjects(self, classes, domainIds):
        if len(classes) != len(domainIds):
            self.die(None, "Size mismatch in paramaters. classes.size() = %d domainIds.size=%d",
                    len(classes), len(domainIds))
        toReturn = list()
        for i, clazz in enumerate(classes):
            toReturn.append(self.getTop().loadDomainObject(clazz, domainIds[i]))
        return toReturn


    def setProperty(self, domainObject, property_, expectedType, value):
        try:
            setter = self.getTop().getSetter(domainObject.getClass(), property_)
            if setter is None:
                self.die(None, "Could not locate setter for property %s in type %s",
                        property_, domainObject.__class__.__name__)
            setter.invoke(domainObject, value)
            return
        except Exception, e:
            self.die(e, "Could not set property %s", property_)


    def validate(self, domainObject):
        return set()


    def getFind(self, clazz):
        if clazz is None:
            return self.die(None, "Could not find static method with a single"
                    + " parameter of a key type")
        searchFor = "find" + clazz.getSimpleName()
        for method in clazz.getMethods():
            if not Modifier.isStatic(method.getModifiers()):
                continue
            if not searchFor.equals(method.getName()):
                continue
            if method.getParameterTypes().length != 1:
                continue
            if not self.isKeyType(method.getParameterTypes()[0]):
                continue
            return method
        return self.getFind(clazz.getSuperclass())


    def isKeyType(self, domainClass):
        """Returns <code>true</code> if the given class can be used as an id or
        version key.
        """
        if ValueCodex.canDecode(domainClass):
            return True

        return issubclass(self.getTop().resolveClientType(domainClass,
                BaseProxy.__class__, True), BaseProxy)
