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


class RequestContext(object):
    """The base interface for RequestFactory service endpoints. Implementations of
    this interface are provided by the RequestFactory plumbing and this interface
    may be extended in the future.

    @see com.google.web.bindery.requestfactory.shared.testing.FakeRequestContext
    """

    def append(self, other):
        """Joins another RequestContext to this RequestContext.

        <pre>
        SomeContext ctx = myFactory.someContext();
        // Perform operations on ctx
        OtherContext other = ctx.append(myFactory.otherContext());
        // Perform operations on both other and ctx
        ctx.fire() // or other.fire() are equivalent
        </pre>

        @param other a freshly-constructed RequestContext whose state should be
                 bound to this RequestContext
        @return {@code other}
        @throws IllegalStateException if any methods have been called on
                  {@code other} or if {@code other} was constructed by a different
                  RequestFactory instance
        """
        pass

    def create(self, clazz):
        """Returns a new mutable proxy that this request can carry to the server,
        perhaps to be persisted. If the object is succesfully persisted, a PERSIST
        event will be posted including the EntityProxyId of this proxy.

        @param clazz a Class object of type T
        @return an {@link BaseProxy} instance of type T
        """
        pass

    def edit(self, object_):
        """Returns a mutable version of the proxy, whose mutations will accumulate in
        this context. Proxies reached via getters on this mutable proxy will also
        be mutable.

        @param object an instance of type T
        @return an {@link EntityProxy} or {@link ValueProxy} instance of type T
        """
        pass

    def find(self, proxyId):
        """Return a request to find a fresh instance of the referenced proxy.

        @param proxyId an {@link EntityProxyId} instance of type P
        @return a {@link Request} object
        """
        pass

    def fire(self, receiver=None):
        """Send the accumulated changes and method invocations associated with the
        RequestContext.
        <p>
        If {@link Request#to(Receiver)} has not been called, this method will
        install a default receiver that will throw a RuntimeException if there is a
        server failure.

        @param receiver a {@link Receiver} instance for receiving errors or
        validation failures.
        @throws IllegalArgumentException if <code>receiver</code> is
                  <code>null</code>
        """
        pass

    def getRequestFactory(self):
        """Returns the {@link RequestFactory} that created the RequestContext."""
        pass

    def isChanged(self):
        """Returns true if any changes have been made to proxies mutable under this
        context. Note that vacuous changes &mdash; e.g. foo.setName(foo.getName()
        &mdash; will not trip the changed flag. Similarly, "unmaking" a change will
        clear the isChanged flag

        <pre>
        String name = bar.getName();
        bar.setName("something else");
        assertTrue(context.isChanged());
        bar.setName(name);
        assertFalse(context.isChanged());
        </pre>

        @return {@code true} if any changes have been made
        """
        pass
