package com.pyjavabridge.facade;

import com.pyjavabridge.PyJavaBridgePlugin;
import com.google.gson.JsonObject;
import org.bukkit.Bukkit;
import org.bukkit.World;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.Map;

public class DatapackFacade {
    private final PyJavaBridgePlugin plugin;
    private final Map<String, JsonObject> models = new ConcurrentHashMap<>();
    private final Map<String, JsonObject> advancements = new ConcurrentHashMap<>();
    private final Map<String, JsonObject> predicates = new ConcurrentHashMap<>();
    private final Map<String, JsonObject> registries = new ConcurrentHashMap<>();

    public DatapackFacade(PyJavaBridgePlugin plugin) {
        this.plugin = plugin;
    }

    public void registerModel(String namespace, String path, JsonObject json) {
        String key = namespace + ":" + path;
        models.put(key, json);
        plugin.getLogger().info("Registered model: " + key);
    }

    public void registerAdvancement(String namespace, String path, JsonObject json) {
        String key = namespace + ":" + path;
        advancements.put(key, json);
        plugin.getLogger().info("Registered advancement: " + key);
    }

    public void registerPredicate(String namespace, String path, JsonObject json) {
        String key = namespace + ":" + path;
        predicates.put(key, json);
        plugin.getLogger().info("Registered predicate: " + key);
    }

    public void registerRegistryEntry(String namespace, String registry, String path, JsonObject json) {
        String key = namespace + ":" + registry + ":" + path;
        registries.put(key, json);
        plugin.getLogger().info("Registered registry entry: " + key);
    }

    public void registerDamageType(String namespace, String id, JsonObject json) {
        registerRegistryEntry(namespace, "damage_types", id, json);
    }

    public void registerChatType(String namespace, String id, JsonObject json) {
        registerRegistryEntry(namespace, "chat_types", id, json);
    }

    public void applyAll() {
        Bukkit.getScheduler().runTask(plugin, () -> {
            plugin.getLogger().info("Applying datapack entries in-memory: models=" + models.size()
                    + " advancements=" + advancements.size()
                    + " predicates=" + predicates.size()
                    + " registries=" + registries.size());

            try {
                boolean wroteAny = writeRuntimeDatapack();
                if (wroteAny) {
                    Bukkit.reloadData();
                    plugin.getLogger().info("Runtime datapack reloaded successfully.");
                }
            } catch (Exception ex) {
                plugin.getLogger().warning("Failed to write/apply runtime datapack files: " + ex.getMessage());
            }

            // Best-effort in-memory injection using reflection into server internals.
            // This attempts to find the server's advancement manager and load
            // the JsonObjects directly without writing datapack files.
            try {
                Object craftServer = Bukkit.getServer();
                Class<?> craftServerClass = craftServer.getClass();

                // Obtain NMS server (CraftServer#getServer)
                Object nmsServer = null;
                try {
                    java.lang.reflect.Method getServer = craftServerClass.getMethod("getServer");
                    nmsServer = getServer.invoke(craftServer);
                } catch (NoSuchMethodException ignored) {
                    // older/newer mappings: try field access
                    try {
                        java.lang.reflect.Field f = craftServerClass.getDeclaredField("server");
                        f.setAccessible(true);
                        nmsServer = f.get(craftServer);
                    } catch (Exception ex) {
                        plugin.getLogger().warning("Could not obtain NMS server handle: " + ex.getMessage());
                    }
                }

                if (nmsServer == null) {
                    plugin.getLogger().severe("In-memory apply failed: NMS server handle unavailable");
                    return;
                }

                Class<?> nmsServerClass = nmsServer.getClass();

                // Try to find an advancement manager field or method on the server
                Object advancementManager = null;
                for (java.lang.reflect.Field f : nmsServerClass.getDeclaredFields()) {
                    if (f.getType().getSimpleName().toLowerCase().contains("advancement")) {
                        f.setAccessible(true);
                        try { advancementManager = f.get(nmsServer); } catch (Exception ignored) {}
                        if (advancementManager != null) break;
                    }
                }
                if (advancementManager == null) {
                    for (java.lang.reflect.Method m : nmsServerClass.getDeclaredMethods()) {
                        if (m.getReturnType().getSimpleName().toLowerCase().contains("advancement") && m.getParameterCount() == 0) {
                            m.setAccessible(true);
                            try { advancementManager = m.invoke(nmsServer); } catch (Exception ignored) {}
                            if (advancementManager != null) break;
                        }
                    }
                }

                if (advancementManager != null) {
                    Class<?> advClass = advancementManager.getClass();

                    // Find a method that accepts a resource key and a JsonObject / JsonElement
                    java.lang.reflect.Method loaderMethod = null;
                    for (java.lang.reflect.Method m : advClass.getDeclaredMethods()) {
                        String name = m.getName().toLowerCase();
                        if ((name.contains("load") || name.contains("add") || name.contains("register") || name.contains("parse"))
                                && m.getParameterCount() >= 2) {
                            Class<?>[] params = m.getParameterTypes();
                            // look for (ResourceLocation/ResourceKey/Identifier, JsonObject/json)
                            if (params.length >= 2 && params[1].getName().contains("Json")) {
                                loaderMethod = m;
                                break;
                            }
                        }
                    }

                    // Prepare ResourceLocation class if present
                    Class<?> resourceLocationClass = null;
                    try {
                        resourceLocationClass = Class.forName("net.minecraft.resources.ResourceLocation");
                    } catch (ClassNotFoundException ignored) {}

                    for (Map.Entry<String, JsonObject> e : advancements.entrySet()) {
                        try {
                            String[] parts = e.getKey().split(":", 2);
                            if (parts.length != 2) continue;
                            String ns = parts[0];
                            String path = parts[1];

                            Object keyObj = null;
                            if (resourceLocationClass != null) {
                                try {
                                    java.lang.reflect.Constructor<?> rc = resourceLocationClass.getConstructor(String.class, String.class);
                                    keyObj = rc.newInstance(ns, path);
                                } catch (NoSuchMethodException ex) {
                                    // try single-string constructor
                                    try {
                                        java.lang.reflect.Constructor<?> rc2 = resourceLocationClass.getConstructor(String.class);
                                        keyObj = rc2.newInstance((Object)(ns + ":" + path));
                                    } catch (Exception ex2) { keyObj = null; }
                                }
                            }

                            if (loaderMethod != null) {
                                // Attempt to call loaderMethod(keyObj, json)
                                loaderMethod.setAccessible(true);
                                if (keyObj != null) {
                                    try {
                                        loaderMethod.invoke(advancementManager, keyObj, e.getValue());
                                        plugin.getLogger().info("Injected advancement in-memory: " + e.getKey());
                                        continue;
                                    } catch (Exception ex) {
                                        // fall through to other attempts
                                    }
                                }
                            }

                            // As a fallback, try calling a method that accepts (String, JsonObject)
                            java.lang.reflect.Method stringLoader = null;
                            for (java.lang.reflect.Method m : advClass.getDeclaredMethods()) {
                                if (m.getParameterCount() >= 2 && m.getParameterTypes()[0] == String.class && m.getParameterTypes()[1].getName().contains("Json")) {
                                    stringLoader = m;
                                    break;
                                }
                            }
                            if (stringLoader != null) {
                                stringLoader.setAccessible(true);
                                stringLoader.invoke(advancementManager, ns + ":" + path, e.getValue());
                                plugin.getLogger().info("Injected advancement (string fallback): " + e.getKey());
                                continue;
                            }

                            plugin.getLogger().warning("Could not inject advancement in-memory, no compatible loader found for: " + e.getKey());
                        } catch (Exception ex) {
                            plugin.getLogger().warning("Failed to inject advancement " + e.getKey() + ": " + ex.getMessage());
                        }
                    }
                } else {
                    plugin.getLogger().warning("Advancement manager not found on server; in-memory injection skipped.");
                }

                // Predicates: try similar approach for predicate/loot manager
                Object predicateManager = null;
                for (java.lang.reflect.Field f : nmsServerClass.getDeclaredFields()) {
                    if (f.getType().getSimpleName().toLowerCase().contains("predicate") || f.getName().toLowerCase().contains("loot") || f.getName().toLowerCase().contains("predicate")) {
                        f.setAccessible(true);
                        try { predicateManager = f.get(nmsServer); } catch (Exception ignored) {}
                        if (predicateManager != null) break;
                    }
                }
                if (predicateManager == null) {
                    for (java.lang.reflect.Method m : nmsServerClass.getDeclaredMethods()) {
                        if (m.getReturnType().getSimpleName().toLowerCase().contains("predicate") && m.getParameterCount() == 0) {
                            m.setAccessible(true);
                            try { predicateManager = m.invoke(nmsServer); } catch (Exception ignored) {}
                            if (predicateManager != null) break;
                        }
                    }
                }

                if (predicateManager != null) {
                    Class<?> pmClass = predicateManager.getClass();
                    java.lang.reflect.Method loader = null;
                    for (java.lang.reflect.Method m : pmClass.getDeclaredMethods()) {
                        String name = m.getName().toLowerCase();
                        if ((name.contains("load") || name.contains("parse") || name.contains("register")) && m.getParameterCount() >= 2 && m.getParameterTypes()[1].getName().contains("Json")) {
                            loader = m;
                            break;
                        }
                    }

                    for (Map.Entry<String, JsonObject> e : predicates.entrySet()) {
                        try {
                            String[] parts = e.getKey().split(":", 2);
                            if (parts.length != 2) continue;
                            String ns = parts[0];
                            String path = parts[1];

                            if (loader != null) {
                                loader.setAccessible(true);
                                // attempt loader with (ResourceLocation/String, JsonObject)
                                try {
                                    loader.invoke(predicateManager, ns + ":" + path, e.getValue());
                                    plugin.getLogger().info("Injected predicate in-memory: " + e.getKey());
                                    continue;
                                } catch (Exception ex) {
                                    // ignore and try other options
                                }
                            }

                            plugin.getLogger().warning("Could not inject predicate in-memory, no compatible loader found for: " + e.getKey());
                        } catch (Exception ex) {
                            plugin.getLogger().warning("Failed to inject predicate " + e.getKey() + ": " + ex.getMessage());
                        }
                    }
                } else {
                    plugin.getLogger().warning("Predicate/loot manager not found on server; in-memory injection skipped.");
                }

            } catch (Throwable ex) {
                plugin.getLogger().severe("In-memory apply failed: " + ex.getMessage());
            }
        });
    }

    private boolean writeRuntimeDatapack() throws IOException {
        List<World> worlds = Bukkit.getWorlds();
        if (worlds.isEmpty()) {
            return false;
        }

        Path packRoot = worlds.get(0).getWorldFolder().toPath().resolve("datapacks").resolve("pyjavabridge_runtime");
        Files.createDirectories(packRoot);
        writePackMeta(packRoot);

        boolean wroteAny = false;
        wroteAny |= writeNamespaceEntries(packRoot, advancements, "advancements");
        wroteAny |= writeNamespaceEntries(packRoot, predicates, "predicates");
        wroteAny |= writeRegistryEntries(packRoot, registries);
        wroteAny |= writeModelEntries(packRoot, models);
        return wroteAny;
    }

    private void writePackMeta(Path packRoot) throws IOException {
        int packFormat = resolveServerDataPackFormat();
        String mcmeta = "{\"pack\":{\"pack_format\":" + packFormat
                + ",\"description\":\"PyJavaBridge runtime datapack\"}}";
        Files.writeString(packRoot.resolve("pack.mcmeta"), mcmeta, StandardCharsets.UTF_8);
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private int resolveServerDataPackFormat() {
        try {
            Class<?> sharedConstants = Class.forName("net.minecraft.SharedConstants");
            Object currentVersion = sharedConstants.getMethod("getCurrentVersion").invoke(null);
            Class<?> packTypeClass = Class.forName("net.minecraft.server.packs.PackType");
            Object serverData = Enum.valueOf((Class<? extends Enum>) packTypeClass, "SERVER_DATA");
            Object packVersion = currentVersion.getClass().getMethod("getPackVersion", packTypeClass)
                    .invoke(currentVersion, serverData);
            if (packVersion instanceof Number n) {
                return n.intValue();
            }
        } catch (Exception ignored) {
        }
        return 61;
    }

    private boolean writeNamespaceEntries(Path packRoot, Map<String, JsonObject> entries, String folder) throws IOException {
        boolean wroteAny = false;
        for (Map.Entry<String, JsonObject> entry : entries.entrySet()) {
            String[] parts = splitTwoPartKey(entry.getKey());
            if (parts == null) {
                continue;
            }
            Path out = packRoot.resolve("data").resolve(parts[0]).resolve(folder)
                    .resolve(parts[1] + ".json");
            Files.createDirectories(out.getParent());
            Files.writeString(out, entry.getValue().toString(), StandardCharsets.UTF_8);
            wroteAny = true;
        }
        return wroteAny;
    }

    private boolean writeRegistryEntries(Path packRoot, Map<String, JsonObject> entries) throws IOException {
        boolean wroteAny = false;
        for (Map.Entry<String, JsonObject> entry : entries.entrySet()) {
            String[] parts = splitThreePartKey(entry.getKey());
            if (parts == null) {
                continue;
            }
            Path out = packRoot.resolve("data").resolve(parts[0]).resolve(parts[1])
                    .resolve(parts[2] + ".json");
            Files.createDirectories(out.getParent());
            Files.writeString(out, entry.getValue().toString(), StandardCharsets.UTF_8);
            wroteAny = true;
        }
        return wroteAny;
    }

    private boolean writeModelEntries(Path packRoot, Map<String, JsonObject> entries) throws IOException {
        boolean wroteAny = false;
        for (Map.Entry<String, JsonObject> entry : entries.entrySet()) {
            String[] parts = splitTwoPartKey(entry.getKey());
            if (parts == null) {
                continue;
            }
            Path out = packRoot.resolve("assets").resolve(parts[0]).resolve("models")
                    .resolve(parts[1] + ".json");
            Files.createDirectories(out.getParent());
            Files.writeString(out, entry.getValue().toString(), StandardCharsets.UTF_8);
            wroteAny = true;
        }
        return wroteAny;
    }

    private String[] splitTwoPartKey(String key) {
        String[] parts = key.split(":", 2);
        if (parts.length != 2 || parts[0].isBlank() || parts[1].isBlank()) {
            plugin.getLogger().warning("Invalid datapack key: " + key);
            return null;
        }
        return parts;
    }

    private String[] splitThreePartKey(String key) {
        String[] parts = key.split(":", 3);
        if (parts.length != 3 || parts[0].isBlank() || parts[1].isBlank() || parts[2].isBlank()) {
            plugin.getLogger().warning("Invalid registry key: " + key);
            return null;
        }
        return parts;
    }
}
