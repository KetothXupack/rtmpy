# Copyright (c) 2007-2009 The RTMPy Project.
# See LICENSE for details.

"""
Tests for L{rtmpy.rtmp.event}.
"""

from zope.interface import implements
from twisted.trial import unittest
from twisted.internet import defer
from twisted.python.failure import Failure
import pyamf

from rtmpy.rtmp import interfaces, event
from rtmpy.util import BufferedByteStream


class MockPacket(object):
    """
    """

    implements(interfaces.IEvent)

    expected_encode = None
    expected_decode = None

    encode_func = lambda bbs: None
    decode_func = lambda bbs: None

    def encode(self, bbs, *args, **kwargs):
        self.encode_func(bbs, *args, **kwargs)

        return self.expected_encode

    def decode(self, bbs, *args, **kwargs):
        self.decode_func(bbs, *args, **kwargs)

        return self.expected_decode


class MockEventListener(object):
    """
    """

    implements(interfaces.IEventListener)

    def __init__(self):
        self.calls = []

    def onInvoke(self, *args, **kwargs):
        self.calls.append(('invoke', args, kwargs))

        return self

    def onNotify(self, *args, **kwargs):
        self.calls.append(('notify', args, kwargs))

        return self

    def onFrameSize(self, *args, **kwargs):
        self.calls.append(('frame-size', args, kwargs))

        return self

    def onBytesRead(self, *args, **kwargs):
        self.calls.append(('bytes-read', args, kwargs))

        return self

    def onControlMessage(self, *args, **kwargs):
        self.calls.append(('control', args, kwargs))

        return self

    def onDownstreamBandwidth(self, *args, **kwargs):
        self.calls.append(('bw-down', args, kwargs))

        return self

    def onUpstreamBandwidth(self, *args, **kwargs):
        self.calls.append(('bw-up', args, kwargs))

        return self

    def onAudioData(self, *args, **kwargs):
        self.calls.append(('audio', args, kwargs))

        return self

    def onVideoData(self, *args, **kwargs):
        self.calls.append(('video', args, kwargs))

        return self


class BaseTestCase(unittest.TestCase):
    """
    Ensures that L{event.TYPE_MAP} is properly restored.
    """

    def setUp(self):
        self._type_map = event.TYPE_MAP.copy()
        self._mock_dict = MockPacket.__dict__.copy()

        self.buffer = BufferedByteStream()

    def tearDown(self):
        event.TYPE_MAP = self._type_map

        for k, v in self._mock_dict.iteritems():
            if not k.startswith('_'):
                setattr(MockPacket, k, v)

    def _fail(self, r):
        print r, str(r.value)
        self.fail()


class DecodeTestCase(BaseTestCase):
    """
    Tests for L{event.decode}
    """

    def test_return_type(self):
        d = event.decode(None, None).addErrback(lambda f: None)

        self.assertTrue(isinstance(d, defer.Deferred))

    def test_unknown_type(self):
        def eb(f):
            self.assertTrue(isinstance(f, Failure))
            self.assertEquals(f.type, event.DecodeError)

            self.assertEquals(str(f.value), 'Unknown datatype \'None\'')

        return event.decode(None, None).addErrback(eb)

    def test_trailing_data(self):
        body = 'foo.bar'
        self.executed = False

        def decode(event, bbs):
            self.executed = True
            bbs.read(4)

        MockPacket.decode_func = decode

        event.TYPE_MAP[0] = MockPacket

        def eb(f):
            self.assertTrue(isinstance(f, Failure))
            self.assertEquals(f.type, event.TrailingDataError)

            self.assertEquals(str(f.value), '')
            self.assertTrue(self.executed)

        return event.decode(0, body).addCallback(self._fail).addErrback(eb)

    def test_return(self):
        body = 'foo.bar'
        self.executed = False

        def decode(event, bbs):
            self.executed = True
            bbs.read(7)

        MockPacket.decode_func = decode

        event.TYPE_MAP[0] = MockPacket

        def cb(r):
            self.assertTrue(isinstance(r, MockPacket))
            self.assertTrue(self.executed)

        return event.decode(0, body).addCallback(cb).addErrback(self._fail)

    def test_args(self):
        args = ('foo', 'bar')
        kwargs = {'baz': 'gak', 'spam': 'eggs'}
        self.executed = False

        def decode(event, bbs, *a, **kw):
            self.assertEquals(args, a)
            self.assertEquals(kwargs, kw)

            self.executed = True

        MockPacket.decode_func = decode

        event.TYPE_MAP[0] = MockPacket

        d = event.decode(0, '', *args, **kwargs)
        d.addCallback(lambda r: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d


class EncodeTestCase(BaseTestCase):
    """
    Tests for L{event.encode}
    """

    def test_return_type(self):
        d = event.encode(None).addErrback(lambda f: None)

        self.assertTrue(isinstance(d, defer.Deferred))

    def test_interface(self):
        x = object()

        self.assertFalse(interfaces.IEvent.implementedBy(x))

        def eb(f):
            self.assertTrue(isinstance(f, Failure))
            self.assertEquals(f.type, TypeError)

            self.assertEquals(str(f.value),
                "Expected an event interface (got:<type 'object'>)")

        return event.encode(x).addCallback(self._fail).addErrback(eb)

    def test_unknown_type(self):
        self.assertFalse(MockPacket in event.TYPE_MAP.values())
        x = MockPacket()

        def eb(f):
            self.assertTrue(isinstance(f, Failure))
            self.assertEquals(f.type, event.UnknownEventType)

            self.assertEquals(str(f.value), 'Unknown event type for %r' % x)

        return event.encode(x).addCallback(self._fail).addErrback(eb)

    def test_return(self):
        def encode(event, bbs):
            bbs.write('foo.bar')

        MockPacket.encode_func = encode
        event.TYPE_MAP[0] = MockPacket

        def cb(b):
            self.assertEquals(b, (0, 'foo.bar'))

        x = MockPacket()

        return event.encode(x).addErrback(self._fail).addCallback(cb)

    def test_args(self):
        args = ('foo', 'bar')
        kwargs = {'baz': 'gak', 'spam': 'eggs'}
        self.executed = False

        def encode(event, bbs, *a, **kw):
            self.assertEquals(args, a)
            self.assertEquals(kwargs, kw)

            self.executed = True

        MockPacket.encode_func = encode
        event.TYPE_MAP[0] = MockPacket

        x = MockPacket()

        d = event.encode(x, *args, **kwargs)
        d.addCallback(lambda r: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d


class BaseEventTestCase(unittest.TestCase):
    """
    Tests for L{event.BaseEvent}
    """

    def test_interface(self):
        x = event.BaseEvent()

        self.assertTrue(interfaces.IEvent.providedBy(x))

        self.assertRaises(NotImplementedError, x.encode, None)
        self.assertRaises(NotImplementedError, x.decode, None)
        self.assertRaises(NotImplementedError, x.dispatch, None)


class FrameSizeTestCase(BaseTestCase):
    """
    Tests for L{event.FrameSize}
    """

    def test_create(self):
        x = event.FrameSize()
        self.assertEquals(x.__dict__, {'size': None})

        x = event.FrameSize(10)
        self.assertEquals(x.__dict__, {'size': 10})

        x = event.FrameSize(size=20)
        self.assertEquals(x.__dict__, {'size': 20})

    def test_raw_encode(self):
        # test default encode
        x = event.FrameSize()
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), 'Frame size not set')

        # test non-int encode
        x = event.FrameSize(size='foo.bar')
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), 'Frame size wrong type '
            '(expected int, got <type \'str\'>)')

        x = event.FrameSize(size=50)
        e = x.encode(self.buffer)

        self.assertEquals(e, None)

        self.assertEquals(self.buffer.getvalue(), '\x00\x00\x00\x32')

    def test_raw_decode(self):
        x = event.FrameSize()

        self.assertEquals(x.size, None)
        self.buffer.write('\x00\x00\x00\x32')
        self.buffer.seek(0)

        e = x.decode(self.buffer)

        self.assertEquals(e, None)
        self.assertEquals(x.size, 50)

    def test_encode(self):
        e = event.FrameSize(size=2342)
        self.executed = False

        def cb(r):
            self.assertEquals(r, (1, '\x00\x00\t&'))
            self.executed = True

        d = event.encode(e).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_decode(self):
        self.executed = False

        def cb(r):
            self.assertTrue(isinstance(r, event.FrameSize))
            self.assertEquals(r.__dict__, {'size': 2342})
            self.executed = True

        d = event.decode(1, '\x00\x00\t&').addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_dispatch(self):
        listener = MockEventListener()
        x = event.FrameSize(5678)

        ret = x.dispatch(listener)
        self.assertIdentical(ret, listener)

        self.assertEquals(listener.calls, [('frame-size', (5678,), {})])


class ControlEventTestCase(BaseTestCase):
    """
    Tests for L{event.ControlEvent}
    """

    def test_create(self):
        x = event.ControlEvent()
        self.assertEquals(x.__dict__, {
            'type': None,
            'value1': 0,
            'value2': -1,
            'value3': -1
        })

        x = event.ControlEvent(9, 123, 456, 789)
        self.assertEquals(x.__dict__, {
            'type': 9,
            'value1': 123,
            'value2': 456,
            'value3': 789
        })

        x = event.ControlEvent(type=0, value1=123, value3=789, value2=456)
        self.assertEquals(x.__dict__, {
            'type': 0,
            'value1': 123,
            'value2': 456,
            'value3': 789
        })

    def test_raw_encode(self):
        x = event.ControlEvent()
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), 'Type not set')

        # test types ..
        x = event.ControlEvent(type='3')
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), "TypeError encoding type "
            "(expected int, got <type 'str'>)")

        x = event.ControlEvent(type=3, value1=None)
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), "TypeError encoding value1 "
            "(expected int, got <type 'NoneType'>)")

        x = event.ControlEvent(type=3, value1=10, value2=object())
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), "TypeError encoding value2 "
            "(expected int, got <type 'object'>)")

        x = event.ControlEvent(type=3, value1=10, value2=7, value3='foo')
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), "TypeError encoding value3 "
            "(expected int, got <type 'str'>)")

        self.buffer.truncate(0)
        x = event.ControlEvent(2)
        e = x.encode(self.buffer)
        self.assertEquals(self.buffer.getvalue(),
            '\x00\x02\x00\x00\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff')

        self.buffer.truncate(0)
        x = event.ControlEvent(type=0, value1=123, value3=789, value2=456)
        e = x.encode(self.buffer)

        self.assertEquals(e, None)
        self.assertEquals(self.buffer.getvalue(),
            '\x00\x00\x00\x00\x00{\x00\x00\x01\xc8\x00\x00\x03\x15')

    def test_raw_decode(self):
        x = event.ControlEvent()

        self.assertEquals(x.__dict__, {
            'type': None,
            'value1': 0,
            'value2': -1,
            'value3': -1
        })

        self.buffer.write('\x00\x00\x00\x00\x00{\x00\x00\x01\xc8\x00\x00\x03\x15')
        self.buffer.seek(0)

        e = x.decode(self.buffer)

        self.assertEquals(e, None)
        self.assertEquals(x.type, 0)
        self.assertEquals(x.value1, 123)
        self.assertEquals(x.value2, 456)
        self.assertEquals(x.value3, 789)

    def test_encode(self):
        e = event.ControlEvent(9, 123, 456, 789)
        self.executed = False

        def cb(r):
            self.assertEquals(r, (4, '\x00\t\x00\x00\x00{\x00\x00\x01\xc8\x00'
                '\x00\x03\x15'))
            self.executed = True

        d = event.encode(e).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_decode(self):
        bytes = '\x00\t\x00\x00\x00{\x00\x00\x01\xc8\x00\x00\x03\x15'
        self.executed = False

        def cb(r):
            self.assertTrue(isinstance(r, event.ControlEvent))
            self.assertEquals(r.__dict__, {
                'type': 9,
                'value1': 123,
                'value2': 456,
                'value3': 789})

            self.executed = True

        d = event.decode(4, bytes).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_repr(self):
        e = event.ControlEvent(9, 13, 45, 23)

        self.assertEquals(repr(e),
            '<ControlEvent type=9 value1=13 value2=45 value3=23 at 0x%x>' % (
                id(e)))

    def test_dispatch(self):
        listener = MockEventListener()
        x = event.ControlEvent()

        ret = x.dispatch(listener)
        self.assertIdentical(ret, listener)

        self.assertEquals(listener.calls, [('control', (x,), {})])


class NotifyTestCase(BaseTestCase):
    """
    Tests for L{event.Notify}
    """

    def test_create(self):
        e = event.Notify()
        self.assertEquals(e.__dict__, {'name': None, 'id': None, 'argv': []})

        e = event.Notify('foo', 'bar', 'baz', ['gak', 'foo', 'bar'])
        self.assertEquals(e.__dict__, {'name': 'foo', 'id': 'bar',
            'argv': ['baz', ['gak', 'foo', 'bar']]})

    def test_repr(self):
        e = event.Notify()
        self.assertEquals(repr(e),
            '<Notify name=None id=None argv=[] at 0x%x>' % (id(e),))

        e = event.Notify('foo', 'bar', {'baz': 'gak', 'spam': 'eggs'})
        self.assertEquals(repr(e),
            "<Notify name='foo' id='bar' argv=[{'baz': 'gak', 'spam': 'eggs'}] "
            "at 0x%x>" % (id(e),))

    def test_raw_encode(self):
        l = []
        e = event.Notify()

        b1 = BufferedByteStream()
        d = e.encode(b1)
        self.assertTrue(isinstance(d, defer.Deferred))

        def cb(buf):
            self.assertEquals(buf, None)
            self.assertEquals(b1.getvalue(), '\x05\x05')

        d.addCallback(cb)

        l.append(d)

        b2 = BufferedByteStream()
        d = e.encode(b2, encoding=pyamf.AMF3)
        self.assertTrue(isinstance(d, defer.Deferred))

        def cb2(buf):
            self.assertEquals(buf, None)
            self.assertEquals(b2.getvalue(), '\x01\x01')

        d.addCallback(cb2)

        l.append(d)

        return defer.DeferredList(l)

    def test_raw_decode(self):
        l = []
        e = event.Notify()

        b1 = BufferedByteStream('\x05\x05\x03\x00\x00\t')
        d = e.decode(b1)
        self.assertTrue(isinstance(d, defer.Deferred))

        def cb(res):
            self.assertEquals(res, None)
            self.assertEquals(e.name, None)
            self.assertEquals(e.id, None)
            self.assertEquals(e.argv, [{}])

        d.addCallback(cb)

        l.append(d)

        b2 = BufferedByteStream('\x01\x01\n\x0b\x01\x01')
        d = e.decode(b2, encoding=pyamf.AMF3)
        self.assertTrue(isinstance(d, defer.Deferred))

        def cb2(res):
            self.assertEquals(res, None)
            self.assertEquals(e.name, None)
            self.assertEquals(e.id, None)
            self.assertEquals(e.argv, [{}])

        d.addCallback(cb2)

        l.append(d)

        return defer.DeferredList(l)

    def test_encode(self):
        e = event.Notify('_result', 2, {'foo': 'bar', 'baz': 'gak'})
        self.executed = False

        def cb(r):
            self.assertEquals(r, (18, '\x02\x00\x07_result\x00@\x00\x00\x00'
                '\x00\x00\x00\x00\x03\x00\x03foo\x02\x00\x03bar\x00\x03baz'
                '\x02\x00\x03gak\x00\x00\t'))
            self.executed = True

        d = event.encode(e).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_decode(self):
        bytes = '\x02\x00\x07_result\x00@\x00\x00\x00\x00\x00\x00\x00\x03' + \
            '\x00\x03foo\x02\x00\x03bar\x00\x03baz\x02\x00\x03gak\x00\x00\t'
        self.executed = False

        def cb(r):
            self.assertTrue(isinstance(r, event.Notify))
            self.assertEquals(r.name, '_result')
            self.assertEquals(r.id, 2)
            self.assertEquals(r.argv, [{'foo': 'bar', 'baz': 'gak'}])

            self.executed = True

        d = event.decode(18, bytes).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_dispatch(self):
        listener = MockEventListener()
        x = event.Notify()

        ret = x.dispatch(listener)
        self.assertIdentical(ret, listener)

        self.assertEquals(listener.calls, [('notify', (x,), {})])


class InvokeTestCase(BaseTestCase):
    """
    Tests for L{event.Invoke}
    """

    def test_create(self):
        e = event.Invoke()
        self.assertEquals(e.__dict__, {'name': None, 'id': None, 'argv': []})

        e = event.Invoke('foo', 'bar', {'baz': 'gak', 'spam': 'eggs'}, 'yar')
        self.assertEquals(e.__dict__, {'name': 'foo', 'id': 'bar',
            'argv': [{'baz': 'gak', 'spam': 'eggs'}, 'yar']})

    def test_repr(self):
        e = event.Invoke()
        self.assertEquals(repr(e),
            '<Invoke name=None id=None argv=[] at 0x%x>' % (id(e),))

        e = event.Invoke('foo', 'bar', 'gak', 'spam', ['eggs'])
        self.assertEquals(repr(e),
            "<Invoke name='foo' id='bar' argv=['gak', 'spam', ['eggs']] "
            "at 0x%x>" % (id(e),))

    def test_raw_encode(self):
        l = []
        e = event.Invoke()

        b1 = BufferedByteStream()
        d = e.encode(b1)
        self.assertTrue(isinstance(d, defer.Deferred))

        def cb(buf):
            self.assertEquals(buf, None)
            self.assertEquals(b1.getvalue(), '\x05\x05')

        d.addCallback(cb)

        l.append(d)

        b2 = BufferedByteStream()
        d = e.encode(b2, encoding=pyamf.AMF3)
        self.assertTrue(isinstance(d, defer.Deferred))

        def cb2(buf):
            self.assertEquals(buf, None)
            self.assertEquals(b2.getvalue(), '\x01\x01')

        d.addCallback(cb2)

        l.append(d)

        return defer.DeferredList(l)

    def test_raw_decode(self):
        l = []
        e = event.Invoke()

        b1 = BufferedByteStream('\x05\x05\x03\x00\x00\t')
        d = e.decode(b1)
        self.assertTrue(isinstance(d, defer.Deferred))

        def cb(res):
            self.assertEquals(res, None)
            self.assertEquals(e.name, None)
            self.assertEquals(e.id, None)
            self.assertEquals(e.argv, [])

        d.addCallback(cb)

        l.append(d)

        b2 = BufferedByteStream('\x01\x01')
        d = e.decode(b2, encoding=pyamf.AMF3)
        self.assertTrue(isinstance(d, defer.Deferred))

        def cb2(res):
            self.assertEquals(res, None)
            self.assertEquals(e.name, None)
            self.assertEquals(e.id, None)
            self.assertEquals(e.argv, [])

        d.addCallback(cb2)

        l.append(d)

        return defer.DeferredList(l)

    def test_encode(self):
        e = event.Invoke('_result', 2, {'foo': 'bar', 'baz': 'gak'})
        self.executed = False

        def cb(r):
            self.assertEquals(r, (20, '\x02\x00\x07_result\x00@\x00\x00\x00'
                '\x00\x00\x00\x00\x03\x00\x03foo\x02\x00\x03bar\x00\x03baz'
                '\x02\x00\x03gak\x00\x00\t'))
            self.executed = True

        d = event.encode(e).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_decode(self):
        bytes = '\x02\x00\x07_result\x00@\x00\x00\x00\x00\x00\x00\x00\x03' + \
            '\x00\x03foo\x02\x00\x03bar\x00\x03baz\x02\x00\x03gak\x00\x00\t'
        self.executed = False

        def cb(r):
            self.assertTrue(isinstance(r, event.Invoke))
            self.assertEquals(r.name, '_result')
            self.assertEquals(r.id, 2)
            self.assertEquals(r.argv, [{'foo': 'bar', 'baz': 'gak'}])

            self.executed = True

        d = event.decode(20, bytes).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_dispatch(self):
        listener = MockEventListener()
        x = event.Invoke()

        ret = x.dispatch(listener)
        self.assertIdentical(ret, listener)

        self.assertEquals(listener.calls, [('invoke', (x,), {})])


class BytesReadTestCase(BaseTestCase):
    """
    Tests for L{event.BytesRead}
    """

    def test_create(self):
        x = event.BytesRead()
        self.assertEquals(x.__dict__, {'bytes': None})

        x = event.BytesRead(10)
        self.assertEquals(x.__dict__, {'bytes': 10})

        x = event.BytesRead(bytes=20)
        self.assertEquals(x.__dict__, {'bytes': 20})

    def test_raw_encode(self):
        # test default encode
        x = event.BytesRead()
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), 'Bytes read not set')

        # test non-int encode
        x = event.BytesRead(bytes='foo.bar')
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), 'Bytes read wrong type '
            '(expected int, got <type \'str\'>)')

        x = event.BytesRead(bytes=50)
        e = x.encode(self.buffer)

        self.assertEquals(e, None)

        self.assertEquals(self.buffer.getvalue(), '\x00\x00\x00\x32')

    def test_raw_decode(self):
        x = event.BytesRead()

        self.assertEquals(x.bytes, None)
        self.buffer.write('\x00\x00\x00\x32')
        self.buffer.seek(0)

        e = x.decode(self.buffer)

        self.assertEquals(e, None)
        self.assertEquals(x.bytes, 50)

    def test_encode(self):
        e = event.BytesRead(bytes=2342)
        self.executed = False

        def cb(r):
            self.assertEquals(r, (3, '\x00\x00\t&'))
            self.executed = True

        d = event.encode(e).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_decode(self):
        self.executed = False

        def cb(r):
            self.assertTrue(isinstance(r, event.BytesRead))
            self.assertEquals(r.__dict__, {'bytes': 2342})
            self.executed = True

        d = event.decode(3, '\x00\x00\t&').addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_dispatch(self):
        listener = MockEventListener()
        x = event.BytesRead(90)

        ret = x.dispatch(listener)
        self.assertIdentical(ret, listener)

        self.assertEquals(listener.calls, [('bytes-read', (90,), {})])


class DownstreamBandwidthTestCase(BaseTestCase):
    """
    Tests for L{event.DownstreamBandwidth}
    """

    def test_create(self):
        x = event.DownstreamBandwidth()
        self.assertEquals(x.__dict__, {'bandwidth': None})

        x = event.DownstreamBandwidth(10)
        self.assertEquals(x.__dict__, {'bandwidth': 10})

        x = event.DownstreamBandwidth(bandwidth=20)
        self.assertEquals(x.__dict__, {'bandwidth': 20})

    def test_raw_encode(self):
        # test default encode
        x = event.DownstreamBandwidth()
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), 'Downstream bandwidth not set')

        # test non-int encode
        x = event.DownstreamBandwidth(bandwidth='foo.bar')
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), "TypeError for downstream bandwidth "
            "(expected int, got <type 'str'>)")

        x = event.DownstreamBandwidth(bandwidth=50)
        e = x.encode(self.buffer)

        self.assertEquals(e, None)

        self.assertEquals(self.buffer.getvalue(), '\x00\x00\x00\x32')

    def test_raw_decode(self):
        x = event.DownstreamBandwidth()

        self.assertEquals(x.bandwidth, None)
        self.buffer.write('\x00\x00\x00\x32')
        self.buffer.seek(0)

        e = x.decode(self.buffer)

        self.assertEquals(e, None)
        self.assertEquals(x.bandwidth, 50)

    def test_encode(self):
        e = event.DownstreamBandwidth(bandwidth=2342)
        self.executed = False

        def cb(r):
            self.assertEquals(r, (5, '\x00\x00\t&'))
            self.executed = True

        d = event.encode(e).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_decode(self):
        self.executed = False

        def cb(r):
            self.assertTrue(isinstance(r, event.DownstreamBandwidth))
            self.assertEquals(r.__dict__, {'bandwidth': 2342})
            self.executed = True

        d = event.decode(5, '\x00\x00\t&').addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_dispatch(self):
        listener = MockEventListener()
        x = event.DownstreamBandwidth('foo')

        ret = x.dispatch(listener)
        self.assertIdentical(ret, listener)

        self.assertEquals(listener.calls, [('bw-down', ('foo',), {})])


class UpstreamBandwidthTestCase(BaseTestCase):
    """
    Tests for L{event.UpstreamBandwidth}
    """

    def test_create(self):
        x = event.UpstreamBandwidth()
        self.assertEquals(x.__dict__, {'bandwidth': None, 'extra': None})

        x = event.UpstreamBandwidth(10, 32)
        self.assertEquals(x.__dict__, {'bandwidth': 10, 'extra': 32})

        x = event.UpstreamBandwidth(bandwidth=20, extra=233)
        self.assertEquals(x.__dict__, {'bandwidth': 20, 'extra': 233})

    def test_raw_encode(self):
        # test default encode
        x = event.UpstreamBandwidth()
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), 'Upstream bandwidth not set')
        self.buffer.truncate(0)

        x = event.UpstreamBandwidth(bandwidth='234')
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), 'Extra not set')
        self.buffer.truncate(0)

        # test non-int encode
        x = event.UpstreamBandwidth(bandwidth='foo.bar', extra=234)
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), "TypeError: Upstream bandwidth "
            "(expected int, got <type 'str'>)")
        self.buffer.truncate(0)

        # test non-int encode
        x = event.UpstreamBandwidth(bandwidth=1200, extra='asdfas')
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), "TypeError: extra "
            "(expected int, got <type 'str'>)")
        self.buffer.truncate(0)

        x = event.UpstreamBandwidth(bandwidth=50, extra=12)
        e = x.encode(self.buffer)

        self.assertEquals(e, None)

        self.assertEquals(self.buffer.getvalue(), '\x00\x00\x00\x32\x0C')

    def test_raw_decode(self):
        x = event.UpstreamBandwidth()

        self.assertEquals(x.bandwidth, None)
        self.buffer.write('\x00\x00\x00\x32\x0C')
        self.buffer.seek(0)

        e = x.decode(self.buffer)

        self.assertEquals(e, None)
        self.assertEquals(x.bandwidth, 50)
        self.assertEquals(x.extra, 12)

    def test_encode(self):
        e = event.UpstreamBandwidth(bandwidth=2342, extra=65)
        self.executed = False

        def cb(r):
            self.assertEquals(r, (6, '\x00\x00\t&A'))
            self.executed = True

        d = event.encode(e).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_decode(self):
        self.executed = False

        def cb(r):
            self.assertTrue(isinstance(r, event.UpstreamBandwidth))
            self.assertEquals(r.__dict__, {'bandwidth': 2342, 'extra': 65})
            self.executed = True

        d = event.decode(6, '\x00\x00\t&A').addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_dispatch(self):
        listener = MockEventListener()
        x = event.UpstreamBandwidth('foo', 'bar')

        ret = x.dispatch(listener)
        self.assertIdentical(ret, listener)

        self.assertEquals(listener.calls, [('bw-up', ('foo', 'bar'), {})])


class AudioDataTestCase(BaseTestCase):
    """
    Tests for L{event.AudioData}
    """

    def test_interface(self):
        self.assertTrue(interfaces.IStreamable.implementedBy(event.VideoData))

    def test_create(self):
        x = event.AudioData()
        self.assertEquals(x.__dict__, {'data': None})

        x = event.AudioData(10)
        self.assertEquals(x.__dict__, {'data': 10})

        x = event.AudioData(data=20)
        self.assertEquals(x.__dict__, {'data': 20})

    def test_raw_encode(self):
        # test default encode
        x = event.AudioData()
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), 'No data set')

        # test non-str encode
        x = event.AudioData(data=20)
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), "TypeError: data "
            "(expected str, got <type 'int'>)")

        x = event.AudioData(data='foo.bar')
        e = x.encode(self.buffer)

        self.assertEquals(e, None)

        self.assertEquals(self.buffer.getvalue(), 'foo.bar')

    def test_raw_decode(self):
        x = event.AudioData()

        self.assertEquals(x.data, None)
        self.buffer.write('foo.bar')
        self.buffer.seek(0)

        e = x.decode(self.buffer)

        self.assertEquals(e, None)
        self.assertEquals(x.data, 'foo.bar')

    def test_encode(self):
        e = event.AudioData(data=('abcdefg' * 50))
        self.executed = False

        def cb(r):
            self.assertEquals(r, (7, 'abcdefg' * 50))
            self.executed = True

        d = event.encode(e).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_decode(self):
        self.executed = False

        def cb(r):
            self.assertTrue(isinstance(r, event.AudioData))
            self.assertEquals(r.__dict__, {'data': 'abcdefg' * 50})
            self.executed = True

        d = event.decode(7, 'abcdefg' * 50).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_dispatch(self):
        listener = MockEventListener()
        x = event.AudioData('foo')

        ret = x.dispatch(listener)
        self.assertIdentical(ret, listener)

        self.assertEquals(listener.calls, [('audio', ('foo',), {})])


class VideoDataTestCase(BaseTestCase):
    """
    Tests for L{event.VideoData}
    """

    def test_interface(self):
        self.assertTrue(interfaces.IStreamable.implementedBy(event.VideoData))

    def test_create(self):
        x = event.VideoData()
        self.assertEquals(x.__dict__, {'data': None})

        x = event.VideoData(10)
        self.assertEquals(x.__dict__, {'data': 10})

        x = event.VideoData(data=20)
        self.assertEquals(x.__dict__, {'data': 20})

    def test_raw_encode(self):
        # test default encode
        x = event.VideoData()
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), 'No data set')

        # test non-str encode
        x = event.VideoData(data=20)
        e = self.assertRaises(event.EncodeError, x.encode, self.buffer)
        self.assertEquals(str(e), "TypeError: data "
            "(expected str, got <type 'int'>)")

        x = event.VideoData(data='foo.bar')
        e = x.encode(self.buffer)

        self.assertEquals(e, None)

        self.assertEquals(self.buffer.getvalue(), 'foo.bar')

    def test_raw_decode(self):
        x = event.VideoData()

        self.assertEquals(x.data, None)
        self.buffer.write('foo.bar')
        self.buffer.seek(0)

        e = x.decode(self.buffer)

        self.assertEquals(e, None)
        self.assertEquals(x.data, 'foo.bar')

    def test_encode(self):
        e = event.VideoData(data=('abcdefg' * 50))
        self.executed = False

        def cb(r):
            self.assertEquals(r, (8, 'abcdefg' * 50))
            self.executed = True

        d = event.encode(e).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_decode(self):
        self.executed = False

        def cb(r):
            self.assertTrue(isinstance(r, event.VideoData))
            self.assertEquals(r.__dict__, {'data': 'abcdefg' * 50})
            self.executed = True

        d = event.decode(8, 'abcdefg' * 50).addCallback(cb)
        d.addCallback(lambda x: self.assertTrue(self.executed))
        d.addErrback(self._fail)

        return d

    def test_dispatch(self):
        listener = MockEventListener()
        x = event.VideoData('foo')

        ret = x.dispatch(listener)
        self.assertIdentical(ret, listener)

        self.assertEquals(listener.calls, [('video', ('foo',), {})])


class HelperTestCase(unittest.TestCase):
    def test_type_class(self):
        for k, v in event.TYPE_MAP.iteritems():
            self.assertEquals(event.get_type_class(k), v)

        self.assertFalse('foo' in event.TYPE_MAP.keys())
        self.assertRaises(event.UnknownEventType, event.get_type_class, 'foo')