package com.pyjavabridge;

import com.pyjavabridge.event.EventSubscription;
import com.pyjavabridge.event.PendingEvent;
import com.pyjavabridge.facade.*;
import com.pyjavabridge.util.EntityGoneException;
import com.pyjavabridge.util.EnumValue;
import com.pyjavabridge.util.EntitySpawner;
import com.pyjavabridge.util.ObjectRegistry;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Registry;
import org.bukkit.Sound;
import io.papermc.paper.registry.RegistryAccess;
import io.papermc.paper.registry.RegistryKey;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.Sign;
import org.bukkit.block.sign.Side;
import org.bukkit.block.sign.SignSide;
import org.bukkit.block.Furnace;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.event.Event;
import org.bukkit.event.EventPriority;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.ShapedRecipe;
import org.bukkit.inventory.ShapelessRecipe;
import org.bukkit.inventory.FurnaceRecipe;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.inventory.meta.Damageable;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.GameRule;
import org.bukkit.WorldBorder;
import org.bukkit.TreeType;
import org.bukkit.Particle;
import org.bukkit.Statistic;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.permissions.PermissionAttachment;
import org.bukkit.util.Transformation;
import org.bukkit.Color;
import net.kyori.adventure.text.minimessage.MiniMessage;
import org.joml.Vector3f;
import org.joml.Quaternionf;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import org.msgpack.core.MessagePack;
import org.msgpack.core.MessagePacker;
import org.msgpack.core.MessageUnpacker;
import org.msgpack.core.MessageFormat;
import org.msgpack.core.buffer.ArrayBufferOutput;
import org.bukkit.event.Listener;
import org.bukkit.event.EventHandler;
import org.bukkit.event.player.PlayerQuitEvent;

public class BridgeInstance {
    private final PyJavaBridgePlugin plugin;
    private final String name;
    private final Path scriptPath;
    private final Path scriptsDir;
    private final Path runtimeDir;
    private final Gson gson = new Gson();
    private final ObjectRegistry registry = new ObjectRegistry();
    private final Map<String, EventSubscription> subscriptions = new ConcurrentHashMap<>();
    private final Map<UUID, PermissionAttachment> permissionAttachments = new ConcurrentHashMap<>();

    private static final Object UNHANDLED = new Object();
    private static final JsonObject EMPTY_JSON_OBJ = new JsonObject();

    private final Map<Integer, PendingEvent> pendingEvents = new ConcurrentHashMap<>();
    private final Map<Integer, CompletableFuture<List<String>>> pendingTabCompletes = new ConcurrentHashMap<>();
    private final java.util.concurrent.atomic.AtomicInteger tabCompleteIdCounter = new java.util.concurrent.atomic.AtomicInteger(0);
    private final Object writeLock = new Object();

    // Serialization format negotiation: default JSON, may switch to msgpack on handshake
    private volatile boolean useMsgpack = false;

    private final BridgeSerializer serializer;
    private final EventDispatcher eventDispatcher;
    private final EntitySpawner entitySpawner;

    private final ChatFacade chatFacade = new ChatFacade();
    private final RaycastFacade raycastFacade = new RaycastFacade();
    private final ReflectFacade reflectFacade = new ReflectFacade();
    private final RegionFacade regionFacade = new RegionFacade();
    private final ParticleFacade particleFacade = new ParticleFacade();
    private final PermissionsFacade permissionsFacade;
    private final MetricsFacade metricsFacade;
    private final RefFacade refFacade;
    private final CommandsFacade commandsFacade;

    private DataInputStream reader;
    private DataOutputStream writer;
    private Thread bridgeThread;
    private Process pythonProcess;
    private volatile boolean running = false;
    private volatile CountDownLatch shutdownLatch;

    BridgeInstance(PyJavaBridgePlugin plugin, String name, Path scriptPath, Path scriptsDir, Path runtimeDir) {
        this.plugin = plugin;
        this.name = name;
        this.scriptPath = scriptPath;
        this.scriptsDir = scriptsDir;
        this.runtimeDir = runtimeDir;
        this.serializer = new BridgeSerializer(registry, gson, plugin);
        this.entitySpawner = new EntitySpawner(plugin.getLogger(), name);
        this.eventDispatcher = new EventDispatcher(plugin, serializer, name, pendingEvents, this::send, gson);
        this.permissionsFacade = new PermissionsFacade(plugin, permissionAttachments);
        this.metricsFacade = new MetricsFacade(plugin);
        this.refFacade = new RefFacade(this);
        this.commandsFacade = new CommandsFacade(plugin, this);

        Bukkit.getPluginManager().registerEvents(new Listener() {
            @EventHandler
            public void onPlayerQuit(PlayerQuitEvent event) {
                PermissionAttachment attachment = permissionAttachments.remove(event.getPlayer().getUniqueId());
                if (attachment != null) {
                    try {
                        event.getPlayer().removeAttachment(attachment);
                    } catch (Exception ignored) {
                    }
                }
            }
        }, plugin);
    }

    public boolean isRunning() {
        return running && writer != null;
    }

    public PyJavaBridgePlugin getPlugin() {
        return plugin;
    }

    public Gson getGson() {
        return gson;
    }

    Path getScriptPath() {
        return scriptPath;
    }

    public boolean hasSubscription(String eventName) {
        return subscriptions.containsKey(eventName);
    }

    void start() {
        running = true;

        startPythonProcess();
        if (pythonProcess == null) {
            logError("Failed to start python process", null);
            return;
        }

        bridgeThread = new Thread(this::bridgeLoop, "PyJavaBridge-" + name);
        bridgeThread.start();
    }

    private volatile boolean shutdownStarted = false;

    void shutdown() {
        synchronized (writeLock) {
            if (shutdownStarted) return;
            shutdownStarted = true;
        }
        if (Bukkit.isPrimaryThread()) {
            new Thread(this::shutdownInternal, "PyJavaBridge-Shutdown-" + name).start();
        } else {
            shutdownInternal();
        }
    }

    private void shutdownInternal() {
        running = false;

        // Remove all boss bars so they disappear from players' screens
        for (Object obj : registry.getAll()) {
            if (obj instanceof org.bukkit.boss.BossBar bar) {
                try {
                    bar.removeAll();
                } catch (Exception ignored) {}
            }
        }

        for (EventSubscription subscription : subscriptions.values()) {
            subscription.unregister();
        }
        subscriptions.clear();

        closeQuietly(reader);
        closeQuietly(writer);

        if (pythonProcess != null) {
            pythonProcess.destroy();

            try {
                if (!pythonProcess.waitFor(2, java.util.concurrent.TimeUnit.SECONDS)) {
                    pythonProcess.destroyForcibly();
                }

            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
                pythonProcess.destroyForcibly();
            }
        }
    }

    private void bridgeLoop() {
        try {
            reader = new DataInputStream(pythonProcess.getInputStream());
            writer = new DataOutputStream(pythonProcess.getOutputStream());
            plugin.getLogger().info("[" + name + "] Bridge connected via stdin/stdout");

            while (running) {
                int length;
                try {
                    length = reader.readInt();
                } catch (IOException eof) {
                    break;
                }
                if (length <= 0 || length > 16_777_216) {
                    plugin.getLogger().severe("[" + name + "] Invalid message length: " + length);
                    break;
                }
                byte[] payload = new byte[length];
                reader.readFully(payload);
                JsonObject message;
                try {
                    message = deserializePayload(payload);
                } catch (Exception e) {
                    plugin.getLogger().severe("[" + name + "] Failed to parse message: " + e.getMessage());
                    continue;
                }
                handleMessage(message);
            }

        } catch (IOException e) {
            if (running) {
                logError("Bridge IO error", e);
            }

        } finally {
            shutdown();
        }
    }

    private void handleMessage(JsonObject message) {
        String type = message.get("type").getAsString();
        long startNano = System.nanoTime();

        if (plugin.isDebugEnabled()) {
            plugin.broadcastDebug("[PJB] P2J " + name + ": " + type + " " + summarizeMessage(message));
        }

        switch (type) {
            case "subscribe" -> handleSubscribe(message);
            case "call" -> { handleCall(message, startNano); return; }
            case "call_batch" -> { handleCallBatch(message, startNano); return; }
            case "wait" -> handleWait(message);
            case "handshake" -> handleHandshake(message);
            case "ready" -> Bukkit.getScheduler().runTaskLater(plugin,
                    () -> sendEvent("server_boot", new JsonObject()),
                    2L);
            case "event_done" -> handleEventDone(message);
            case "event_cancel" -> handleEventCancel(message);
            case "event_result" -> handleEventResult(message);
            case "register_command" -> handleRegisterCommand(message);
            case "tab_complete_response" -> handleTabCompleteResponse(message);
            case "script_message" -> handleScriptMessage(message);
            case "get_scripts" -> handleGetScripts(message);
            case "remove_entities" -> handleRemoveEntities(message);
            case "update_entities" -> handleUpdateEntities(message);
            case "move_entities" -> handleMoveEntities(message);
            case "release" -> handleRelease(message);
            case "fire_event" -> handleFireEvent(message);
            case "shutdown_ack" -> {
                if (shutdownLatch != null) {
                    shutdownLatch.countDown();
                }
            }
            default -> sendError(message, "Unknown message type: " + type, null);
        }
    }

    private String summarizeMessage(JsonObject message) {
        String type = message.has("type") ? message.get("type").getAsString() : "";
        StringBuilder sb = new StringBuilder();
        switch (type) {
            case "call" -> {
                if (message.has("method")) sb.append(message.get("method").getAsString());
                if (message.has("handle")) sb.append(" handle=").append(message.get("handle").getAsInt());
                if (message.has("id")) sb.append(" id=").append(message.get("id").getAsInt());
            }
            case "call_batch" -> {
                int count = message.has("messages") ? message.getAsJsonArray("messages").size() : 0;
                boolean atomic = message.has("atomic") && message.get("atomic").getAsBoolean();
                sb.append(count).append(" calls").append(atomic ? " atomic" : "");
            }
            case "subscribe" -> {
                if (message.has("event")) sb.append(message.get("event").getAsString());
            }
            case "register_command" -> {
                if (message.has("name")) sb.append("/").append(message.get("name").getAsString());
            }
            case "return" -> {
                if (message.has("id")) sb.append("id=").append(message.get("id").getAsInt());
            }
            case "error" -> {
                if (message.has("id")) sb.append("id=").append(message.get("id").getAsInt());
                if (message.has("message")) sb.append(" ").append(message.get("message").getAsString());
            }
            case "event" -> {
                if (message.has("event")) sb.append(message.get("event").getAsString());
            }
            case "event_done", "event_cancel" -> {
                if (message.has("id")) sb.append("id=").append(message.get("id").getAsInt());
            }
            case "event_result" -> {
                if (message.has("id")) sb.append("id=").append(message.get("id").getAsInt());
                if (message.has("result_type")) sb.append(" ").append(message.get("result_type").getAsString());
            }
            case "release" -> {
                int count = message.has("handles") && message.get("handles").isJsonArray()
                        ? message.getAsJsonArray("handles").size() : 0;
                sb.append(count).append(" handles");
            }
            case "remove_entities" -> {
                int count = message.has("handles") && message.get("handles").isJsonArray()
                        ? message.getAsJsonArray("handles").size() : 0;
                sb.append(count).append(" entities");
            }
            case "move_entities", "update_entities" -> {
                int count = message.has("entries") && message.get("entries").isJsonArray()
                        ? message.getAsJsonArray("entries").size() : 0;
                sb.append(count).append(" entries");
            }
            case "wait" -> {
                if (message.has("ticks")) sb.append(message.get("ticks").getAsLong()).append(" ticks");
            }
            default -> {}
        }
        return sb.toString();
    }

    private void handleWait(JsonObject message) {
        int id = message.get("id").getAsInt();

        long ticks = message.has("ticks") ? message.get("ticks").getAsLong() : 1L;

        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            JsonObject response = new JsonObject();

            response.addProperty("type", "return");
            response.addProperty("id", id);
            response.add("result", gson.toJsonTree(null));

            send(response);
        }, ticks);
    }

    private void handleHandshake(JsonObject message) {
        String format = message.has("format") ? message.get("format").getAsString() : "json";
        if ("msgpack".equals(format)) {
            useMsgpack = true;
            plugin.getLogger().info("[" + name + "] Switched to msgpack serialization");
        } else {
            plugin.getLogger().info("[" + name + "] Using JSON serialization");
        }
    }

    private void handleRegisterCommand(JsonObject message) {
        String commandName = message.get("name").getAsString();
        String permission = message.has("permission") ? message.get("permission").getAsString() : null;
        boolean hasDynamicTabComplete = message.has("has_tab_complete") && message.get("has_tab_complete").getAsBoolean();

        Map<Integer, List<String>> completions = null;
        if (message.has("completions")) {
            completions = new java.util.HashMap<>(16);
            JsonObject compObj = message.getAsJsonObject("completions");
            for (var entry : compObj.entrySet()) {
                int index = Integer.parseInt(entry.getKey());
                List<String> values = new ArrayList<>(entry.getValue().getAsJsonArray().size());
                for (var el : entry.getValue().getAsJsonArray()) {
                    values.add(el.getAsString());
                }
                completions.put(index, values);
            }
        }

        plugin.getLogger().info("[" + name + "] Registering command /" + commandName);
        plugin.registerScriptCommand(commandName, this, permission, completions, hasDynamicTabComplete);
    }

    private void handleTabCompleteResponse(JsonObject message) {
        int id = message.get("id").getAsInt();
        CompletableFuture<List<String>> future = pendingTabCompletes.remove(id);
        if (future == null) return;

        List<String> results = new ArrayList<>();
        if (message.has("results") && message.get("results").isJsonArray()) {
            var arr = message.getAsJsonArray("results");
            results = new ArrayList<>(arr.size());
            for (var el : arr) {
                results.add(el.getAsString());
            }
        }
        future.complete(results);
    }

    public List<String> requestTabComplete(String commandName, String[] args, org.bukkit.command.CommandSender sender) {
        if (!running) return List.of();

        int requestId = tabCompleteIdCounter.incrementAndGet();
        CompletableFuture<List<String>> future = new CompletableFuture<>();
        pendingTabCompletes.put(requestId, future);

        JsonObject request = new JsonObject();
        request.addProperty("type", "tab_complete");
        request.addProperty("id", requestId);
        request.addProperty("command", commandName);
        request.add("args", gson.toJsonTree(args));
        request.add("sender", serialize(sender));
        if (sender instanceof Player player) {
            request.add("player", serialize(player));
        }
        send(request);

        try {
            return future.get(500, TimeUnit.MILLISECONDS);
        } catch (Exception e) {
            pendingTabCompletes.remove(requestId);
            return List.of();
        }
    }

    private void handleScriptMessage(JsonObject message) {
        String target = message.has("target") ? message.get("target").getAsString() : null;
        JsonElement data = message.has("data") ? message.get("data") : new JsonObject();
        if (target != null) {
            plugin.sendScriptMessage(name, target, data);
        }
    }

    private void handleGetScripts(JsonObject message) {
        int id = message.get("id").getAsInt();
        JsonObject response = new JsonObject();
        response.addProperty("type", "return");
        response.addProperty("id", id);
        com.google.gson.JsonArray arr = new com.google.gson.JsonArray();
        for (String scriptName : plugin.getScriptNames()) {
            arr.add(scriptName);
        }
        response.add("result", arr);
        send(response);
    }

    private void handleRemoveEntities(JsonObject message) {
        boolean hasId = message.has("id");
        int id = hasId ? message.get("id").getAsInt() : 0;
        JsonElement handlesEl = message.get("handles");
        if (handlesEl == null || !handlesEl.isJsonArray()) {
            if (hasId) sendError(id, "remove_entities requires handles array", null);
            return;
        }
        List<Integer> handles = new ArrayList<>(handlesEl.getAsJsonArray().size());
        for (JsonElement el : handlesEl.getAsJsonArray()) {
            handles.add(el.getAsInt());
        }
        plugin.runOnMainThread(this, () -> {
            for (int handle : handles) {
                Object obj = registry.get(handle);
                if (obj instanceof Entity entity) {
                    try {
                        entity.remove();
                    } catch (Exception ignored) {
                    }
                }
                registry.release(handle);
            }
            if (hasId) {
                JsonObject response = new JsonObject();
                response.addProperty("type", "return");
                response.addProperty("id", id);
                response.add("result", gson.toJsonTree(handles.size()));
                send(response);
            }
            return null;
        });
    }

    private void handleUpdateEntities(JsonObject message) {
        // Fire-and-forget: no id required, but support it for backward compat
        JsonElement entriesEl = message.get("entries");
        if (entriesEl == null || !entriesEl.isJsonArray()) {
            if (message.has("id")) {
                sendError(message.get("id").getAsInt(), "update_entities requires entries array", null);
            }
            return;
        }
        var entries = entriesEl.getAsJsonArray();
        boolean hasId = message.has("id");
        int id = hasId ? message.get("id").getAsInt() : 0;
        plugin.runOnMainThread(this, () -> {
            int updated = 0;
            for (JsonElement el : entries) {
                if (!el.isJsonArray()) continue;
                var pair = el.getAsJsonArray();
                if (pair.size() < 2) continue;
                int handle = pair.get(0).getAsInt();
                int argb = pair.get(1).getAsInt();
                Object obj = registry.get(handle);
                if (obj instanceof TextDisplay textDisplay) {
                    textDisplay.setBackgroundColor(Color.fromARGB(argb));
                    updated++;
                }
            }
            if (hasId) {
                JsonObject response = new JsonObject();
                response.addProperty("type", "return");
                response.addProperty("id", id);
                response.add("result", gson.toJsonTree(updated));
                send(response);
            }
            return null;
        });
    }

    private void handleMoveEntities(JsonObject message) {
        // Fire-and-forget bulk teleport + rotation + color + optional scale update
        // entries: [[handle, x, y, z, yaw, pitch, argb], ...]
        //      or: [[handle, x, y, z, yaw, pitch, argb, scaleX, scaleY, scaleZ, yOffset], ...]
        JsonElement entriesEl = message.get("entries");
        if (entriesEl == null || !entriesEl.isJsonArray()) {
            return;
        }
        var entries = entriesEl.getAsJsonArray();
        plugin.runOnMainThread(this, () -> {
            for (JsonElement el : entries) {
                if (!el.isJsonArray()) continue;
                var arr = el.getAsJsonArray();
                if (arr.size() < 7) continue;
                int handle = arr.get(0).getAsInt();
                double x = arr.get(1).getAsDouble();
                double y = arr.get(2).getAsDouble();
                double z = arr.get(3).getAsDouble();
                float yaw = arr.get(4).getAsFloat();
                float pitch = arr.get(5).getAsFloat();
                int argb = arr.get(6).getAsInt();
                Object obj = registry.get(handle);
                if (obj instanceof TextDisplay textDisplay) {
                    Location loc = textDisplay.getLocation();
                    loc.setX(x);
                    loc.setY(y);
                    loc.setZ(z);
                    loc.setYaw(yaw);
                    loc.setPitch(pitch);
                    textDisplay.teleport(loc);
                    textDisplay.setRotation(yaw, pitch);
                    textDisplay.setBackgroundColor(Color.fromARGB(argb));
                    if (arr.size() >= 10) {
                        float sx = arr.get(7).getAsFloat();
                        float sy = arr.get(8).getAsFloat();
                        float sz = arr.get(9).getAsFloat();
                        float yOff = arr.size() >= 11 ? arr.get(10).getAsFloat() : 0f;
                        Quaternionf identity = new Quaternionf(0, 0, 0, 1);
                        textDisplay.setTransformation(new Transformation(
                            new Vector3f(0, yOff, 0), identity,
                            new Vector3f(sx, sy, sz), new Quaternionf(identity)));
                    }
                }
            }
            return null;
        });
    }

    private void handleRelease(JsonObject message) {
        JsonElement handlesEl = message.get("handles");
        if (handlesEl != null && handlesEl.isJsonArray()) {
            var idArray = handlesEl.getAsJsonArray();
            List<Integer> ids = new ArrayList<>(idArray.size());
            for (JsonElement el : idArray) {
                ids.add(el.getAsInt());
            }
            registry.releaseAll(ids);
        }
    }

    private void handleFireEvent(JsonObject message) {
        String eventName = message.has("event") ? message.get("event").getAsString() : null;
        if (eventName == null) return;
        JsonObject payload = message.has("data") ? message.getAsJsonObject("data") : new JsonObject();
        sendEvent(eventName, payload);
    }

    void sendShutdownEvent() {
        if (!running)
            return;
        try {
            shutdownLatch = new CountDownLatch(1);
            JsonObject msg = new JsonObject();
            msg.addProperty("type", "shutdown");
            send(msg);
            shutdownLatch.await(10, TimeUnit.SECONDS);
        } catch (Exception e) {
            plugin.getLogger().warning("[" + name + "] Shutdown wait interrupted");
        }
    }

    public Object handleKick(Player player, List<Object> args) {
        String reason = args.isEmpty() ? "" : String.valueOf(args.get(0));
        try {
            Method kick = player.getClass().getMethod("kick", Component.class);
            kick.invoke(player, Component.text(reason));
            return null;
        } catch (Exception ignored) {
        }
        try {
            Method kick = player.getClass().getMethod("kick", String.class);
            kick.invoke(player, reason);
            return null;
        } catch (Exception ignored) {
        }
        try {
            Method kickPlayer = player.getClass().getMethod("kickPlayer", String.class);
            kickPlayer.invoke(player, reason);
        } catch (Exception ignored) {
        }
        return null;
    }

    private void handleEventDone(JsonObject message) {
        int id = message.get("id").getAsInt();
        PendingEvent pending = pendingEvents.get(id);

        if (pending != null) {
            pending.latch.countDown();
        }
    }

    private void handleEventCancel(JsonObject message) {
        int id = message.get("id").getAsInt();
        PendingEvent pending = pendingEvents.get(id);

        if (pending != null) {
            pending.cancelRequested.set(true);
            pending.latch.countDown();
        }
    }

    private void handleEventResult(JsonObject message) {
        int id = message.get("id").getAsInt();
        PendingEvent pending = pendingEvents.get(id);

        if (pending == null) {
            return;
        }

        if (!message.has("result") || message.get("result").isJsonNull()) {
            return;
        }

        String resultType = message.has("result_type") ? message.get("result_type").getAsString() : null;
        if ("damage".equalsIgnoreCase(resultType)) {
            JsonElement result = message.get("result");
            if (result.isJsonPrimitive() && result.getAsJsonPrimitive().isNumber()) {
                pending.damageOverride = result.getAsDouble();
            }
            return;
        }

        if ("respawn".equalsIgnoreCase(resultType)) {
            JsonElement result = message.get("result");
            Object deserialized = serializer.deserialize(result);
            if (deserialized instanceof org.bukkit.Location loc) {
                pending.respawnOverride = loc;
            }
            return;
        }

        if ("target".equalsIgnoreCase(resultType)) {
            JsonElement result = message.get("result");
            if (result.isJsonNull()) {
                pending.targetOverride = null;
                pending.targetOverrideSet = true;
            } else {
                Object deserialized = serializer.deserialize(result);
                if (deserialized instanceof org.bukkit.entity.Entity entity) {
                    pending.targetOverride = entity;
                    pending.targetOverrideSet = true;
                }
            }
            return;
        }

        if (resultType == null || "chat".equalsIgnoreCase(resultType)) {
            pending.chatOverride = message.get("result").getAsString();
        }
    }

    private void handleSubscribe(JsonObject message) {
        String eventName = message.get("event").getAsString();

        boolean oncePerTick = message.has("once_per_tick") && message.get("once_per_tick").getAsBoolean();
        long throttleMs = message.has("throttle_ms") ? message.get("throttle_ms").getAsLong() : 0L;
        EventPriority priority = EventPriority.NORMAL;
        if (message.has("priority")) {
            try {
                priority = EventPriority.valueOf(message.get("priority").getAsString().toUpperCase());
            } catch (IllegalArgumentException ignored) {
            }
        }

        if (eventName.equalsIgnoreCase("server_boot")) {
            return;
        }

        try {

            plugin.getLogger().info(
                    "[" + name + "] Subscribing to event " + eventName + " (oncePerTick=" + oncePerTick + ")");

            if (eventName.equalsIgnoreCase("block_explode")) {
                EventSubscription blockSub = new EventSubscription(plugin, this, eventName, oncePerTick,
                        priority, throttleMs, org.bukkit.event.block.BlockExplodeEvent.class);

                blockSub.register();
                subscriptions.put(eventName + "#block", blockSub);
                EventSubscription entitySub = new EventSubscription(plugin, this, eventName, oncePerTick,
                        priority, throttleMs, org.bukkit.event.entity.EntityExplodeEvent.class);

                entitySub.register();
                subscriptions.put(eventName + "#entity", entitySub);

            } else {
                EventSubscription subscription = new EventSubscription(plugin, this, eventName, oncePerTick,
                        priority, throttleMs);

                subscription.register();
                subscriptions.put(eventName, subscription);
            }

        } catch (Exception ex) {
            sendError(message, "Failed to subscribe to " + eventName, ex);
        }
    }

    private void handleCall(JsonObject message, long startNano) {
        int id = message.get("id").getAsInt();
        boolean noResponse = message.has("no_response") && message.get("no_response").getAsBoolean();

        if (isCallThreadSafe(message)) {
            try {
                Object result = invoke(message);
                if (!noResponse) {
                    JsonObject response = new JsonObject();
                    response.addProperty("type", "return");
                    response.addProperty("id", id);
                    response.add("result", serialize(result));
                    sendWithTiming(response, startNano);
                }
            } catch (Exception ex) {
                if (!noResponse) {
                    Throwable cause = ex;
                    String errorMessage = cause.getMessage();
                    if (errorMessage == null || errorMessage.isBlank()) {
                        errorMessage = cause.getClass().getSimpleName();
                    }
                    sendError(id, errorMessage, cause);
                }
            }
            return;
        }

        CompletableFuture<Object> future = plugin.runOnMainThread(this, () -> invoke(message));

        future.whenCompleteAsync((result, error) -> {
            if (noResponse) return;
            if (error != null) {
                Throwable cause = error instanceof java.util.concurrent.CompletionException
                        && error.getCause() != null ? error.getCause() : error;
                String errorMessage = cause.getMessage();
                if (errorMessage == null || errorMessage.isBlank()) {
                    errorMessage = cause.getClass().getSimpleName();
                }
                sendError(id, errorMessage, cause);

            } else {
                JsonObject response = new JsonObject();

                response.addProperty("type", "return");
                response.addProperty("id", id);
                response.add("result", serialize(result));

                sendWithTiming(response, startNano);
            }
        });
    }

    private void handleCallBatch(JsonObject message, long startNano) {

        boolean atomic = message.has("atomic") && message.get("atomic").getAsBoolean();
        var msgArray = message.has("messages") ? message.getAsJsonArray("messages") : null;
        List<JsonObject> calls = new ArrayList<>(msgArray != null ? msgArray.size() : 4);

        if (msgArray != null) {
            for (JsonElement element : msgArray) {
                if (element.isJsonObject()) {
                    calls.add(element.getAsJsonObject());
                }
            }
        }

        boolean allThreadSafe = true;
        for (JsonObject call : calls) {
            if (!isCallThreadSafe(call)) {
                allThreadSafe = false;
                break;
            }
        }

        if (allThreadSafe) {
            executeBatchCalls(calls, atomic, startNano);
            return;
        }

        CompletableFuture<Object> future = plugin.runOnMainThread(this, () -> {
            executeBatchCalls(calls, atomic, startNano);
            return null;
        });

        future.whenComplete((result, error) -> {
            if (error != null) {
                logError("Batch call failed", error);
            }
        });
    }

    private void executeBatchCalls(List<JsonObject> calls, boolean atomic, long startNano) {
        if (atomic) {
            List<JsonObject> responses = new ArrayList<>(calls.size());
            List<Integer> ids = new ArrayList<>(calls.size());
            boolean failed = false;
            int failedId = -1;
            Exception failedEx = null;
            String failedMessage = null;

            for (JsonObject callMessage : calls) {
                int id = callMessage.get("id").getAsInt();
                ids.add(id);
                boolean noResponse = callMessage.has("no_response") && callMessage.get("no_response").getAsBoolean();

                if (failed) {
                    continue;
                }

                try {
                    Object result = invoke(callMessage);

                    if (!noResponse) {
                        JsonObject response = new JsonObject();
                        response.addProperty("type", "return");
                        response.addProperty("id", id);
                        response.add("result", serialize(result));
                        responses.add(response);
                    }

                } catch (Exception ex) {
                    failed = true;
                    failedId = id;
                    failedEx = ex;
                    String messageText = ex.getMessage();
                    if (messageText == null || messageText.isBlank()) {
                        messageText = ex.getClass().getSimpleName();
                    }
                    failedMessage = messageText;
                }
            }

            if (failed) {
                for (int id : ids) {
                    if (id == failedId) {
                        sendError(id, failedMessage, failedEx);
                    } else {
                        sendError(id, "Atomic batch aborted", null, "ATOMIC_ABORT");
                    }
                }
            } else {
                sendAll(responses, startNano);
            }
            return;
        }

        List<JsonObject> batchResponses = new ArrayList<>(calls.size());
        for (JsonObject callMessage : calls) {
            int id = callMessage.get("id").getAsInt();
            boolean noResponse = callMessage.has("no_response") && callMessage.get("no_response").getAsBoolean();

            try {
                Object result = invoke(callMessage);

                if (!noResponse) {
                    JsonObject response = new JsonObject();
                    response.addProperty("type", "return");
                    response.addProperty("id", id);
                    response.add("result", serialize(result));
                    batchResponses.add(response);
                }

            } catch (Exception ex) {
                // Flush any accumulated responses first, then send error
                if (!batchResponses.isEmpty()) {
                    sendAll(batchResponses, startNano);
                    batchResponses = new ArrayList<>();
                }
                sendError(id, ex.getMessage(), ex);
            }
        }
        if (!batchResponses.isEmpty()) {
            sendAll(batchResponses, startNano);
        }
    }

    private static final Set<String> THREAD_SAFE_SERVER_METHODS = Set.of(
        "getName", "getVersion", "getBukkitVersion", "getMaxPlayers",
        "getOnlinePlayers", "getOfflinePlayer", "getWorlds",
        "getPort", "getViewDistance", "getMotd", "hasWhitelist"
    );

    private static final Set<String> THREAD_SAFE_OFFLINEPLAYER_METHODS = Set.of(
        "getUniqueId", "getName", "hasPermission", "isPermissionSet",
        "isWhitelisted", "isBanned", "isOnline", "getFirstPlayed",
        "getLastPlayed", "hasPlayedBefore"
    );

    private static final Set<String> THREAD_SAFE_METADATA_METHODS = Set.of(
        "hasMetadata", "getMetadata"
    );

    private static final Set<String> THREAD_SAFE_ENTITY_METHODS = Set.of(
        "getUniqueId", "getType", "isDead", "isValid",
        "getEntityId", "getTicksLived", "getCustomName",
        "isCustomNameVisible", "getName"
    );

    private boolean isCallThreadSafe(JsonObject message) {
        String method = message.has("method") ? message.get("method").getAsString() : null;
        if (method == null) return false;

        // Target-based calls
        if (message.has("target")) {
            String target = message.get("target").getAsString();
            // MetricsFacade: reads atomic/volatile values only
            if ("metrics".equals(target)) return true;
            // ReflectFacade: Class.forName() is thread-safe
            if ("reflect".equals(target)) return true;
            // Server: only specific read-only info methods
            if ("server".equals(target)) {
                return THREAD_SAFE_SERVER_METHODS.contains(method);
            }
            return false;
        }

        // Handle-based calls — resolve handle to check object type
        if (message.has("handle")) {
            Object target = registry.get(message.get("handle").getAsInt());
            if (target == null) return false;

            // Metadatable read-only checks (hasMetadata, getMetadata)
            if (target instanceof org.bukkit.metadata.Metadatable
                    && THREAD_SAFE_METADATA_METHODS.contains(method)) {
                return true;
            }

            // OfflinePlayer (also covers Player): UUID, name, permission checks, ban/whitelist status
            if (target instanceof org.bukkit.OfflinePlayer) {
                return THREAD_SAFE_OFFLINEPLAYER_METHODS.contains(method);
            }

            // Entity (non-Player): UUID, type, and other read-only getters
            if (target instanceof Entity) {
                return THREAD_SAFE_ENTITY_METHODS.contains(method);
            }
        }

        return false;
    }

    private Object invoke(JsonObject message) throws Exception {
        String method = message.get("method").getAsString();

        JsonObject argsObj = message.has("args") ? message.getAsJsonObject("args") : EMPTY_JSON_OBJ;

        var argsList = message.has("args_list") ? message.getAsJsonArray("args_list") : null;
        List<Object> args = new ArrayList<>(argsList != null ? argsList.size() : 4);

        if (argsList != null) {
            for (JsonElement element : argsList) {
                args.add(serializer.deserialize(element));
            }
        }

        Object target = resolveInvokeTarget(message, argsObj);

        if (target == null && "close".equals(method)) {
            return null;
        }

        validateTarget(target, message);

        // Convert coordinate list to Location for teleport
        if ("teleport".equals(method) && target instanceof Entity entity && args.size() == 1) {
            args = preprocessTeleportArgs(entity, args);
        }

        if ("getUniqueId".equals(method) && target instanceof Entity entity) {
            return entity.getUniqueId();
        }

        // Type-specific dispatch — else-if chain avoids redundant instanceof checks
        Object result = UNHANDLED;

        if (target instanceof World world) {
            result = invokeWorldMethod(world, method, args, argsObj);
        } else if (target instanceof Player player) {
            // Player before Entity since Player extends Entity
            result = invokePlayerMethod(player, method, args);
            if (result == UNHANDLED) {
                result = invokeMobMethod(player, method, args);
            }
        } else if (target instanceof Entity entity) {
            if (target instanceof Display) {
                result = invokeDisplayMethod(target, method, args);
            }
            if (result == UNHANDLED) {
                result = invokeMobMethod(entity, method, args);
            }
        } else if (target instanceof Block block) {
            result = invokeBlockMethod(block, method);
            if (result == UNHANDLED) {
                result = invokeBlockMethodWithArgs(block, method, args);
            }
        } else if (target instanceof org.bukkit.inventory.Inventory inv) {
            result = invokeInventoryMethod(inv, method);
        } else if (target instanceof ItemStack itemStack) {
            result = invokeItemStackMethod(itemStack, method, args);
        } else if (target instanceof org.bukkit.Server server) {
            result = invokeServerMethod(server, method, args);
        }

        if (result != UNHANDLED) {
            return result;
        }

        if ("get_attr".equals(method)) {
            return serializer.getField(target, message.get("field").getAsString());
        }
        if ("set_attr".equals(method)) {
            serializer.setField(target, message.get("field").getAsString(), serializer.deserialize(message.get("value")));
            return null;
        }

        return invokeReflective(target, method, args);
    }

    private Object resolveInvokeTarget(JsonObject message, JsonObject argsObj) throws Exception {
        if (message.has("handle")) {
            return registry.get(message.get("handle").getAsInt());
        } else if (message.has("target")) {
            return resolveTarget(message.get("target").getAsString(), argsObj);
        }
        throw new IllegalStateException("Missing target or handle");
    }

    private void validateTarget(Object target, JsonObject message) throws EntityGoneException {
        if (target == null) {
            String targetLabel = message.has("handle")
                    ? "handle " + message.get("handle").getAsInt()
                    : message.has("target") ? "target " + message.get("target").getAsString() : "unknown";
            throw new EntityGoneException("Target not found: " + targetLabel);
        }
        if (target instanceof Player player && !player.isOnline()) {
            throw new EntityGoneException("Player is no longer online");
        }
        if (target instanceof Entity entity) {
            if (entity.isDead()) {
                throw new EntityGoneException("Entity is no longer valid");
            }
            if (!entity.isValid() && !(entity instanceof Display)) {
                throw new EntityGoneException("Entity is no longer valid");
            }
        }
    }

    private List<Object> preprocessTeleportArgs(Entity entity, List<Object> args) {
        Object arg = args.get(0);
        if (arg instanceof List<?> list && list.size() >= 3) {
            Double x = list.get(0) instanceof Number n ? n.doubleValue() : null;
            Double y = list.get(1) instanceof Number n ? n.doubleValue() : null;
            Double z = list.get(2) instanceof Number n ? n.doubleValue() : null;
            if (x != null && y != null && z != null) {
                float yaw = list.size() > 3 && list.get(3) instanceof Number n ? n.floatValue()
                        : entity.getLocation().getYaw();
                float pitch = list.size() > 4 && list.get(4) instanceof Number n ? n.floatValue()
                        : entity.getLocation().getPitch();
                return List.of(new Location(entity.getWorld(), x, y, z, yaw, pitch));
            }
        }
        return args;
    }

    private Map<String, Object> serializeMerchantRecipe(org.bukkit.inventory.MerchantRecipe recipe) {
        Map<String, Object> map = new java.util.LinkedHashMap<>();
        map.put("result", recipe.getResult().serialize());
        List<Map<String, Object>> ingredients = new ArrayList<>(recipe.getIngredients().size());
        for (ItemStack ingredient : recipe.getIngredients()) {
            ingredients.add(ingredient.serialize());
        }
        map.put("ingredients", ingredients);
        map.put("maxUses", recipe.getMaxUses());
        map.put("uses", recipe.getUses());
        map.put("experienceReward", recipe.hasExperienceReward());
        map.put("villagerExperience", recipe.getVillagerExperience());
        map.put("priceMultiplier", recipe.getPriceMultiplier());
        map.put("demand", recipe.getDemand());
        map.put("specialPrice", recipe.getSpecialPrice());
        return map;
    }

    private org.bukkit.inventory.MerchantRecipe deserializeMerchantRecipe(Map<String, Object> map) {
        if (map == null) return null;
        // Deserialize result item
        Object resultObj = map.get("result");
        ItemStack result;
        if (resultObj instanceof Map<?, ?> resultMap) {
            result = ItemStack.deserialize(toStringKeyMap(resultMap));
        } else {
            return null;
        }
        int maxUses = map.containsKey("maxUses") ? ((Number) map.get("maxUses")).intValue() : 1;
        boolean experienceReward = map.containsKey("experienceReward") ? Boolean.TRUE.equals(map.get("experienceReward")) : true;
        int villagerExperience = map.containsKey("villagerExperience") ? ((Number) map.get("villagerExperience")).intValue() : 0;
        float priceMultiplier = map.containsKey("priceMultiplier") ? ((Number) map.get("priceMultiplier")).floatValue() : 0.0f;
        int demand = map.containsKey("demand") ? ((Number) map.get("demand")).intValue() : 0;
        int specialPrice = map.containsKey("specialPrice") ? ((Number) map.get("specialPrice")).intValue() : 0;
        int uses = map.containsKey("uses") ? ((Number) map.get("uses")).intValue() : 0;

        org.bukkit.inventory.MerchantRecipe recipe = new org.bukkit.inventory.MerchantRecipe(
            result, uses, maxUses, experienceReward, villagerExperience, priceMultiplier, demand, specialPrice
        );

        // Deserialize ingredients
        Object ingredientsObj = map.get("ingredients");
        if (ingredientsObj instanceof List<?> ingredientsList) {
            List<ItemStack> ingredients = new ArrayList<>(ingredientsList.size());
            for (Object ingObj : ingredientsList) {
                if (ingObj instanceof Map<?, ?> ingMap) {
                    ItemStack ing = ItemStack.deserialize(toStringKeyMap(ingMap));
                    ingredients.add(ing);
                }
            }
            recipe.setIngredients(ingredients);
        }

        return recipe;
    }

    private Map<String, Object> toStringKeyMap(Map<?, ?> map) {
        Map<String, Object> result = new java.util.LinkedHashMap<>();
        for (Map.Entry<?, ?> entry : map.entrySet()) {
            result.put(String.valueOf(entry.getKey()), entry.getValue());
        }
        return result;
    }

    private Location toLocation(Object arg, Entity context) {
        if (arg instanceof Location loc) return loc;
        if (arg instanceof List<?> list && list.size() >= 3) {
            Double x = list.get(0) instanceof Number n ? n.doubleValue() : null;
            Double y = list.get(1) instanceof Number n ? n.doubleValue() : null;
            Double z = list.get(2) instanceof Number n ? n.doubleValue() : null;
            if (x != null && y != null && z != null) {
                return new Location(context.getWorld(), x, y, z);
            }
        }
        return null;
    }

    private Object invokeWorldMethod(World world, String method, List<Object> args, JsonObject argsObj) throws Exception {
        if (args.size() == 2 && ("spawnEntity".equals(method) || "spawn".equals(method))) {
            Object locationObj = args.get(0);
            Object typeObj = args.get(1);
            if ("spawn".equals(method) && !(typeObj instanceof EnumValue)
                    && !(typeObj instanceof String) && !(typeObj instanceof EntityType)) {
                return UNHANDLED;
            }
            Map<String, Object> options = serializer.deserializeArgsObject(argsObj);
            return entitySpawner.spawnEntityWithOptions(world, locationObj, typeObj, options);
        }
        if ("spawnImagePixels".equals(method) && args.size() >= 2) {
            return entitySpawner.spawnImagePixels(world, args.get(0), args.get(1));
        }
        if ("spawnFirework".equals(method) && args.size() >= 1) {
            Object locationObj = args.get(0);
            Map<String, Object> options = serializer.deserializeArgsObject(argsObj);
            return entitySpawner.spawnFirework(world, locationObj, options);
        }
        if ("getGameRule".equals(method) && !args.isEmpty()) {
            String ruleName = args.get(0) instanceof EnumValue ev ? ev.name : String.valueOf(args.get(0));
            @SuppressWarnings("unchecked")
            GameRule<Object> rule = (GameRule<Object>) GameRule.getByName(ruleName);
            if (rule != null) return world.getGameRuleValue(rule);
            return null;
        }
        if ("setGameRule".equals(method) && args.size() >= 2) {
            String ruleName = args.get(0) instanceof EnumValue ev ? ev.name : String.valueOf(args.get(0));
            @SuppressWarnings("unchecked")
            GameRule<Object> rule = (GameRule<Object>) GameRule.getByName(ruleName);
            if (rule != null) {
                Object val = args.get(1);
                if (val instanceof Boolean b) {
                    @SuppressWarnings("unchecked")
                    GameRule<Boolean> boolRule = (GameRule<Boolean>) GameRule.getByName(ruleName);
                    world.setGameRule(boolRule, b);
                } else if (val instanceof Number n) {
                    @SuppressWarnings("unchecked")
                    GameRule<Integer> intRule = (GameRule<Integer>) GameRule.getByName(ruleName);
                    world.setGameRule(intRule, n.intValue());
                }
            }
            return null;
        }
        if ("getGameRules".equals(method)) {
            Map<String, Object> rules = new java.util.HashMap<>();
            for (String name : world.getGameRules()) {
                @SuppressWarnings("unchecked")
                GameRule<Object> gr = (GameRule<Object>) GameRule.getByName(name);
                if (gr != null) rules.put(name, world.getGameRuleValue(gr));
            }
            return rules;
        }
        if ("getWorldBorder".equals(method)) {
            WorldBorder border = world.getWorldBorder();
            Map<String, Object> result = new java.util.HashMap<>();
            result.put("center_x", border.getCenter().getX());
            result.put("center_z", border.getCenter().getZ());
            result.put("size", border.getSize());
            result.put("damage_amount", border.getDamageAmount());
            result.put("damage_buffer", border.getDamageBuffer());
            result.put("warning_distance", border.getWarningDistance());
            result.put("warning_time", border.getWarningTime());
            return result;
        }
        if ("setWorldBorder".equals(method) && !args.isEmpty()) {
            WorldBorder border = world.getWorldBorder();
            if (args.get(0) instanceof Map<?, ?> map) {
                if (map.containsKey("center_x") && map.containsKey("center_z")) {
                    double cx = ((Number) map.get("center_x")).doubleValue();
                    double cz = ((Number) map.get("center_z")).doubleValue();
                    border.setCenter(cx, cz);
                }
                if (map.containsKey("size")) {
                    border.setSize(((Number) map.get("size")).doubleValue());
                }
                if (map.containsKey("damage_amount")) {
                    border.setDamageAmount(((Number) map.get("damage_amount")).doubleValue());
                }
                if (map.containsKey("damage_buffer")) {
                    border.setDamageBuffer(((Number) map.get("damage_buffer")).doubleValue());
                }
                if (map.containsKey("warning_distance")) {
                    border.setWarningDistance(((Number) map.get("warning_distance")).intValue());
                }
                if (map.containsKey("warning_time")) {
                    border.setWarningTime(((Number) map.get("warning_time")).intValue());
                }
            }
            return null;
        }
        if ("getHighestBlockAt".equals(method) && args.size() >= 2) {
            int x = ((Number) args.get(0)).intValue();
            int z = ((Number) args.get(1)).intValue();
            return world.getHighestBlockAt(x, z);
        }
        if ("generateTree".equals(method) && args.size() >= 2) {
            Location loc = toLocation(args.get(0), null);
            if (loc == null && args.get(0) instanceof Location l) loc = l;
            if (loc != null) {
                loc.setWorld(world);
                String typeName = args.get(1) instanceof EnumValue ev ? ev.name : String.valueOf(args.get(1));
                TreeType type = TreeType.valueOf(typeName.toUpperCase());
                return world.generateTree(loc, type);
            }
            return false;
        }
        if ("getNearbyEntities".equals(method) && args.size() >= 4) {
            Location loc = toLocation(args.get(0), null);
            if (loc == null && args.get(0) instanceof Location l) loc = l;
            if (loc != null) {
                loc.setWorld(world);
                double dx = ((Number) args.get(1)).doubleValue();
                double dy = ((Number) args.get(2)).doubleValue();
                double dz = ((Number) args.get(3)).doubleValue();
                return new ArrayList<>(world.getNearbyEntities(loc, dx, dy, dz));
            }
            return List.of();
        }
        if ("getChunkAtAsync".equals(method) && args.size() >= 2) {
            int cx = ((Number) args.get(0)).intValue();
            int cz = ((Number) args.get(1)).intValue();
            return world.getChunkAtAsync(cx, cz);
        }
        if ("batchSpawn".equals(method) && !args.isEmpty() && args.get(0) instanceof List<?> batch) {
            List<Entity> spawned = new ArrayList<>(batch.size());
            for (Object entry : batch) {
                if (entry instanceof Map<?, ?> spec) {
                    Object locObj = spec.get("location");
                    Object typeObj = spec.get("type");
                    Location loc = locObj instanceof Location l ? l : toLocation(locObj, null);
                    if (loc != null && typeObj != null) {
                        loc.setWorld(world);
                        String typeName = typeObj instanceof EnumValue ev ? ev.name : String.valueOf(typeObj);
                        EntityType et = EntityType.valueOf(typeName.toUpperCase());
                        spawned.add(world.spawnEntity(loc, et));
                    }
                }
            }
            return spawned;
        }
        if ("worldRayTrace".equals(method) && args.size() >= 3) {
            Location start = toLocation(args.get(0), null);
            if (start == null && args.get(0) instanceof Location l) start = l;
            if (start != null) {
                start.setWorld(world);
                org.bukkit.util.Vector direction;
                if (args.get(1) instanceof org.bukkit.util.Vector v) {
                    direction = v;
                } else if (args.get(1) instanceof Map<?,?> m) {
                    direction = new org.bukkit.util.Vector(
                        ((Number)m.get("x")).doubleValue(),
                        ((Number)m.get("y")).doubleValue(),
                        ((Number)m.get("z")).doubleValue()
                    );
                } else {
                    return null;
                }
                double maxDist = ((Number) args.get(2)).doubleValue();
                org.bukkit.util.RayTraceResult hit = world.rayTraceBlocks(start, direction, maxDist);
                if (hit != null) {
                    Map<String, Object> result = new java.util.HashMap<>();
                    if (hit.getHitBlock() != null) result.put("block", hit.getHitBlock());
                    if (hit.getHitEntity() != null) result.put("entity", hit.getHitEntity());
                    if (hit.getHitPosition() != null) {
                        result.put("position", new Location(world, hit.getHitPosition().getX(), hit.getHitPosition().getY(), hit.getHitPosition().getZ()));
                    }
                    return result;
                }
            }
            return null;
        }
        return UNHANDLED;
    }

    private Object invokeBlockMethod(Block block, String method) {
        if ("getInventory".equals(method)) {
            BlockState state = block.getState();
            return state instanceof InventoryHolder holder ? holder.getInventory() : null;
        }
        if ("getStateType".equals(method)) {
            BlockState state = block.getState();
            return state.getClass().getSimpleName().replace("Craft", "");
        }
        if ("isContainer".equals(method)) {
            return block.getState() instanceof InventoryHolder;
        }
        // Sign methods
        if ("getSignLines".equals(method)) {
            BlockState state = block.getState();
            if (state instanceof Sign sign) {
                SignSide side = sign.getSide(Side.FRONT);
                List<String> lines = new ArrayList<>(4);
                for (int i = 0; i < 4; i++) {
                    lines.add(PlainTextComponentSerializer.plainText().serialize(side.line(i)));
                }
                return lines;
            }
            return null;
        }
        if ("getSignBackLines".equals(method)) {
            BlockState state = block.getState();
            if (state instanceof Sign sign) {
                SignSide side = sign.getSide(Side.BACK);
                List<String> lines = new ArrayList<>(4);
                for (int i = 0; i < 4; i++) {
                    lines.add(PlainTextComponentSerializer.plainText().serialize(side.line(i)));
                }
                return lines;
            }
            return null;
        }
        // Furnace methods
        if ("getFurnaceBurnTime".equals(method)) {
            BlockState state = block.getState();
            return state instanceof Furnace furnace ? furnace.getBurnTime() : null;
        }
        if ("getFurnaceCookTime".equals(method)) {
            BlockState state = block.getState();
            return state instanceof Furnace furnace ? furnace.getCookTime() : null;
        }
        if ("getFurnaceCookTimeTotal".equals(method)) {
            BlockState state = block.getState();
            return state instanceof Furnace furnace ? furnace.getCookTimeTotal() : null;
        }
        return UNHANDLED;
    }

    private Object invokeBlockMethodWithArgs(Block block, String method, List<Object> args) {
        // Sign methods with args
        if ("setSignLine".equals(method) && args.size() >= 2) {
            BlockState state = block.getState();
            if (state instanceof Sign sign) {
                int line = ((Number) args.get(0)).intValue();
                String text = String.valueOf(args.get(1));
                sign.getSide(Side.FRONT).line(line, Component.text(text));
                sign.update();
                return null;
            }
            return null;
        }
        if ("setSignLines".equals(method) && args.size() >= 1) {
            BlockState state = block.getState();
            if (state instanceof Sign sign) {
                @SuppressWarnings("unchecked")
                List<String> lines = (List<String>) args.get(0);
                SignSide side = sign.getSide(Side.FRONT);
                for (int i = 0; i < Math.min(lines.size(), 4); i++) {
                    side.line(i, Component.text(lines.get(i)));
                }
                sign.update();
                return null;
            }
            return null;
        }
        if ("setSignBackLine".equals(method) && args.size() >= 2) {
            BlockState state = block.getState();
            if (state instanceof Sign sign) {
                int line = ((Number) args.get(0)).intValue();
                String text = String.valueOf(args.get(1));
                sign.getSide(Side.BACK).line(line, Component.text(text));
                sign.update();
                return null;
            }
            return null;
        }
        if ("setSignBackLines".equals(method) && args.size() >= 1) {
            BlockState state = block.getState();
            if (state instanceof Sign sign) {
                @SuppressWarnings("unchecked")
                List<String> lines = (List<String>) args.get(0);
                SignSide side = sign.getSide(Side.BACK);
                for (int i = 0; i < Math.min(lines.size(), 4); i++) {
                    side.line(i, Component.text(lines.get(i)));
                }
                sign.update();
                return null;
            }
            return null;
        }
        if ("setSignGlowing".equals(method) && args.size() >= 1) {
            BlockState state = block.getState();
            if (state instanceof Sign sign) {
                boolean glowing = (boolean) args.get(0);
                sign.getSide(Side.FRONT).setGlowingText(glowing);
                sign.update();
                return null;
            }
            return null;
        }
        if ("isSignGlowing".equals(method)) {
            BlockState state = block.getState();
            if (state instanceof Sign sign) {
                return sign.getSide(Side.FRONT).isGlowingText();
            }
            return null;
        }
        // Furnace set methods
        if ("setFurnaceBurnTime".equals(method) && args.size() >= 1) {
            BlockState state = block.getState();
            if (state instanceof Furnace furnace) {
                furnace.setBurnTime(((Number) args.get(0)).shortValue());
                furnace.update();
                return null;
            }
            return null;
        }
        if ("setFurnaceCookTime".equals(method) && args.size() >= 1) {
            BlockState state = block.getState();
            if (state instanceof Furnace furnace) {
                furnace.setCookTime(((Number) args.get(0)).shortValue());
                furnace.update();
                return null;
            }
            return null;
        }
        if ("setBlockData".equals(method) && args.size() >= 1) {
            String dataStr = null;
            if (args.get(0) instanceof String str) {
                dataStr = str;
            } else if (args.get(0) instanceof EnumValue enumValue) {
                dataStr = enumValue.name;
            }
            if (dataStr != null) {
                try {
                    block.setBlockData(Bukkit.createBlockData(dataStr.toLowerCase()));
                    return null;
                } catch (IllegalArgumentException e) {
                    try {
                        block.setBlockData(Bukkit.createBlockData(Material.valueOf(dataStr.toUpperCase())));
                        return null;
                    } catch (IllegalArgumentException ignored) {
                    }
                }
            }
        }
        if ("getDrops".equals(method)) {
            if (!args.isEmpty() && args.get(0) instanceof ItemStack tool) {
                return List.copyOf(block.getDrops(tool));
            }
            return List.copyOf(block.getDrops());
        }
        if ("getHardness".equals(method)) {
            return block.getType().getHardness();
        }
        if ("getBlastResistance".equals(method)) {
            return block.getType().getBlastResistance();
        }
        if ("getBlockPDC".equals(method)) {
            BlockState state = block.getState();
            if (state instanceof org.bukkit.block.TileState tile) {
                PersistentDataContainer pdc = tile.getPersistentDataContainer();
                Map<String, Object> result = new java.util.HashMap<>();
                for (NamespacedKey key : pdc.getKeys()) {
                    Object val = pdc.get(key, PersistentDataType.STRING);
                    if (val != null) result.put(key.toString(), val);
                }
                return result;
            }
            return Map.of();
        }
        if ("setBlockPDC".equals(method) && args.size() >= 2) {
            BlockState state = block.getState();
            if (state instanceof org.bukkit.block.TileState tile) {
                String keyStr = String.valueOf(args.get(0));
                NamespacedKey key = new NamespacedKey(plugin, keyStr);
                tile.getPersistentDataContainer().set(key, PersistentDataType.STRING, String.valueOf(args.get(1)));
                tile.update();
            }
            return null;
        }
        if ("removeBlockPDC".equals(method) && !args.isEmpty()) {
            BlockState state = block.getState();
            if (state instanceof org.bukkit.block.TileState tile) {
                String keyStr = String.valueOf(args.get(0));
                NamespacedKey key = new NamespacedKey(plugin, keyStr);
                tile.getPersistentDataContainer().remove(key);
                tile.update();
            }
            return null;
        }
        return UNHANDLED;
    }

    private Object invokeInventoryMethod(org.bukkit.inventory.Inventory inventory, String method) {
        if ("close".equals(method)) {
            try {
                for (org.bukkit.entity.HumanEntity viewer : new ArrayList<>(inventory.getViewers())) {
                    if (viewer != null) {
                        viewer.closeInventory();
                    }
                }
            } catch (Exception ignored) {
            }
            return null;
        }
        if ("getTitle".equals(method)) {
            try {
                Method getTitle = inventory.getClass().getMethod("getTitle");
                Object titleObj = getTitle.invoke(inventory);
                return titleObj != null ? titleObj.toString() : "";
            } catch (Exception ignored) {
                return "";
            }
        }
        return UNHANDLED;
    }

    private Object invokePlayerMethod(Player player, String method, List<Object> args) throws Exception {
        switch (method) {
            case "playSound" -> {
                Sound sound = resolveSound(args.isEmpty() ? null : args.get(0));
                float volume = args.size() > 1 && args.get(1) instanceof Number n ? n.floatValue() : 1.0f;
                float pitch = args.size() > 2 && args.get(2) instanceof Number n ? n.floatValue() : 1.0f;
                if (sound != null) {
                    player.playSound(player.getLocation(), sound, volume, pitch);
                }
                return null;
            }
            case "grantAdvancement", "revokeAdvancement" -> {
                Object keyObj = args.isEmpty() ? null : args.get(0);
                org.bukkit.advancement.Advancement advancement = null;
                if (keyObj instanceof org.bukkit.advancement.Advancement adv) {
                    advancement = adv;
                } else if (keyObj instanceof NamespacedKey key) {
                    advancement = Bukkit.getAdvancement(key);
                } else if (keyObj instanceof String text) {
                    NamespacedKey key = NamespacedKey.fromString(text);
                    if (key != null) {
                        advancement = Bukkit.getAdvancement(key);
                    }
                }
                if (advancement == null) {
                    throw new IllegalArgumentException("Advancement not found");
                }
                org.bukkit.advancement.AdvancementProgress progress = player.getAdvancementProgress(advancement);
                if ("grantAdvancement".equals(method)) {
                    for (String criterion : progress.getRemainingCriteria()) {
                        progress.awardCriteria(criterion);
                    }
                } else {
                    for (String criterion : progress.getAwardedCriteria()) {
                        progress.revokeCriteria(criterion);
                    }
                }
                return progress;
            }
            case "kick" -> {
                return handleKick(player, args);
            }
            case "setTabListHeaderFooter" -> {
                String header = !args.isEmpty() ? String.valueOf(args.get(0)) : "";
                String footer = args.size() > 1 ? String.valueOf(args.get(1)) : "";
                setTabListHeaderFooter(player, header, footer);
                return null;
            }
            case "setTabListHeader" -> {
                setTabListHeader(player, !args.isEmpty() ? String.valueOf(args.get(0)) : "");
                return null;
            }
            case "setTabListFooter" -> {
                setTabListFooter(player, !args.isEmpty() ? String.valueOf(args.get(0)) : "");
                return null;
            }
            case "getTabListHeader" -> {
                return getTabListHeader(player);
            }
            case "getTabListFooter" -> {
                return getTabListFooter(player);
            }
            case "setResourcePack" -> {
                if (args.isEmpty()) return null;
                String url = String.valueOf(args.get(0));
                String hash = args.size() > 1 && args.get(1) != null ? String.valueOf(args.get(1)) : "";
                boolean required = args.size() > 2 && args.get(2) instanceof Boolean b && b;
                String prompt = args.size() > 3 && args.get(3) != null ? String.valueOf(args.get(3)) : null;
                if (prompt != null) {
                    player.setResourcePack(url, hash, required, Component.text(prompt));
                } else {
                    player.setResourcePack(url, hash, required, null);
                }
                return null;
            }
            case "hidePlayer" -> {
                if (!args.isEmpty() && args.get(0) instanceof Player other) {
                    player.hidePlayer(plugin, other);
                }
                return null;
            }
            case "showPlayer" -> {
                if (!args.isEmpty() && args.get(0) instanceof Player other) {
                    player.showPlayer(plugin, other);
                }
                return null;
            }
            case "canSee" -> {
                if (!args.isEmpty() && args.get(0) instanceof Player other) {
                    return player.canSee(other);
                }
                return false;
            }
            case "openBook" -> {
                if (!args.isEmpty() && args.get(0) instanceof ItemStack book) {
                    player.openBook(book);
                }
                return null;
            }
            case "sendBlockChange" -> {
                if (args.size() >= 2) {
                    Location loc = toLocation(args.get(0), player);
                    if (loc != null) {
                        Object matArg = args.get(1);
                        org.bukkit.block.data.BlockData blockData;
                        if (matArg instanceof org.bukkit.block.data.BlockData bd) {
                            blockData = bd;
                        } else {
                            String matName = matArg instanceof EnumValue ev ? ev.name : String.valueOf(matArg);
                            blockData = Bukkit.createBlockData(Material.matchMaterial(matName));
                        }
                        player.sendBlockChange(loc, blockData);
                    }
                }
                return null;
            }
            case "sendParticle" -> {
                if (args.size() >= 2) {
                    Object particleArg = args.get(0);
                    String particleName = particleArg instanceof EnumValue ev ? ev.name : String.valueOf(particleArg);
                    Particle particle;
                    try {
                        particle = Particle.valueOf(particleName.toUpperCase());
                    } catch (IllegalArgumentException ex) {
                        throw new IllegalArgumentException("Unknown particle: " + particleName);
                    }
                    Location loc = toLocation(args.get(1), player);
                    int count = args.size() > 2 && args.get(2) instanceof Number n ? n.intValue() : 1;
                    double offX = args.size() > 3 && args.get(3) instanceof Number n ? n.doubleValue() : 0;
                    double offY = args.size() > 4 && args.get(4) instanceof Number n ? n.doubleValue() : 0;
                    double offZ = args.size() > 5 && args.get(5) instanceof Number n ? n.doubleValue() : 0;
                    double extra = args.size() > 6 && args.get(6) instanceof Number n ? n.doubleValue() : 0;
                    if (loc != null) {
                        player.spawnParticle(particle, loc, count, offX, offY, offZ, extra);
                    }
                }
                return null;
            }
            case "getCooldown" -> {
                if (!args.isEmpty()) {
                    String matName = args.get(0) instanceof EnumValue ev ? ev.name : String.valueOf(args.get(0));
                    Material mat = Material.matchMaterial(matName);
                    if (mat != null) return player.getCooldown(mat);
                }
                return 0;
            }
            case "setCooldown" -> {
                if (args.size() >= 2) {
                    String matName = args.get(0) instanceof EnumValue ev ? ev.name : String.valueOf(args.get(0));
                    Material mat = Material.matchMaterial(matName);
                    int ticks = ((Number) args.get(1)).intValue();
                    if (mat != null) player.setCooldown(mat, ticks);
                }
                return null;
            }
            case "hasCooldown" -> {
                if (!args.isEmpty()) {
                    String matName = args.get(0) instanceof EnumValue ev ? ev.name : String.valueOf(args.get(0));
                    Material mat = Material.matchMaterial(matName);
                    if (mat != null) return player.hasCooldown(mat);
                }
                return false;
            }
            case "getStatistic" -> {
                if (!args.isEmpty()) {
                    String statName = args.get(0) instanceof EnumValue ev ? ev.name : String.valueOf(args.get(0));
                    Statistic stat = Statistic.valueOf(statName.toUpperCase());
                    if (args.size() == 1) {
                        return player.getStatistic(stat);
                    } else if (args.size() >= 2) {
                        String arg2 = args.get(1) instanceof EnumValue ev ? ev.name : String.valueOf(args.get(1));
                        Material mat = Material.matchMaterial(arg2);
                        if (mat != null) return player.getStatistic(stat, mat);
                        EntityType et = EntityType.valueOf(arg2.toUpperCase());
                        return player.getStatistic(stat, et);
                    }
                }
                return 0;
            }
            case "setStatistic" -> {
                if (args.size() >= 2) {
                    String statName = args.get(0) instanceof EnumValue ev ? ev.name : String.valueOf(args.get(0));
                    Statistic stat = Statistic.valueOf(statName.toUpperCase());
                    if (args.size() == 2) {
                        player.setStatistic(stat, ((Number) args.get(1)).intValue());
                    } else if (args.size() >= 3) {
                        int val = ((Number) args.get(2)).intValue();
                        String arg2 = args.get(1) instanceof EnumValue ev ? ev.name : String.valueOf(args.get(1));
                        Material mat = Material.matchMaterial(arg2);
                        if (mat != null) {
                            player.setStatistic(stat, mat, val);
                        } else {
                            EntityType et = EntityType.valueOf(arg2.toUpperCase());
                            player.setStatistic(stat, et, val);
                        }
                    }
                }
                return null;
            }
            case "getMaxHealth" -> {
                org.bukkit.attribute.AttributeInstance attr = player.getAttribute(org.bukkit.attribute.Attribute.MAX_HEALTH);
                return attr != null ? attr.getValue() : 20.0;
            }
            case "setMaxHealth" -> {
                if (!args.isEmpty() && args.get(0) instanceof Number n) {
                    org.bukkit.attribute.AttributeInstance attr = player.getAttribute(org.bukkit.attribute.Attribute.MAX_HEALTH);
                    if (attr != null) attr.setBaseValue(n.doubleValue());
                }
                return null;
            }
            case "getBedSpawnLocation" -> {
                return player.getRespawnLocation();
            }
            case "setBedSpawnLocation" -> {
                if (!args.isEmpty()) {
                    Location loc = toLocation(args.get(0), player);
                    boolean force = args.size() > 1 && Boolean.TRUE.equals(args.get(1));
                    player.setRespawnLocation(loc, force);
                }
                return null;
            }
            case "getCompassTarget" -> {
                return player.getCompassTarget();
            }
            case "setCompassTarget" -> {
                if (!args.isEmpty()) {
                    Location loc = toLocation(args.get(0), player);
                    if (loc != null) player.setCompassTarget(loc);
                }
                return null;
            }
            case "getPDC", "getPersistentData" -> {
                PersistentDataContainer pdc = player.getPersistentDataContainer();
                Map<String, Object> result = new java.util.HashMap<>();
                for (NamespacedKey key : pdc.getKeys()) {
                    Object val = pdc.get(key, PersistentDataType.STRING);
                    if (val != null) result.put(key.toString(), val);
                }
                return result;
            }
            case "setPDC", "setPersistentData" -> {
                if (args.size() >= 2) {
                    String keyStr = String.valueOf(args.get(0));
                    NamespacedKey key = new NamespacedKey(plugin, keyStr);
                    String val = String.valueOf(args.get(1));
                    player.getPersistentDataContainer().set(key, PersistentDataType.STRING, val);
                }
                return null;
            }
            case "removePDC", "removePersistentData" -> {
                if (!args.isEmpty()) {
                    String keyStr = String.valueOf(args.get(0));
                    NamespacedKey key = new NamespacedKey(plugin, keyStr);
                    player.getPersistentDataContainer().remove(key);
                }
                return null;
            }
            case "hasPDC", "hasPersistentData" -> {
                if (!args.isEmpty()) {
                    String keyStr = String.valueOf(args.get(0));
                    NamespacedKey key = new NamespacedKey(plugin, keyStr);
                    return player.getPersistentDataContainer().has(key, PersistentDataType.STRING);
                }
                return false;
            }
        }
        return UNHANDLED;
    }

    private Object invokeMobMethod(Entity entity, String method, List<Object> args) {
        if (!(entity instanceof org.bukkit.entity.Mob mob)) return UNHANDLED;
        switch (method) {
            case "getTarget" -> { return mob.getTarget(); }
            case "setTarget" -> {
                if (args.size() >= 1 && args.get(0) instanceof org.bukkit.entity.LivingEntity le) {
                    mob.setTarget(le);
                } else {
                    mob.setTarget(null);
                }
                return null;
            }
            case "isAware" -> { return mob.isAware(); }
            case "setAware" -> {
                mob.setAware(args.size() >= 1 && Boolean.TRUE.equals(args.get(0)));
                return null;
            }
            case "pathfindTo" -> {
                if (args.isEmpty()) return null;
                Location loc = toLocation(args.get(0), mob);
                if (loc == null) return false;
                double speed = args.size() >= 2 ? ((Number) args.get(1)).doubleValue() : 1.0;
                com.destroystokyo.paper.entity.Pathfinder pathfinder = mob.getPathfinder();
                if (pathfinder != null) {
                    return pathfinder.moveTo(loc, speed);
                }
                return false;
            }
            case "stopPathfinding" -> {
                com.destroystokyo.paper.entity.Pathfinder pathfinder = mob.getPathfinder();
                if (pathfinder != null) {
                    pathfinder.stopPathfinding();
                }
                return null;
            }
            case "hasLineOfSight" -> {
                if (args.size() >= 1 && args.get(0) instanceof Entity other) {
                    return mob.hasLineOfSight(other);
                }
                return false;
            }
            case "lookAt" -> {
                if (args.size() >= 1) {
                    Location loc = toLocation(args.get(0), mob);
                    if (loc != null) {
                        Location mobLoc = mob.getLocation();
                        double dx = loc.getX() - mobLoc.getX();
                        double dy = loc.getY() - mobLoc.getY();
                        double dz = loc.getZ() - mobLoc.getZ();
                        double dist = Math.sqrt(dx * dx + dz * dz);
                        float yaw = (float) Math.toDegrees(Math.atan2(-dx, dz));
                        float pitch = (float) Math.toDegrees(-Math.atan2(dy, dist));
                        mob.setRotation(yaw, pitch);
                    }
                }
                return null;
            }
            case "getGoalTypes" -> {
                com.destroystokyo.paper.entity.ai.MobGoals goals = Bukkit.getMobGoals();
                var allGoals = goals.getAllGoals(mob);
                List<String> names = new ArrayList<>(allGoals.size());
                for (var goal : allGoals) {
                    names.add(goal.getKey().getNamespacedKey().getKey());
                }
                return names;
            }
            case "removeGoal" -> {
                if (!args.isEmpty()) {
                    String goalKey = String.valueOf(args.get(0));
                    com.destroystokyo.paper.entity.ai.MobGoals goals = Bukkit.getMobGoals();
                    var allGoals = goals.getAllGoals(mob);
                    for (var goal : allGoals) {
                        if (goal.getKey().getNamespacedKey().getKey().equals(goalKey)) {
                            goals.removeGoal(mob, goal);
                            return true;
                        }
                    }
                }
                return false;
            }
            case "removeAllGoals" -> {
                com.destroystokyo.paper.entity.ai.MobGoals goals = Bukkit.getMobGoals();
                goals.removeAllGoals(mob);
                return null;
            }
            // ── Villager trades ──────────────────────────────────────
            case "getRecipes" -> {
                if (!(mob instanceof org.bukkit.entity.AbstractVillager villager)) return UNHANDLED;
                List<org.bukkit.inventory.MerchantRecipe> recipes = villager.getRecipes();
                List<Map<String, Object>> result = new ArrayList<>(recipes.size());
                for (org.bukkit.inventory.MerchantRecipe recipe : recipes) {
                    result.add(serializeMerchantRecipe(recipe));
                }
                return result;
            }
            case "getRecipeCount" -> {
                if (!(mob instanceof org.bukkit.entity.AbstractVillager villager)) return UNHANDLED;
                return villager.getRecipeCount();
            }
            case "setRecipes" -> {
                if (!(mob instanceof org.bukkit.entity.AbstractVillager villager)) return UNHANDLED;
                if (args.isEmpty()) return null;
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> recipeMaps = (List<Map<String, Object>>) args.get(0);
                List<org.bukkit.inventory.MerchantRecipe> recipes = new ArrayList<>(recipeMaps.size());
                for (Map<String, Object> map : recipeMaps) {
                    org.bukkit.inventory.MerchantRecipe recipe = deserializeMerchantRecipe(map);
                    if (recipe != null) recipes.add(recipe);
                }
                villager.setRecipes(recipes);
                return null;
            }
            case "addRecipe" -> {
                if (!(mob instanceof org.bukkit.entity.AbstractVillager villager)) return UNHANDLED;
                if (args.isEmpty()) return null;
                @SuppressWarnings("unchecked")
                Map<String, Object> recipeMap = (Map<String, Object>) args.get(0);
                org.bukkit.inventory.MerchantRecipe recipe = deserializeMerchantRecipe(recipeMap);
                if (recipe != null) {
                    List<org.bukkit.inventory.MerchantRecipe> recipes = new ArrayList<>(villager.getRecipes());
                    recipes.add(recipe);
                    villager.setRecipes(recipes);
                }
                return null;
            }
            case "clearRecipes" -> {
                if (!(mob instanceof org.bukkit.entity.AbstractVillager villager)) return UNHANDLED;
                villager.setRecipes(List.of());
                return null;
            }
        }
        return UNHANDLED;
    }

    private Object invokeItemStackMethod(ItemStack itemStack, String method, List<Object> args) {
        ItemMeta meta = itemStack.getItemMeta();
        switch (method) {
            case "getName" -> {
                if (meta != null && meta.hasDisplayName()) {
                    return PlainTextComponentSerializer.plainText().serialize(meta.displayName());
                }
                return null;
            }
            case "setName" -> {
                if (meta != null && !args.isEmpty()) {
                    meta.displayName(Component.text(String.valueOf(args.get(0))));
                    itemStack.setItemMeta(meta);
                }
                return null;
            }
            case "getLore" -> {
                if (meta != null && meta.hasLore()) {
                    List<Component> lore = meta.lore();
                    if (lore == null) {
                        return List.of();
                    }
                    List<String> loreText = new ArrayList<>(lore.size());
                    for (Component component : lore) {
                        loreText.add(PlainTextComponentSerializer.plainText().serialize(component));
                    }
                    return loreText;
                }
                return List.of();
            }
            case "setLore" -> {
                if (meta != null && !args.isEmpty()) {
                    Object loreArg = args.get(0);
                    List<Component> loreComponents;
                    if (loreArg instanceof List<?> loreList) {
                        loreComponents = new ArrayList<>(loreList.size());
                        for (Object entry : loreList) {
                            if (entry != null) {
                                loreComponents.add(Component.text(entry.toString()));
                            }
                        }
                    } else {
                        loreComponents = List.of();
                    }
                    meta.lore(loreComponents);
                    itemStack.setItemMeta(meta);
                }
                return null;
            }
            case "getCustomModelData" -> {
                if (meta != null && meta.hasCustomModelData()) {
                    return meta.getCustomModelData();
                }
                return null;
            }
            case "setCustomModelData" -> {
                if (meta != null && !args.isEmpty() && args.get(0) instanceof Number number) {
                    meta.setCustomModelData(number.intValue());
                    itemStack.setItemMeta(meta);
                }
                return null;
            }
            case "getAttributes" -> {
                return meta != null ? serializer.attributeList(meta) : List.of();
            }
            case "setAttributes" -> {
                if (meta != null && !args.isEmpty()) {
                    serializer.applyAttributes(meta, gson.toJsonTree(args.get(0)));
                    itemStack.setItemMeta(meta);
                }
                return null;
            }
            case "getNbt" -> {
                return itemStack.serialize();
            }
            case "setNbt" -> {
                if (!args.isEmpty()) {
                    ItemStack deserialized = serializer.deserializeItemFromNbt(gson.toJsonTree(args.get(0)));
                    if (deserialized != null) {
                        try {
                            Method setType = ItemStack.class.getMethod("setType", Material.class);
                            setType.invoke(itemStack, deserialized.getType());
                        } catch (Exception ignored) {
                        }
                        itemStack.setAmount(deserialized.getAmount());
                        if (deserialized.hasItemMeta()) {
                            itemStack.setItemMeta(deserialized.getItemMeta());
                        }
                    }
                }
                return null;
            }
            case "getDurability" -> {
                if (meta instanceof Damageable dmg) {
                    return dmg.getDamage();
                }
                return 0;
            }
            case "setDurability" -> {
                if (meta instanceof Damageable dmg && !args.isEmpty() && args.get(0) instanceof Number n) {
                    dmg.setDamage(n.intValue());
                    itemStack.setItemMeta(dmg);
                }
                return null;
            }
            case "getMaxDurability" -> {
                return (int) itemStack.getType().getMaxDurability();
            }
            case "getEnchantments" -> {
                Map<String, Integer> result = new java.util.HashMap<>();
                for (Map.Entry<Enchantment, Integer> e : itemStack.getEnchantments().entrySet()) {
                    result.put(e.getKey().getKey().getKey(), e.getValue());
                }
                return result;
            }
            case "addEnchantment" -> {
                if (args.size() >= 2) {
                    String enchName = args.get(0) instanceof EnumValue ev ? ev.name : String.valueOf(args.get(0));
                    int level = ((Number) args.get(1)).intValue();
                    Registry<Enchantment> enchReg = RegistryAccess.registryAccess().getRegistry(RegistryKey.ENCHANTMENT);
                    Enchantment ench = enchReg.get(NamespacedKey.minecraft(enchName.toLowerCase()));
                    if (ench != null) {
                        meta.addEnchant(ench, level, true);
                        itemStack.setItemMeta(meta);
                    }
                }
                return null;
            }
            case "removeEnchantment" -> {
                if (!args.isEmpty()) {
                    String enchName = args.get(0) instanceof EnumValue ev ? ev.name : String.valueOf(args.get(0));
                    Registry<Enchantment> enchReg = RegistryAccess.registryAccess().getRegistry(RegistryKey.ENCHANTMENT);
                    Enchantment ench = enchReg.get(NamespacedKey.minecraft(enchName.toLowerCase()));
                    if (ench != null) itemStack.removeEnchantment(ench);
                }
                return null;
            }
            case "getItemFlags" -> {
                if (meta != null) {
                    var itemFlags = meta.getItemFlags();
                    List<String> flags = new ArrayList<>(itemFlags.size());
                    for (ItemFlag f : itemFlags) {
                        flags.add(f.name());
                    }
                    return flags;
                }
                return List.of();
            }
            case "addItemFlags" -> {
                if (meta != null && !args.isEmpty()) {
                    for (Object arg : args) {
                        String flagName = arg instanceof EnumValue ev ? ev.name : String.valueOf(arg);
                        meta.addItemFlags(ItemFlag.valueOf(flagName.toUpperCase()));
                    }
                    itemStack.setItemMeta(meta);
                }
                return null;
            }
            case "removeItemFlags" -> {
                if (meta != null && !args.isEmpty()) {
                    for (Object arg : args) {
                        String flagName = arg instanceof EnumValue ev ? ev.name : String.valueOf(arg);
                        meta.removeItemFlags(ItemFlag.valueOf(flagName.toUpperCase()));
                    }
                    itemStack.setItemMeta(meta);
                }
                return null;
            }
            case "isUnbreakable" -> {
                return meta != null && meta.isUnbreakable();
            }
            case "setUnbreakable" -> {
                if (meta != null && !args.isEmpty()) {
                    meta.setUnbreakable(Boolean.TRUE.equals(args.get(0)));
                    itemStack.setItemMeta(meta);
                }
                return null;
            }
        }
        return UNHANDLED;
    }

    private Object invokeServerMethod(org.bukkit.Server server, String method, List<Object> args) {
        if ("execute".equals(method) && !args.isEmpty()) {
            String commandLine = String.valueOf(args.get(0));
            if (commandLine.startsWith("/")) {
                commandLine = commandLine.substring(1);
            }
            return server.dispatchCommand(Bukkit.getConsoleSender(), commandLine);
        }
        if ("broadcastMessage".equals(method) && !args.isEmpty()) {
            plugin.getLogger().info("[broadcast] " + args.get(0));
        }
        // Recipe methods
        if ("addShapedRecipe".equals(method) && args.size() >= 4) {
            return addShapedRecipe(args);
        }
        if ("addShapelessRecipe".equals(method) && args.size() >= 3) {
            return addShapelessRecipe(args);
        }
        if ("addFurnaceRecipe".equals(method) && args.size() >= 3) {
            return addFurnaceRecipe(args);
        }
        if ("removeRecipe".equals(method) && args.size() >= 1) {
            String key = String.valueOf(args.get(0));
            return Bukkit.removeRecipe(new NamespacedKey(plugin, key));
        }
        if ("getAllEnchantments".equals(method)) {
            List<String> names = new ArrayList<>(40);
            Registry<org.bukkit.enchantments.Enchantment> enchReg = RegistryAccess.registryAccess().getRegistry(RegistryKey.ENCHANTMENT);
            for (org.bukkit.enchantments.Enchantment ench : enchReg) {
                names.add(ench.getKey().getKey().toUpperCase());
            }
            return names;
        }
        if ("getEnchantmentsForItem".equals(method) && args.size() >= 1) {
            String materialName = String.valueOf(args.get(0)).toUpperCase();
            Material mat = Material.valueOf(materialName);
            ItemStack testItem = new ItemStack(mat);
            List<String> names = new ArrayList<>(16);
            Registry<org.bukkit.enchantments.Enchantment> enchReg2 = RegistryAccess.registryAccess().getRegistry(RegistryKey.ENCHANTMENT);
            for (org.bukkit.enchantments.Enchantment ench : enchReg2) {
                if (ench.canEnchantItem(testItem)) {
                    names.add(ench.getKey().getKey().toUpperCase());
                }
            }
            return names;
        }
        // Packet API
        if ("listenPacketSend".equals(method) && args.size() >= 1) {
            if (!plugin.hasPacketBridge()) return "ProtocolLib not available";
            String packetName = String.valueOf(args.get(0));
            plugin.getPacketBridge().listenSend(packetName, (player, data) -> {
                JsonObject payload = new JsonObject();
                payload.addProperty("direction", "send");
                payload.addProperty("packet_type", packetName);
                payload.add("fields", data);
                payload.add("player", serializer.serialize(player));
                eventDispatcher.sendEvent("packet_send", payload);
            });
            return true;
        }
        if ("listenPacketReceive".equals(method) && args.size() >= 1) {
            if (!plugin.hasPacketBridge()) return "ProtocolLib not available";
            String packetName = String.valueOf(args.get(0));
            plugin.getPacketBridge().listenReceive(packetName, (player, data) -> {
                JsonObject payload = new JsonObject();
                payload.addProperty("direction", "receive");
                payload.addProperty("packet_type", packetName);
                payload.add("fields", data);
                payload.add("player", serializer.serialize(player));
                eventDispatcher.sendEvent("packet_receive", payload);
            });
            return true;
        }
        if ("removePacketListener".equals(method) && args.size() >= 1) {
            if (!plugin.hasPacketBridge()) return "ProtocolLib not available";
            plugin.getPacketBridge().removeListener(String.valueOf(args.get(0)));
            return true;
        }
        if ("sendPacket".equals(method) && args.size() >= 3) {
            if (!plugin.hasPacketBridge()) return "ProtocolLib not available";
            Object playerObj = args.get(0);
            String packetName = String.valueOf(args.get(1));
            Object fieldsObj = args.get(2);
            if (playerObj instanceof org.bukkit.entity.Player player && fieldsObj instanceof Map<?,?> map) {
                JsonObject fields = new JsonObject();
                for (Map.Entry<?, ?> entry : map.entrySet()) {
                    String k = String.valueOf(entry.getKey());
                    Object v = entry.getValue();
                    if (v instanceof Number n) fields.addProperty(k, n);
                    else if (v instanceof Boolean b) fields.addProperty(k, b);
                    else if (v instanceof String s) fields.addProperty(k, s);
                }
                plugin.getPacketBridge().sendPacket(player, packetName, fields);
            }
            return true;
        }
        if ("hasPacketApi".equals(method)) {
            return plugin.hasPacketBridge();
        }
        // StructureManager
        if ("saveStructure".equals(method) && args.size() >= 5) {
            String structName = String.valueOf(args.get(0));
            NamespacedKey key = new NamespacedKey(plugin, structName);
            org.bukkit.structure.StructureManager mgr = Bukkit.getStructureManager();
            org.bukkit.structure.Structure structure = mgr.createStructure();
            World w = Bukkit.getWorld(String.valueOf(args.get(1)));
            if (w == null) return null;
            int x1 = ((Number) args.get(2)).intValue();
            int y1 = ((Number) args.get(3)).intValue();
            int z1 = ((Number) args.get(4)).intValue();
            int x2 = args.size() > 7 ? ((Number) args.get(5)).intValue() : x1;
            int y2 = args.size() > 7 ? ((Number) args.get(6)).intValue() : y1;
            int z2 = args.size() > 7 ? ((Number) args.get(7)).intValue() : z1;
            org.bukkit.util.BlockVector size = new org.bukkit.util.BlockVector(
                Math.abs(x2 - x1) + 1, Math.abs(y2 - y1) + 1, Math.abs(z2 - z1) + 1);
            structure.fill(new Location(w, Math.min(x1, x2), Math.min(y1, y2), Math.min(z1, z2)), size, true);
            try {
                mgr.saveStructure(key, structure);
            } catch (Exception e) {
                return "Error: " + e.getMessage();
            }
            return structName;
        }
        if ("loadStructure".equals(method) && args.size() >= 5) {
            String structName = String.valueOf(args.get(0));
            NamespacedKey key = new NamespacedKey(plugin, structName);
            org.bukkit.structure.StructureManager mgr = Bukkit.getStructureManager();
            org.bukkit.structure.Structure structure;
            try {
                structure = mgr.loadStructure(key);
            } catch (Exception e) {
                return "Error: " + e.getMessage();
            }
            if (structure == null) return "Error: Structure not found";
            World w = Bukkit.getWorld(String.valueOf(args.get(1)));
            if (w == null) return "Error: World not found";
            Location loc = new Location(w,
                ((Number) args.get(2)).doubleValue(),
                ((Number) args.get(3)).doubleValue(),
                ((Number) args.get(4)).doubleValue());
            boolean includeEntities = args.size() > 5 && Boolean.TRUE.equals(args.get(5));
            structure.place(loc, includeEntities, org.bukkit.block.structure.StructureRotation.NONE,
                org.bukkit.block.structure.Mirror.NONE, 0, 1.0f, new java.util.Random());
            return structName;
        }
        if ("deleteStructure".equals(method) && !args.isEmpty()) {
            String structName = String.valueOf(args.get(0));
            NamespacedKey key = new NamespacedKey(plugin, structName);
            try {
                Bukkit.getStructureManager().deleteStructure(key);
            } catch (Exception e) {
                return "Error: " + e.getMessage();
            }
            return true;
        }
        if ("listStructures".equals(method)) {
            Map<NamespacedKey, org.bukkit.structure.Structure> all = Bukkit.getStructureManager().getStructures();
            List<String> names = new ArrayList<>(all.size());
            for (NamespacedKey k : all.keySet()) {
                names.add(k.getKey());
            }
            return names;
        }
        // WorldCreator
        if ("createWorld".equals(method) && !args.isEmpty()) {
            Map<?, ?> opts = args.get(0) instanceof Map<?, ?> m ? m : Map.of("name", String.valueOf(args.get(0)));
            String worldName = String.valueOf(opts.get("name"));
            org.bukkit.WorldCreator creator = new org.bukkit.WorldCreator(worldName);
            if (opts.containsKey("environment")) {
                creator.environment(World.Environment.valueOf(String.valueOf(opts.get("environment")).toUpperCase()));
            }
            if (opts.containsKey("type")) {
                creator.type(org.bukkit.WorldType.valueOf(String.valueOf(opts.get("type")).toUpperCase()));
            }
            if (opts.containsKey("seed")) {
                creator.seed(((Number) opts.get("seed")).longValue());
            }
            if (opts.containsKey("generate_structures")) {
                creator.generateStructures(Boolean.TRUE.equals(opts.get("generate_structures")));
            }
            World w = creator.createWorld();
            return w;
        }
        if ("deleteWorld".equals(method) && !args.isEmpty()) {
            String worldName = String.valueOf(args.get(0));
            World w = Bukkit.getWorld(worldName);
            if (w != null) {
                return Bukkit.unloadWorld(w, false);
            }
            return false;
        }
        if ("getWorlds".equals(method)) {
            return new ArrayList<>(Bukkit.getWorlds());
        }
        return UNHANDLED;
    }

    @SuppressWarnings("unchecked")
    private Object addShapedRecipe(List<Object> args) {
        String key = String.valueOf(args.get(0));
        String resultMaterial = String.valueOf(args.get(1));
        int resultAmount = args.size() > 4 ? ((Number) args.get(4)).intValue() : 1;
        List<String> shape = (List<String>) args.get(2);
        Map<String, Object> ingredients = (Map<String, Object>) args.get(3);

        ItemStack result = new ItemStack(Material.valueOf(resultMaterial.toUpperCase()), resultAmount);
        NamespacedKey recipeKey = new NamespacedKey(plugin, key);
        ShapedRecipe recipe = new ShapedRecipe(recipeKey, result);
        recipe.shape(shape.toArray(new String[0]));

        for (Map.Entry<String, Object> entry : ingredients.entrySet()) {
            char c = entry.getKey().charAt(0);
            Material mat = Material.valueOf(String.valueOf(entry.getValue()).toUpperCase());
            recipe.setIngredient(c, mat);
        }

        Bukkit.addRecipe(recipe);
        return key;
    }

    @SuppressWarnings("unchecked")
    private Object addShapelessRecipe(List<Object> args) {
        String key = String.valueOf(args.get(0));
        String resultMaterial = String.valueOf(args.get(1));
        int resultAmount = args.size() > 3 ? ((Number) args.get(3)).intValue() : 1;
        List<String> ingredients = (List<String>) args.get(2);

        ItemStack result = new ItemStack(Material.valueOf(resultMaterial.toUpperCase()), resultAmount);
        NamespacedKey recipeKey = new NamespacedKey(plugin, key);
        ShapelessRecipe recipe = new ShapelessRecipe(recipeKey, result);

        for (String mat : ingredients) {
            recipe.addIngredient(Material.valueOf(mat.toUpperCase()));
        }

        Bukkit.addRecipe(recipe);
        return key;
    }

    private Object addFurnaceRecipe(List<Object> args) {
        String key = String.valueOf(args.get(0));
        String inputMaterial = String.valueOf(args.get(1));
        String resultMaterial = String.valueOf(args.get(2));
        int resultAmount = args.size() > 5 ? ((Number) args.get(5)).intValue() : 1;
        float experience = args.size() > 3 ? ((Number) args.get(3)).floatValue() : 0f;
        int cookTime = args.size() > 4 ? ((Number) args.get(4)).intValue() : 200;

        ItemStack result = new ItemStack(Material.valueOf(resultMaterial.toUpperCase()), resultAmount);
        NamespacedKey recipeKey = new NamespacedKey(plugin, key);
        FurnaceRecipe recipe = new FurnaceRecipe(recipeKey, result, Material.valueOf(inputMaterial.toUpperCase()), experience, cookTime);

        Bukkit.addRecipe(recipe);
        return key;
    }

    private Object invokeDisplayMethod(Object target, String method, List<Object> args) {
        if (target instanceof TextDisplay textDisplay && "text".equals(method) && args.size() == 1) {
            if (args.get(0) instanceof String str) {
                textDisplay.text(str.contains("<")
                        ? MiniMessage.miniMessage().deserialize(str)
                        : Component.text(str));
                return null;
            }
        }
        if (target instanceof Display display && "setTransform".equals(method) && args.size() == 6) {
            float tx = args.get(0) instanceof Number n ? n.floatValue() : 0f;
            float ty = args.get(1) instanceof Number n ? n.floatValue() : 0f;
            float tz = args.get(2) instanceof Number n ? n.floatValue() : 0f;
            float sx = args.get(3) instanceof Number n ? n.floatValue() : 1f;
            float sy = args.get(4) instanceof Number n ? n.floatValue() : 1f;
            float sz = args.get(5) instanceof Number n ? n.floatValue() : 1f;
            Quaternionf identity = new Quaternionf(0, 0, 0, 1);
            display.setTransformation(new Transformation(
                    new Vector3f(tx, ty, tz), identity, new Vector3f(sx, sy, sz), new Quaternionf(identity)));
            return null;
        }
        if (target instanceof TextDisplay textDisplay && "setBackgroundColor".equals(method) && args.size() == 1) {
            if (args.get(0) instanceof Number number) {
                int argb = number.intValue();
                textDisplay.setBackgroundColor(Color.fromARGB(
                        (argb >> 24) & 0xFF, (argb >> 16) & 0xFF, (argb >> 8) & 0xFF, argb & 0xFF));
                return null;
            }
        }
        return UNHANDLED;
    }

    // #2: Cache getMethods() per class to avoid repeated reflection
    private static final ConcurrentHashMap<Class<?>, Method[]> reflectiveMethodsCache = new ConcurrentHashMap<>();

    private Object invokeReflective(Object target, String method, List<Object> args) throws Exception {
        // Try exact name first, then snake_case → camelCase variants (get prefix, is prefix, plain)
        String[] candidates = methodNameCandidates(method);
        Method[] methods = reflectiveMethodsCache.computeIfAbsent(target.getClass(), Class::getMethods);
        for (String name : candidates) {
            for (Method candidate : methods) {
                if (!candidate.getName().equals(name)) {
                    continue;
                }
                int paramCount = candidate.getParameterCount();
                boolean isVarArgs = candidate.isVarArgs();
                // Match exact count, or varargs where args cover all fixed params
                if (!isVarArgs && paramCount != args.size()) {
                    continue;
                }
                if (isVarArgs && args.size() < paramCount - 1) {
                    continue;
                }
                // For varargs with fewer args than params, pad with empty varargs array
                List<Object> effectiveArgs = args;
                if (isVarArgs && args.size() < paramCount) {
                    effectiveArgs = new java.util.ArrayList<>(args);
                    Class<?> componentType = candidate.getParameterTypes()[paramCount - 1].getComponentType();
                    effectiveArgs.add(java.lang.reflect.Array.newInstance(componentType, 0));
                }
                Object[] converted = serializer.convertArgs(candidate.getParameterTypes(), effectiveArgs);
                if (converted != null) {
                    try {
                        return candidate.invoke(target, converted);
                    } catch (InvocationTargetException ex) {
                        Throwable cause = ex.getCause();
                        if (cause instanceof Exception exception) {
                            throw exception;
                        }
                        throw ex;
                    }
                }
            }
        }
        throw new NoSuchMethodException("Method not found: " + method + " on " + target.getClass().getName());
    }

    /**
     * Build candidate Java method names from a Python-style name.
     * e.g. "new_slot" → ["new_slot", "getNewSlot", "isNewSlot", "newSlot"]
     */
    private static String[] methodNameCandidates(String pythonName) {
        if (!pythonName.contains("_")) {
            return new String[] { pythonName };
        }
        String camel = snakeToCamel(pythonName);
        String pascal = Character.toUpperCase(camel.charAt(0)) + camel.substring(1);
        return new String[] { pythonName, "get" + pascal, "is" + pascal, camel };
    }

    private static String snakeToCamel(String snake) {
        StringBuilder sb = new StringBuilder();
        boolean upper = false;
        for (int i = 0; i < snake.length(); i++) {
            char c = snake.charAt(i);
            if (c == '_') {
                upper = true;
            } else {
                sb.append(upper ? Character.toUpperCase(c) : c);
                upper = false;
            }
        }
        return sb.toString();
    }

    private Object resolveTarget(String targetName, JsonObject argsObj) throws Exception {
        return switch (targetName) {
            case "server" -> Bukkit.getServer();
            case "chat" -> chatFacade;
            case "raycast" -> raycastFacade;
            case "permissions" -> permissionsFacade;
            case "metrics" -> metricsFacade;
            case "ref" -> refFacade;
            case "reflect" -> reflectFacade;
            case "commands" -> commandsFacade;
            case "region" -> regionFacade;
            case "particle" -> particleFacade;
            default -> throw new IllegalArgumentException("Unknown target: " + targetName);
        };
    }

    private Sound resolveSound(Object arg) {
        if (arg instanceof Sound sound) {
            return sound;
        }
        String name = null;

        if (arg instanceof EnumValue enumValue) {
            name = enumValue.name;

        } else if (arg instanceof String text) {
            name = text;
        }

        if (name != null) {
            String keyText = name.toLowerCase();
            NamespacedKey key = keyText.contains(":")
                    ? NamespacedKey.fromString(keyText)
                    : NamespacedKey.minecraft(keyText);

            if (key != null) {
                try {
                    for (Field field : Registry.class.getFields()) {
                        if (!Registry.class.isAssignableFrom(field.getType())) {
                            continue;
                        }

                        String fieldName = field.getName().toLowerCase();

                        if (!fieldName.contains("sound")) {
                            continue;
                        }

                        Object registryObj = field.get(null);

                        if (registryObj instanceof Registry<?> registry) {
                            Object value = registry.get(key);
                            if (value instanceof Sound sound) {
                                return sound;
                            }
                        }
                    }
                } catch (Exception ignored) {
                }
            }

            String enumName = name.toUpperCase().replace(':', '_').replace('.', '_');
            enumName = enumName.replaceAll("[^A-Z0-9_]+", "_");

            try {
                Method valueOf = Sound.class.getMethod("valueOf", String.class);
                Object soundObj = valueOf.invoke(null, enumName);
                if (soundObj instanceof Sound sound) {
                    return sound;
                }
            } catch (Exception ignored) {
            }
        }
        return null;
    }

    private String getTabListHeader(Player player) {
        return getTabListValue(player, true);
    }

    private String getTabListFooter(Player player) {
        return getTabListValue(player, false);
    }

    private String getTabListValue(Player player, boolean header) {
        Object value = null;
        String[] methodNames = header
                ? new String[] { "getPlayerListHeader", "playerListHeader" }
                : new String[] { "getPlayerListFooter", "playerListFooter" };

        for (String name : methodNames) {
            try {
                Method method = player.getClass().getMethod(name);
                value = method.invoke(player);
                break;
            } catch (Exception ignored) {
            }
        }

        if (value instanceof Component component) {
            return PlainTextComponentSerializer.plainText().serialize(component);
        }
        return value != null ? value.toString() : "";
    }

    private void setTabListHeader(Player player, String header) {
        if (tryTabListSetter(player, header, null, true)) {
            return;
        }
        Component headerComponent = Component.text(header == null ? "" : header);
        tryTabListSetter(player, headerComponent, null, true);
    }

    private void setTabListFooter(Player player, String footer) {
        if (tryTabListSetter(player, footer, null, false)) {
            return;
        }
        Component footerComponent = Component.text(footer == null ? "" : footer);
        tryTabListSetter(player, footerComponent, null, false);
    }

    private void setTabListHeaderFooter(Player player, String header, String footer) {
        String headerText = header == null ? "" : header;
        String footerText = footer == null ? "" : footer;

        if (tryTabListSetter(player, headerText, footerText, null)) {
            return;
        }

        Component headerComponent = Component.text(headerText);
        Component footerComponent = Component.text(footerText);

        if (tryTabListSetter(player, headerComponent, footerComponent, null)) {
            return;
        }

        setTabListHeader(player, headerText);
        setTabListFooter(player, footerText);
    }

    private boolean tryTabListSetter(Player player, Object header, Object footer, Boolean headerOnly) {
        List<String> methods = new ArrayList<>(3);

        if (headerOnly == null) {
            methods.add("setPlayerListHeaderFooter");
            methods.add("sendPlayerListHeaderFooter");
            methods.add("sendPlayerListHeaderAndFooter");
        } else if (headerOnly) {
            methods.add("setPlayerListHeader");
            methods.add("sendPlayerListHeader");
        } else {
            methods.add("setPlayerListFooter");
            methods.add("sendPlayerListFooter");
        }

        Class<?> headerType = header instanceof Component ? Component.class : String.class;
        Class<?> footerType = footer instanceof Component ? Component.class : String.class;

        for (String name : methods) {
            try {
                if (headerOnly == null) {
                    Method method = player.getClass().getMethod(name, headerType, footerType);
                    method.invoke(player, header, footer);
                    return true;
                }

                Method method = player.getClass().getMethod(name, headerType);
                method.invoke(player, header);
                return true;

            } catch (Exception ignored) {
            }
        }
        return false;
    }

    public JsonElement serialize(Object value) {
        return serializer.serialize(value);
    }

    public Object resolveRef(String refType, String refId) {
        return serializer.resolveRef(refType, refId);
    }

    public Object[] convertArgs(Class<?>[] parameterTypes, List<Object> args) {
        return serializer.convertArgs(parameterTypes, args);
    }

    public Object convertArg(Class<?> parameterType, Object arg) {
        return serializer.convertArg(parameterType, arg);
    }

    public Map<String, Object> deserializeArgsObject(JsonObject argsObj) {
        return serializer.deserializeArgsObject(argsObj);
    }

    public Object getField(Object target, String field) throws Exception {
        return serializer.getField(target, field);
    }

    public void setField(Object target, String field, Object value) throws Exception {
        serializer.setField(target, field, value);
    }

    public void sendEvent(String eventName, JsonObject payload) {
        eventDispatcher.sendEvent(eventName, payload);
    }

    public void sendEvent(Event event, String eventName) {
        eventDispatcher.sendEvent(event, eventName);
    }

    public Entity spawnEntityWithOptions(World world, Object locationObj, Object typeObj,
            Map<String, Object> options) throws Exception {
        return entitySpawner.spawnEntityWithOptions(world, locationObj, typeObj, options);
    }

    public List<Entity> spawnImagePixels(World world, Object locationObj, Object pixelsObj) throws Exception {
        return entitySpawner.spawnImagePixels(world, locationObj, pixelsObj);
    }

    // ─── msgpack ↔ JsonObject conversion helpers ───

    private JsonObject msgpackToJsonObject(byte[] data) throws IOException {
        try (MessageUnpacker unpacker = MessagePack.newDefaultUnpacker(data)) {
            return (JsonObject) unpackValue(unpacker);
        }
    }

    private JsonElement unpackValue(MessageUnpacker unpacker) throws IOException {
        MessageFormat fmt = unpacker.getNextFormat();
        switch (fmt.getValueType()) {
            case NIL -> { unpacker.unpackNil(); return com.google.gson.JsonNull.INSTANCE; }
            case BOOLEAN -> { return new com.google.gson.JsonPrimitive(unpacker.unpackBoolean()); }
            case INTEGER -> {
                // Try long first, works for all integer sizes
                long v = unpacker.unpackLong();
                if (v == (int) v) return new com.google.gson.JsonPrimitive((int) v);
                return new com.google.gson.JsonPrimitive(v);
            }
            case FLOAT -> { return new com.google.gson.JsonPrimitive(unpacker.unpackDouble()); }
            case STRING -> { return new com.google.gson.JsonPrimitive(unpacker.unpackString()); }
            case BINARY -> {
                int len = unpacker.unpackBinaryHeader();
                byte[] bin = new byte[len];
                unpacker.readPayload(bin);
                // Treat binary as a UTF-8 string for compatibility
                return new com.google.gson.JsonPrimitive(new String(bin, StandardCharsets.UTF_8));
            }
            case ARRAY -> {
                int size = unpacker.unpackArrayHeader();
                com.google.gson.JsonArray arr = new com.google.gson.JsonArray(size);
                for (int i = 0; i < size; i++) arr.add(unpackValue(unpacker));
                return arr;
            }
            case MAP -> {
                int size = unpacker.unpackMapHeader();
                JsonObject obj = new JsonObject();
                for (int i = 0; i < size; i++) {
                    String key = unpacker.unpackString();
                    obj.add(key, unpackValue(unpacker));
                }
                return obj;
            }
            default -> {
                unpacker.skipValue();
                return com.google.gson.JsonNull.INSTANCE;
            }
        }
    }

    private byte[] jsonObjectToMsgpack(JsonObject obj) throws IOException {
        ArrayBufferOutput out = new ArrayBufferOutput();
        try (MessagePacker packer = MessagePack.newDefaultPacker(out)) {
            packJsonElement(packer, obj);
        }
        return out.toByteArray();
    }

    private void packJsonElement(MessagePacker packer, JsonElement el) throws IOException {
        if (el == null || el.isJsonNull()) {
            packer.packNil();
        } else if (el.isJsonPrimitive()) {
            com.google.gson.JsonPrimitive prim = el.getAsJsonPrimitive();
            if (prim.isBoolean()) {
                packer.packBoolean(prim.getAsBoolean());
            } else if (prim.isNumber()) {
                Number num = prim.getAsNumber();
                // Check if it's an integer type
                double d = num.doubleValue();
                if (d == Math.floor(d) && !Double.isInfinite(d) && d >= Long.MIN_VALUE && d <= Long.MAX_VALUE) {
                    long l = num.longValue();
                    if (l >= Integer.MIN_VALUE && l <= Integer.MAX_VALUE) {
                        packer.packInt((int) l);
                    } else {
                        packer.packLong(l);
                    }
                } else {
                    packer.packDouble(d);
                }
            } else {
                packer.packString(prim.getAsString());
            }
        } else if (el.isJsonArray()) {
            com.google.gson.JsonArray arr = el.getAsJsonArray();
            packer.packArrayHeader(arr.size());
            for (JsonElement child : arr) {
                packJsonElement(packer, child);
            }
        } else if (el.isJsonObject()) {
            JsonObject obj = el.getAsJsonObject();
            packer.packMapHeader(obj.size());
            for (Map.Entry<String, JsonElement> entry : obj.entrySet()) {
                packer.packString(entry.getKey());
                packJsonElement(packer, entry.getValue());
            }
        }
    }

    private byte[] serializePayload(JsonObject obj) {
        if (useMsgpack) {
            try {
                return jsonObjectToMsgpack(obj);
            } catch (IOException e) {
                logError("Msgpack serialization failed, falling back to JSON", e);
            }
        }
        return gson.toJson(obj).getBytes(StandardCharsets.UTF_8);
    }

    private JsonObject deserializePayload(byte[] payload) {
        if (useMsgpack) {
            try {
                return msgpackToJsonObject(payload);
            } catch (IOException e) {
                plugin.getLogger().severe("[" + name + "] Msgpack deserialization failed, trying JSON: " + e.getMessage());
            }
        }
        return JsonParser.parseString(new String(payload, StandardCharsets.UTF_8)).getAsJsonObject();
    }

    public void send(JsonObject response) {
        if (writer == null || !running) {
            return;
        }
        try {
            byte[] payload = serializePayload(response);
            synchronized (writeLock) {
                writer.writeInt(payload.length);
                writer.write(payload);
                writer.flush();
            }
            if (plugin.isDebugEnabled()) {
                String type = response.has("type") ? response.get("type").getAsString() : "?";
                plugin.broadcastDebug("[PJB] J2P " + name + ": " + type + " " + summarizeMessage(response));
            }
        } catch (IOException e) {
            logError("Failed to send message", e);
        }
    }

    /**
     * Write multiple responses under a single lock acquisition + single flush.
     * Much more efficient than calling send() in a loop for batch responses.
     */
    private void sendAll(List<JsonObject> responses, long startNano) {
        if (writer == null || !running || responses.isEmpty()) {
            return;
        }
        try {
            synchronized (writeLock) {
                for (JsonObject response : responses) {
                    byte[] payload = serializePayload(response);
                    writer.writeInt(payload.length);
                    writer.write(payload);
                }
                writer.flush();
            }
            if (plugin.isDebugEnabled()) {
                double ms = (System.nanoTime() - startNano) / 1_000_000.0;
                plugin.broadcastDebug(String.format("[PJB] J2P (%.2fms) %s: batch %d responses",
                        ms, name, responses.size()));
            }
        } catch (IOException e) {
            logError("Failed to send batch responses", e);
        }
    }

    private void sendWithTiming(JsonObject response, long startNano) {
        if (writer == null || !running) {
            return;
        }
        try {
            byte[] payload = serializePayload(response);
            synchronized (writeLock) {
                writer.writeInt(payload.length);
                writer.write(payload);
                writer.flush();
            }
            if (plugin.isDebugEnabled()) {
                double ms = (System.nanoTime() - startNano) / 1_000_000.0;
                String type = response.has("type") ? response.get("type").getAsString() : "?";
                plugin.broadcastDebug(String.format("[PJB] J2P (%.2fms) %s: %s %s",
                        ms, name, type, summarizeMessage(response)));
            }
        } catch (IOException e) {
            logError("Failed to send message", e);
        }
    }

    private void sendError(JsonObject message, String error, Exception ex) {
        int id = message.has("id") ? message.get("id").getAsInt() : -1;
        sendError(id, error, ex);
    }

    private void sendError(int id, String error, Throwable ex) {
        sendError(id, error, ex, null);
    }

    private void sendError(int id, String error, Throwable ex, String code) {
        JsonObject response = new JsonObject();
        response.addProperty("type", "error");
        response.addProperty("id", id);
        response.addProperty("message", error);
        if (code != null) {
            response.addProperty("code", code);
        }
        if (ex != null) {
            response.addProperty("details", ex.toString());
            // Auto-detect error code from exception type if not explicitly set
            if (code == null) {
                response.addProperty("code", classifyException(ex));
            }
            // Include Java stack trace
            java.io.StringWriter sw = new java.io.StringWriter();
            ex.printStackTrace(new java.io.PrintWriter(sw));
            response.addProperty("stacktrace", sw.toString());
        }
        send(response);
    }

    private String classifyException(Throwable ex) {
        if (ex instanceof EntityGoneException) return "ENTITY_GONE";
        if (ex instanceof IllegalArgumentException) {
            String msg = ex.getMessage();
            if (msg != null) {
                String lower = msg.toLowerCase();
                if (lower.contains("material")) return "INVALID_MATERIAL";
                if (lower.contains("enum")) return "INVALID_ENUM";
                if (lower.contains("slot")) return "SLOT_OUT_OF_RANGE";
            }
            return "INVALID_ARGUMENT";
        }
        if (ex instanceof NoSuchMethodException || ex instanceof NoSuchMethodError)
            return "METHOD_NOT_FOUND";
        if (ex instanceof ClassNotFoundException || ex instanceof ClassCastException || ex instanceof NoClassDefFoundError)
            return "CLASS_NOT_FOUND";
        if (ex instanceof SecurityException || ex instanceof IllegalAccessException)
            return "ACCESS_DENIED";
        if (ex instanceof NullPointerException) return "NULL_REFERENCE";
        if (ex instanceof java.util.concurrent.TimeoutException) return "TIMEOUT";
        if (ex instanceof java.lang.reflect.InvocationTargetException ite) {
            if (ite.getCause() != null) return classifyException(ite.getCause());
        }
        return null;
    }

    void logError(String message, Throwable ex) {
        String detail = ex != null ? ex.getMessage() : "unknown";
        plugin.getLogger().severe("[" + name + "] " + message + ": " + detail);
        plugin.broadcastErrorToDebugPlayers("[" + name + "] " + message + ": " + detail);
    }

    private void startPythonProcess() {
        List<String> command = new ArrayList<>(4);

        String python = resolvePythonExecutable();

        command.add(python);
        command.add("-u");
        command.add(runtimeDir.resolve("runner.py").toAbsolutePath().toString());
        command.add(scriptPath.toAbsolutePath().toString());

        ProcessBuilder builder = new ProcessBuilder(command);

        builder.directory(scriptsDir.toFile());
        builder.redirectError(ProcessBuilder.Redirect.INHERIT);

        Map<String, String> env = builder.environment();

        env.put("PYJAVABRIDGE_RUNTIME", runtimeDir.toString());
        env.put("PYJAVABRIDGE_SCRIPT", scriptPath.toAbsolutePath().toString());

        boolean isWindows = System.getProperty("os.name", "").toLowerCase().contains("win");

        Path venvDir = scriptsDir.resolve(".venv");
        Path venvBinDir = isWindows ? venvDir.resolve("Scripts") : venvDir.resolve("bin");
        Path venvPython = isWindows ? venvBinDir.resolve("python.exe") : venvBinDir.resolve("python");

        if (Files.exists(venvPython)) {
            env.put("VIRTUAL_ENV", venvDir.toAbsolutePath().toString());
            String existingPath = env.getOrDefault("PATH", "");
            String venvBin = venvBinDir.toAbsolutePath().toString();
            if (!existingPath.startsWith(venvBin)) {
                env.put("PATH", venvBin + File.pathSeparator + existingPath);
            }
        }

        try {
            plugin.getLogger().info("[" + name + "] Launching python: " + String.join(" ", command));
            pythonProcess = builder.start();
        } catch (IOException e) {
            logError("Failed to start python", e);
        }
    }

    private String resolvePythonExecutable() {
        boolean isWindows = System.getProperty("os.name", "").toLowerCase().contains("win");

        Path venvDir = scriptsDir.resolve(".venv");
        Path venvPython = isWindows
                ? venvDir.resolve("Scripts").resolve("python.exe")
                : venvDir.resolve("bin").resolve("python");

        if (Files.exists(venvPython)) {
            Path absolute = venvPython.toAbsolutePath();
            if (Files.exists(absolute) && (isWindows || Files.isExecutable(absolute))) {
                return absolute.toString();
            }
        }
        return isWindows ? "python" : "python3";
    }

    private void closeQuietly(AutoCloseable closable) {
        if (closable == null) {
            return;
        }
        try {
            closable.close();
        } catch (Exception ignored) {
        }
    }
}
