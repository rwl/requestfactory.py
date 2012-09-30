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

from autobean.shared.auto_bean_visitor import AutoBeanVisitor, CollectionPropertyContext
from autobean.shared.value_codex import ValueCodex
from autobean.vm.impl.type_utils import TypeUtils
from autobean.shared.auto_bean_utils import AutoBeanUtils

from requestfactory.server.exceptions import ReportableException, DeadEntityException
from requestfactory.shared.base_proxy import BaseProxy
from requestfactory.shared.entity_proxy_id import EntityProxyId
from requestfactory.shared.impl.constants import Constants

from requestfactory.server.simple_request_processor import toBase64


class CollectionType(object):
    """A parameterized type with a single parameter."""

    def __init__(self, rawType, elementType):
        self._rawType = rawType
        self._elementType = elementType

    def equals(self, o):
        if not isinstance(o, CollectionType):
            return False
        other = o
        return (self._rawType == other.rawType
                and self._elementType == other.elementType)

    def getActualTypeArguments(self):
        return [self._elementType]

    def getOwnerType(self):
        return None

    def getRawType(self):
        return self._rawType

    def hashCode(self):
        return ((self._rawType.hashCode() * 13)
                + (self._elementType.hashCode() * 7))


class PropertyResolver(AutoBeanVisitor):
    """Copies values and references from a domain object to a client object.
    This type does not descend into referenced objects.
    """

    def __init__(self, resolution, resolver):
        key = resolution.getResolutionKey()
        self._domainEntity = key.getDomainObject()
        self._isOwnerValueProxy = self._resolver._state.isValueType(TypeUtils.ensureBaseType(key.requestedType))
        self._needsSimpleValues = resolution.needsSimpleValues()
        self._propertyRefs = resolution.takeWork()

        self._resolver = resolver

    def visitReferenceProperty(self, propertyName, value, ctx):
        # Send the property if the enclosing type is a ValueProxy, if the owner
        # requested the property, or if the property is a list of values.

        elementType = ctx.getElementType() if isinstance(ctx, CollectionPropertyContext) else None
        shouldSend = (self._isOwnerValueProxy or self._resolver.matchesPropertyRef(self._propertyRefs, propertyName)) or (elementType is not None and ValueCodex.canDecode(elementType))
        if not shouldSend:
            return False
        # Call the getter
        domainValue = self._resolver._service.getProperty(self._domainEntity, propertyName)
        if domainValue is None:
            return False
        # Turn the domain object into something usable on the client side
        if elementType is None:
            type_ = ctx.getType()
        else:
            type_ = CollectionType(ctx.getType(), elementType)
        resolution = self._resolver.resolveClientValue(domainValue, type_)
        self._resolver.addPathsToResolution(resolution, propertyName, self._propertyRefs)
        ctx.set(resolution.getClientObject())
        return False

    def visitValueProperty(self, propertyName, value, ctx):
        # Only call the getter for simple values once since they're not
        # explicitly enumerated.

        if self._needsSimpleValues:
            # Limit unrequested value properties?
            value = self._resolver._service.getProperty(self._domainEntity, propertyName)
            ctx.set(value)
        return False


class Resolution(object):
    """Tracks the state of resolving a single client object."""

    _EMPTY = TreeSet()

    def __init__(self, simpleValueOrKey, clientObject=None):

        # The client object.
        self._clientObject = None

        # A one-shot flag for {@link #hasWork()} to ensure that simple properties
        # will be resolved, even when there's no requested property set.
        self._needsSimpleValues = None
        self._toResolve = self._EMPTY
        self._resolved = TreeSet()
        self._key = None

        if clientObject is None:
            simpleValue = simpleValueOrKey
            assert not isinstance(simpleValue, Resolution)
            self._clientObject = simpleValue
            self._key = None
        else:
            key = simpleValueOrKey
            self._clientObject = clientObject
            self._key = key
            self._needsSimpleValues = True


    def addPaths(self, prefix, requestedPaths):
        """Removes the prefix from each requested path and enqueues paths that
        have not been previously resolved for the next batch of work.
        """
        if self._clientObject is None:
            # No point trying to follow paths past a null value
            return
        # Identity comparison intentional
        if self._toResolve == self._EMPTY:
            self._toResolve = TreeSet()
        prefix = prefix if len(prefix) == 0 else prefix + '.'
        prefixLength = len(prefix)
        for path in requestedPaths:
            if path.startswith(prefix):
                self._toResolve.add(path[prefixLength:])
            elif path.startswith('*.'):
                self._toResolve.add(path[len('*.'):])
        self._toResolve = self._toResolve.difference(self._resolved)
        if len(self._toResolve) == 0:
            self._toResolve = self._EMPTY


    def getClientObject(self):
        return self._clientObject


    def getResolutionKey(self):
        return self._key


    def hasWork(self):
        return self._needsSimpleValues or (not self._toResolve.isEmpty())


    def needsSimpleValues(self):
        return self._needsSimpleValues


    def takeWork(self):
        """Returns client-object-relative reference paths that should be further
        resolved.
        """
        self._needsSimpleValues = False
        toReturn = self._toResolve
        self._resolved.update(toReturn)
        self._toResolve = self._EMPTY
        return toReturn


class ResolutionKey(object):
    """Used to map the objects being resolved and its API slice to the client-side
    value. This handles the case where a domain object is returned to the
    client mapped to two proxies of differing types.
    """

    def __init__(self, domainObject, requestedType):
        self._domainObject = domainObject
        self._requestedType = requestedType
        self._hashCode = ((System.identityHashCode(domainObject) * 13)
                + (requestedType.hashCode() * 7))


    def __eq__(self, o):
        if not isinstance(o, ResolutionKey):
            return False
        other = o
        # Object identity comparison intentional
        if self._domainObject != other.domainObject:
            return False
        if not (self._requestedType == other.requestedType):
            return False
        return True


    def getDomainObject(self):
        return self._domainObject


    def __hash__(self):
        return self._hashCode


    def __str__(self):
        """For debugging use only."""
        return str(self._domainObject) + ' => ' + str(self._requestedType)


class Resolver(object):
    """Responsible for converting between domain and client entities. This class has
    a small amount of temporary state used to handle graph cycles and assignment
    of synthetic ids.

    @see RequestState#getResolver()
    """

    @classmethod
    def index(cls, path):
        """Returns the trailing {@code [n]} index value from a path."""
        idx = path.rfind('[')
        if idx == -1:
            return -1
        return int(path[idx + 1:path.rfind(']')])


    @classmethod
    def matchesPropertyRef(cls, propertyRefs, newPrefix):
        """Returns {@code true} if the given prefix is one of the requested property
        references.
        """
        # Match all fields for a wildcard
        #
        # Also, remove list index suffixes. Not actually used, was in anticipation
        # of OGNL type schemes. That said, Editor will slip in such things.
        return (('*' in propertyRefs)
                or (newPrefix.replaceAll('\\[\\d+\\]', '') in propertyRefs))


    @classmethod
    def snipIndex(cls, path):
        """Removes the trailing {@code [n]} from a path."""
        idx = path.rfind('[')
        if idx == -1:
            return path
        return path[:idx]


    @classmethod
    def expandPropertyRefs(cls, refs):
        """Expand the property references in an InvocationMessage into a
        fully-expanded list of properties. For example, <code>[foo.bar.baz]</code>
        will be converted into <code>[foo, foo.bar, foo.bar.baz]</code>.
        """
        # Maps proxy instances to the Resolution objects.
        #    *<p>
        # FIXME: The proxies are later mutated, which is not an issue as this is an
        # IdentityHashMap, but still feels weird. We should try to find a way to
        # put immutable objects as keys in this map.

        if refs is None:
            return set()
        toReturn = TreeSet()
        for raw in refs:
            idx = len(raw)
            while idx >= 0:
                toReturn.add(raw[:idx])
                idx = raw.rfind('.', idx - 1)
        return toReturn


    def __init__(self, state):
        """Should only be called from {@link RequestState}."""

        self._clientObjectsToResolutions = IdentityHashMap()
        # Maps domain values to client values. This map prevents cycles in the object
        # graph from causing infinite recursion.
        self._resolved = dict()
        # Contains Resolutions with path references that have not yet been resolved.
        self._toProcess = OrderedSet()
        self._syntheticId = None

        self._state = state
        self._service = state.getServiceLayer()


    def resolveClientValue(self, domainValue, clientTypeOrAssignableTo, propertyRefs=None):
        """Given a domain object, return a value that can be encoded by the client.

        Creates a Resolution object that holds a client value that represents the
        given domain value. The resolved client value will be assignable to
        {@code clientType}.

        @param domainValue the domain object to be converted into a client-side
                 value
        @param assignableTo the type in the client to which the resolved value
                 should be assignable. A value of {@code null} indicates that any
                 resolution will suffice.
        @param propertyRefs the property references requested by the client
        """
        if propertyRefs is None:
            clientType = clientTypeOrAssignableTo
            if domainValue is None:
                return Resolution(None)
            anyType = clientType is None
            if anyType:
                clientType = object()
            assignableTo = TypeUtils.ensureBaseType(clientType)
            key = ResolutionKey(domainValue, clientType)
            previous = self._resolved[key]

            if (previous is not None
                    and assignableTo.isInstance(previous.getClientObject())):
                return previous

            returnClass = self._service.resolveClientType(domainValue.getClass(),
                    assignableTo, True)
            if anyType:
                assignableTo = returnClass

            # Pass simple values through
            if ValueCodex.canDecode(returnClass):
                return self.makeResolution(domainValue)

            # Convert entities to EntityProxies or EntityProxyIds
            isProxy = BaseProxy.isAssignableFrom(returnClass)
            isId = issubclass(returnClass, EntityProxyId)
            if isProxy or isId:
                proxyClass = returnClass.asSubclass(BaseProxy)
                return self.resolveClientProxy(domainValue, proxyClass, key)
            # Convert collections
            if issubclass(returnClass, Collection):
                if issubclass(returnClass, list):
                    accumulator = list()
                elif issubclass(returnClass, set):
                    accumulator = set()
                else:
                    raise ReportableException('Unsupported collection type'
                            + returnClass.getName())
                elementType = TypeUtils.getSingleParameterization(Collection, clientType)
                for o in domainValue:
                    accumulator.add(self.resolveClientValue(o, elementType).getClientObject())
                return self.makeResolution(accumulator)
            raise ReportableException('Unsupported domain type ' + returnClass.getCanonicalName())
        else:
            assignableTo = clientTypeOrAssignableTo
            toReturn = self.resolveClientValue(domainValue, assignableTo)
            if toReturn is None:
                return None
            self.addPathsToResolution(toReturn, '',
                    self.expandPropertyRefs(propertyRefs))
            while len(self._toProcess) > 0:
                working = list(self._toProcess)
                self._toProcess.clear()
                for resolution in working:
                    if resolution.hasWork():
                        bean = AutoBeanUtils.getAutoBean(resolution.getClientObject())
                        bean.accept(self.PropertyResolver(resolution))
            return toReturn.getClientObject()


    def resolveDomainValue(self, maybeEntityProxy, detectDeadEntities):
        """Convert a client-side value into a domain value.

        @param maybeEntityProxy the client object to resolve
        @param detectDeadEntities if <code>true</code> this method will throw a
                 ReportableException containing a {@link DeadEntityException}
                 if an EntityProxy cannot be resolved
        """
        if isinstance(maybeEntityProxy, BaseProxy):
            bean = AutoBeanUtils.getAutoBean(maybeEntityProxy)
            domain = bean.getTag(Constants.DOMAIN_OBJECT)
            if domain is None and detectDeadEntities:
                raise ReportableException(DeadEntityException(
                        'The requested entity is not available on the server'))
            return domain
        elif isinstance(maybeEntityProxy, (list, set)):
            if isinstance(maybeEntityProxy, list):
                accumulator = list()
            elif isinstance(maybeEntityProxy, set):
                accumulator = set()
            else:
                raise ReportableException('Unsupported collection type '
                        + maybeEntityProxy.getClass().getName())
            for o in maybeEntityProxy:
                accumulator.add(self.resolveDomainValue(o, detectDeadEntities))
            return accumulator
        return maybeEntityProxy


    def addPathsToResolution(self, resolution, prefix, propertyRefs):
        """Calls {@link Resolution#addPaths(String, Collection)}, enqueuing
        {@code key} if {@link Resolution#hasWork()} returns {@code true}. This
        method will also expand paths on the members of Collections.
        """
        if len(propertyRefs) == 0:
            # No work to do
            return

        if resolution.getResolutionKey() is not None:
            # Working on a proxied type
            assert isinstance(resolution.getClientObject(), BaseProxy), \
                    'Expecting BaseProxy, found ' \
                    + resolution.getClientObject().__class__.__name__
            resolution.addPaths(prefix, propertyRefs)
            if resolution.hasWork():
                self._toProcess.add(resolution)
            return

        if isinstance(resolution.getClientObject(), Collection):
            # Pass the paths onto the Resolutions for the contained elements
            collection = resolution.getClientObject()
            for obj in collection:
                subResolution = self._clientObjectsToResolutions.get(obj)
                # subResolution will be null for List<Integer>, etc.
                if subResolution is not None:
                    self.addPathsToResolution(subResolution, prefix, propertyRefs)
            return

        assert False, 'Should not add paths to client type ' \
                + resolution.getClientObject().__class__.__name__


    def makeResolution(self, domainValueOrKey, clientObject=None):
        """Creates a resolution for a simple value.
        ---
        Create or reuse a Resolution for a proxy object.
        """
        if clientObject is None:
            domainValue = domainValueOrKey
            assert (not self._state.isEntityType(domainValue.getClass())
                    and not self._state.isValueType(domainValue.getClass()),
                    'Not a simple value type')
            return Resolution(domainValue)
        else:
            key = domainValueOrKey
            resolution = self._resolved[key]
            if resolution is None:
                resolution = Resolution(key, clientObject)
                self._clientObjectsToResolutions[clientObject] = resolution
                self._toProcess.add(resolution)
                self._resolved[key] = resolution
            return resolution


    def resolveClientProxy(self, domainEntity, proxyType, key):
        """Creates a proxy instance held by a Resolution for a given domain type."""
        if domainEntity is None:
            return None

        id_ = self._state.getStableId(domainEntity)

        isEntityProxy = self._state.isEntityType(proxyType)

        # Create the id or update an ephemeral id by calculating its address
        if (id_ is None) or id_.isEphemeral():
            # The address is an id or an id plus a path
            if isEntityProxy:
                # Compute data needed to return id to the client
                domainId = self._service.getId(domainEntity)
                domainVersion = self._service.getVersion(domainEntity)
            else:
                domainId = None
                domainVersion = None

            if id_ is None:
                if domainId is None:
                    # This will happen when server code attempts to return an unpersisted
                    # object to the client. In this case, we'll assign a synthetic id
                    # that is valid for the duration of the response. The client is
                    # expected to assign a client-local id to this object and then it
                    # will behave as though it were an object newly-created by the
                    # client.
                    self._syntheticId += 1
                    id_ = self._state.getIdFactory().allocateSyntheticId(proxyType, self._syntheticId)
                else:
                    flatValue = self._state.flatten(domainId)
                    id_ = self._state.getIdFactory().getId(proxyType, flatValue.getPayload(), 0)
            elif domainId is not None:
                # Mark an ephemeral id as having been persisted
                flatValue = self._state.flatten(domainId)
                id_.setServerId(flatValue.getPayload())
        elif isEntityProxy:
            # Already have the id, just pull the current version
            domainVersion = self._service.getVersion(domainEntity)
        else:
            # The version of a value object is always null
            domainVersion = None

        bean = self._state.getBeanForPayload(id_, domainEntity)
        bean.setTag(Constants.IN_RESPONSE, True)
        if domainVersion is not None:
            flatVersion = self._state.flatten(domainVersion)
            bean.setTag(Constants.VERSION_PROPERTY_B64, toBase64(flatVersion.getPayload()))

        clientObject = bean.as_()
        return self.makeResolution(key, clientObject)
