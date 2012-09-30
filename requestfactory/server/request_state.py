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

from requestfactory.shared.value_proxy import ValueProxy
from requestfactory.shared.entity_proxy import EntityProxy
from requestfactory.shared.impl.id_factory import IdFactory
from requestfactory.shared.impl.constants import Constants
from requestfactory.shared.impl.entity_codex import EntityCodex
from requestfactory.shared.impl.message_factory_holder import MessageFactoryHolder
from requestfactory.shared.messages.id_message import IdMessage, Strength

from requestfactory.server.exceptions import UnexpectedException
from requestfactory.server.service_layer import ServiceLayer
from requestfactory.server.resolver import Resolver

from autobean.shared.value_codex import ValueCodex
from autobean.shared.impl.string_quoter import StringQuoter
from autobean.shared.auto_bean_codex import AutoBeanCodex
from autobean.vm.auto_bean_factory_source import AutoBeanFactorySource

from requestfactory.server.simple_request_processor \
    import SimpleRequestProcessor, IdToEntityMap, fromBase64, toBase64


class _IdFactory(IdFactory):

    def __init__(self, service):
        self._service = service

    def isEntityType(self, clazz):
        return EntityProxy.isAssignableFrom(clazz)

    def isValueType(self, clazz):
        return ValueProxy.isAssignableFrom(clazz)

    def getTypeFromToken(self, typeToken):
        return self._service.resolveClass(typeToken)

    def getTypeToken(self, clazz):
        return self._service.resolveTypeToken(clazz)


class RequestState(EntityCodex.EntitySource):
    """Encapsulates all state relating to the processing of a single request so
    that the SimpleRequestProcessor can be stateless.
    """

    def __init__(self, parentOrService):
        self.beans = IdToEntityMap()

        if isinstance(parentOrService, RequestState):
            parent = parentOrService
            self._idFactory = parent.idFactory
            self._domainObjectsToId = parent.domainObjectsToId
            self._service = parent.service
            self._resolver = Resolver(self)
        else:
            self._service = parentOrService
            self._idFactory = _IdFactory(self._service)
            self._domainObjectsToId = IdentityHashMap()
            self._resolver = Resolver(self)


    def flatten(self, domainValue):
        """Turn a domain value into a wire format message."""
        if ValueCodex.canDecode(domainValue.getClass()):
            flatValue = ValueCodex.encode(domainValue)
        else:
            flatValue = SimpleRequestProcessor(self._service).createOobMessage([domainValue])
        return flatValue


    def getBeanForPayload(self, id_, domainObject=None):
        """Get or create a BaseProxy AutoBean for the given id."""
        if domainObject is None:
            idMessage = AutoBeanCodex.decode(MessageFactoryHolder.FACTORY, IdMessage, id_).as_()
            toReturn = self.getBeansForPayload([idMessage]).get(0)
            return toReturn
        else:
            toReturn = self.beans.get(id_)
            if toReturn is None:
                toReturn = self.createProxyBean(id_, domainObject)
            return toReturn


    def getBeansForPayload(self, idMessages):
        """Get or create BaseProxy AutoBeans for a list of id-bearing messages."""
        ids = list()
        for idMessage in idMessages:
            if Strength.SYNTHETIC == idMessage.getStrength():
                clazz = self._service.resolveClass(idMessage.getTypeToken())
                id_ = self._idFactory.allocateSyntheticId(clazz,
                        idMessage.getSyntheticId())
            else:
                decodedId = None if idMessage.getServerId() is None else fromBase64(idMessage.getServerId())
                id_ = self._idFactory.getId(idMessage.getTypeToken(),
                        decodedId, idMessage.getClientId())
            ids.append(id_)
        return self.getBeansForIds(ids)


    def getIdFactory(self):
        return self._idFactory


    def getResolver(self):
        return self._resolver


    def getSerializedProxyId(self, stableId):
        """EntityCodex support. This method is identical to
        {@link IdFactory#getHistoryToken(SimpleProxyId)} except that it
        base64-encodes the server ids.
        <p>
        XXX: Merge this with AbstsractRequestContext's implementation
        """
        bean = MessageFactoryHolder.FACTORY.id()
        ref = bean.as_()
        ref.setTypeToken(self._service.resolveTypeToken(stableId.getProxyClass()))
        if stableId.isSynthetic():
            ref.setStrength(Strength.SYNTHETIC)
            ref.setSyntheticId(stableId.getSyntheticId())
        elif stableId.isEphemeral():
            ref.setStrength(Strength.EPHEMERAL)
            ref.setClientId(stableId.getClientId())
        else:
            ref.setServerId(toBase64(stableId.getServerId()))
        return AutoBeanCodex.encode(bean)


    def getServiceLayer(self):
        return self._service


    def getStableId(self, domain):
        """If the given domain object has been previously associated with an
        id, return it.
        """
        return self._domainObjectsToId.get(domain)


    def isEntityType(self, clazz):
        """EntityCodex support."""
        return self._idFactory.isEntityType(clazz)


    def isValueType(self, clazz):
        """EntityCodex support."""
        return self._idFactory.isValueType(clazz)


    def createProxyBean(self, id_, domainObject):
        """Creates an AutoBean for the given id, tracking a domain object."""
        toReturn = AutoBeanFactorySource.createBean(id_.getProxyClass(),
                SimpleRequestProcessor.CONFIGURATION)
        toReturn.setTag(Constants.STABLE_ID, id_)
        toReturn.setTag(Constants.DOMAIN_OBJECT, domainObject)
        self.beans[id_] = toReturn
        return toReturn


    def getBeansForIds(self, ids):
        """Returns the AutoBeans corresponding to the given ids, or creates
        them if they do not yet exist.
        """
        domainClasses = list()
        domainIds = list()
        idsToLoad = list()

        # Create proxies for ephemeral or synthetic ids that we haven't seen. Queue
        # up the domain ids for entities that need to be loaded.
        for id_ in ids:
            domainClass = self._service.resolveDomainClass(id_.getProxyClass())
            if id_ in self.beans:
                # Already have a proxy for this id, no-op
                pass
            elif id_.isEphemeral() or id_.isSynthetic():
                # Create a new domain object for the short-lived id
                domain = self._service.createDomainObject(domainClass)
                if domain is None:
                    raise UnexpectedException('Could not create instance of '
                            + domainClass.getCanonicalName(), None)
                bean = self.createProxyBean(id_, domain)
                self.beans[id_] = bean
                self._domainObjectsToId[domain] = id_
            else:
                # Decode the domain parameter
                split = StringQuoter.split(id_.getServerId())
                param = self._service.getIdType(domainClass)
                if ValueCodex.canDecode(param):
                    domainParam = ValueCodex.decode(param, split)
                else:
                    domainParam = SimpleRequestProcessor(self._service).decodeOobMessage(param, split).get(0)

                # Enqueue
                domainClasses.append(self._service.resolveDomainClass(id_.getProxyClass()))
                domainIds.append(domainParam)
                idsToLoad.append(id_)

        # Actually load the data
        if len(domainClasses) > 0:
            assert (len(domainClasses) == len(domainIds)
                    and len(domainClasses) == len(idsToLoad))
            loaded = self._service.loadDomainObjects(domainClasses, domainIds)
            if len(idsToLoad) != len(loaded):
                raise UnexpectedException('Expected ' + len(idsToLoad)
                        + ' objects to be loaded, got ' + len(loaded), None)
            itLoaded = iter(loaded)
            for id_ in idsToLoad:
                domain = itLoaded.next()
                self._domainObjectsToId[domain] = id_
                bean = self.createProxyBean(id_, domain)
                self.beans[id_] = bean

        # Construct the return value
        toReturn = list()
        for id_ in ids:
            toReturn.append(self.beans.get(id_))

        return toReturn

