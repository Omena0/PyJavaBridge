package com.pyjavabridge;

import com.comphenix.protocol.PacketType;
import com.comphenix.protocol.ProtocolLibrary;
import com.comphenix.protocol.ProtocolManager;
import com.comphenix.protocol.events.*;
import com.comphenix.protocol.reflect.StructureModifier;
import com.google.gson.JsonObject;

import org.bukkit.entity.Player;
import org.bukkit.plugin.Plugin;

import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.BiConsumer;

/**
 * Optional ProtocolLib integration for packet-level API.
 * Only loaded when ProtocolLib is available.
 */
public class PacketBridge {
    private final Plugin plugin;
    private final ProtocolManager protocolManager;
    private final Map<String, PacketAdapter> activeListeners = new ConcurrentHashMap<>();

    public PacketBridge(Plugin plugin) {
        this.plugin = plugin;
        this.protocolManager = ProtocolLibrary.getProtocolManager();
    }

    public void listenSend(String packetName, BiConsumer<Player, JsonObject> callback) {
        PacketType type = resolvePacketType(packetName, PacketType.Protocol.PLAY, PacketType.Sender.SERVER);
        if (type == null) return;
        String key = "send:" + packetName;
        removeListener(key);
        PacketAdapter adapter = new PacketAdapter(plugin, ListenerPriority.NORMAL, type) {
            @Override
            public void onPacketSending(PacketEvent event) {
                JsonObject data = serializePacket(event.getPacket(), packetName);
                callback.accept(event.getPlayer(), data);
                if (data.has("__cancel__") && data.get("__cancel__").getAsBoolean()) {
                    event.setCancelled(true);
                }
            }
        };
        protocolManager.addPacketListener(adapter);
        activeListeners.put(key, adapter);
    }

    public void listenReceive(String packetName, BiConsumer<Player, JsonObject> callback) {
        PacketType type = resolvePacketType(packetName, PacketType.Protocol.PLAY, PacketType.Sender.CLIENT);
        if (type == null) return;
        String key = "recv:" + packetName;
        removeListener(key);
        PacketAdapter adapter = new PacketAdapter(plugin, ListenerPriority.NORMAL, type) {
            @Override
            public void onPacketReceiving(PacketEvent event) {
                JsonObject data = serializePacket(event.getPacket(), packetName);
                callback.accept(event.getPlayer(), data);
                if (data.has("__cancel__") && data.get("__cancel__").getAsBoolean()) {
                    event.setCancelled(true);
                }
            }
        };
        protocolManager.addPacketListener(adapter);
        activeListeners.put(key, adapter);
    }

    public void removeListener(String key) {
        PacketAdapter old = activeListeners.remove(key);
        if (old != null) {
            protocolManager.removePacketListener(old);
        }
    }

    public void removeAllListeners() {
        for (Map.Entry<String, PacketAdapter> entry : activeListeners.entrySet()) {
            protocolManager.removePacketListener(entry.getValue());
        }
        activeListeners.clear();
    }

    public Set<String> getListenerKeys() {
        return activeListeners.keySet();
    }

    public void sendPacket(Player player, String packetName, JsonObject fields) {
        PacketType type = resolvePacketType(packetName, PacketType.Protocol.PLAY, PacketType.Sender.SERVER);
        if (type == null) return;
        PacketContainer packet = protocolManager.createPacket(type);
        applyFields(packet, fields);
        protocolManager.sendServerPacket(player, packet);
    }

    private PacketType resolvePacketType(String name, PacketType.Protocol protocol, PacketType.Sender sender) {
        String upper = name.toUpperCase();
        for (PacketType type : PacketType.values()) {
            if (type.getProtocol() == protocol && type.getSender() == sender) {
                if (type.name().equalsIgnoreCase(upper)) {
                    return type;
                }
            }
        }
        // Try loose match
        for (PacketType type : PacketType.values()) {
            if (type.name().equalsIgnoreCase(upper)) {
                return type;
            }
        }
        return null;
    }

    private JsonObject serializePacket(PacketContainer packet, String name) {
        JsonObject obj = new JsonObject();
        obj.addProperty("packet_type", name);
        try {
            StructureModifier<Integer> ints = packet.getIntegers();
            for (int i = 0; i < ints.size(); i++) {
                Integer val = ints.readSafely(i);
                if (val != null) obj.addProperty("int_" + i, val);
            }
            StructureModifier<Double> doubles = packet.getDoubles();
            for (int i = 0; i < doubles.size(); i++) {
                Double val = doubles.readSafely(i);
                if (val != null) obj.addProperty("double_" + i, val);
            }
            StructureModifier<Float> floats = packet.getFloat();
            for (int i = 0; i < floats.size(); i++) {
                Float val = floats.readSafely(i);
                if (val != null) obj.addProperty("float_" + i, val);
            }
            StructureModifier<String> strings = packet.getStrings();
            for (int i = 0; i < strings.size(); i++) {
                String val = strings.readSafely(i);
                if (val != null) obj.addProperty("string_" + i, val);
            }
            StructureModifier<Boolean> booleans = packet.getBooleans();
            for (int i = 0; i < booleans.size(); i++) {
                Boolean val = booleans.readSafely(i);
                if (val != null) obj.addProperty("bool_" + i, val);
            }
        } catch (Exception ignored) {
        }
        return obj;
    }

    private void applyFields(PacketContainer packet, JsonObject fields) {
        if (fields == null) return;
        for (String key : fields.keySet()) {
            try {
                if (key.startsWith("int_")) {
                    int idx = Integer.parseInt(key.substring(4));
                    packet.getIntegers().writeSafely(idx, fields.get(key).getAsInt());
                } else if (key.startsWith("double_")) {
                    int idx = Integer.parseInt(key.substring(7));
                    packet.getDoubles().writeSafely(idx, fields.get(key).getAsDouble());
                } else if (key.startsWith("float_")) {
                    int idx = Integer.parseInt(key.substring(6));
                    packet.getFloat().writeSafely(idx, fields.get(key).getAsFloat());
                } else if (key.startsWith("string_")) {
                    int idx = Integer.parseInt(key.substring(7));
                    packet.getStrings().writeSafely(idx, fields.get(key).getAsString());
                } else if (key.startsWith("bool_")) {
                    int idx = Integer.parseInt(key.substring(5));
                    packet.getBooleans().writeSafely(idx, fields.get(key).getAsBoolean());
                }
            } catch (Exception ignored) {
            }
        }
    }
}
