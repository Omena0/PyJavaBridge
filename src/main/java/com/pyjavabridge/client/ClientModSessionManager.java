package com.pyjavabridge.client;

import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

public class ClientModSessionManager {
    private final Map<UUID, SessionState> sessions = new ConcurrentHashMap<>();

    public SessionState getOrCreate(UUID uuid) {
        return sessions.computeIfAbsent(uuid, ignored -> new SessionState());
    }

    public SessionState get(UUID uuid) {
        return sessions.get(uuid);
    }

    public void remove(UUID uuid) {
        SessionState removed = sessions.remove(uuid);
        if (removed != null) {
            removed.completeAllPending(Map.of(
                    "status", "fail",
                    "code", "CLIENT_DISCONNECTED",
                    "message", "Client disconnected"
            ));
        }
    }

    public static final class SessionState {
        private final AtomicInteger requestCounter = new AtomicInteger(1);
        private final Map<Integer, CompletableFuture<Map<String, Object>>> pending = new ConcurrentHashMap<>();
        private final Set<String> grantedCapabilities = ConcurrentHashMap.newKeySet();
        // Store bodies for outstanding requests keyed by request id so server-side
        // synthetic replies (e.g. from chat/click handlers) can reconstruct
        // the original request context.
        private final Map<Integer, Map<String, Object>> requestBodies = new ConcurrentHashMap<>();

        private volatile boolean connected;
        private volatile int protocolVersion;
        // Hold state used when the server needs to pause a player's join
        // until a client permission decision is received.
        private volatile boolean holdActive = false;
        private volatile org.bukkit.GameMode previousGameMode = null;
        private volatile boolean previousInvulnerable = false;
        private volatile boolean previousAllowFlight = false;

        public int nextRequestId() {
            return requestCounter.getAndIncrement();
        }

        public Map<Integer, CompletableFuture<Map<String, Object>>> pending() {
            return pending;
        }

        public void storeRequestBody(int requestId, Map<String, Object> body) {
            if (body == null) return;
            requestBodies.put(requestId, body);
        }

        public Map<String, Object> takeRequestBody(int requestId) {
            return requestBodies.remove(requestId);
        }

        public Set<String> grantedCapabilities() {
            return grantedCapabilities;
        }

        public boolean connected() {
            return connected;
        }

        public void setConnected(boolean connected) {
            this.connected = connected;
        }

        public int protocolVersion() {
            return protocolVersion;
        }

        public void setProtocolVersion(int protocolVersion) {
            this.protocolVersion = protocolVersion;
        }

        public synchronized void setHoldSnapshot(org.bukkit.GameMode gm, boolean invulnerable, boolean allowFlight) {
            this.holdActive = true;
            this.previousGameMode = gm;
            this.previousInvulnerable = invulnerable;
            this.previousAllowFlight = allowFlight;
        }

        public synchronized boolean hasHold() {
            return this.holdActive;
        }

        public synchronized org.bukkit.GameMode previousGameMode() {
            return this.previousGameMode;
        }

        public synchronized boolean previousInvulnerable() {
            return this.previousInvulnerable;
        }

        public synchronized boolean previousAllowFlight() {
            return this.previousAllowFlight;
        }

        public synchronized void clearHold() {
            this.holdActive = false;
            this.previousGameMode = null;
            this.previousInvulnerable = false;
            this.previousAllowFlight = false;
        }

        public void completeAllPending(Map<String, Object> payload) {
            for (var entry : pending.entrySet()) {
                CompletableFuture<Map<String, Object>> future = entry.getValue();
                future.complete(payload);
            }
            pending.clear();
            requestBodies.clear();
        }
    }
}
