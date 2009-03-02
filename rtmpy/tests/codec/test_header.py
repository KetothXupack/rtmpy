# Copyright (c) 2007-2009 The RTMPy Project.
# See LICENSE.txt for details.

"""
Tests for L{rtmpy.rtmp.codec.header}.
"""

from zope.interface import implements
from twisted.internet import reactor, defer
from twisted.trial import unittest

from rtmpy.rtmp.codec import header
from rtmpy import util


class DummyHeader(object):
    """
    A dumb object that implements L{header.IHeader}
    """

    implements(header.IHeader)

    def __init__(self, *args, **kwargs):
        self.channelId = kwargs.get('channelId', None)
        self.relative = kwargs.get('relative', None)
        self.timestamp = kwargs.get('timestamp', None)
        self.datatype = kwargs.get('datatype', None)
        self.bodyLength = kwargs.get('bodyLength', None)
        self.streamId = kwargs.get('streamId', None)


class DecodeHeaderByteTestCase(unittest.TestCase):
    """
    Tests for L{header.decodeHeaderByte}
    """

    def test_types(self):
        self.assertRaises(TypeError, header.decodeHeaderByte, 'asdfasd')

        try:
            header.decodeHeaderByte(123)
        except TypeError, e:
            self.fail('Unexpected TypeError raised')

    def test_overflow(self):
        self.assertRaises(OverflowError, header.decodeHeaderByte, -1)
        self.assertRaises(OverflowError, header.decodeHeaderByte, 256)

    def test_return(self):
        self.assertEquals(header.decodeHeaderByte(0), (12, 0))
        self.assertEquals(header.decodeHeaderByte(192), (1, 0))
        self.assertEquals(header.decodeHeaderByte(255), (1, 63))


class EncodeHeaderByteTestCase(unittest.TestCase):
    """
    Tests for L{header.encodeHeaderByte}
    """

    def test_types(self):
        self.assertRaises(TypeError, header.encodeHeaderByte, 'foo', 0)
        self.assertRaises(TypeError, header.encodeHeaderByte, 0, 'foo')

        try:
            header.encodeHeaderByte(0, 0)
        except TypeError, e:
            self.fail('Unexpected TypeError raised')
        except:
            pass

    def test_values(self):
        for x in header.HEADER_SIZES:
            try:
                header.encodeHeaderByte(x, 0)
            except ValueError:
                self.fail('Raised ValueError on %d' % (x,))

        self.assertFalse(16 in header.HEADER_SIZES)
        self.assertRaises(ValueError, header.encodeHeaderByte, 16, 0)

        self.assertRaises(ValueError, header.encodeHeaderByte, 1, -1)
        self.assertRaises(ValueError, header.encodeHeaderByte, 1, 0x40)

    def test_return(self):
        self.assertEquals(header.encodeHeaderByte(12, 0), 0)
        self.assertEquals(header.encodeHeaderByte(1, 0), 192)
        self.assertEquals(header.encodeHeaderByte(1, 63), 255)


class GetHeaderSizeIndexTestCase(unittest.TestCase):
    """
    Tests for L{header.getHeaderSizeIndex}
    """

    def test_types(self):
        self.assertRaises(TypeError, header.getHeaderSizeIndex, object())

        h = DummyHeader()
        self.assertTrue(header.IHeader.providedBy(h))

        try:
            header.getHeaderSizeIndex(h)
        except TypeError:
            self.fail('Unexpected TypeError raised')
        except:
            pass

    def test_values(self):
        h = DummyHeader()
        self.assertEquals(h.channelId, None)

        self.assertRaises(ValueError, header.getHeaderSizeIndex, h)

    def test_return(self):
        h = DummyHeader(channelId=3)

        self.assertEquals(
            [h.timestamp, h.datatype, h.bodyLength, h.streamId],
            [None, None, None, None])
        self.assertEquals(header.getHeaderSizeIndex(h), 3)
        self.assertEquals(
            [h.timestamp, h.datatype, h.bodyLength, h.streamId],
            [None, None, None, None])

        h.timestamp = 23455
        self.assertEquals(header.getHeaderSizeIndex(h), 2)

        h.datatype = 12
        h.bodyLength = 1234

        self.assertEquals(header.getHeaderSizeIndex(h), 1)
        h.timestamp = None
        e = self.assertRaises(ValueError, header.getHeaderSizeIndex, h)

        h = DummyHeader(channelId=23, streamId=234, bodyLength=1232,
            datatype=2, timestamp=234234)

        self.assertEquals(header.getHeaderSizeIndex(h), 0)

        h.bodyLength = None
        e = self.assertRaises(ValueError, header.getHeaderSizeIndex, h)
        h.bodyLength = 1232

        h.datatype = None
        e = self.assertRaises(ValueError, header.getHeaderSizeIndex, h)
        h.datatype = 2

        h.timestamp = None
        e = self.assertRaises(ValueError, header.getHeaderSizeIndex, h)
        h.timestamp = 2345123


class GetHeaderSizeTestCase(unittest.TestCase):
    """
    Tests for L{header.getHeaderSize}
    """

    def test_types(self):
        self.assertRaises(TypeError, header.getHeaderSize, object())

        h = DummyHeader()
        self.assertTrue(header.IHeader.providedBy(h))

        try:
            header.getHeaderSize(h)
        except TypeError:
            self.fail('Unexpected TypeError raised')
        except:
            pass

    def test_return(self):
        h = DummyHeader(channelId=3)

        self.assertEquals(
            [h.timestamp, h.datatype, h.bodyLength, h.streamId],
            [None, None, None, None])

        self.assertEquals(header.getHeaderSize(h), 1)
        h.timestamp = 234234
        self.assertEquals(header.getHeaderSize(h), 4)
        h.datatype = 2
        h.bodyLength = 1231211
        self.assertEquals(header.getHeaderSize(h), 8)
        h.streamId = 2134
        self.assertEquals(header.getHeaderSize(h), 12)


class EncodeHeaderTestCase(unittest.TestCase):
    """
    Tests for L{header.encodeHeader}
    """

    def setUp(self):
        self.stream = util.BufferedByteStream()

    def test_types(self):
        h = DummyHeader()
        self.assertTrue(header.IHeader.providedBy(h))
        self.assertRaises(TypeError, header.encodeHeader, object(), h)
        self.assertRaises(TypeError, header.encodeHeader, self.stream, object())

        try:
            self.assertRaises(TypeError, header.encodeHeader, self.stream, h)
        except TypeError:
            self.fail('Unexpected TypeError raised')
        except:
            pass

    def _encode(self, h):
        self.stream.seek(0, 2)
        self.stream.truncate()
        header.encodeHeader(self.stream, h)

        return self.stream.getvalue()

    def test_encode(self):
        h = DummyHeader(channelId=3)

        self.assertEquals(
            [h.timestamp, h.datatype, h.bodyLength, h.streamId],
            [None, None, None, None])

        self.assertEquals(self._encode(h), '\xc3')

        h.channelId = 21
        self.assertEquals(self._encode(h), '\xd5')

        h.timestamp = 234234
        self.assertEquals(self._encode(h), '\x95\x03\x92\xfa')

        h.datatype = 3
        h.bodyLength = 31242
        self.assertEquals(self._encode(h), 'U\x03\x92\xfa\x00z\n\x03')

        h.streamId = 45
        self.assertEquals(self._encode(h), '\x15\x03\x92\xfa\x00z\n\x03\x00\x00\x00-')

    def test_encode_little_endian(self):
        """
        In this test we set the stream's endian to LITTLE_ENDIAN to ensure
        that endianness is correctly handled.
        """
        self.stream.endian = util.BufferedByteStream.ENDIAN_LITTLE

        self.test_encode()
        self.assertEquals(self.stream.endian, util.BufferedByteStream.ENDIAN_LITTLE)


class DecodeHeaderTestCase(unittest.TestCase):
    """
    Tests for L{header.decodeHeader}
    """

    def _decode(self, s):
        stream = util.BufferedByteStream(s)

        return header.decodeHeader(stream)

    def test_decodeSize1(self):
        h = self._decode('\xc3')

        self.assertTrue(header.IHeader.providedBy(h))
        self.assertEquals(h.channelId, 3)
        self.assertEquals(h.relative, True)
        self.assertEquals(h.timestamp, None)
        self.assertEquals(h.bodyLength, None)
        self.assertEquals(h.datatype, None)
        self.assertEquals(h.streamId, None)

        h = self._decode('\xd5')

        self.assertTrue(header.IHeader.providedBy(h))
        self.assertEquals(h.channelId, 21)
        self.assertEquals(h.relative, True)
        self.assertEquals(h.timestamp, None)
        self.assertEquals(h.bodyLength, None)
        self.assertEquals(h.datatype, None)
        self.assertEquals(h.streamId, None)

    def test_decodeSize4(self):
        h = self._decode('\x95\x03\x92\xfa')

        self.assertTrue(header.IHeader.providedBy(h))
        self.assertEquals(h.channelId, 21)
        self.assertEquals(h.relative, True)
        self.assertEquals(h.timestamp, 234234)
        self.assertEquals(h.bodyLength, None)
        self.assertEquals(h.datatype, None)
        self.assertEquals(h.streamId, None)

    def test_decodeSize8(self):
        h = self._decode('U\x03\x92\xfa\x00z\n\x03')

        self.assertTrue(header.IHeader.providedBy(h))
        self.assertEquals(h.channelId, 21)
        self.assertEquals(h.relative, True)
        self.assertEquals(h.timestamp, 234234)
        self.assertEquals(h.bodyLength, 31242)
        self.assertEquals(h.datatype, 3)
        self.assertEquals(h.streamId, None)

    def test_decodeSize12(self):
        h = self._decode('\x15\x03\x92\xfa\x00z\n\x03\x00\x00\x00-')

        self.assertTrue(header.IHeader.providedBy(h))
        self.assertEquals(h.channelId, 21)
        self.assertEquals(h.relative, False)
        self.assertEquals(h.timestamp, 234234)
        self.assertEquals(h.bodyLength, 31242)
        self.assertEquals(h.datatype, 3)
        self.assertEquals(h.streamId, 45)


class DiffHeadersTestCase(unittest.TestCase):
    """
    Tests for L{header.diffHeaders}
    """

    def _generate(self):
        """
        Generates an absolute header and guarantees that the attributes will
        be the same on each call.
        """
        return DummyHeader(relative=False, channelId=3, timestamp=1000,
            bodyLength=2000, datatype=3, streamId=243)

    def test_types(self):
        h = DummyHeader()

        self.assertTrue(header.IHeader.providedBy(h))
        self.assertRaises(TypeError, header.diffHeaders, h, object())
        self.assertRaises(TypeError, header.diffHeaders, object(), h)

        try:
            header.diffHeaders(h, h)
        except TypeError:
            self.fail('Unexpected TypeError raised')
        except:
            pass

    def test_absolute(self):
        h1 = DummyHeader(relative=None)
        h2 = DummyHeader(relative=True)
        h3 = DummyHeader(relative=False)

        e = self.assertRaises(ValueError, header.diffHeaders, h1, h1)
        self.assertEquals(str(e),
            'Received a non-absolute header for old (relative = None)')

        e = self.assertRaises(ValueError, header.diffHeaders, h2, h2)
        self.assertEquals(str(e),
            'Received a non-absolute header for old (relative = True)')

        e = self.assertRaises(ValueError, header.diffHeaders, h3, h1)
        self.assertEquals(str(e),
            'Received a non-absolute header for new (relative = None)')

        e = self.assertRaises(ValueError, header.diffHeaders, h3, h2)
        self.assertEquals(str(e),
            'Received a non-absolute header for new (relative = True)')

    def test_sameChannel(self):
        h1 = DummyHeader(relative=False, channelId=3)
        h2 = DummyHeader(relative=False, channelId=42)

        e = self.assertRaises(ValueError, header.diffHeaders, h1, h2)
        self.assertEquals(str(e), 'The two headers are not for the same channel')

    def test_nodiff(self):
        old = self._generate()
        new = self._generate()

        h = header.diffHeaders(old, new)
        self.assertTrue(header.IHeader.providedBy(h))
        self.assertTrue(h.relative)
        self.assertEquals(h.timestamp, None)
        self.assertEquals(h.bodyLength, None)
        self.assertEquals(h.datatype, None)
        self.assertEquals(h.streamId, None)
        self.assertEquals(h.channelId, 3)

    def test_timestamp(self):
        old = self._generate()
        new = self._generate()

        new.timestamp = old.timestamp + 234234
        h = header.diffHeaders(old, new)

        self.assertTrue(header.IHeader.providedBy(h))
        self.assertTrue(h.relative)
        self.assertEquals(h.timestamp, 234234)
        self.assertEquals(h.bodyLength, None)
        self.assertEquals(h.datatype, None)
        self.assertEquals(h.streamId, None)
        self.assertEquals(h.channelId, 3)

    def test_datatype(self):
        old = self._generate()
        new = self._generate()

        new.datatype = 0
        self.assertNotEquals(new.datatype, old.datatype)
        h = header.diffHeaders(old, new)

        self.assertTrue(header.IHeader.providedBy(h))
        self.assertTrue(h.relative)
        self.assertEquals(h.timestamp, None)
        self.assertEquals(h.bodyLength, None)
        self.assertEquals(h.datatype, 0)
        self.assertEquals(h.streamId, None)
        self.assertEquals(h.channelId, 3)

    def test_bodyLength(self):
        old = self._generate()
        new = self._generate()

        new.bodyLength = 2001
        self.assertNotEquals(new.bodyLength, old.bodyLength)
        h = header.diffHeaders(old, new)

        self.assertTrue(header.IHeader.providedBy(h))
        self.assertTrue(h.relative)
        self.assertEquals(h.timestamp, None)
        self.assertEquals(h.bodyLength, 1)
        self.assertEquals(h.datatype, None)
        self.assertEquals(h.streamId, None)
        self.assertEquals(h.channelId, 3)

    def test_streamId(self):
        old = self._generate()
        new = self._generate()

        new.streamId = 12
        self.assertNotEquals(new.streamId, old.streamId)
        h = header.diffHeaders(old, new)

        self.assertTrue(header.IHeader.providedBy(h))
        self.assertTrue(h.relative)
        self.assertEquals(h.timestamp, None)
        self.assertEquals(h.bodyLength, None)
        self.assertEquals(h.datatype, None)
        self.assertEquals(h.streamId, 12)
        self.assertEquals(h.channelId, 3)

    def test_complex(self):
        old = self._generate()
        new = self._generate()

        new.streamId = 12
        new.timestamp = 234234
        new.datatype = 0
        new.bodyLength = 2001
        new.streamId = 12

        h = header.diffHeaders(old, new)

        self.assertTrue(header.IHeader.providedBy(h))
        self.assertTrue(h.relative)
        self.assertEquals(h.timestamp, 233234)
        self.assertEquals(h.bodyLength, 1)
        self.assertEquals(h.datatype, 0)
        self.assertEquals(h.streamId, 12)
        self.assertEquals(h.channelId, 3)