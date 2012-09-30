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

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from requestfactory.server.exceptions import UnexpectedException, ReportableException
from requestfactory.server.request_state import RequestState
from requestfactory.server.default_exception_handler import DefaultExceptionHandler

from requestfactory.shared.messages.message_factory import MessageFactory
from requestfactory.shared.entity_proxy_id import EntityProxyId
from requestfactory.shared.request import Request
from requestfactory.shared.impl.constants import Constants
from requestfactory.shared.instance_request import InstanceRequest
from requestfactory.shared.messages.request_message import RequestMessage
from requestfactory.shared.write_operation import WriteOperation
from requestfactory.shared.impl.entity_codex import EntityCodex
from requestfactory.shared.messages.id_message import IdMessage, Strength
from requestfactory.shared.impl.value_proxy_category import ValueProxyCategory
from requestfactory.shared.impl.base_proxy_category import BaseProxyCategory
from requestfactory.shared.base_proxy import BaseProxy
from requestfactory.shared.impl.entity_proxy_category import EntityProxyCategory

from autobean.shared.value_codex import ValueCodex
from autobean.vm.impl.type_utils import TypeUtils
from autobean.shared.auto_bean_visitor import AutoBeanVisitor, CollectionPropertyContext
from autobean.vm.auto_bean_factory_source import AutoBeanFactorySource
from autobean.shared.auto_bean_utils import AutoBeanUtils
from autobean.shared.auto_bean_codex import AutoBeanCodex
from autobean.vm.configuration import Configuration

from com.google.gwt.user.server.base64_utils import Base64Utils


# Vends message objects.
FACTORY = AutoBeanFactorySource.create(MessageFactory)


class SimpleRequestProcessor(object):
    """Processes request payloads from a RequestFactory client. This implementation
    is stateless. A single instance may be reused and is thread-safe.
    """

    # Allows the creation of properly-configured AutoBeans without having to
    # create an AutoBeanFactory with the desired annotations.
    CONFIGURATION = Configuration.Builder().setCategories(EntityProxyCategory,
        ValueProxyCategory, BaseProxyCategory).setNoWrap(EntityProxyId).build()

    def __init__(self, serviceLayer):
        self._service = serviceLayer
        self._exceptionHandler = DefaultExceptionHandler()


    def processPayload(self, payload):
        """Process a payload sent by a RequestFactory client.

        @param payload the payload sent by the client
        @return a payload to return to the client
        """
        req = AutoBeanCodex.decode(FACTORY, RequestMessage, payload).as_()
        responseBean = FACTORY.response()
        # Create a new response envelope, since the state is unknown
        # Return a JSON-formatted payload
        try:
            self.process(req, responseBean.as_())
        except ReportableException, e:
            responseBean = FACTORY.response()
            responseBean.as_().setGeneralFailure(self.createFailureMessage(e).as_())
        return AutoBeanCodex.encode(responseBean).getPayload()


    def process(self, req, resp):
        """Main processing method."""
        source = RequestState(self._service)

        # Make sure the RequestFactory is valid
        requestFactoryToken = req.getRequestFactory()
        if requestFactoryToken is None:
            # Tell old clients to go away
            raise ReportableException('The client payload version is out of sync with the server')
        self._service.resolveRequestFactory(requestFactoryToken)

        # Apply operations
        self.processOperationMessages(source, req)

        # Validate entities
        errorMessages = self.validateEntities(source)

        if not errorMessages.isEmpty():
            resp.setViolations(errorMessages)
            return

        returnState = RequestState(source)

        # Invoke methods
        invocationResults = list()
        invocationSuccess = list()
        self.processInvocationMessages(source, req, invocationResults,
                invocationSuccess, returnState)

        # Store return objects
        operations = list()
        toProcess = IdToEntityMap()
        toProcess.extend(source.beans)
        toProcess.extend(returnState.beans)
        self.createReturnOperations(operations, returnState, toProcess)

        assert len(invocationResults) == len(invocationSuccess)
        if not invocationResults.isEmpty():
            resp.setInvocationResults(invocationResults)
            resp.setStatusCodes(invocationSuccess)
        if not operations.isEmpty():
            resp.setOperations(operations)


    def setExceptionHandler(self, exceptionHandler):
        self._exceptionHandler = exceptionHandler


    def createOobMessage(self, domainValues):
        """Encode a list of objects into a self-contained message that can be used for
        out-of-band communication.
        """
        state = RequestState(self._service)

        encodedValues = list()
        for domainValue in domainValues:
            if domainValue is None:
                clientValue = None
            else:
                clientType = self._service.resolveClientType(
                        domainValue.__class__, BaseProxy, True)
                clientValue = state.getResolver().resolveClientValue(
                        domainValue, clientType, set())
            encodedValues.append(EntityCodex.encode(state, clientValue))

        map_ = IdToEntityMap()
        map_.update(state.beans)
        operations = list()
        self.createReturnOperations(operations, state, map_)

        invocation = FACTORY.invocation().as_()
        invocation.setParameters(encodedValues)

        bean = FACTORY.request()
        resp = bean.as_()
        resp.setInvocations(list(invocation))
        resp.setOperations(operations)
        return AutoBeanCodex.encode(bean)


    def decodeOobMessage(self, domainClass, payload):
        """Decode an out-of-band message."""
        proxyType = self._service.resolveClientType(domainClass, BaseProxy, True)
        state = RequestState(self._service)
        message = AutoBeanCodex.decode(FACTORY, RequestMessage, payload).as_()
        self.processOperationMessages(state, message)
        decoded = self.decodeInvocationArguments(state,
                message.getInvocations()[0].getParameters(),
                [proxyType], [domainClass])
        return decoded


    def createFailureMessage(self, e):
        failure = self._exceptionHandler.createServerFailure(e if e.getCause() is None else e.getCause())
        bean = FACTORY.failure()
        msg = bean.as_()
        msg.setExceptionType(failure.getExceptionType())
        msg.setMessage(failure.getMessage())
        msg.setStackTrace(failure.getStackTraceString())
        msg.setFatal(failure.isFatal())
        return bean


    def createReturnOperations(self, operations, returnState, toProcess):
        for id_, bean in toProcess.iteritems():
            domainObject = bean.getTag(Constants.DOMAIN_OBJECT)
            if id_.isEphemeral() and returnState.isEntityType(id_.getProxyClass()):
                # See if the entity has been persisted in the meantime
                returnState.getResolver().resolveClientValue(domainObject,
                        id_.getProxyClass(), set())

            if (id_.isEphemeral() or id_.isSynthetic()) or (domainObject is None):
                # If the object isn't persistent, there's no reason to send an update
                writeOperation = None
            elif not self._service.isLive(domainObject):
                writeOperation = WriteOperation.DELETE
            elif id_.wasEphemeral():
                writeOperation = WriteOperation.PERSIST
            else:
                writeOperation = WriteOperation.UPDATE

            version = None
            if ((writeOperation == WriteOperation.PERSIST)
                    or (writeOperation == WriteOperation.UPDATE)):
                # If we're sending an operation, the domain object must be persistent.
                # This means that it must also have a non-null version.
                domainVersion = self._service.getVersion(domainObject)
                if domainVersion is None:
                    raise UnexpectedException('The persisted entity with id '
                            + self._service.getId(domainObject)
                            + ' has a null version', None)
                version = returnState.flatten(domainVersion)

            inResponse = bean.getTag(Constants.IN_RESPONSE) is not None

            # Don't send any data back to the client for an update on an object that
            # isn't part of the response payload when the client's version matches
            # the domain version.
            if WriteOperation.UPDATE == writeOperation and not inResponse:
                previousVersion = bean.getTag(Constants.VERSION_PROPERTY_B64)
                if (version is not None and previousVersion is not None
                        and version == fromBase64(previousVersion)):
                    continue

            op = FACTORY.operation().as_()

            # Send a client id if the id is ephemeral or was previously associated
            # with a client id.
            if id_.wasEphemeral():
                op.setClientId(id_.getClientId())

            op.setOperation(writeOperation)

            # Only send properties for entities that are part of the return graph
            if inResponse:
                propertyMap = OrderedDict()
                # Add all non-null properties to the serialized form
                diff = AutoBeanUtils.getAllProperties(bean)
                for d in diff.iteritems():
                    value = d[1]
                    if value is not None:
                        propertyMap[d[0]] = EntityCodex.encode(returnState, value)
                op.setPropertyMap(propertyMap)

            if not id_.isEphemeral() and not id_.isSynthetic():
                # Send the server address only for persistent objects
                op.setServerId(toBase64(id_.getServerId()))

            if id_.isSynthetic():
                op.setStrength(Strength.SYNTHETIC)
                op.setSyntheticId(id_.getSyntheticId())
            elif id_.isEphemeral():
                op.setStrength(Strength.EPHEMERAL)

            op.setTypeToken(self._service.resolveTypeToken(id_.getProxyClass()))

            if version is not None:
                op.setVersion(toBase64(version.getPayload()))

            operations.add(op)


    def decodeInvocationArguments_(self, source, invocation, contextMethod):
        """Decode the arguments to pass into the domain method. If the domain method
        is not static, the instance object will be in the 0th position.
        """
        isStatic = Request.isAssignableFrom(contextMethod.getReturnType())
        baseLength = contextMethod.getParameterTypes().length
        length = baseLength + (0 if isStatic else 1)
        offset = 0 if isStatic else 1
        contextArgs = [None] * length
        genericArgs = [None] * length

        if not isStatic:
            genericArgs[0] = TypeUtils.getSingleParameterization(InstanceRequest, contextMethod.getGenericReturnType())
            contextArgs[0] = TypeUtils.ensureBaseType(genericArgs[0])

        System.arraycopy(contextMethod.getParameterTypes(), 0, contextArgs, offset, baseLength)
        System.arraycopy(contextMethod.getGenericParameterTypes(), 0, genericArgs, offset, baseLength)

        args = self.decodeInvocationArguments(source, invocation.getParameters(), contextArgs, genericArgs)
        return args


    def decodeInvocationArguments(self, source, parameters, contextArgs,
            genericArgs):
        """Handles instance invocations as the instance at the 0th parameter.
        """
        if parameters is None:
            # Can't return Collections.emptyList() because this must be mutable
            return list()

        assert len(parameters) == contextArgs.length
        args = list()
        for i in range(contextArgs.length):
            type_ = contextArgs[i]
            elementType = None
            if Collection.isAssignableFrom(type_):
                elementType = TypeUtils.ensureBaseType(TypeUtils.getSingleParameterization(Collection, genericArgs[i]))
                split = parameters.get(i)
            else:
                split = parameters.get(i)
            arg = EntityCodex.decode(source, type_, elementType, split)
            arg = source.getResolver().resolveDomainValue(arg, not (EntityProxyId == contextArgs[i]))
            args.add(arg)
        return args


    def processInvocationMessages(self, state, req, results, successes, returnState):
        invocations = req.getInvocations()
        if invocations is None:
            # No method invocations which can happen via RequestContext.fire()
            return
        contextMethods = list()
        invocationResults = list()
        allPropertyRefs = dict()
        for invocation in invocations:
            # Find the Method
            try:
                operation = invocation.getOperation()
                contextMethod = self._service.resolveRequestContextMethod(operation)
                if contextMethod is None:
                    raise UnexpectedException('Cannot resolve operation '
                            + invocation.getOperation(), None)
                contextMethods.append(contextMethod)
                domainMethod = self._service.resolveDomainMethod(operation)
                if domainMethod is None:
                    raise UnexpectedException('Cannot resolve domain method '
                            + invocation.getOperation(), None)
                # Compute the arguments
                args = self.decodeInvocationArguments_(state, invocation, contextMethod)
                # Possibly use a ServiceLocator
                if self._service.requiresServiceLocator(contextMethod, domainMethod):
                    requestContext = self._service.resolveRequestContext(operation)
                    serviceInstance = self._service.createServiceInstance(requestContext)
                    args.add(0, serviceInstance)
                # Invoke it
                domainReturnValue = self._service.invoke(domainMethod, list(args))
                if invocation.getPropertyRefs() is not None:
                    paths = allPropertyRefs[domainReturnValue]
                    if paths is None:
                        paths = set()#TreeSet()
                        allPropertyRefs[domainReturnValue] = paths
                    paths.update(invocation.getPropertyRefs())
                ok = True
            except ReportableException, e:
                domainReturnValue = AutoBeanCodex.encode(self.createFailureMessage(e))
                ok = False
            invocationResults.append(domainReturnValue)
            successes.append(ok)
        contextMethodIt = contextMethods
        objects = invocationResults
        for i, success in enumerate(successes):
            assert len(contextMethodIt) > i
            assert len(objects) > i
            contextMethod = contextMethodIt[i]
            returnValue = objects[i]
            if success:
                # Convert domain object to client object
                requestReturnType = self._service.getRequestReturnType(contextMethod)
                returnValue = state.getResolver().resolveClientValue(returnValue,
                        requestReturnType, allPropertyRefs[returnValue])
                # Convert the client object to a string
                results.append(EntityCodex.encode(returnState, returnValue))
            else:
                results.append(returnValue)


    def processOperationMessages(self, state, req):
        operations = req.getOperations()
        if operations is None:
            return

        beans = state.getBeansForPayload(operations)
        assert len(operations) == len(beans)

        itOp = operations
        for bean in beans:
            operation = itOp.next()
            # Save the client's version information to reduce payload size later
            bean.setTag(Constants.VERSION_PROPERTY_B64, operation.getVersion())

            # Load the domain object with properties, if it exists
            domain = bean.getTag(Constants.DOMAIN_OBJECT)
            if domain is not None:
                # Apply any property updates
                flatValueMap = operation.getPropertyMap()
                if flatValueMap is not None:
                    abv = _AutoBeanVisitor(self, state, domain, flatValueMap)
                    bean.accept(abv)


    def validateEntities(self, source):
        """Validate all of the entities referenced in a RequestState."""
        errorMessages = list()
        for id_, bean in source.beans.iteritems():
            domainObject = bean.getTag(Constants.DOMAIN_OBJECT)
            # The object could have been deleted
            if domainObject is not None:
                errors = self._service.validate(domainObject)
                if errors is not None and not errors.isEmpty():
                    for error in errors:
                        # Construct an ID that represents domainObject
                        rootId = FACTORY.id().as_()
                        rootId.setClientId(id_.getClientId())
                        rootId.setTypeToken(self._service.resolveTypeToken(id_.getProxyClass()))
                        if id_.isEphemeral():
                            rootId.setStrength(Strength.EPHEMERAL)
                        else:
                            rootId.setServerId(toBase64(id_.getServerId()))
                        # If possible, also include the id of the leaf bean
                        leafId = None
                        if error.getLeafBean() is not None:
                            stableId = source.getStableId(error.getLeafBean())
                            if stableId is not None:
                                leafId = FACTORY.id().as_()
                                leafId.setClientId(stableId.getClientId())
                                leafId.setTypeToken(self._service.resolveTypeToken(stableId.getProxyClass()))
                                if stableId.isEphemeral():
                                    leafId.setStrength(Strength.EPHEMERAL)
                                else:
                                    leafId.setServerId(toBase64(stableId.getServerId()))
                        message = FACTORY.violation().as_()
                        message.setLeafBeanId(leafId)
                        message.setMessage(error.getMessage())
                        message.setMessageTemplate(error.getMessageTemplate())
                        message.setPath(str(error.getPropertyPath()))
                        message.setRootBeanId(rootId)
                        errorMessages.add(message)
        return errorMessages


def fromBase64(encoded):
    try:
        return str(Base64Utils.fromBase64(encoded)).encode('UTF-8')
    except Exception, e:
        raise UnexpectedException(e)


def toBase64(data):
    try:
        return Base64Utils.toBase64(data.getBytes('UTF-8'))
    except Exception, e:
        raise UnexpectedException(e)


class IdToEntityMap(dict):
    """This parameterization is so long, it improves readability to have a
    specific type.
    <p>
    FIXME: IDs used as keys in this map can be mutated (turning an ephemeral
    ID to a persisted ID in Resolver#resolveClientProxy) in a way that can
    change their hashCode value and equals behavior, therefore breaking the
    Map contract. We should find a way to only put immutable IDs here, or
    change SimpleProxyId so that its hashCode value and equals behavior don't
    change, or possibly remove and re-add the entry when the ID is modified
    (as this is something entirely under our control).
    """
    pass


class _AutoBeanVisitor(AutoBeanVisitor):

    def __init__(self, procesor, state, domain, flatValueMap):
        self._procesor = procesor
        self._state = state
        self._domain = domain
        self._flatValueMap = flatValueMap


    def visitReferenceProperty(self, propertyName, value, ctx):
        # containsKey to distinguish null from unknown
        if propertyName in self._flatValueMap:
            elementType = ctx.getElementType() if isinstance(ctx, CollectionPropertyContext) else None
            newValue = EntityCodex.decode(self._state, ctx.getType(),
                    elementType, self._flatValueMap[propertyName])
            resolved = self._state.getResolver().resolveDomainValue(newValue, False)
            self._procesor._service.setProperty(self._domain, propertyName,
                    self._procesor._service.resolveDomainClass(ctx.getType()), resolved)
        return False


    def visitValueProperty(self, propertyName, value, ctx):
        if propertyName in self._flatValueMap:
            split = self._flatValueMap[propertyName]
            newValue = ValueCodex.decode(ctx.getType(), split)
            resolved = self._state.getResolver().resolveDomainValue(newValue, False)
            self._procesor._service.setProperty(self._domain, propertyName,
                    ctx.getType(), resolved)
        return False
