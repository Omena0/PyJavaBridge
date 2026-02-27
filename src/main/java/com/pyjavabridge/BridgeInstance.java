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
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.event.Event;
import org.bukkit.event.EventPriority;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
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

    private final Map<Integer, PendingEvent> pendingEvents = new ConcurrentHashMap<>();
    private final Object writeLock = new Object();

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
                    message = JsonParser.parseString(new String(payload, StandardCharsets.UTF_8))
                            .getAsJsonObject();
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
            case "ready" -> Bukkit.getScheduler().runTaskLater(plugin,
                    () -> sendEvent("server_boot", new JsonObject()),
                    2L);
            case "event_done" -> handleEventDone(message);
            case "event_cancel" -> handleEventCancel(message);
            case "event_result" -> handleEventResult(message);
            case "register_command" -> handleRegisterCommand(message);
            case "remove_entities" -> handleRemoveEntities(message);
            case "update_entities" -> handleUpdateEntities(message);
            case "move_entities" -> handleMoveEntities(message);
            case "release" -> handleRelease(message);
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

    private void handleRegisterCommand(JsonObject message) {
        String commandName = message.get("name").getAsString();
        String permission = message.has("permission") ? message.get("permission").getAsString() : null;

        plugin.getLogger().info("[" + name + "] Registering command /" + commandName);
        plugin.registerScriptCommand(commandName, this, permission);
    }

    private void handleRemoveEntities(JsonObject message) {
        boolean hasId = message.has("id");
        int id = hasId ? message.get("id").getAsInt() : 0;
        JsonElement handlesEl = message.get("handles");
        if (handlesEl == null || !handlesEl.isJsonArray()) {
            if (hasId) sendError(id, "remove_entities requires handles array", null);
            return;
        }
        List<Integer> handles = new ArrayList<>();
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
            List<Integer> ids = new ArrayList<>();
            for (JsonElement el : handlesEl.getAsJsonArray()) {
                ids.add(el.getAsInt());
            }
            registry.releaseAll(ids);
        }
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

        if (isCallThreadSafe(message)) {
            try {
                Object result = invoke(message);
                JsonObject response = new JsonObject();
                response.addProperty("type", "return");
                response.addProperty("id", id);
                response.add("result", serialize(result));
                sendWithTiming(response, startNano);
            } catch (Exception ex) {
                Throwable cause = ex;
                String errorMessage = cause.getMessage();
                if (errorMessage == null || errorMessage.isBlank()) {
                    errorMessage = cause.getClass().getSimpleName();
                }
                sendError(id, errorMessage, cause);
            }
            return;
        }

        CompletableFuture<Object> future = plugin.runOnMainThread(this, () -> invoke(message));

        future.whenComplete((result, error) -> {
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
        List<JsonObject> calls = new ArrayList<>();

        if (message.has("messages")) {
            for (JsonElement element : message.getAsJsonArray("messages")) {
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
            List<JsonObject> responses = new ArrayList<>();
            List<Integer> ids = new ArrayList<>();
            boolean failed = false;
            int failedId = -1;
            Exception failedEx = null;
            String failedMessage = null;

            for (JsonObject callMessage : calls) {
                int id = callMessage.get("id").getAsInt();
                ids.add(id);

                if (failed) {
                    continue;
                }

                try {
                    Object result = invoke(callMessage);
                    JsonObject response = new JsonObject();

                    response.addProperty("type", "return");
                    response.addProperty("id", id);
                    response.add("result", serialize(result));

                    responses.add(response);

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
                for (JsonObject response : responses) {
                    sendWithTiming(response, startNano);
                }
            }
            return;
        }

        for (JsonObject callMessage : calls) {
            int id = callMessage.get("id").getAsInt();

            try {
                Object result = invoke(callMessage);
                JsonObject response = new JsonObject();

                response.addProperty("type", "return");
                response.addProperty("id", id);
                response.add("result", serialize(result));

                sendWithTiming(response, startNano);

            } catch (Exception ex) {
                sendError(id, ex.getMessage(), ex);
            }
        }
    }

    private static final Set<String> THREAD_SAFE_SERVER_METHODS = Set.of(
        "getName", "getVersion", "getBukkitVersion", "getMaxPlayers"
    );

    private static final Set<String> THREAD_SAFE_OFFLINEPLAYER_METHODS = Set.of(
        "getUniqueId", "getName", "hasPermission", "isPermissionSet",
        "isWhitelisted", "isBanned"
    );

    private static final Set<String> THREAD_SAFE_METADATA_METHODS = Set.of(
        "hasMetadata", "getMetadata"
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

            // Entity (non-Player): only getUniqueId
            if (target instanceof Entity) {
                return "getUniqueId".equals(method);
            }
        }

        return false;
    }

    private Object invoke(JsonObject message) throws Exception {
        String method = message.get("method").getAsString();

        JsonObject argsObj = message.has("args") ? message.getAsJsonObject("args") : new JsonObject();

        List<Object> args = new ArrayList<>();

        if (message.has("args_list")) {
            for (JsonElement element : message.getAsJsonArray("args_list")) {
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

        // Type-specific dispatch
        Object result = UNHANDLED;

        if (target instanceof World world) {
            result = invokeWorldMethod(world, method, args, argsObj);
        }

        if (result == UNHANDLED && target instanceof Block block) {
            result = invokeBlockMethod(block, method);
        }

        if (result == UNHANDLED && target instanceof org.bukkit.inventory.Inventory inv) {
            result = invokeInventoryMethod(inv, method);
        }

        if (result == UNHANDLED && target instanceof Player player) {
            result = invokePlayerMethod(player, method, args);
        }

        if (result == UNHANDLED && target instanceof ItemStack itemStack) {
            result = invokeItemStackMethod(itemStack, method, args);
        }

        if (result == UNHANDLED && target instanceof org.bukkit.Server server) {
            result = invokeServerMethod(server, method, args);
        }

        if (result == UNHANDLED && target instanceof Display) {
            result = invokeDisplayMethod(target, method, args);
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
        return UNHANDLED;
    }

    private Object invokeBlockMethod(Block block, String method) {
        if ("getInventory".equals(method)) {
            BlockState state = block.getState();
            return state instanceof InventoryHolder holder ? holder.getInventory() : null;
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
                    List<String> loreText = new ArrayList<>();
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
                    List<Component> loreComponents = new ArrayList<>();
                    if (loreArg instanceof List<?> loreList) {
                        for (Object entry : loreList) {
                            if (entry != null) {
                                loreComponents.add(Component.text(entry.toString()));
                            }
                        }
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
        return UNHANDLED;
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

    private Object invokeReflective(Object target, String method, List<Object> args) throws Exception {
        for (Method candidate : target.getClass().getMethods()) {
            if (!candidate.getName().equals(method) || candidate.getParameterCount() != args.size()) {
                continue;
            }
            Object[] converted = serializer.convertArgs(candidate.getParameterTypes(), args);
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
        throw new NoSuchMethodException("Method not found: " + method + " on " + target.getClass().getName());
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
        List<String> methods = new ArrayList<>();

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

    public void send(JsonObject response) {
        if (writer == null) {
            return;
        }
        try {
            byte[] payload = gson.toJson(response).getBytes(StandardCharsets.UTF_8);
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

    private void sendWithTiming(JsonObject response, long startNano) {
        if (writer == null) {
            return;
        }
        try {
            byte[] payload = gson.toJson(response).getBytes(StandardCharsets.UTF_8);
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
            if (ex instanceof EntityGoneException) {
                response.addProperty("code", "ENTITY_GONE");
            }
        }
        send(response);
    }

    void logError(String message, Throwable ex) {
        String detail = ex != null ? ex.getMessage() : "unknown";
        plugin.getLogger().severe("[" + name + "] " + message + ": " + detail);
        plugin.broadcastErrorToDebugPlayers("[" + name + "] " + message + ": " + detail);
    }

    private void startPythonProcess() {
        List<String> command = new ArrayList<>();

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
