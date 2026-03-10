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
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

public class PlayerUuidResolver {
    private static final int MAX_CACHE_SIZE = 1000;

    // #11: Reuse a single HttpClient instance instead of creating one per lookup
    private static final HttpClient HTTP_CLIENT = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3))
            .build();

    // #12: Proper LRU eviction instead of clear()-on-overflow
    private final Map<String, UUID> playerUuidCache = Collections.synchronizedMap(
            new LinkedHashMap<String, UUID>(64, 0.75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<String, UUID> eldest) {
                    return size() > MAX_CACHE_SIZE;
                }
            });

    // #13: Cached usercache.json parse result with timestamp
    private volatile long userCacheLastModified = -1;
    private volatile Map<String, UUID> userCacheParsed = Map.of();

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
            cacheUuid(key, cachedFile);
            return cachedFile;
        }
        try {
            org.bukkit.OfflinePlayer offline = Bukkit.getOfflinePlayer(name);
            if (offline.isOnline() || offline.hasPlayedBefore()) {
                UUID uuid = offline.getUniqueId();
                if (uuid != null) {
                    cacheUuid(key, uuid);
                    return uuid;
                }
            }
        } catch (Exception ignored) {
        }

        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("https://api.mojang.com/users/profiles/minecraft/" + name))
                    .timeout(Duration.ofSeconds(3))
                    .GET()
                    .build();
            HttpResponse<String> response = HTTP_CLIENT.send(request, HttpResponse.BodyHandlers.ofString());
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
            cacheUuid(key, uuid);
            return uuid;
        } catch (Exception ignored) {
        }
        if (!Bukkit.getOnlineMode()) {
            try {
                UUID offline = UUID.nameUUIDFromBytes(("OfflinePlayer:" + name).getBytes(StandardCharsets.UTF_8));
                if (offline != null) {
                    cacheUuid(key, offline);
                    return offline;
                }
            } catch (Exception ignored) {
            }
        }
        return null;
    }

    private void cacheUuid(String key, UUID uuid) {
        playerUuidCache.put(key, uuid);
    }

    private UUID resolvePlayerUuidFromUserCache(String name) {
        try {
            Path cachePath = Bukkit.getServer().getWorldContainer().toPath().resolve("usercache.json");
            if (!Files.exists(cachePath)) {
                return null;
            }
            // #13: Only re-parse if the file was modified since last read
            long lastMod = Files.getLastModifiedTime(cachePath).toMillis();
            if (lastMod != userCacheLastModified) {
                Map<String, UUID> parsed = new LinkedHashMap<>();
                String content = Files.readString(cachePath, StandardCharsets.UTF_8);
                JsonElement element = JsonParser.parseString(content);
                if (element.isJsonArray()) {
                    for (JsonElement entry : element.getAsJsonArray()) {
                        if (!entry.isJsonObject()) continue;
                        JsonObject obj = entry.getAsJsonObject();
                        if (!obj.has("name") || !obj.has("uuid")) continue;
                        String entryName = obj.get("name").getAsString();
                        String raw = obj.get("uuid").getAsString();
                        if (entryName == null || raw == null) continue;
                        UUID uuid;
                        if (raw.length() == 32) {
                            String formatted = raw.substring(0, 8) + "-" + raw.substring(8, 12) + "-"
                                    + raw.substring(12, 16) + "-" + raw.substring(16, 20) + "-" + raw.substring(20);
                            uuid = UUID.fromString(formatted);
                        } else {
                            uuid = UUID.fromString(raw);
                        }
                        parsed.put(entryName.toLowerCase(), uuid);
                    }
                }
                userCacheParsed = parsed;
                userCacheLastModified = lastMod;
            }
            return userCacheParsed.get(name.toLowerCase());
        } catch (Exception ignored) {
        }
        return null;
    }
}
