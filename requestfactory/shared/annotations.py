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

"""Shared RequestFactory annotations."""


class Service(object):
    """Annotation on Request classes specifying the server side implementations
    that back them.

    @see ServiceName
    """

    def __init__(self, domainType, locator=None):
        #: The domain type that provides the implementations for the methods
        #  defined in the RequestContext.
        self.domainType = domainType

        #: An optional {@link ServiceLocator} that provides instances of
        #  service objects used when invoking instance methods on the type
        #  returned by {@link #value()}.
        self.locator = locator


class ServiceName(object):
    """Annotation on Request classes specifying the server side implementations that
    back them.This annotation can be used in place of {@link Service} if the
    service type is not available to the GWT compiler or DevMode runtime.
    """

    def __init__(self, domainType, locator=None):
        #: The binary name of the domain type that provides the implementations
        #  for the methods defined in the RequestContext.
        self.domainType = domainType

        #: An optional binary name of a {@link ServiceLocator} that provides
        #  instances of service objects used when invoking instance methods on
        #  the type returned by {@link #value()}.
        self.locator = locator


class ProxyFor(object):
    """Annotation on EntityProxy and ValueProxy classes specifying the domain
    (server-side) object type.

    @see ProxyForName
    """

    def __init__(self, domainType, locator=None):
        #: The domain type that the proxy is mapped to.
        self.domainType = domainType

        #: An optional {@link Locator} that provides instances of the domain
        #  objects.
        self.locator = locator


class ProxyForName(object):
    """Annotation on EntityProxy classes specifying the domain (server-side) object
    type. This annotation can be used in place of {@link ProxyFor} if the domain
    object is not available to the GWT compiler or DevMode runtime.
    """

    def __init__(self, domainType, locator=None):
        #: The name of the domain type that the proxy is mapped to.
        self.domainType = domainType

        #: An optional name of a {@link Locator} that provides instances of the
        #  domain objects.
        self.locator = locator
