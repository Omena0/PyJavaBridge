package com.pyjavabridge.util;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;

import java.util.Collections;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import java.util.logging.Logger;

public class DebugManager {
    private final Set<UUID> debugPlayers = Collections.synchronizedSet(new HashSet<>());
    private volatile boolean consoleDebug = false;
    private volatile Logger logger;

    public void setLogger(Logger logger) {
        this.logger = logger;
    }

    public void addDebugPlayer(UUID playerId) {
        debugPlayers.add(playerId);
    }

    public void removeDebugPlayer(UUID playerId) {
        debugPlayers.remove(playerId);
    }

    public boolean isDebugPlayer(UUID playerId) {
        return debugPlayers.contains(playerId);
    }

    public void setConsoleDebug(boolean enabled) {
        this.consoleDebug = enabled;
    }

    public boolean isConsoleDebug() {
        return consoleDebug;
    }

    public void broadcastErrorToDebugPlayers(String message) {
        for (UUID uuid : debugPlayers) {
            Player player = Bukkit.getPlayer(uuid);
            if (player != null) {
                player.sendMessage("\u00a7c[PyJavaBridge] " + message);
            }
        }
    }

    public void broadcastDebug(String message) {
        if (consoleDebug && logger != null) {
            logger.info(message);
        }
        for (UUID uuid : debugPlayers) {
            Player player = Bukkit.getPlayer(uuid);
            if (player != null) {
                player.sendMessage("\u00a77" + message);
            }
        }
    }

    public Set<UUID> getDebugPlayerUuids() {
        return debugPlayers;
    }

    public boolean isDebugEnabled() {
        return consoleDebug || !debugPlayers.isEmpty();
    }
}
