package com.pyjavabridge.client;

import com.pyjavabridge.PyJavaBridgePlugin;

import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.entity.Player;
import org.bukkit.plugin.messaging.PluginMessageListener;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;

public class ClientModChannelBridge implements PluginMessageListener {
    private final PyJavaBridgePlugin plugin;
    private final ClientModSessionManager sessions = new ClientModSessionManager();
    private final Map<String, Object> requestDataRegistry = new ConcurrentHashMap<>();

    public ClientModChannelBridge(PyJavaBridgePlugin plugin) {
        this.plugin = plugin;
    }

    public void registerChannels() {
        var messenger = plugin.getServer().getMessenger();
        messenger.registerIncomingPluginChannel(plugin, ClientModProtocol.CHANNEL, this);
        messenger.registerOutgoingPluginChannel(plugin, ClientModProtocol.CHANNEL);
        // No fallback login negotiation — all negotiation occurs over the
        // client_mod plugin channel once the client handshake is complete.
    }

    public void shutdown() {
        var messenger = plugin.getServer().getMessenger();
        messenger.unregisterIncomingPluginChannel(plugin, ClientModProtocol.CHANNEL);
        messenger.unregisterOutgoingPluginChannel(plugin, ClientModProtocol.CHANNEL);

        for (Player player : Bukkit.getOnlinePlayers()) {
            sessions.remove(player.getUniqueId());
        }
    }

    public boolean isClientAvailable(Player player) {
        if (player == null) {
            return false;
        }

        ClientModSessionManager.SessionState session = sessions.get(player.getUniqueId());
        return session != null && session.connected();
    }

    public CompletableFuture<Map<String, Object>> sendCommand(Player player, String capability, Map<String, Object> args,
            String handle, long timeoutMs) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("capability", capability);
        body.put("args", args == null ? Map.of() : args);
        if (handle != null && !handle.isBlank()) {
            body.put("handle", handle);
        }
        return sendRequest(player, ClientModProtocol.COMMAND_REQUEST, body, timeoutMs);
    }

    public CompletableFuture<Map<String, Object>> sendData(Player player, String channel, Map<String, Object> payload,
            long timeoutMs) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("channel", channel);
        body.put("payload", payload == null ? Map.of() : payload);
        return sendRequest(player, ClientModProtocol.CUSTOM_DATA, body, timeoutMs);
    }

    public CompletableFuture<Map<String, Object>> registerScript(Player player, String name, String source,
            boolean autoStart, Map<String, Object> metadata, long timeoutMs) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("name", name);
        body.put("source", source);
        body.put("auto_start", autoStart);
        body.put("metadata", metadata == null ? Map.of() : metadata);
        return sendRequest(player, ClientModProtocol.SCRIPT_REGISTER, body, timeoutMs);
    }

    public CompletableFuture<Map<String, Object>> setPermissions(Player player, List<String> capabilities, String reason,
            boolean rememberPrompt, long timeoutMs) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("capabilities", capabilities == null ? List.of() : capabilities);
        body.put("reason", reason == null ? "" : reason);
        body.put("remember_prompt", rememberPrompt);

        CompletableFuture<Map<String, Object>> future = sendRequest(player, ClientModProtocol.PERMISSION_REQUEST, body, timeoutMs);

        return future;
    }

    public List<String> getPermissions(Player player) {
        if (player == null) {
            return List.of();
        }

        ClientModSessionManager.SessionState session = sessions.get(player.getUniqueId());
        if (session == null) {
            return List.of();
        }

        return new ArrayList<>(session.grantedCapabilities());
    }

    public void registerRequestData(String key, Object value) {
        if (key == null || key.isBlank()) {
            return;
        }

        requestDataRegistry.put(key, value);
    }

    public void unregisterRequestData(String key) {
        if (key == null || key.isBlank()) {
            return;
        }

        requestDataRegistry.remove(key);
    }

    public void onPlayerQuit(org.bukkit.entity.Player player) {
        if (player == null) return;
        java.util.UUID uuid = player.getUniqueId();
        sessions.remove(uuid);
        plugin.getLogger().info("Client mod session cleared for " + player.getName());
    }

    @Override
    public void onPluginMessageReceived(String channel, Player player, byte[] message) {
        if (!ClientModProtocol.CHANNEL.equals(channel) || player == null) {
            return;
        }

        try {
            byte[] payload = message;

            if (payload != null && payload.length > 0) {
                int varIntValue = 0;
                int varIntLen = 0;
                int shift = 0;
                int maxVarIntBytes = Math.min(5, payload.length);
                for (int i = 0; i < maxVarIntBytes; i++) {
                    int b = payload[i] & 0xFF;
                    varIntValue |= (b & 0x7F) << shift;
                    varIntLen++;
                    if ((b & 0x80) == 0) {
                        break;
                    }
                    shift += 7;
                }

                if (varIntLen > 0) {
                    int remaining = payload.length - varIntLen;
                    if (varIntValue == remaining && varIntValue >= 0 && varIntValue <= ClientModProtocol.MAX_BODY_BYTES) {
                        byte[] stripped = new byte[remaining];
                        System.arraycopy(payload, varIntLen, stripped, 0, remaining);
                        payload = stripped;
                    }
                }
            }

            ClientModFrameCodec.Frame frame = ClientModFrameCodec.decodeFrame(payload);
            handleIncomingFrame(player, frame);
        } catch (Exception ex) {
            String hex;
            try {
                if (message != null && message.length > 0) {
                    int max = Math.min(32, message.length);
                    StringBuilder sb = new StringBuilder();
                    for (int i = 0; i < max; i++) {
                        sb.append(String.format("%02X", message[i] & 0xFF));
                        if (i < max - 1) sb.append(' ');
                    }
                    if (message.length > max) sb.append("...");
                    hex = sb.toString();
                } else {
                    hex = "(empty)";
                }
            } catch (Throwable t) {
                hex = "(hex dump failed: " + t.getMessage() + ")";
            }

            plugin.getLogger().warning("Client mod frame decode failed: " + ex.getMessage() + " payload_hex=" + hex);
        }
    }

    private void handleIncomingFrame(Player player, ClientModFrameCodec.Frame frame) {
        UUID uuid = player.getUniqueId();
        ClientModSessionManager.SessionState session = sessions.getOrCreate(uuid);

        switch (frame.packetType()) {
            case ClientModProtocol.HELLO_ACK -> {
                session.setConnected(true);
                session.setProtocolVersion(frame.protocolVersion());
            }
            case ClientModProtocol.PERMISSION_DECISION -> {
                plugin.getLogger().info("Received PERMISSION_DECISION from " + player.getName() + " req=" + frame.requestId());
                updateGrantedCapabilities(session, frame.body());
                completePending(session, frame.requestId(), frame.body());
                plugin.emitClientModPermissionEvent(player, frame.body());
            }
            case ClientModProtocol.COMMAND_RESPONSE, ClientModProtocol.SCRIPT_RESULT ->
                    completePending(session, frame.requestId(), frame.body());
                case ClientModProtocol.CUSTOM_DATA -> {
                    if (frame.requestId() > 0) {
                        // Treat as a response to a previous request only.
                        completePending(session, frame.requestId(), frame.body());
                    } else {
                        // Unsolicited push from client: deliver to scripts.
                        handleCustomData(player, frame.body());
                    }
                }
            case ClientModProtocol.ERROR -> completePending(session, frame.requestId(), frame.body());
            default -> {
                // ignore unknown packet types for forward compatibility
            }
        }
    }

    private void handleCustomData(Player player, Map<String, Object> body) {
        Object requestKeyObj = body.get("request_key");
        if (requestKeyObj instanceof String requestKey && !requestKey.isBlank()) {
            Map<String, Object> response = new LinkedHashMap<>();
            response.put("request_key", requestKey);

            if (requestDataRegistry.containsKey(requestKey)) {
                response.put("status", "ok");
                response.put("value", requestDataRegistry.get(requestKey));
            } else {
                response.put("status", "fail");
                response.put("message", "No request data registered for key: " + requestKey);
                response.put("code", "DATA_KEY_NOT_FOUND");
            }

            try {
                sendPacket(player, ClientModProtocol.CUSTOM_DATA, 0, response);
            } catch (IOException ex) {
                plugin.getLogger().warning("Failed to send request() data response: " + ex.getMessage());
            }
            return;
        }

        plugin.emitClientModDataEvent(player, body);
    }

    private CompletableFuture<Map<String, Object>> sendRequest(Player player, int packetType, Map<String, Object> body,
            long timeoutMs) {
        if (player == null) {
            return CompletableFuture.completedFuture(Map.of(
                    "status", "fail",
                    "code", "INVALID_PLAYER",
                    "message", "Player is required"
            ));
        }

        ClientModSessionManager.SessionState session = sessions.getOrCreate(player.getUniqueId());
        if (!session.connected()) {
            return CompletableFuture.completedFuture(Map.of(
                    "status", "fail",
                    "code", "CLIENT_MOD_UNAVAILABLE",
                    "message", "Client mod is not connected"
            ));
        }

        int requestId = session.nextRequestId();
        CompletableFuture<Map<String, Object>> future = new CompletableFuture<>();
        session.pending().put(requestId, future);
        // Store the request body so server-side chat/command handlers can
        // synthesize a response later if needed.
        session.storeRequestBody(requestId, body);

        try {
            sendPacket(player, packetType, requestId, body);
        } catch (IOException ex) {
            session.pending().remove(requestId);
            future.complete(Map.of(
                    "status", "fail",
                    "code", "CLIENT_ENCODE_ERROR",
                    "message", ex.getMessage() == null ? "Failed to encode frame" : ex.getMessage()
            ));
            return future;
        }

        long safeTimeoutMs = Math.max(50L, timeoutMs);
        long timeoutTicks = Math.max(1L, (long) Math.ceil(safeTimeoutMs / 50.0));

        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            CompletableFuture<Map<String, Object>> pending = session.pending().remove(requestId);
            if (pending != null && !pending.isDone()) {
                pending.complete(Map.of(
                        "status", "fail",
                        "code", "CLIENT_TIMEOUT",
                        "message", "No response from client within timeout"
                ));
            }
        }, timeoutTicks);

        return future;
    }

    private void sendPacket(Player player, int packetType, int requestId, Map<String, Object> body) throws IOException {
        byte[] payload = ClientModFrameCodec.encodeFrame(packetType, 0, requestId, body);
        // Log outgoing request for debugging
        try {
            int max = Math.min(16, payload.length);
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < max; i++) {
                sb.append(String.format("%02X", payload[i] & 0xFF));
                if (i < max - 1) sb.append(' ');
            }
            if (payload.length > max) sb.append("...");
            plugin.getLogger().info("Sending client_mod packet to " + player.getName() + " type=" + packetType + " req=" + requestId + " len=" + payload.length + " payload_hex=" + sb.toString());
        } catch (Throwable t) {
            plugin.getLogger().info("Sending client_mod packet to " + player.getName() + " type=" + packetType + " req=" + requestId + " len=" + payload.length);
        }

        byte[] wrapped = encodeWithVarIntPrefix(payload);
        player.sendPluginMessage(plugin, ClientModProtocol.CHANNEL, wrapped);
    }

    private static byte[] encodeWithVarIntPrefix(byte[] payload) {
        int len = payload == null ? 0 : payload.length;
        int value = len;

        // compute varint length
        int varIntLen = 0;
        do {
            value >>>= 7;
            varIntLen++;
        } while (value != 0);

        byte[] out = new byte[varIntLen + len];

        // write varint
        value = len;
        int idx = 0;
        do {
            int temp = value & 0x7F;
            value >>>= 7;
            if (value != 0) temp |= 0x80;
            out[idx++] = (byte) temp;
        } while (value != 0);

        if (len > 0) System.arraycopy(payload, 0, out, idx, len);
        return out;
    }

    private void completePending(ClientModSessionManager.SessionState session, int requestId, Map<String, Object> body) {
        CompletableFuture<Map<String, Object>> future = session.pending().remove(requestId);
        if (future != null) {
            future.complete(body == null ? Map.of("status", "ok") : body);
        } else {
            int pendingSize = session.pending().size();
            plugin.getLogger().warning("No pending client_mod request found for req=" + requestId + " (pendingSize=" + pendingSize + ")");
        }
    }

    /**
     * Handle a server-side synthetic permission decision (e.g. from chat/click).
     * This reconstructs the PERMISSION_DECISION payload and completes the
     * pending request as if the client had sent the plugin-channel frame.
     */
    public void handlePermissionDecisionFromChat(Player player, int requestId, boolean allowed, boolean remember) {
        if (player == null) return;
        ClientModSessionManager.SessionState session = sessions.get(player.getUniqueId());
        if (session == null) return;

        Map<String, Object> original = session.takeRequestBody(requestId);
        java.util.List<String> granted = new ArrayList<>();
        if (allowed && original != null && original.get("capabilities") instanceof java.util.List<?> caps) {
            for (Object v : caps) {
                if (v != null) granted.add(String.valueOf(v));
            }
        }

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("status", "ok");
        payload.put("allowed", allowed);
        payload.put("remember", remember);
        payload.put("granted_capabilities", allowed ? granted : List.of());

        // Update session and complete pending future just like an incoming frame
        updateGrantedCapabilities(session, payload);
        completePending(session, requestId, payload);
        plugin.emitClientModPermissionEvent(player, payload);
    }

    private void updateGrantedCapabilities(ClientModSessionManager.SessionState session, Map<String, Object> payload) {
        if (payload == null) {
            return;
        }

        Object grantedObj = payload.get("granted_capabilities");
        if (!(grantedObj instanceof List<?> list)) {
            return;
        }

        session.grantedCapabilities().clear();
        for (Object value : list) {
            if (value != null) {
                session.grantedCapabilities().add(String.valueOf(value));
            }
        }
    }
}
