package com.pyjavabridge.facade;

import com.pyjavabridge.PyJavaBridgePlugin;
import com.google.gson.JsonObject;
import org.bukkit.Bukkit;

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
}
