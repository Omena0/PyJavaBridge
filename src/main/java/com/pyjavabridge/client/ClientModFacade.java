package com.pyjavabridge.client;

import com.pyjavabridge.PyJavaBridgePlugin;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.CompletableFuture;

public class ClientModFacade {
    private final PyJavaBridgePlugin plugin;

    public ClientModFacade(PyJavaBridgePlugin plugin) {
        this.plugin = plugin;
    }

    public boolean isAvailable(Player player) {
        ClientModChannelBridge bridge = plugin.getClientModBridge();
        if (bridge == null) return false;

        // Fast-path: if already connected, return immediately
        if (bridge.isClientAvailable(player)) return true;

        // Avoid blocking the main server thread; only poll when off-thread
        if (Bukkit.isPrimaryThread()) {
            return false;
        }

        // Poll briefly for the client handshake to complete (up to 1s)
        long deadline = System.currentTimeMillis() + 1000L;
        while (System.currentTimeMillis() < deadline) {
            if (bridge.isClientAvailable(player)) return true;
            try {
                Thread.sleep(50L);
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                break;
            }
        }

        return bridge.isClientAvailable(player);
    }

    public CompletableFuture<Object> sendCommand(Player player, String capability) {
        return sendCommand(player, capability, Map.of(), null, 1000);
    }

    public CompletableFuture<Object> sendCommand(Player player, String capability, Map<String, Object> args) {
        return sendCommand(player, capability, args, null, 1000);
    }

    public CompletableFuture<Object> sendCommand(Player player, String capability, Map<String, Object> args, String handle) {
        return sendCommand(player, capability, args, handle, 1000);
    }

    public CompletableFuture<Object> sendCommand(Player player, String capability, Map<String, Object> args, String handle, Number timeoutMs) {
        ClientModChannelBridge bridge = plugin.getClientModBridge();
        if (bridge == null) {
            return CompletableFuture.completedFuture(fail("CLIENT_MOD_DISABLED", "Client mod bridge is unavailable"));
        }

        long timeout = timeoutMs == null ? 10000L : Math.max(500L, timeoutMs.longValue());
        return bridge.sendCommand(player, capability, args, handle, timeout)
                .<Object>thenApply(result -> result == null ? Map.of("status", "ok") : result)
                .exceptionally(ex -> fail("CLIENT_TIMEOUT", ex.getMessage() == null ? "Timed out waiting for client" : ex.getMessage()));
    }

    public CompletableFuture<Object> sendData(Player player, String channel, Map<String, Object> payload) {
        return sendData(player, channel, payload, 1000);
    }

    public CompletableFuture<Object> sendData(Player player, String channel, Map<String, Object> payload, Number timeoutMs) {
        ClientModChannelBridge bridge = plugin.getClientModBridge();
        if (bridge == null) {
            return CompletableFuture.completedFuture(fail("CLIENT_MOD_DISABLED", "Client mod bridge is unavailable"));
        }

        long timeout = timeoutMs == null ? 10000L : Math.max(500L, timeoutMs.longValue());
        return bridge.sendData(player, channel, payload, timeout)
                .<Object>thenApply(result -> result == null ? Map.of("status", "ok") : result)
                .exceptionally(ex -> fail("CLIENT_TIMEOUT", ex.getMessage() == null ? "Timed out waiting for client" : ex.getMessage()));
    }

    public CompletableFuture<Object> registerScript(Player player, String name, String source) {
        return registerScript(player, name, source, true, Map.of(), 2000);
    }

    public CompletableFuture<Object> registerScript(Player player, String name, String source, boolean autoStart, Map<String, Object> metadata,
            Number timeoutMs) {
        ClientModChannelBridge bridge = plugin.getClientModBridge();
        if (bridge == null) {
            return CompletableFuture.completedFuture(fail("CLIENT_MOD_DISABLED", "Client mod bridge is unavailable"));
        }

        long timeout = timeoutMs == null ? 10000L : Math.max(500L, timeoutMs.longValue());
        return bridge.registerScript(player, name, source, autoStart, metadata, timeout)
                .<Object>thenApply(result -> result == null ? Map.of("status", "ok") : result)
                .exceptionally(ex -> fail("CLIENT_TIMEOUT", ex.getMessage() == null ? "Timed out waiting for client" : ex.getMessage()));
    }

    public CompletableFuture<Object> setPermissions(Player player, List<Object> capabilities, String reason, boolean rememberPrompt,
            Number timeoutMs) {
        ClientModChannelBridge bridge = plugin.getClientModBridge();
        if (bridge == null) {
            return CompletableFuture.completedFuture(fail("CLIENT_MOD_DISABLED", "Client mod bridge is unavailable"));
        }
        // Permission negotiation has been replaced by a ProtocolLib-based
        // negotiation during the login phase (JOIN_GAME hold). This method
        // is now deprecated; return a failure explaining the migration.
        List<String> capabilityNames = new ArrayList<>();
        if (capabilities != null) {
            for (Object value : capabilities) {
                if (value != null) {
                    capabilityNames.add(String.valueOf(value));
                }
            }
        }

        long timeout = timeoutMs == null ? 60000L : Math.max(500L, timeoutMs.longValue());
        return bridge.setPermissions(player, capabilityNames, reason, rememberPrompt, timeout)
                .<Object>thenApply(result -> result == null ? Map.of("status", "ok") : result)
                .exceptionally(ex -> fail("CLIENT_TIMEOUT", ex.getMessage() == null ? "Timed out waiting for client" : ex.getMessage()));
    }

    public List<String> getPermissions(Player player) {
        ClientModChannelBridge bridge = plugin.getClientModBridge();
        if (bridge == null) {
            return List.of();
        }
        return bridge.getPermissions(player);
    }

    public boolean registerRequestData(String key, Object value) {
        ClientModChannelBridge bridge = plugin.getClientModBridge();
        if (bridge == null || key == null || key.isBlank()) {
            return false;
        }

        bridge.registerRequestData(key, value);
        return true;
    }

    public boolean unregisterRequestData(String key) {
        ClientModChannelBridge bridge = plugin.getClientModBridge();
        if (bridge == null || key == null || key.isBlank()) {
            return false;
        }

        bridge.unregisterRequestData(key);
        return true;
    }

    private Map<String, Object> fail(String code, String message) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("status", "fail");
        payload.put("code", code);
        payload.put("message", message);
        return payload;
    }
}
