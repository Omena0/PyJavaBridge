package com.pyjavabridge.client;

import org.msgpack.core.MessagePack;
import org.msgpack.core.MessagePacker;
import org.msgpack.core.MessageUnpacker;
import org.msgpack.core.MessageFormat;
import org.msgpack.core.buffer.ArrayBufferOutput;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class ClientModFrameCodec {
    private ClientModFrameCodec() {
    }

    public record Frame(int protocolVersion, int packetType, int flags, int requestId, Map<String, Object> body) {
    }

    public static byte[] encodeFrame(int packetType, int flags, int requestId, Map<String, Object> body) throws IOException {
        byte[] bodyBytes = encodeBody(body == null ? Map.of() : body);
        ByteBuffer buffer = ByteBuffer
                .allocate(2 + 1 + 1 + 2 + 4 + 4 + bodyBytes.length)
                .order(ByteOrder.BIG_ENDIAN);

        buffer.putShort((short) ClientModProtocol.MAGIC);
        buffer.put((byte) ClientModProtocol.PROTOCOL_VERSION);
        buffer.put((byte) packetType);
        buffer.putShort((short) flags);
        buffer.putInt(requestId);
        buffer.putInt(bodyBytes.length);
        buffer.put(bodyBytes);

        return buffer.array();
    }

    public static Frame decodeFrame(byte[] data) throws IOException {
        if (data == null || data.length < 14) {
            throw new IOException("Frame too short");
        }

        ByteBuffer buffer = ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN);

        int magic = buffer.getShort() & 0xFFFF;
        if (magic != ClientModProtocol.MAGIC) {
            throw new IOException("Invalid frame magic");
        }

        int protocolVersion = buffer.get() & 0xFF;
        int packetType = buffer.get() & 0xFF;
        int flags = buffer.getShort() & 0xFFFF;
        int requestId = buffer.getInt();
        int bodyLen = buffer.getInt();

        if (bodyLen < 0 || bodyLen > ClientModProtocol.MAX_BODY_BYTES) {
            throw new IOException("Invalid frame body length: " + bodyLen);
        }

        if (buffer.remaining() != bodyLen) {
            throw new IOException("Frame body length mismatch");
        }

        byte[] bodyBytes = new byte[bodyLen];
        buffer.get(bodyBytes);
        Map<String, Object> body = decodeBody(bodyBytes);

        return new Frame(protocolVersion, packetType, flags, requestId, body);
    }

    private static byte[] encodeBody(Map<String, Object> body) throws IOException {
        try (ArrayBufferOutput out = new ArrayBufferOutput(); MessagePacker packer = MessagePack.newDefaultPacker(out)) {
            packAny(packer, body);
            packer.flush();
            return out.toByteArray();
        }
    }

    private static Map<String, Object> decodeBody(byte[] bodyBytes) throws IOException {
        try (MessageUnpacker unpacker = MessagePack.newDefaultUnpacker(bodyBytes)) {
            Object value = unpackAny(unpacker);
            if (value instanceof Map<?, ?> rawMap) {
                Map<String, Object> map = new LinkedHashMap<>();
                for (Map.Entry<?, ?> entry : rawMap.entrySet()) {
                    map.put(String.valueOf(entry.getKey()), entry.getValue());
                }
                return map;
            }
            return Map.of();
        }
    }

    private static void packAny(MessagePacker packer, Object value) throws IOException {
        if (value == null) {
            packer.packNil();
            return;
        }

        if (value instanceof String text) {
            packer.packString(text);
            return;
        }

        if (value instanceof Boolean bool) {
            packer.packBoolean(bool);
            return;
        }

        if (value instanceof Integer i) {
            packer.packInt(i);
            return;
        }

        if (value instanceof Long l) {
            packer.packLong(l);
            return;
        }

        if (value instanceof Short s) {
            packer.packShort(s);
            return;
        }

        if (value instanceof Byte b) {
            packer.packByte(b);
            return;
        }

        if (value instanceof Float f) {
            packer.packFloat(f);
            return;
        }

        if (value instanceof Double d) {
            packer.packDouble(d);
            return;
        }

        if (value instanceof byte[] bytes) {
            packer.packBinaryHeader(bytes.length);
            packer.writePayload(bytes);
            return;
        }

        if (value instanceof Map<?, ?> map) {
            packer.packMapHeader(map.size());
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                packAny(packer, String.valueOf(entry.getKey()));
                packAny(packer, entry.getValue());
            }
            return;
        }

        if (value instanceof List<?> list) {
            packer.packArrayHeader(list.size());
            for (Object item : list) {
                packAny(packer, item);
            }
            return;
        }

        if (value.getClass().isArray()) {
            Object[] values = (Object[]) value;
            packer.packArrayHeader(values.length);
            for (Object item : values) {
                packAny(packer, item);
            }
            return;
        }

        packer.packString(String.valueOf(value));
    }

    private static Object unpackAny(MessageUnpacker unpacker) throws IOException {
        MessageFormat fmt = unpacker.getNextFormat();
        return switch (fmt.getValueType()) {
            case NIL -> {
                unpacker.unpackNil();
                yield null;
            }
            case BOOLEAN -> unpacker.unpackBoolean();
            case INTEGER -> unpacker.unpackLong();
            case FLOAT -> unpacker.unpackDouble();
            case STRING -> unpacker.unpackString();
            case BINARY -> {
                int len = unpacker.unpackBinaryHeader();
                byte[] bytes = new byte[len];
                unpacker.readPayload(bytes);
                yield bytes;
            }
            case ARRAY -> {
                int size = unpacker.unpackArrayHeader();
                List<Object> list = new ArrayList<>(size);
                for (int i = 0; i < size; i++) {
                    list.add(unpackAny(unpacker));
                }
                yield list;
            }
            case MAP -> {
                int size = unpacker.unpackMapHeader();
                Map<String, Object> map = new LinkedHashMap<>(size);
                for (int i = 0; i < size; i++) {
                    Object key = unpackAny(unpacker);
                    Object val = unpackAny(unpacker);
                    map.put(String.valueOf(key), val);
                }
                yield map;
            }
            case EXTENSION -> {
                var ext = unpacker.unpackExtensionTypeHeader();
                byte[] payload = new byte[ext.getLength()];
                unpacker.readPayload(payload);
                yield payload;
            }
        };
    }
}
