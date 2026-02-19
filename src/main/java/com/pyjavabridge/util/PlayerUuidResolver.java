package com.pyjavabridge.util;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.bukkit.Bukkit;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

public class PlayerUuidResolver {
    private final Map<String, UUID> playerUuidCache = new ConcurrentHashMap<>();

    public UUID resolvePlayerUuidByName(String name) {
        if (name == null || name.isBlank()) {
            return null;
        }
        String key = name.toLowerCase();
        UUID cached = playerUuidCache.get(key);
        if (cached != null) {
            return cached;
        }
        UUID cachedFile = resolvePlayerUuidFromUserCache(name);
        if (cachedFile != null) {
            playerUuidCache.put(key, cachedFile);
            return cachedFile;
        }
        try {
            org.bukkit.OfflinePlayer offline = Bukkit.getOfflinePlayer(name);
            if (offline.isOnline() || offline.hasPlayedBefore()) {
                UUID uuid = offline.getUniqueId();
                if (uuid != null) {
                    playerUuidCache.put(key, uuid);
                    return uuid;
                }
            }
        } catch (Exception ignored) {
        }

        try {
            HttpClient client = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(3))
                    .build();
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("https://api.mojang.com/users/profiles/minecraft/" + name))
                    .timeout(Duration.ofSeconds(3))
                    .GET()
                    .build();
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                return null;
            }
            JsonObject obj = JsonParser.parseString(response.body()).getAsJsonObject();
            if (!obj.has("id")) {
                return null;
            }
            String raw = obj.get("id").getAsString();
            if (raw == null || raw.length() != 32) {
                return null;
            }
            String formatted = raw.substring(0, 8) + "-" + raw.substring(8, 12) + "-" + raw.substring(12, 16)
                    + "-" + raw.substring(16, 20) + "-" + raw.substring(20);
            UUID uuid = UUID.fromString(formatted);
            playerUuidCache.put(key, uuid);
            return uuid;
        } catch (Exception ignored) {
        }
        if (!Bukkit.getOnlineMode()) {
            try {
                UUID offline = UUID.nameUUIDFromBytes(("OfflinePlayer:" + name).getBytes(StandardCharsets.UTF_8));
                if (offline != null) {
                    playerUuidCache.put(key, offline);
                    return offline;
                }
            } catch (Exception ignored) {
            }
        }
        return null;
    }

    private UUID resolvePlayerUuidFromUserCache(String name) {
        try {
            Path cachePath = Bukkit.getServer().getWorldContainer().toPath().resolve("usercache.json");
            if (!Files.exists(cachePath)) {
                return null;
            }
            String content = Files.readString(cachePath, StandardCharsets.UTF_8);
            JsonElement element = JsonParser.parseString(content);
            if (!element.isJsonArray()) {
                return null;
            }
            String target = name.toLowerCase();
            for (JsonElement entry : element.getAsJsonArray()) {
                if (!entry.isJsonObject()) {
                    continue;
                }
                JsonObject obj = entry.getAsJsonObject();
                if (!obj.has("name") || !obj.has("uuid")) {
                    continue;
                }
                String entryName = obj.get("name").getAsString();
                if (entryName == null || !entryName.toLowerCase().equals(target)) {
                    continue;
                }
                String raw = obj.get("uuid").getAsString();
                if (raw == null) {
                    return null;
                }
                if (raw.length() == 32) {
                    String formatted = raw.substring(0, 8) + "-" + raw.substring(8, 12) + "-"
                            + raw.substring(12, 16) + "-" + raw.substring(16, 20) + "-" + raw.substring(20);
                    return UUID.fromString(formatted);
                }
                return UUID.fromString(raw);
            }
        } catch (Exception ignored) {
        }
        return null;
    }
}
