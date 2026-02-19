package com.pyjavabridge.util;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;

import java.util.Collections;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

public class DebugManager {
    private final Set<UUID> debugPlayers = Collections.synchronizedSet(new HashSet<>());

    public void addDebugPlayer(UUID playerId) {
        debugPlayers.add(playerId);
    }

    public void removeDebugPlayer(UUID playerId) {
        debugPlayers.remove(playerId);
    }

    public boolean isDebugPlayer(UUID playerId) {
        return debugPlayers.contains(playerId);
    }

    public void broadcastErrorToDebugPlayers(String message) {
        for (UUID uuid : debugPlayers) {
            Player player = Bukkit.getPlayer(uuid);
            if (player != null) {
                player.sendMessage("\u00a7c[PyJavaBridge] " + message);
            }
        }
    }

    public Set<UUID> getDebugPlayerUuids() {
        return debugPlayers;
    }

    public boolean isDebugEnabled() {
        return !debugPlayers.isEmpty();
    }
}
