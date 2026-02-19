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
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

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

    @SuppressWarnings("unused")
    private final AtomicInteger requestId = new AtomicInteger(1);
    private final Map<Integer, PendingEvent> pendingEvents = new ConcurrentHashMap<>();
    private final Object writeLock = new Object();

    private final BridgeSerializer serializer;
    private final EventDispatcher eventDispatcher;
    private final EntitySpawner entitySpawner;

    private ServerSocket serverSocket;
    private Socket socket;
    private DataInputStream reader;
    private DataOutputStream writer;
    private Thread bridgeThread;
    private Process pythonProcess;
    private volatile boolean running = false;
    private String authToken;
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
        authToken = UUID.randomUUID().toString();

        try {
            serverSocket = new ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"));
            plugin.getLogger().info("[" + name + "] Bridge listening on 127.0.0.1:" + serverSocket.getLocalPort());
            startPythonProcess(serverSocket.getLocalPort());

        } catch (IOException e) {
            logError("Failed to start socket", e);
            return;
        }

        bridgeThread = new Thread(this::bridgeLoop, "PyJavaBridge-" + name);
        bridgeThread.start();
    }

    void shutdown() {
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

        closeQuietly(socket);
        closeQuietly(serverSocket);
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
            serverSocket.setSoTimeout(30_000);
            socket = serverSocket.accept();
            plugin.getLogger().info("[" + name + "] Python connected");

            reader = new DataInputStream(socket.getInputStream());
            writer = new DataOutputStream(socket.getOutputStream());

            // Verify auth token
            int authLength = reader.readInt();
            if (authLength <= 0 || authLength > 4096) {
                plugin.getLogger().severe("[" + name + "] Invalid auth message size");
                return;
            }
            byte[] authPayload = new byte[authLength];
            reader.readFully(authPayload);
            JsonObject authMsg = JsonParser.parseString(new String(authPayload, StandardCharsets.UTF_8))
                    .getAsJsonObject();
            if (!"auth".equals(authMsg.has("type") ? authMsg.get("type").getAsString() : "")
                    || !authToken.equals(authMsg.has("token") ? authMsg.get("token").getAsString() : "")) {
                plugin.getLogger().severe("[" + name + "] Authentication failed");
                socket.close();
                return;
            }
            plugin.getLogger().info("[" + name + "] Authenticated");

            while (running) {
                int length;
                try {
                    length = reader.readInt();
                } catch (IOException eof) {
                    break;
                }
                if (length <= 0 || length > 1_073_741_824) {
                    logError("Invalid message length: " + length, null);
                    break;
                }
                byte[] payload = new byte[length];
                reader.readFully(payload);
                JsonObject message = JsonParser.parseString(new String(payload, StandardCharsets.UTF_8))
                        .getAsJsonObject();
                handleMessage(message);
            }

        } catch (SocketTimeoutException e) {
            plugin.getLogger().warning("[" + name + "] Python process did not connect within 30s");

        } catch (IOException e) {
            if (running) {
                logError("Bridge socket error", e);
            }

        } finally {
            shutdown();
        }
    }

    private void handleMessage(JsonObject message) {
        String type = message.get("type").getAsString();

        switch (type) {
            case "subscribe" -> handleSubscribe(message);
            case "call" -> handleCall(message);
            case "call_batch" -> handleCallBatch(message);
            case "wait" -> handleWait(message);
            case "ready" -> Bukkit.getScheduler().runTaskLater(plugin,
                    () -> sendEvent("server_boot", new JsonObject()),
                    2L);
            case "event_done" -> handleEventDone(message);
            case "event_cancel" -> handleEventCancel(message);
            case "event_result" -> handleEventResult(message);
            case "register_command" -> handleRegisterCommand(message);
            case "release" -> handleRelease(message);
            case "shutdown_ack" -> {
                if (shutdownLatch != null) {
                    shutdownLatch.countDown();
                }
            }
            default -> sendError(message, "Unknown message type: " + type, null);
        }
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

    private void handleCall(JsonObject message) {
        int id = message.get("id").getAsInt();

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

                send(response);
            }
        });
    }

    private void handleCallBatch(JsonObject message) {

        boolean atomic = message.has("atomic") && message.get("atomic").getAsBoolean();
        List<JsonObject> calls = new ArrayList<>();

        if (message.has("messages")) {
            for (JsonElement element : message.getAsJsonArray("messages")) {
                if (element.isJsonObject()) {
                    calls.add(element.getAsJsonObject());
                }
            }
        }

        CompletableFuture<Object> future = plugin.runOnMainThread(this, () -> {
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
                        send(response);
                    }
                }
                return null;
            }

            for (JsonObject callMessage : calls) {
                int id = callMessage.get("id").getAsInt();

                try {
                    Object result = invoke(callMessage);
                    JsonObject response = new JsonObject();

                    response.addProperty("type", "return");
                    response.addProperty("id", id);
                    response.add("result", serialize(result));

                    send(response);

                } catch (Exception ex) {
                    sendError(id, ex.getMessage(), ex);
                }
            }
            return null;
        });

        future.whenComplete((result, error) -> {
            if (error != null) {
                logError("Batch call failed", error);
            }
        });
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
            case "chat" -> new ChatFacade();
            case "raycast" -> new RaycastFacade();
            case "permissions" -> new PermissionsFacade(plugin, permissionAttachments);
            case "metrics" -> new MetricsFacade(plugin);
            case "ref" -> new RefFacade(this);
            case "reflect" -> new ReflectFacade();
            case "commands" -> new CommandsFacade(plugin, this);
            case "region" -> new RegionFacade();
            case "particle" -> new ParticleFacade();
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
        plugin.getLogger().severe("[" + name + "] " + message + ": " + ex.getMessage());
        plugin.broadcastErrorToDebugPlayers("[" + name + "] " + message + ": " + ex.getMessage());
    }

    private void startPythonProcess(int port) {
        List<String> command = new ArrayList<>();

        String python = resolvePythonExecutable();

        command.add(python);
        command.add("-u");
        command.add(runtimeDir.resolve("runner.py").toAbsolutePath().toString());
        command.add(scriptPath.toAbsolutePath().toString());

        ProcessBuilder builder = new ProcessBuilder(command);

        builder.directory(scriptsDir.toFile());
        builder.redirectErrorStream(true);
        builder.redirectOutput(ProcessBuilder.Redirect.INHERIT);

        Map<String, String> env = builder.environment();

        env.put("PYJAVABRIDGE_PORT", String.valueOf(port));
        env.put("PYJAVABRIDGE_TOKEN", authToken);
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
