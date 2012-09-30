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

"""A Locator allows entity types that do not conform to the RequestFactory
entity protocol to be used."""


class Locator(object):
    """A Locator allows entity types that do not conform to the RequestFactory
    entity protocol to be used. Instead of attempting to use a {@code findFoo()},
    {@code getId()}, and {@code getVersion()} declared in the domain entity type,
    an instance of a Locator will be created to provide implementations of these
    methods.
    <p>
    Locator subtypes must be default instantiable (i.e. public static types with
    a no-arg constructor). Instances of Locators may be retained and reused by
    the RequestFactory service layer.

    @param <T> the type of domain object the Locator will operate on
    @param <I> the type of object the Locator expects to use as an id for the
             domain object
    @see ProxyFor#locator()
    """

    def create(self, clazz):
        """Create a new instance of the requested type.

        @param clazz the type of object to create
        @return the new instance of the domain type
        """
        raise NotImplementedError


    def find(self, clazz, id):
        """Retrieve an object. May return {@code null} to indicate that the requested
        object could not be found.

        @param clazz the type of object to retrieve
        @param id an id previously returned from {@link #getId(Object)}
        @return the requested object or {@code null} if it could not be found
        """
        raise NotImplementedError


    def getDomainType(self):
        """Returns the domain type."""
        raise NotImplementedError


    def getId(self, domainObject):
        """Returns a domain object to be used as the id for the given object. This
        method may return {@code null} if the object has not been persisted or
        should be treated as irretrievable.

        @param domainObject the object to obtain an id for
        @return the object's id or {@code null}
        """
        raise NotImplementedError


    def getIdType(self):
        """Returns the id type."""
        raise NotImplementedError


    def getVersion(self, domainObject):
        """Returns a domain object to be used as the version for the given object.
        This method may return {@code null} if the object has not been persisted or
        should be treated as irretrievable.

        @param domainObject the object to obtain an id for
        @return the object's version or {@code null}
        """
        raise NotImplementedError


    def isLive(self, domainObject):
        """Returns a value indicating if the domain object should no longer be
        considered accessible. This method might return false if the record
        underlying the domain object had been deleted as a side-effect of
        processing a request.
        <p>
        The default implementation of this method uses {@link #getId(Object)} and
        {@link #find(Class, Object)} to determine if an object can be retrieved.
        """
        clazz = domainObject.__class__
        return self.find(clazz, self.getId(domainObject)) != None
