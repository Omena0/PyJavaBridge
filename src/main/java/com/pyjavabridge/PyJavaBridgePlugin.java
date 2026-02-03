package com.pyjavabridge;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.ConsoleCommandSender;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.entity.Tameable;
import org.bukkit.entity.AnimalTamer;
import org.bukkit.event.Event;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.plugin.EventExecutor;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.command.CommandMap;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;
import org.bukkit.permissions.PermissionAttachment;
import org.bukkit.projectiles.BlockProjectileSource;
import org.bukkit.projectiles.ProjectileSource;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.InventoryView;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.NamespacedKey;
import org.bukkit.Registry;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import com.google.common.collect.Multimap;

import java.lang.reflect.Array;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import org.bukkit.event.block.BlockExplodeEvent;
import org.bukkit.event.entity.EntityExplodeEvent;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.lang.reflect.InvocationTargetException;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class PyJavaBridgePlugin extends JavaPlugin {
    private final ConcurrentLinkedQueue<Runnable> mainThreadQueue = new ConcurrentLinkedQueue<>();
    private final Map<String, BridgeInstance> instances = new ConcurrentHashMap<>();
    private final Set<UUID> debugPlayers = Collections.synchronizedSet(new HashSet<>());
    private final Map<String, UUID> playerUuidCache = new ConcurrentHashMap<>();

    private static final Map<EntityType, NonLivingSpawner> NON_LIVING_SPAWNERS = new EnumMap<>(EntityType.class);

    static {
        for (EntityType type : EntityType.values()) {
            Class<?> entityClass = type.getEntityClass();
            if (entityClass != null && !LivingEntity.class.isAssignableFrom(entityClass)) {
                NON_LIVING_SPAWNERS.put(type, (world, location, entityType) -> spawnNonLivingEntity(world, location, entityType));
            }
        }
    }

    private BukkitTask mainThreadPump;

    private long currentTick = 0L;
    private long lastTickNano = 0L;
    private double lastTickTimeMs = 0.0;

    private final java.util.concurrent.atomic.AtomicInteger eventCounter = new java.util.concurrent.atomic.AtomicInteger(
            1);

    @FunctionalInterface
    private interface NonLivingSpawner {
        Entity spawn(World world, Location location, EntityType entityType) throws Exception;
    }

    private static Entity spawnNonLivingEntity(World world, Location location, EntityType entityType) throws Exception {
        Object craftWorld = world;
        Class<?> craftWorldClass = craftWorld.getClass();

        Method getHandle = craftWorldClass.getMethod("getHandle");
        Object serverLevel = getHandle.invoke(craftWorld);

        Class<?> craftEntityTypeClass = Class.forName("org.bukkit.craftbukkit.entity.CraftEntityType");
        Method bukkitToMinecraft = craftEntityTypeClass.getMethod("bukkitToMinecraft", EntityType.class);
        Object nmsEntityType = bukkitToMinecraft.invoke(null, entityType);

        if (nmsEntityType == null) {
            return null;
        }

        Class<?> blockPosClass = Class.forName("net.minecraft.core.BlockPos");
        Method containing = blockPosClass.getMethod("containing", double.class, double.class, double.class);
        Object blockPos = containing.invoke(null, location.getX(), location.getY(), location.getZ());

        Class<?> spawnReasonClass = Class.forName("net.minecraft.world.entity.EntitySpawnReason");
        @SuppressWarnings({ "rawtypes", "unchecked" })
        Object spawnReason = Enum.valueOf((Class) spawnReasonClass, "COMMAND");

        Method create = nmsEntityType.getClass().getMethod(
                "create",
                Class.forName("net.minecraft.server.level.ServerLevel"),
                java.util.function.Consumer.class,
                blockPosClass,
                spawnReasonClass,
                boolean.class,
                boolean.class);

        Object nmsEntity = create.invoke(
                nmsEntityType,
                serverLevel,
                (java.util.function.Consumer<Object>) entity -> {},
                blockPos,
                spawnReason,
                false,
                false);

        if (nmsEntity == null) {
            return null;
        }

        Method addEntityToWorld = craftWorldClass.getMethod(
                "addEntityToWorld",
                Class.forName("net.minecraft.world.entity.Entity"),
                CreatureSpawnEvent.SpawnReason.class);

        addEntityToWorld.invoke(craftWorld, nmsEntity, CreatureSpawnEvent.SpawnReason.CUSTOM);

        Method getBukkitEntity = nmsEntity.getClass().getMethod("getBukkitEntity");
        Object bukkitEntity = getBukkitEntity.invoke(nmsEntity);

        return bukkitEntity instanceof Entity entity ? entity : null;
    }

    @Override
    public void onEnable() {
        getCommand("bridge").setExecutor(this);
        getCommand("bridge").setTabCompleter(this);

        Path dataDir = getDataFolder().toPath();
        Path scriptsDir = dataDir.resolve("scripts");
        Path runtimeDir = dataDir.resolve("runtime");

        try {
            Files.createDirectories(scriptsDir);
            Files.createDirectories(runtimeDir);

            copyRuntimeResource("python/runner.py", runtimeDir.resolve("runner.py"));
            copyRuntimeResource("python/bridge.py", scriptsDir.resolve("bridge.py"));
            copyRuntimeResource("python/bridge.pyi", scriptsDir.resolve("bridge.pyi"));

            getLogger().info("PyJavaBridge runtime initialized at " + runtimeDir);
        } catch (IOException e) {
            getLogger().severe("Failed to initialize runtime: " + e.getMessage());
            return;
        }

        mainThreadPump = Bukkit.getScheduler().runTaskTimer(this, () -> {
            long now = System.nanoTime();

            if (lastTickNano != 0L) {
                lastTickTimeMs = (now - lastTickNano) / 1_000_000.0;
            }

            lastTickNano = now;
            currentTick++;

            Runnable task;

            while ((task = mainThreadQueue.poll()) != null) {
                try {
                    task.run();

                } catch (Exception ex) {
                    getLogger().severe("Main-thread task error: " + ex.getMessage());
                }
            }
        }, 1L, 1L);

        startScripts(scriptsDir, runtimeDir);
    }

    @Override
    public void onDisable() {
        if (mainThreadPump != null) {
            mainThreadPump.cancel();
        }

        for (BridgeInstance instance : instances.values()) {
            instance.shutdown();
        }

        instances.clear();
    }

    private void startScripts(Path scriptsDir, Path runtimeDir) {
        try {
            getLogger().info("Scanning scripts in " + scriptsDir);

            Files.list(scriptsDir)
                    .filter(path -> path.toString().endsWith(".py"))
                    .filter(path -> !path.getFileName().toString().equals("bridge.py"))
                    .filter(path -> !path.getFileName().toString().equals("runner.py"))
                    .forEach(path -> startScript(path, scriptsDir, runtimeDir));

        } catch (IOException e) {
            getLogger().severe("Failed to list scripts: " + e.getMessage());
        }
    }

    private void startScript(Path scriptPath, Path scriptsDir, Path runtimeDir) {
        String scriptName = scriptPath.getFileName().toString();

        getLogger().info("Starting script: " + scriptName);

        BridgeInstance instance = new BridgeInstance(this, scriptName, scriptPath, scriptsDir, runtimeDir);

        instances.put(scriptName, instance);
        instance.start();
    }

    private void restartScript(String scriptName) {
        BridgeInstance existing = instances.get(scriptName);

        if (existing != null) {
            existing.shutdown();
        }

        Path scriptPath = getDataFolder().toPath().resolve("scripts").resolve(scriptName);

        if (Files.exists(scriptPath)) {
            startScript(scriptPath, getDataFolder().toPath().resolve("scripts"),
                    getDataFolder().toPath().resolve("runtime"));
        }
    }

    private void restartAllScripts() {
        for (BridgeInstance instance : instances.values()) {
            instance.shutdown();
        }

        instances.clear();
        startScripts(getDataFolder().toPath().resolve("scripts"), getDataFolder().toPath().resolve("runtime"));
    }

    void registerScriptCommand(String name, BridgeInstance instance) {
        CommandMap commandMap = getCommandMap();

        if (commandMap == null) {
            getLogger().warning("CommandMap unavailable; cannot register command " + name);
            return;
        }

        String commandName = name.toLowerCase();
        Command existing = commandMap.getCommand(commandName);

        if (existing instanceof ScriptCommand scriptCommand) {
            scriptCommand.setInstance(instance);
            return;
        }

        if (existing != null) {
            getLogger().warning("Command /" + commandName + " already registered by another plugin.");
        }

        ScriptCommand command = new ScriptCommand(commandName, instance);
        commandMap.register(getName(), command);
    }

    private CommandMap getCommandMap() {
        try {
            Field field = Bukkit.getServer().getClass().getDeclaredField("commandMap");
            field.setAccessible(true);

            return (CommandMap) field.get(Bukkit.getServer());

        } catch (Exception e) {
            getLogger().warning("Failed to access commandMap: " + e.getMessage());
            return null;
        }
    }

    private UUID resolvePlayerUuidByName(String name) {
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
                    String formatted = raw.substring(0, 8) + "-" + raw.substring(8, 12) + "-" + raw.substring(12, 16)
                            + "-" + raw.substring(16, 20) + "-" + raw.substring(20);
                    return UUID.fromString(formatted);
                }
                return UUID.fromString(raw);
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    private void copyRuntimeResource(String resourcePath, Path destination) throws IOException {
        try (InputStream input = getResource(resourcePath)) {
            if (input == null) {
                throw new IOException("Missing resource: " + resourcePath);
            }

            Files.copy(input, destination, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        }
    }

    CompletableFuture<Object> runOnMainThread(BridgeInstance instance, CallableTask task) {
        CompletableFuture<Object> future = new CompletableFuture<>();

        mainThreadQueue.add(() -> {
            try {
                Object result = task.call();
                future.complete(result);

            } catch (Exception ex) {
                future.completeExceptionally(ex);
                instance.logError("Main-thread call failed", ex);
            }
        });
        return future;
    }

    void drainMainThreadQueue() {
        Runnable task;

        while ((task = mainThreadQueue.poll()) != null) {
            try {
                task.run();

            } catch (Exception ex) {
                getLogger().severe("Main-thread task error: " + ex.getMessage());
            }
        }
    }

    long getCurrentTick() {
        return currentTick;
    }

    double getLastTickTimeMs() {
        return lastTickTimeMs;
    }

    int getQueueLen() {
        return mainThreadQueue.size();
    }

    void addDebugPlayer(UUID playerId) {
        debugPlayers.add(playerId);
    }

    void removeDebugPlayer(UUID playerId) {
        debugPlayers.remove(playerId);
    }

    void broadcastErrorToDebugPlayers(String message) {
        for (UUID uuid : debugPlayers) {
            Player player = Bukkit.getPlayer(uuid);
            if (player != null) {
                player.sendMessage("§c[PyJavaBridge] " + message);
            }
        }
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0) {
            sender.sendMessage("§eUsage: /bridge reload [<script>] | /bridge debug | /bridge plugins");
            return true;
        }

        if (args[0].equalsIgnoreCase("reload")) {
            if (args.length >= 2) {
                restartScript(args[1]);
                sender.sendMessage("§aReloaded script: " + args[1]);

            } else {
                restartAllScripts();
                sender.sendMessage("§aReloaded all scripts.");
            }
            return true;
        }

        if (args[0].equalsIgnoreCase("debug")) {
            if (sender instanceof Player player) {
                if (debugPlayers.contains(player.getUniqueId())) {
                    removeDebugPlayer(player.getUniqueId());
                    player.sendMessage("§ePyJavaBridge debug disabled.");

                } else {
                    addDebugPlayer(player.getUniqueId());
                    player.sendMessage("§aPyJavaBridge debug enabled.");
                }

            } else if (sender instanceof ConsoleCommandSender) {
                sender.sendMessage("§eDebug is for players only.");
            }

            return true;
        }

        if (args[0].equalsIgnoreCase("plugins")) {
            if (instances.isEmpty()) {
                sender.sendMessage("§eNo scripts loaded.");
                return true;
            }
            sender.sendMessage("§eLoaded scripts:");
            List<String> names = new ArrayList<>(instances.keySet());
            names.sort(String.CASE_INSENSITIVE_ORDER);
            for (String name : names) {
                BridgeInstance instance = instances.get(name);
                String description = instance != null ? getScriptDescription(instance.scriptPath) : "";
                if (description == null || description.isBlank()) {
                    description = "(no description)";
                }
                sender.sendMessage("§7- " + name + ": §f" + description);
            }
            return true;
        }

        sender.sendMessage("§cUnknown subcommand.");
        return true;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 1) {
            return List.of("reload", "debug", "plugins");
        }

        if (args.length == 2 && args[0].equalsIgnoreCase("reload")) {
            return new ArrayList<>(instances.keySet());
        }

        return List.of();
    }

    private String getScriptDescription(Path scriptPath) {
        if (scriptPath == null) {
            return "";
        }
        try {
            String content = Files.readString(scriptPath, StandardCharsets.UTF_8);
            Pattern pattern = Pattern.compile("\\A\\s*(?:#.*\\R|\\s*\\R)*\\s*(?:\"\"\"(.*?)\"\"\"|'''(.*?)''')",
                    Pattern.DOTALL);
            Matcher matcher = pattern.matcher(content);
            if (matcher.find()) {
                String doc = matcher.group(1) != null ? matcher.group(1) : matcher.group(2);
                if (doc != null) {
                    String cleaned = doc.strip().replaceAll("\\R+", " ");
                    return cleaned;
                }
            }
        } catch (IOException ignored) {
        }
        return "";
    }

    interface CallableTask {
        Object call() throws Exception;
    }

    static class ScriptCommand extends org.bukkit.command.Command {
        private volatile BridgeInstance instance;

        protected ScriptCommand(String name, BridgeInstance instance) {
            super(name);
            this.instance = instance;
        }

        void setInstance(BridgeInstance instance) {
            this.instance = instance;
        }

        @Override
        public boolean execute(CommandSender sender, String label, String[] args) {
            BridgeInstance current = instance;

            if (current == null || !current.isRunning()) {
                sender.sendMessage("§cPyJavaBridge command unavailable (script not running).");
                return true;
            }

            JsonObject payload = new JsonObject();

            payload.add("event", current.serialize(sender));
            payload.add("sender", current.serialize(sender));

            if (sender instanceof org.bukkit.entity.Player player) {

                payload.add("player", current.serialize(player));
                payload.add("location", current.serialize(player.getLocation()));
                payload.add("world", current.serialize(player.getWorld()));

            } else {

                payload.add("player", com.google.gson.JsonNull.INSTANCE);
                payload.add("location", com.google.gson.JsonNull.INSTANCE);
                payload.add("world", com.google.gson.JsonNull.INSTANCE);

            }

            payload.addProperty("label", label);
            payload.add("args", instance.gson.toJsonTree(args));
            payload.addProperty("command", getName());

            current.sendEvent("command_" + getName(), payload);
            return true;
        }
    }

    static class BridgeInstance {
        private final PyJavaBridgePlugin plugin;
        private final String name;
        private final Path scriptPath;
        private final Path scriptsDir;
        private final Path runtimeDir;
        private final Gson gson = new Gson();
        private final ObjectRegistry registry = new ObjectRegistry();
        private final Map<String, EventSubscription> subscriptions = new ConcurrentHashMap<>();
        private final Map<UUID, PermissionAttachment> permissionAttachments = new ConcurrentHashMap<>();
        @SuppressWarnings("unused")
        private final AtomicInteger requestId = new AtomicInteger(1);
        private final Map<Integer, PendingEvent> pendingEvents = new ConcurrentHashMap<>();

        private ServerSocket serverSocket;
        private Socket socket;
        private DataInputStream reader;
        private DataOutputStream writer;
        private Thread bridgeThread;
        private Process pythonProcess;
        private volatile boolean running = false;

        BridgeInstance(PyJavaBridgePlugin plugin, String name, Path scriptPath, Path scriptsDir, Path runtimeDir) {
            this.plugin = plugin;
            this.name = name;
            this.scriptPath = scriptPath;
            this.scriptsDir = scriptsDir;
            this.runtimeDir = runtimeDir;
        }

        boolean isRunning() {
            return running && writer != null;
        }

        void start() {
            running = true;

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
                socket = serverSocket.accept();
                plugin.getLogger().info("[" + name + "] Python connected");

                reader = new DataInputStream(socket.getInputStream());
                writer = new DataOutputStream(socket.getOutputStream());

                while (running) {
                    int length;
                    try {
                        length = reader.readInt();
                    } catch (IOException eof) {
                        break;
                    }
                    if (length <= 0) {
                        continue;
                    }
                    byte[] payload = new byte[length];
                    reader.readFully(payload);
                    JsonObject message = JsonParser.parseString(new String(payload, StandardCharsets.UTF_8))
                            .getAsJsonObject();
                    handleMessage(message);
                }

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
                case "ready" -> sendEvent("server_boot", new JsonObject());
                case "event_done" -> handleEventDone(message);
                case "event_cancel" -> handleEventCancel(message);
                case "event_result" -> handleEventResult(message);
                case "register_command" -> handleRegisterCommand(message);
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

            plugin.getLogger().info("[" + name + "] Registering command /" + commandName);
            plugin.registerScriptCommand(commandName, this);
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

            if (eventName.equalsIgnoreCase("server_boot")) {
                return;
            }

            try {

                plugin.getLogger().info(
                        "[" + name + "] Subscribing to event " + eventName + " (oncePerTick=" + oncePerTick + ")");

                if (eventName.equalsIgnoreCase("block_explode")) {
                    EventSubscription blockSub = new EventSubscription(plugin, this, eventName, oncePerTick,
                            org.bukkit.event.block.BlockExplodeEvent.class);

                    blockSub.register();
                    subscriptions.put(eventName + "#block", blockSub);
                    EventSubscription entitySub = new EventSubscription(plugin, this, eventName, oncePerTick,
                            org.bukkit.event.entity.EntityExplodeEvent.class);

                    entitySub.register();
                    subscriptions.put(eventName + "#entity", entitySub);

                } else {
                    EventSubscription subscription = new EventSubscription(plugin, this, eventName, oncePerTick);

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
                    args.add(deserialize(element));
                }
            }

            Object target;

            if (message.has("handle")) {
                int handle = message.get("handle").getAsInt();
                target = registry.get(handle);

            } else if (message.has("target")) {
                String targetName = message.get("target").getAsString();
                target = resolveTarget(targetName, argsObj);

            } else {
                throw new IllegalStateException("Missing target or handle");
            }

            if (target == null && "close".equals(method)) {
                return null;
            }

            if (target == null) {
                String targetLabel = message.has("handle")
                        ? "handle " + message.get("handle").getAsInt()
                        : message.has("target") ? "target " + message.get("target").getAsString() : "unknown";
                throw new EntityGoneException("Target not found: " + targetLabel);
            }

            if (target instanceof org.bukkit.entity.Player player && !player.isOnline()) {
                throw new EntityGoneException("Player is no longer online");
            }

            if (target instanceof org.bukkit.entity.Entity entity) {
                if (!entity.isValid() || entity.isDead()) {
                    throw new EntityGoneException("Entity is no longer valid");
                }
            }

            if ("getUniqueId".equals(method) && target instanceof org.bukkit.entity.Entity entity) {
                return entity.getUniqueId();
            }

            if ("teleport".equals(method) && target instanceof org.bukkit.entity.Entity entity && args.size() == 1) {
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
                        args = new ArrayList<>(1);

                        args.add(new org.bukkit.Location(entity.getWorld(), x, y, z, yaw, pitch));
                    }
                }
            }

            if (target instanceof World worldTarget && args.size() == 2 && ("spawnEntity".equals(method) || "spawn".equals(method))) {
                Object locationObj = args.get(0);
                Object typeObj = args.get(1);

                if ("spawn".equals(method)) {
                    if (!(typeObj instanceof EnumValue) && !(typeObj instanceof String) && !(typeObj instanceof EntityType)) {
                        // Let regular method resolution handle class-based spawn.
                        typeObj = null;
                    }
                }

                if (typeObj == null && "spawn".equals(method)) {
                    // Not an EntityType-based spawn, allow normal method lookup.
                } else {
                    Map<String, Object> options = deserializeArgsObject(argsObj);
                    return spawnEntityWithOptions(worldTarget, locationObj, typeObj, options);
                }
            }

            if (target instanceof Block blockTarget && "getInventory".equals(method)) {
                BlockState state = blockTarget.getState();

                if (state instanceof InventoryHolder holder) {
                    return holder.getInventory();
                }
                return null;
            }

            if (target instanceof org.bukkit.inventory.Inventory inventoryTarget && "close".equals(method)) {
                try {
                    List<org.bukkit.entity.HumanEntity> viewers = new ArrayList<>(inventoryTarget.getViewers());

                    for (org.bukkit.entity.HumanEntity viewer : viewers) {
                        if (viewer != null) {
                            viewer.closeInventory();
                        }
                    }
                } catch (Exception ignored) {}
                return null;
            }

            if (target instanceof org.bukkit.entity.Player playerTarget && "playSound".equals(method)) {
                Sound sound = resolveSound(args.isEmpty() ? null : args.get(0));

                float volume = args.size() > 1 && args.get(1) instanceof Number n ? n.floatValue() : 1.0f;
                float pitch = args.size() > 2 && args.get(2) instanceof Number n ? n.floatValue() : 1.0f;

                if (sound != null) {
                    playerTarget.playSound(playerTarget.getLocation(), sound, volume, pitch);
                }

                return null;
            }

            if (target instanceof org.bukkit.entity.Player playerTarget && ("grantAdvancement".equals(method) || "revokeAdvancement".equals(method))) {
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

                org.bukkit.advancement.AdvancementProgress progress = playerTarget.getAdvancementProgress(advancement);

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

            if (target instanceof org.bukkit.entity.Player playerTarget && "kick".equals(method)) {
                String reason = args.isEmpty() ? "" : String.valueOf(args.get(0));
                try {
                    Method kick = playerTarget.getClass().getMethod("kick", Component.class);
                    kick.invoke(playerTarget, Component.text(reason));
                    return null;
                } catch (Exception ignored) {
                }
                try {
                    Method kick = playerTarget.getClass().getMethod("kick", String.class);
                    kick.invoke(playerTarget, reason);
                    return null;
                } catch (Exception ignored) {
                }
                try {
                    Method kickPlayer = playerTarget.getClass().getMethod("kickPlayer", String.class);
                    kickPlayer.invoke(playerTarget, reason);
                } catch (Exception ignored) {
                }
                return null;
            }

            if (target instanceof org.bukkit.inventory.Inventory inventoryTarget && "getTitle".equals(method)) {
                try {
                    Method getTitle = inventoryTarget.getClass().getMethod("getTitle");
                    Object titleObj = getTitle.invoke(inventoryTarget);

                    return titleObj != null ? titleObj.toString() : "";

                } catch (Exception ignored) {
                    return "";
                }
            }

            if (target instanceof ItemStack itemStack) {
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
                        if (meta != null) {
                            return attributeList(meta);
                        }

                        return List.of();
                    }
                    case "setAttributes" -> {
                        if (meta != null && !args.isEmpty()) {
                            JsonElement element = gson.toJsonTree(args.get(0));

                            applyAttributes(meta, element);
                            itemStack.setItemMeta(meta);
                        }
                        return null;
                    }
                    case "getNbt" -> {
                        return itemStack.serialize();
                    }
                    case "setNbt" -> {
                        if (!args.isEmpty()) {
                            JsonElement element = gson.toJsonTree(args.get(0));
                            ItemStack deserialized = deserializeItemFromNbt(element);

                            if (deserialized != null) {
                                try {
                                    Method setType = ItemStack.class.getMethod("setType", Material.class);

                                    setType.invoke(itemStack, deserialized.getType());
                                } catch (Exception ignored) {}

                                itemStack.setAmount(deserialized.getAmount());

                                if (deserialized.hasItemMeta()) {
                                    itemStack.setItemMeta(deserialized.getItemMeta());
                                }
                            }
                        }

                        return null;
                    }

                    default -> {}
                }
            }

            if (target instanceof org.bukkit.Server && "broadcastMessage".equals(method) && !args.isEmpty()) {
                plugin.getLogger().info("[broadcast] " + args.get(0));
            }

            if ("get_attr".equals(method)) {
                String field = message.get("field").getAsString();

                return getField(target, field);
            }
            if ("set_attr".equals(method)) {
                String field = message.get("field").getAsString();
                Object value = deserialize(message.get("value"));

                setField(target, field, value);
                return null;
            }

            Method[] methods = target.getClass().getMethods();
            for (Method candidate : methods) {
                if (!candidate.getName().equals(method)) {
                    continue;
                }

                if (candidate.getParameterCount() != args.size()) {
                    continue;
                }
                Object[] converted = convertArgs(candidate.getParameterTypes(), args);

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

        private Map<String, Object> deserializeArgsObject(JsonObject argsObj) {
            Map<String, Object> options = new HashMap<>();

            if (argsObj != null) {
                for (Map.Entry<String, JsonElement> entry : argsObj.entrySet()) {
                    options.put(entry.getKey(), deserialize(entry.getValue()));
                }
            }

            return options;
        }

        private Vector resolveVector(Object obj) {
            if (obj instanceof Vector vector) {
                return vector;
            }
            if (obj instanceof Location location) {
                return location.getDirection();
            }
            if (obj instanceof List<?> list && list.size() >= 3) {
                Double x = list.get(0) instanceof Number n ? n.doubleValue() : null;
                Double y = list.get(1) instanceof Number n ? n.doubleValue() : null;
                Double z = list.get(2) instanceof Number n ? n.doubleValue() : null;

                if (x != null && y != null && z != null) {
                    return new Vector(x, y, z);
                }
            }
            if (obj instanceof Map<?, ?> map) {
                Object xObj = map.get("x");
                Object yObj = map.get("y");
                Object zObj = map.get("z");

                Double x = xObj instanceof Number n ? n.doubleValue() : null;
                Double y = yObj instanceof Number n ? n.doubleValue() : null;
                Double z = zObj instanceof Number n ? n.doubleValue() : null;

                if (x != null && y != null && z != null) {
                    return new Vector(x, y, z);
                }
            }
            return null;
        }

        private Location resolveSpawnLocation(World worldTarget, Object locationObj, Map<String, Object> options) {
            Location location = null;

            if (locationObj instanceof Location loc) {
                location = loc.clone();
            } else if (locationObj instanceof List<?> list && list.size() >= 3) {
                Double x = list.get(0) instanceof Number n ? n.doubleValue() : null;
                Double y = list.get(1) instanceof Number n ? n.doubleValue() : null;
                Double z = list.get(2) instanceof Number n ? n.doubleValue() : null;

                if (x != null && y != null && z != null) {
                    float yaw = list.size() > 3 && list.get(3) instanceof Number n ? n.floatValue() : 0f;
                    float pitch = list.size() > 4 && list.get(4) instanceof Number n ? n.floatValue() : 0f;
                    location = new Location(worldTarget, x, y, z, yaw, pitch);
                }
            }

            if (location == null) {
                throw new IllegalArgumentException("spawnEntity requires a Location");
            }

            if (location.getWorld() == null) {
                location.setWorld(worldTarget);
            }

            Object yawObj = options.get("yaw");
            Object pitchObj = options.get("pitch");

            if (yawObj instanceof Number yaw) {
                location.setYaw(yaw.floatValue());
            }
            if (pitchObj instanceof Number pitch) {
                location.setPitch(pitch.floatValue());
            }

            Object facingObj = options.get("facing");
            Vector facing = resolveVector(facingObj);

            if (facing != null) {
                location.setDirection(facing);
            }

            return location;
        }

        private EntityType resolveEntityType(Object typeObj) {
            if (typeObj instanceof EntityType type) {
                return type;
            }
            if (typeObj instanceof EnumValue enumValue) {
                return EntityType.valueOf(enumValue.name);
            }
            if (typeObj instanceof String text) {
                return EntityType.valueOf(text);
            }
            return null;
        }

        private void applyEntityNbt(Entity entity, Object nbtObj) throws Exception {
            if (entity == null || nbtObj == null) {
                return;
            }
            if (!(nbtObj instanceof String snbt)) {
                throw new IllegalArgumentException("nbt must be an SNBT string");
            }

            Class<?> tagParserClass = Class.forName("net.minecraft.nbt.TagParser");
            Method parseTag = tagParserClass.getMethod("parseTag", String.class);
            Object compoundTag = parseTag.invoke(null, snbt);

            Method remove = compoundTag.getClass().getMethod("remove", String.class);
            remove.invoke(compoundTag, "id");

            Method getHandle = entity.getClass().getMethod("getHandle");
            Object nmsEntity = getHandle.invoke(entity);

            Method load = nmsEntity.getClass().getMethod("load", compoundTag.getClass());
            load.invoke(nmsEntity, compoundTag);
        }

        private void applySpawnOptions(Entity entity, Location location, Map<String, Object> options) throws Exception {
            if (entity == null || options == null) {
                return;
            }

            Vector velocity = resolveVector(options.get("velocity"));

            if (velocity != null) {
                entity.setVelocity(velocity);
            }

            boolean hasFacing = options.containsKey("facing");
            boolean hasYawPitch = options.get("yaw") instanceof Number || options.get("pitch") instanceof Number;

            if ((hasFacing || hasYawPitch) && location != null) {
                Location target = location.clone();

                Object yawObj = options.get("yaw");
                Object pitchObj = options.get("pitch");

                if (yawObj instanceof Number yaw) {
                    target.setYaw(yaw.floatValue());
                }
                if (pitchObj instanceof Number pitch) {
                    target.setPitch(pitch.floatValue());
                }

                Vector facing = resolveVector(options.get("facing"));
                if (facing != null) {
                    target.setDirection(facing);
                }

                entity.teleport(target);
            }

            applyEntityNbt(entity, options.get("nbt"));
        }

        private Entity spawnEntityWithOptions(World worldTarget, Object locationObj, Object typeObj, Map<String, Object> options) throws Exception {
            Location location = resolveSpawnLocation(worldTarget, locationObj, options);
            EntityType entityType = resolveEntityType(typeObj);

            if (entityType == null) {
                throw new IllegalArgumentException("spawnEntity requires a valid EntityType");
            }

            Class<? extends Entity> entityClass = entityType.getEntityClass();
            Entity spawned;

            if (entityClass != null && LivingEntity.class.isAssignableFrom(entityClass)) {
                @SuppressWarnings("unchecked")
                Class<? extends LivingEntity> livingClass = (Class<? extends LivingEntity>) entityClass;
                spawned = worldTarget.spawn(location, livingClass, CreatureSpawnEvent.SpawnReason.CUSTOM, true, entity -> {});

            } else {
                NonLivingSpawner nonLivingSpawner = NON_LIVING_SPAWNERS.get(entityType);

                if (nonLivingSpawner == null) {
                    throw new IllegalArgumentException("spawnEntity could not spawn entity type: " + entityType.name());
                }

                spawned = nonLivingSpawner.spawn(worldTarget, location, entityType);
            }

            if (spawned == null) {
                throw new IllegalArgumentException("spawnEntity could not spawn entity type: " + entityType.name());
            }

            applySpawnOptions(spawned, location, options);
            return spawned;
        }

        private Object resolveTarget(String targetName, JsonObject argsObj) throws Exception {
            return switch (targetName) {
                case "server" -> Bukkit.getServer();
                case "chat" -> new ChatFacade();
                case "raycast" -> new RaycastFacade();
                case "permissions" -> new PermissionsFacade();
                case "metrics" -> new MetricsFacade();
                case "ref" -> new RefFacade();
                case "reflect" -> new ReflectFacade();
                case "commands" -> new CommandsFacade(this);
                default -> throw new IllegalArgumentException("Unknown target: " + targetName);
            };
        }

        private static final Object CONVERSION_FAIL = new Object();

        private Object[] convertArgs(Class<?>[] parameterTypes, List<Object> args) {
            Object[] converted = new Object[parameterTypes.length];

            for (int i = 0; i < parameterTypes.length; i++) {
                Object arg = args.get(i);

                Class<?> parameterType = parameterTypes[i];

                if (parameterType.isArray()) {
                    Object arrayValue = convertArrayArg(parameterType, arg);

                    if (arrayValue == CONVERSION_FAIL) {
                        return null;
                    }

                    converted[i] = arrayValue;
                    continue;
                }

                Object value = convertArg(parameterType, arg);

                if (value == CONVERSION_FAIL) {
                    return null;
                }
                converted[i] = value;
            }

            return converted;
        }

        private Object convertArrayArg(Class<?> parameterType, Object arg) {
            if (arg == null) {
                return null;
            }

            if (parameterType.isInstance(arg)) {
                return arg;
            }
            Class<?> componentType = parameterType.getComponentType();

            if (arg instanceof List<?> list) {
                Object array = Array.newInstance(componentType, list.size());

                for (int index = 0; index < list.size(); index++) {
                    Object element = list.get(index);
                    Object convertedElement = convertArg(componentType, element);

                    if (convertedElement == CONVERSION_FAIL) {
                        return CONVERSION_FAIL;
                    }
                    Array.set(array, index, convertedElement);
                }
                return array;
            }
            Object convertedElement = convertArg(componentType, arg);

            if (convertedElement == CONVERSION_FAIL) {
                return CONVERSION_FAIL;
            }

            Object array = Array.newInstance(componentType, 1);
            Array.set(array, 0, convertedElement);
            return array;

        }

        private Object convertArg(Class<?> parameterType, Object arg) {
            if (arg == null) {
                return null;
            }

            if (parameterType.isInstance(arg)) {
                return arg;
            }

            if (parameterType == int.class || parameterType == Integer.class) {
                return arg instanceof Number number ? number.intValue() : CONVERSION_FAIL;
            }

            if (parameterType == double.class || parameterType == Double.class) {
                return arg instanceof Number number ? number.doubleValue() : CONVERSION_FAIL;
            }

            if (parameterType == float.class || parameterType == Float.class) {
                return arg instanceof Number number ? number.floatValue() : CONVERSION_FAIL;
            }

            if (parameterType == long.class || parameterType == Long.class) {
                return arg instanceof Number number ? number.longValue() : CONVERSION_FAIL;
            }

            if (parameterType == boolean.class || parameterType == Boolean.class) {
                return arg;
            }

            if (parameterType.isEnum() && arg instanceof EnumValue enumValue) {
                @SuppressWarnings("unchecked")
                Class<? extends Enum<?>> enumClass = (Class<? extends Enum<?>>) parameterType;

                @SuppressWarnings({ "rawtypes", "unchecked" })

                Enum<?> enumValueResolved = Enum.valueOf((Class) enumClass, enumValue.name);
                return enumValueResolved;
            }

            if (parameterType == UUID.class && arg instanceof UUID uuid) {
                return uuid;
            }

            return CONVERSION_FAIL;
        }

        private Object deserialize(JsonElement element) {
            if (element == null || element.isJsonNull()) {
                return null;
            }

            if (element.isJsonPrimitive()) {
                if (element.getAsJsonPrimitive().isBoolean()) {
                    return element.getAsBoolean();
                }

                if (element.getAsJsonPrimitive().isNumber()) {
                    return element.getAsNumber();
                }
                return element.getAsString();
            }

            if (element.isJsonArray()) {
                List<Object> list = new ArrayList<>();
                for (JsonElement child : element.getAsJsonArray()) {
                    list.add(deserialize(child));
                }
                return list;
            }

            JsonObject obj = element.getAsJsonObject();

            if (obj.has("__handle__")) {
                int handle = obj.get("__handle__").getAsInt();
                return registry.get(handle);
            }

            if (obj.has("__ref__")) {
                JsonObject ref = obj.getAsJsonObject("__ref__");
                String refType = ref.has("type") ? ref.get("type").getAsString() : null;
                String refId = ref.has("id") ? ref.get("id").getAsString() : null;
                return resolveRef(refType, refId);
            }

            if (obj.has("__value__")) {
                return deserializeValueObject(obj);
            }

            if (obj.has("__uuid__")) {
                return UUID.fromString(obj.get("__uuid__").getAsString());
            }

            if (obj.has("__enum__")) {
                return new EnumValue(obj.get("__enum__").getAsString(), obj.get("name").getAsString());
            }
            return obj;
        }

        private Object resolveRef(String refType, String refId) {
            if (refType == null || refId == null) {
                return null;
            }

            return switch (refType.toLowerCase()) {
                case "player" -> {
                    try {
                        yield Bukkit.getPlayer(UUID.fromString(refId));
                    } catch (IllegalArgumentException ex) {
                        yield null;
                    }
                }

                case "player_name" -> Bukkit.getPlayer(refId);

                case "player_inventory" -> {
                    org.bukkit.entity.Player player = null;
                    try {
                        player = Bukkit.getPlayer(UUID.fromString(refId));
                    } catch (IllegalArgumentException ignored) {
                    }
                    if (player == null) {
                        player = Bukkit.getPlayer(refId);
                    }
                    yield player != null ? player.getInventory() : null;
                }

                case "entity" -> {
                    try {
                        yield Bukkit.getEntity(UUID.fromString(refId));
                    } catch (IllegalArgumentException ex) {
                        yield null;
                    }
                }

                case "world" -> Bukkit.getWorld(refId);
                case "block" -> resolveBlockRef(refId);
                case "chunk" -> resolveChunkRef(refId);

                default -> null;
            };
        }

        private Object resolveBlockRef(String refId) {
            String[] parts = refId.split(":");
            if (parts.length < 4) {
                return null;
            }

            String worldName = parts[0];
            org.bukkit.World world = Bukkit.getWorld(worldName);

            if (world == null) {
                return null;
            }

            try {
                int x = Integer.parseInt(parts[1]);
                int y = Integer.parseInt(parts[2]);
                int z = Integer.parseInt(parts[3]);
                return world.getBlockAt(x, y, z);

            } catch (NumberFormatException ex) {
                return null;
            }
        }

        private Object resolveChunkRef(String refId) {
            String[] parts = refId.split(":");

            if (parts.length < 3) {
                return null;
            }

            String worldName = parts[0];
            org.bukkit.World world = Bukkit.getWorld(worldName);

            if (world == null) {
                return null;
            }

            try {
                int x = Integer.parseInt(parts[1]);
                int z = Integer.parseInt(parts[2]);
                return world.getChunkAt(x, z);

            } catch (NumberFormatException ex) {
                return null;
            }
        }

        private Object deserializeValueObject(JsonObject obj) {
            String valueType = obj.get("__value__").getAsString();
            JsonObject fields = obj.has("fields") ? obj.getAsJsonObject("fields") : new JsonObject();

            return switch (valueType) {

                case "Location" -> {
                    double x = fields.has("x") ? fields.get("x").getAsDouble() : 0.0;
                    double y = fields.has("y") ? fields.get("y").getAsDouble() : 0.0;
                    double z = fields.has("z") ? fields.get("z").getAsDouble() : 0.0;

                    float yaw = fields.has("yaw") ? fields.get("yaw").getAsFloat() : 0f;
                    float pitch = fields.has("pitch") ? fields.get("pitch").getAsFloat() : 0f;

                    org.bukkit.World world = null;

                    if (fields.has("world")) {
                        Object worldObj = deserialize(fields.get("world"));

                        if (worldObj instanceof org.bukkit.World w) {
                            world = w;

                        } else if (worldObj instanceof String name) {
                            world = Bukkit.getWorld(name);
                        }
                    }

                    yield new Location(world, x, y, z, yaw, pitch);
                }

                case "Vector" -> {
                    double x = fields.has("x") ? fields.get("x").getAsDouble() : 0.0;
                    double y = fields.has("y") ? fields.get("y").getAsDouble() : 0.0;
                    double z = fields.has("z") ? fields.get("z").getAsDouble() : 0.0;

                    yield new Vector(x, y, z);
                }

                case "Item", "ItemStack" -> {
                    Object typeObj = fields.has("type") ? deserialize(fields.get("type")) : null;
                    Material material = null;

                    if (typeObj instanceof EnumValue enumValue) {
                        material = Material.matchMaterial(enumValue.name);

                    } else if (typeObj instanceof String text) {
                        material = Material.matchMaterial(text);
                    }

                    if (material == null) {
                        material = Material.AIR;
                    }

                    ItemStack stack = null;

                    if (fields.has("nbt")) {
                        stack = deserializeItemFromNbt(fields.get("nbt"));
                    }

                    if (stack == null) {
                        int amount = fields.has("amount") ? fields.get("amount").getAsInt() : 1;
                        stack = new ItemStack(material, amount);
                    }

                    if (stack != null) {
                        ItemMeta meta = stack.getItemMeta();

                        if (meta != null) {
                            if (fields.has("name")) {
                                meta.displayName(Component.text(fields.get("name").getAsString()));
                            }

                            if (fields.has("lore") && fields.get("lore").isJsonArray()) {
                                List<Component> lore = new ArrayList<>();

                                for (JsonElement element : fields.getAsJsonArray("lore")) {
                                    if (!element.isJsonNull()) {
                                        lore.add(Component.text(element.getAsString()));
                                    }
                                }
                                meta.lore(lore);
                            }

                            if (fields.has("customModelData")) {
                                meta.setCustomModelData(fields.get("customModelData").getAsInt());
                            }

                            if (fields.has("attributes")) {
                                applyAttributes(meta, fields.get("attributes"));
                            }

                            stack.setItemMeta(meta);
                        }
                    }

                    yield stack;
                }

                case "ItemMeta" -> {
                    Object typeObj = fields.has("type") ? deserialize(fields.get("type")) : null;
                    Material material = null;

                    if (typeObj instanceof EnumValue enumValue) {
                        material = Material.matchMaterial(enumValue.name);

                    } else if (typeObj instanceof String text) {
                        material = Material.matchMaterial(text);
                    }

                    if (material == null) {
                        material = Material.STONE;
                    }
                    org.bukkit.inventory.meta.ItemMeta meta = Bukkit.getItemFactory().getItemMeta(material);

                    if (meta == null) {
                        yield null;
                    }

                    if (fields.has("customModelData")) {
                        meta.setCustomModelData(fields.get("customModelData").getAsInt());
                    }

                    if (fields.has("lore") && fields.get("lore").isJsonArray()) {
                        List<Component> lore = new ArrayList<>();

                        for (JsonElement element : fields.getAsJsonArray("lore")) {
                            Object loreObj = deserialize(element);
                            if (loreObj != null) {
                                lore.add(Component.text(loreObj.toString()));
                            }
                        }
                        meta.lore(lore);
                    }
                    yield meta;
                }

                case "Effect" -> {
                    Object typeObj = fields.has("type") ? deserialize(fields.get("type")) : null;
                    org.bukkit.potion.PotionEffectType effectType = null;

                    String keyName = null;

                    if (typeObj instanceof EnumValue enumValue) {
                        keyName = enumValue.name;

                    } else if (typeObj instanceof String text) {
                        keyName = text;
                    }

                    if (keyName != null) {
                        if (keyName.contains(":")) {
                            org.bukkit.NamespacedKey key = org.bukkit.NamespacedKey.fromString(keyName.toLowerCase());

                            if (key != null) {
                                effectType = org.bukkit.Registry.POTION_EFFECT_TYPE.get(key);
                            }

                        } else {
                            effectType = org.bukkit.Registry.POTION_EFFECT_TYPE
                                    .get(org.bukkit.NamespacedKey.minecraft(keyName.toLowerCase()));
                        }
                    }

                    if (effectType == null) {
                        yield null;
                    }

                    int duration = fields.has("duration") ? fields.get("duration").getAsInt() : 0;
                    int amplifier = fields.has("amplifier") ? fields.get("amplifier").getAsInt() : 0;

                    boolean ambient = fields.has("ambient") && fields.get("ambient").getAsBoolean();
                    boolean particles = !fields.has("particles") || fields.get("particles").getAsBoolean();
                    boolean icon = !fields.has("icon") || fields.get("icon").getAsBoolean();

                    yield new org.bukkit.potion.PotionEffect(effectType, duration, amplifier, ambient, particles, icon);
                }
                case "Inventory" -> {
                    int size = fields.has("size") ? fields.get("size").getAsInt() : 9;
                    String title = fields.has("title") ? fields.get("title").getAsString() : "";

                    org.bukkit.inventory.Inventory inventory = Bukkit.createInventory(null, size,
                            Component.text(title));

                    if (fields.has("contents") && fields.get("contents").isJsonArray()) {
                        int index = 0;

                        for (JsonElement element : fields.getAsJsonArray("contents")) {
                            Object itemObj = deserialize(element);

                            if (itemObj instanceof ItemStack itemStack) {
                                inventory.setItem(index, itemStack);
                            }

                            index++;
                            if (index >= size) {
                                break;
                            }
                        }
                    }
                    yield inventory;
                }
                case "Block" -> {
                    org.bukkit.World world = null;
                    if (fields.has("world")) {
                        Object worldObj = deserialize(fields.get("world"));

                        if (worldObj instanceof org.bukkit.World w) {
                            world = w;

                        } else if (worldObj instanceof String name) {
                            world = Bukkit.getWorld(name);
                        }
                    }

                    if (world == null) {
                        yield null;
                    }

                    int x = fields.has("x") ? fields.get("x").getAsInt() : 0;
                    int y = fields.has("y") ? fields.get("y").getAsInt() : 0;
                    int z = fields.has("z") ? fields.get("z").getAsInt() : 0;

                    Block block = world.getBlockAt(x, y, z);

                    if (fields.has("type")) {
                        Object typeObj = deserialize(fields.get("type"));
                        Material material = null;

                        if (typeObj instanceof EnumValue enumValue) {
                            material = Material.matchMaterial(enumValue.name);

                        } else if (typeObj instanceof String text) {
                            material = Material.matchMaterial(text);

                        }
                        if (material != null) {
                            block.setType(material);
                        }
                    }
                    yield block;
                }

                case "World" -> {
                    String name = fields.has("name") ? fields.get("name").getAsString() : null;
                    yield name != null ? Bukkit.getWorld(name) : null;
                }

                case "Entity" -> {
                    String uuid = fields.has("uuid") ? fields.get("uuid").getAsString() : null;
                    yield uuid != null ? resolveRef("entity", uuid) : null;
                }

                case "Player" -> {
                    String uuid = fields.has("uuid") ? fields.get("uuid").getAsString() : null;
                    yield uuid != null ? resolveRef("player", uuid) : null;
                }
                default -> obj;
            };
        }

        private JsonElement serialize(Object value) {
            return serialize(value, Collections.newSetFromMap(new java.util.IdentityHashMap<>()));
        }

        private JsonElement serialize(Object value, Set<Object> seen) {
            if (value == null) {
                return gson.toJsonTree(null);
            }

            if (value instanceof Number || value instanceof String || value instanceof Boolean) {
                return gson.toJsonTree(value);
            }

            if (value instanceof UUID uuid) {
                JsonObject obj = new JsonObject();
                obj.addProperty("__uuid__", uuid.toString());
                return obj;
            }

            if (value instanceof java.util.Optional<?> optional) {
                return serialize(optional.orElse(null), seen);
            }

            if (value.getClass().isEnum()) {
                JsonObject obj = new JsonObject();
                obj.addProperty("__enum__", value.getClass().getName());
                obj.addProperty("name", ((Enum<?>) value).name());
                return obj;
            }

            if (value instanceof List<?> list) {
                return gson.toJsonTree(list.stream().map(item -> serialize(item, seen)).toList());
            }

            if (value instanceof Map<?, ?> map) {
                JsonObject obj = new JsonObject();

                for (Map.Entry<?, ?> entry : map.entrySet()) {
                    obj.add(entry.getKey().toString(), serialize(entry.getValue(), seen));
                }

                return obj;
            }

            if (!seen.add(value)) {
                int handle = registry.register(value);
                JsonObject obj = new JsonObject();

                obj.addProperty("__handle__", handle);
                obj.addProperty("__type__", value.getClass().getSimpleName());

                JsonObject fields = new JsonObject();

                if (value instanceof org.bukkit.block.Block block) {
                    fields.addProperty("x", block.getX());
                    fields.addProperty("y", block.getY());
                    fields.addProperty("z", block.getZ());
                }

                if (value instanceof org.bukkit.Location location) {
                    fields.addProperty("x", location.getX());
                    fields.addProperty("y", location.getY());
                    fields.addProperty("z", location.getZ());
                    fields.addProperty("yaw", location.getYaw());
                    fields.addProperty("pitch", location.getPitch());
                }

                if (value instanceof org.bukkit.entity.Player player) {
                    fields.addProperty("name", player.getName());
                    fields.addProperty("uuid", player.getUniqueId().toString());
                }

                if (value instanceof org.bukkit.entity.Entity entity) {
                    fields.addProperty("uuid", entity.getUniqueId().toString());
                }

                if (value instanceof org.bukkit.Chunk chunk) {
                    fields.addProperty("x", chunk.getX());
                    fields.addProperty("z", chunk.getZ());
                }

                if (fields.size() > 0) {
                    obj.add("fields", fields);
                }
                return obj;
            }

            int handle = registry.register(value);
            JsonObject obj = new JsonObject();

            obj.addProperty("__handle__", handle);
            obj.addProperty("__type__", value.getClass().getSimpleName());

            JsonObject fields = new JsonObject();

            if (value instanceof org.bukkit.entity.Player player) {
                fields.addProperty("name", player.getName());
                fields.addProperty("uuid", player.getUniqueId().toString());
                fields.add("location", serialize(player.getLocation(), seen));
                fields.add("world", serialize(player.getWorld(), seen));
                fields.add("gameMode", serialize(player.getGameMode(), seen));
                fields.addProperty("health", player.getHealth());
                fields.addProperty("foodLevel", player.getFoodLevel());
                fields.add("inventory", serialize(player.getInventory(), seen));
            }

            if (value instanceof org.bukkit.entity.Entity entity) {
                fields.addProperty("uuid", entity.getUniqueId().toString());
                fields.add("type", serialize(entity.getType(), seen));
                fields.add("location", serialize(entity.getLocation(), seen));
                fields.add("world", serialize(entity.getWorld(), seen));
                fields.addProperty("is_projectile", entity instanceof Projectile);
                addAttributionFields(entity, fields, seen);
            }

            if (value instanceof org.bukkit.World world) {
                fields.addProperty("name", world.getName());
                fields.addProperty("uuid", world.getUID().toString());
                fields.add("environment", serialize(world.getEnvironment(), seen));
            }

            if (value instanceof org.bukkit.block.Block block) {
                fields.addProperty("x", block.getX());
                fields.addProperty("y", block.getY());
                fields.addProperty("z", block.getZ());
                fields.add("location", serialize(block.getLocation(), seen));
                fields.add("type", serialize(block.getType(), seen));
                fields.add("world", serialize(block.getWorld(), seen));

                BlockState state = block.getState();
                if (state instanceof InventoryHolder holder) {
                    fields.add("inventory", serialize(holder.getInventory(), seen));
                }
            }

            if (value instanceof org.bukkit.Location location) {
                fields.addProperty("x", location.getX());
                fields.addProperty("y", location.getY());
                fields.addProperty("z", location.getZ());
                fields.addProperty("yaw", location.getYaw());
                fields.addProperty("pitch", location.getPitch());

                if (location.getWorld() != null) {
                    fields.add("world", serialize(location.getWorld(), seen));
                }
            }
            if (value instanceof org.bukkit.Chunk chunk) {
                fields.addProperty("x", chunk.getX());
                fields.addProperty("z", chunk.getZ());
                fields.add("world", serialize(chunk.getWorld(), seen));
            }

            if (value instanceof org.bukkit.inventory.ItemStack itemStack) {
                fields.add("type", serialize(itemStack.getType(), seen));
                fields.addProperty("amount", itemStack.getAmount());
                ItemMeta meta = itemStack.getItemMeta();

                if (meta != null) {
                    if (meta.hasDisplayName()) {
                        fields.addProperty("name",
                                PlainTextComponentSerializer.plainText().serialize(meta.displayName()));
                    }
                    if (meta.hasLore()) {
                        List<Component> lore = meta.lore();

                        if (lore != null) {
                            List<String> loreText = new ArrayList<>();

                            for (Component component : lore) {
                                loreText.add(PlainTextComponentSerializer.plainText().serialize(component));
                            }

                            fields.add("lore", gson.toJsonTree(loreText));
                        }
                    }

                    if (meta.hasCustomModelData()) {
                        fields.addProperty("customModelData", meta.getCustomModelData());
                    }

                    JsonArray attributes = serializeAttributes(meta);
                    if (attributes.size() > 0) {
                        fields.add("attributes", attributes);
                    }
                }
                fields.add("nbt", serialize(itemStack.serialize(), seen));
            }

            if (value instanceof org.bukkit.potion.PotionEffect effect) {
                fields.add("type", serialize(effect.getType(), seen));
                fields.addProperty("duration", effect.getDuration());
                fields.addProperty("amplifier", effect.getAmplifier());
                fields.addProperty("ambient", effect.isAmbient());
                fields.addProperty("particles", effect.hasParticles());
                fields.addProperty("icon", effect.hasIcon());
            }

            if (value instanceof org.bukkit.inventory.Inventory inventory) {
                fields.addProperty("size", inventory.getSize());
                fields.add("contents", serialize(Arrays.asList(inventory.getContents()), seen));

                if (inventory.getHolder() != null) {
                    fields.add("holder", serialize(inventory.getHolder(), seen));
                }

                try {
                    Method getTitle = inventory.getClass().getMethod("getTitle");
                    Object titleObj = getTitle.invoke(inventory);

                    if (titleObj != null) {
                        fields.addProperty("title", titleObj.toString());
                    }
                } catch (Exception ignored) {
                }
            }

            if (value instanceof org.bukkit.Server server) {
                fields.addProperty("name", server.getName());
                fields.addProperty("version", server.getVersion());
            }

            obj.add("fields", fields);
            return obj;
        }

        private JsonElement serializeInventoryWithTitle(org.bukkit.inventory.Inventory inventory, String title) {
            JsonElement element = serialize(inventory);

            if (element != null && element.isJsonObject()) {
                JsonObject obj = element.getAsJsonObject();
                JsonObject fields = obj.has("fields") && obj.get("fields").isJsonObject()
                        ? obj.getAsJsonObject("fields")
                        : new JsonObject();

                fields.addProperty("title", title != null ? title : "");
                obj.add("fields", fields);
            }
            return element;
        }

        private String getInventoryViewTitle(InventoryView view) {
            if (view == null) {
                return "";
            }

            try {
                Component component = view.title();
                if (component != null) {
                    return PlainTextComponentSerializer.plainText().serialize(component);
                }

            } catch (Exception ignored) {
            }

            try {
                Method getTitle = view.getClass().getMethod("getTitle");
                Object result = getTitle.invoke(view);
                if (result != null) {
                    return result.toString();
                }

            } catch (Exception ignored) {
            }
            return "";
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

        private JsonArray serializeAttributes(ItemMeta meta) {
            JsonArray array = new JsonArray();
            Multimap<Attribute, AttributeModifier> modifiers = meta.getAttributeModifiers();

            if (modifiers == null) {
                return array;
            }

            for (Map.Entry<Attribute, AttributeModifier> entry : modifiers.entries()) {
                Attribute attribute = entry.getKey();
                AttributeModifier modifier = entry.getValue();
                JsonObject obj = new JsonObject();

                if (attribute.getKey() != null) {
                    obj.addProperty("attribute", attribute.getKey().toString());
                }

                if (modifier.getKey() != null) {
                    obj.addProperty("key", modifier.getKey().toString());
                }

                obj.addProperty("amount", modifier.getAmount());
                obj.addProperty("operation", modifier.getOperation().name());
                array.add(obj);
            }
            return array;
        }

        private void applyAttributes(ItemMeta meta, JsonElement attributesElement) {
            if (attributesElement == null || !attributesElement.isJsonArray()) {
                return;
            }
            meta.setAttributeModifiers(null);
            for (JsonElement element : attributesElement.getAsJsonArray()) {
                if (!element.isJsonObject()) {
                    continue;
                }

                JsonObject obj = element.getAsJsonObject();
                String attributeKey = obj.has("attribute") ? obj.get("attribute").getAsString() : null;

                if (attributeKey == null) {
                    continue;
                }

                NamespacedKey namespacedKey = NamespacedKey.fromString(attributeKey);
                if (namespacedKey == null) {
                    continue;
                }

                Attribute attribute = Registry.ATTRIBUTE.get(namespacedKey);
                if (attribute == null) {
                    continue;
                }

                NamespacedKey modifierKey = null;
                if (obj.has("key")) {
                    modifierKey = NamespacedKey.fromString(obj.get("key").getAsString());
                }

                if (modifierKey == null) {
                    modifierKey = new NamespacedKey(plugin, "attr_" + UUID.randomUUID());
                }

                double amount = obj.has("amount") ? obj.get("amount").getAsDouble() : 0.0;

                AttributeModifier.Operation operation = AttributeModifier.Operation.ADD_NUMBER;

                if (obj.has("operation")) {
                    try {
                        operation = AttributeModifier.Operation.valueOf(obj.get("operation").getAsString());
                    } catch (IllegalArgumentException ignored) {
                    }
                }

                AttributeModifier modifier = new AttributeModifier(modifierKey, amount, operation);
                meta.addAttributeModifier(attribute, modifier);
            }
        }

        private ItemStack deserializeItemFromNbt(JsonElement nbtElement) {
            if (nbtElement == null || nbtElement.isJsonNull()) {
                return null;
            }
            if (!nbtElement.isJsonObject()) {
                return null;
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> map = gson.fromJson(nbtElement, Map.class);
            try {
                return ItemStack.deserialize(map);
            } catch (Exception ex) {
                return null;
            }
        }

        private List<Map<String, Object>> attributeList(ItemMeta meta) {
            List<Map<String, Object>> list = new ArrayList<>();
            Multimap<Attribute, AttributeModifier> modifiers = meta.getAttributeModifiers();
            if (modifiers == null) {
                return list;
            }
            for (Map.Entry<Attribute, AttributeModifier> entry : modifiers.entries()) {
                Attribute attribute = entry.getKey();
                AttributeModifier modifier = entry.getValue();
                Map<String, Object> entryMap = new HashMap<>();
                if (attribute.getKey() != null) {
                    entryMap.put("attribute", attribute.getKey().toString());
                }
                if (modifier.getKey() != null) {
                    entryMap.put("key", modifier.getKey().toString());
                }
                entryMap.put("amount", modifier.getAmount());
                entryMap.put("operation", modifier.getOperation().name());
                list.add(entryMap);
            }
            return list;
        }

        private Object getField(Object target, String field) throws Exception {
            String getterName = "get" + capitalize(field);
            try {
                Method getter = target.getClass().getMethod(getterName);
                return getter.invoke(target);
            } catch (NoSuchMethodException ignored) {
            }
            String isName = "is" + capitalize(field);
            try {
                Method getter = target.getClass().getMethod(isName);
                return getter.invoke(target);
            } catch (NoSuchMethodException ignored) {
            }
            return target.getClass().getField(field).get(target);
        }

        private void setField(Object target, String field, Object value) throws Exception {
            String setterName = "set" + capitalize(field);
            for (Method method : target.getClass().getMethods()) {
                if (!method.getName().equals(setterName) || method.getParameterCount() != 1) {
                    continue;
                }
                Object[] converted = convertArgs(method.getParameterTypes(), List.of(value));
                if (converted != null) {
                    method.invoke(target, converted);
                    return;
                }
            }
            target.getClass().getField(field).set(target, value);
        }

        private void sendEvent(String eventName, JsonObject payload) {
            JsonObject message = new JsonObject();
            message.addProperty("type", "event");
            message.addProperty("event", eventName);
            message.add("payload", payload);
            send(message);
        }

        void sendEvent(Event event, String eventName) {
            if (eventName.equalsIgnoreCase("block_explode")) {
                if (event instanceof BlockExplodeEvent blockExplodeEvent) {
                    handleBlockExplode(blockExplodeEvent.blockList(), event, eventName);
                    return;
                }
                if (event instanceof EntityExplodeEvent entityExplodeEvent) {
                    handleBlockExplode(entityExplodeEvent.blockList(), event, eventName);
                    return;
                }
                return;
            }
            if (event instanceof EntityExplodeEvent && eventName.equalsIgnoreCase("entity_explode")) {
                JsonObject payload = baseEventPayload(event, eventName);
                dispatchCancellableEvent(event, eventName, payload, CancelMode.EVENT, 1000);
                return;
            }

            JsonObject payload = baseEventPayload(event, eventName);
            dispatchCancellableEvent(event, eventName, payload, CancelMode.EVENT, 1000);
        }

        boolean hasSubscription(String eventName) {
            return subscriptions.containsKey(eventName);
        }

        private JsonObject baseEventPayload(Event event, String eventName) {
            JsonObject payload = new JsonObject();
            payload.add("event", serialize(event));
            tryAddPayload(payload, event, "player", "getPlayer", "getWhoClicked");
            tryAddPayload(payload, event, "block", "getBlock", "getClickedBlock");
            tryAddPayload(payload, event, "entity", "getEntity");
            tryAddPayload(payload, event, "damager", "getDamager");
            if (event instanceof EntityDamageEvent damageEvent) {
                payload.addProperty("damage", damageEvent.getDamage());
                payload.addProperty("final_damage", damageEvent.getFinalDamage());
                payload.add("damage_cause", serialize(damageEvent.getCause()));
            }
            tryAddPayload(payload, event, "location", "getLocation");
            tryAddPayload(payload, event, "world", "getWorld");
            tryAddPayload(payload, event, "item", "getItem");
            tryAddPayload(payload, event, "inventory", "getInventory");
            tryAddPayload(payload, event, "chunk", "getChunk");
            if (event instanceof InventoryClickEvent clickEvent) {
                InventoryView view = clickEvent.getView();
                String title = view != null ? getInventoryViewTitle(view) : "";
                org.bukkit.inventory.Inventory inventory = clickEvent.getClickedInventory();
                if (inventory == null && view != null) {
                    inventory = view.getTopInventory();
                }
                if (inventory != null) {
                    payload.add("inventory", serializeInventoryWithTitle(inventory, title));
                }
                payload.addProperty("slot", clickEvent.getSlot());
                payload.add("item", serialize(clickEvent.getCurrentItem()));
            }
            return payload;
        }

        private boolean dispatchCancellableEvent(Event event, String eventName, JsonObject payload,
                CancelMode cancelMode, long timeoutMs) {
            boolean cancellable = event instanceof org.bukkit.event.Cancellable;
            int eventId = -1;
            if (cancellable) {
                eventId = plugin.eventCounter.getAndIncrement();
                payload.addProperty("id", eventId);
                PendingEvent pending = new PendingEvent();
                pending.cancellable = (org.bukkit.event.Cancellable) event;
                pending.event = event;
                pending.id = eventId;
                pendingEvents.put(eventId, pending);
            }
            sendEvent(eventName, payload);
            if (!cancellable) {
                return false;
            }
            PendingEvent pending = pendingEvents.get(eventId);
            if (pending != null) {
                long deadline = System.currentTimeMillis() + timeoutMs;
                try {
                    while (System.currentTimeMillis() < deadline && pending.latch.getCount() > 0) {
                        plugin.drainMainThreadQueue();
                        pending.latch.await(5, java.util.concurrent.TimeUnit.MILLISECONDS);
                    }
                } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                }
                boolean cancelRequested = pending.cancelRequested.get();
                if (pending.chatOverride != null && isChatEvent(pending.event)) {
                    pending.cancellable.setCancelled(true);
                    String message = pending.chatOverride;
                    Bukkit.getScheduler().runTask(plugin,
                            () -> Bukkit.getServer().broadcast(net.kyori.adventure.text.Component.text(message)));
                }
                if (pending.damageOverride != null && pending.event instanceof EntityDamageEvent damageEvent) {
                    damageEvent.setDamage(pending.damageOverride);
                }
                if (cancelRequested && cancelMode == CancelMode.EVENT) {
                    pending.cancellable.setCancelled(true);
                }
                if (pending.latch.getCount() > 0 && timeoutMs >= 100) {
                    plugin.getLogger().warning("[" + name + "] Event handler timed out for " + eventName);
                }
                pendingEvents.remove(eventId);
            }
            return cancellable && ((org.bukkit.event.Cancellable) event).isCancelled();
        }

        @SuppressWarnings("deprecation")
        private boolean isChatEvent(Event event) {
            return event instanceof org.bukkit.event.player.AsyncPlayerChatEvent
                    || event instanceof org.bukkit.event.player.PlayerChatEvent
                    || event instanceof io.papermc.paper.event.player.AsyncChatEvent;
        }

        private void handleBlockExplode(List<org.bukkit.block.Block> blocks, Event event, String eventName) {
            if (blocks.isEmpty()) {
                return;
            }
            List<PendingEvent> batch = new ArrayList<>();
            List<JsonObject> payloads = new ArrayList<>();
            for (org.bukkit.block.Block block : blocks) {
                JsonObject payload = baseEventPayload(event, eventName);
                int eventId = plugin.eventCounter.getAndIncrement();
                payload.addProperty("id", eventId);
                payload.add("block", serialize(block));
                PendingEvent pending = new PendingEvent();
                pending.block = block;
                pending.id = eventId;
                pendingEvents.put(eventId, pending);
                batch.add(pending);
                payloads.add(payload);
            }
            sendBatch(eventName, payloads);
            long deadline = System.currentTimeMillis() + 100;
            try {
                while (System.currentTimeMillis() < deadline) {
                    boolean allDone = true;
                    for (PendingEvent pending : batch) {
                        if (pending.latch.getCount() > 0) {
                            allDone = false;
                            break;
                        }
                    }
                    if (allDone) {
                        break;
                    }
                    plugin.drainMainThreadQueue();
                    Thread.sleep(2);
                }
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            java.util.Iterator<org.bukkit.block.Block> iterator = blocks.iterator();
            while (iterator.hasNext()) {
                org.bukkit.block.Block block = iterator.next();
                boolean cancel = false;
                for (PendingEvent pending : batch) {
                    if (pending.block == block) {
                        cancel = pending.cancelRequested.get();
                        break;
                    }
                }
                if (cancel) {
                    iterator.remove();
                }
            }
            for (PendingEvent pending : batch) {
                pendingEvents.remove(pending.id);
            }
        }

        enum CancelMode {
            EVENT,
            BLOCK_LIST
        }

        private void tryAddPayload(JsonObject payload, Event event, String key, String... methodNames) {
            for (String methodName : methodNames) {
                try {
                    Method method = event.getClass().getMethod(methodName);
                    Object value = method.invoke(event);
                    if (value != null) {
                        payload.add(key, serialize(value));
                        return;
                    }
                } catch (Exception ignored) {
                }
            }
        }

        private void addAttributionFields(org.bukkit.entity.Entity entity, JsonObject fields, Set<Object> seen) {
            Object shooter = null;
            if (entity instanceof Projectile projectile) {
                shooter = projectile.getShooter();
            } else {
                shooter = tryInvokeNoArg(entity, "getShooter");
            }
            addAttribution("shooter", shooter, fields, seen);

            Object source = tryInvokeNoArg(entity, "getSource");
            addAttribution("source", source, fields, seen);

            Object owner = null;
            if (entity instanceof Tameable tameable) {
                fields.addProperty("is_tamed", tameable.isTamed());
                owner = tameable.getOwner();
            }
            if (owner == null) {
                owner = tryInvokeNoArg(entity, "getOwner");
            }
            if (owner == null) {
                owner = tryInvokeNoArg(entity, "getOwningPlayer");
            }
            if (owner == null) {
                owner = tryInvokeNoArg(entity, "getOwningEntity");
            }
            if (owner == null) {
                owner = tryInvokeNoArg(entity, "getSummoner");
            }
            addAttribution("owner", owner, fields, seen);

        }

        private Object tryInvokeNoArg(Object target, String methodName) {
            try {
                Method method = target.getClass().getMethod(methodName);
                if (method.getParameterCount() != 0) {
                    return null;
                }
                return method.invoke(target);
            } catch (Exception ignored) {
                return null;
            }
        }

        private void addAttribution(String key, Object source, JsonObject fields, Set<Object> seen) {
            if (source == null) {
                return;
            }
            if (fields.has(key)) {
                return;
            }

            Object resolved = source;
            if (source instanceof ProjectileSource projectileSource && !(source instanceof Entity)) {
                if (projectileSource instanceof BlockProjectileSource blockSource) {
                    resolved = blockSource.getBlock();
                }
            }

            if ("source".equals(key) || "shooter".equals(key)) {
                if (resolved instanceof Entity sourceEntity) {
                    fields.add(key, serialize(sourceEntity, seen));
                } else if (resolved instanceof org.bukkit.block.Block block) {
                    fields.add(key, serialize(block, seen));
                }
                return;
            }

            if (resolved instanceof Entity sourceEntity) {
                fields.add(key, serialize(sourceEntity, seen));
                fields.addProperty(key + "_uuid", sourceEntity.getUniqueId().toString());
                if (sourceEntity instanceof Player player) {
                    fields.addProperty(key + "_name", player.getName());
                } else {
                    Object name = tryInvokeNoArg(sourceEntity, "getName");
                    if (name instanceof String nameText && !nameText.isBlank()) {
                        fields.addProperty(key + "_name", nameText);
                    }
                }
                return;
            }

            if (resolved instanceof org.bukkit.block.Block block) {
                fields.add(key, serialize(block, seen));
                return;
            }

            if (resolved instanceof AnimalTamer tamer) {
                fields.addProperty(key + "_uuid", tamer.getUniqueId().toString());
                if (tamer.getName() != null) {
                    fields.addProperty(key + "_name", tamer.getName());
                }
                if (tamer instanceof Player player) {
                    fields.add(key, serialize(player, seen));
                }
                return;
            }

            if (resolved instanceof UUID uuid) {
                fields.addProperty(key + "_uuid", uuid.toString());
                return;
            }

            if (resolved instanceof String nameText) {
                fields.addProperty(key + "_name", nameText);
            }
        }

        private void send(JsonObject response) {
            if (writer == null) {
                return;
            }
            try {
                byte[] payload = gson.toJson(response).getBytes(StandardCharsets.UTF_8);
                writer.writeInt(payload.length);
                writer.write(payload);
                writer.flush();
            } catch (IOException e) {
                logError("Failed to send message", e);
            }
        }

        private void sendBatch(String eventName, List<JsonObject> payloads) {
            if (writer == null) {
                return;
            }
            try {
                JsonObject message = new JsonObject();
                message.addProperty("type", "event_batch");
                message.addProperty("event", eventName);
                message.add("payloads", gson.toJsonTree(payloads));
                byte[] payload = gson.toJson(message).getBytes(StandardCharsets.UTF_8);
                writer.writeInt(payload.length);
                writer.write(payload);
                writer.flush();
            } catch (IOException e) {
                logError("Failed to send batch", e);
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
            env.put("PYJAVABRIDGE_RUNTIME", runtimeDir.toString());
            env.put("PYJAVABRIDGE_SCRIPT", scriptPath.toAbsolutePath().toString());
            Path venvDir = scriptsDir.resolve(".venv");
            Path venvPython = venvDir.resolve("bin").resolve("python");
            if (Files.exists(venvPython)) {
                env.put("VIRTUAL_ENV", venvDir.toAbsolutePath().toString());
                String existingPath = env.getOrDefault("PATH", "");
                String venvBin = venvDir.resolve("bin").toAbsolutePath().toString();
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
            Path venvPython = scriptsDir.resolve(".venv").resolve("bin").resolve("python");
            if (Files.exists(venvPython)) {
                Path absolute = venvPython.toAbsolutePath();
                if (Files.exists(absolute) && Files.isExecutable(absolute)) {
                    return absolute.toString();
                }
            }
            return "python3";
        }

        private static String capitalize(String value) {
            if (value == null || value.isEmpty()) {
                return value;
            }
            return value.substring(0, 1).toUpperCase() + value.substring(1);
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

        class ChatFacade {
            public void broadcast(String message) {
                Bukkit.getServer().broadcast(net.kyori.adventure.text.Component.text(message));
            }
        }

        class RaycastFacade {
            public Map<String, Object> trace(org.bukkit.World world, double startX, double startY, double startZ,
                    Float yaw, Float pitch, double maxDistance, double raySize,
                    boolean includeEntities, boolean includeBlocks, boolean ignorePassable) {
                if (world == null) {
                    return null;
                }
                if (!includeEntities && !includeBlocks) {
                    return null;
                }
                Vector direction;
                if (yaw != null && pitch != null) {
                    direction = new Location(world, startX, startY, startZ, yaw, pitch).getDirection();
                } else {
                    return null;
                }
                if (direction.lengthSquared() == 0) {
                    return null;
                }
                direction.normalize();

                Location start = new Location(world, startX, startY, startZ);

                RayTraceResult result;

                if (includeBlocks && includeEntities) {
                    result = world.rayTrace(start, direction, maxDistance, FluidCollisionMode.NEVER, ignorePassable,
                            raySize, entity -> true);

                } else if (includeBlocks) {
                    result = world.rayTraceBlocks(start, direction, maxDistance, FluidCollisionMode.NEVER,
                            ignorePassable);

                } else {
                    result = world.rayTraceEntities(start, direction, maxDistance, raySize, entity -> true);
                }

                Vector hitPosition = result != null ? result.getHitPosition() : null;
                if (hitPosition == null) {
                    hitPosition = start.toVector().add(direction.clone().multiply(maxDistance));
                }
                double hitX = hitPosition.getX();
                double hitY = hitPosition.getY();
                double hitZ = hitPosition.getZ();
                float outYaw = yaw != null ? yaw
                        : (float) Math.toDegrees(Math.atan2(-direction.getX(), direction.getZ()));
                float outPitch = pitch != null ? pitch : (float) Math.toDegrees(Math.asin(-direction.getY()));
                Block hitBlock = result != null ? result.getHitBlock() : null;

                org.bukkit.entity.Entity hitEntity = result != null ? result.getHitEntity() : null;
                Map<String, Object> payload = new HashMap<>();

                payload.put("x", hitX);
                payload.put("y", hitY);
                payload.put("z", hitZ);

                payload.put("entity", hitEntity);
                payload.put("block", hitBlock);

                payload.put("startX", startX);
                payload.put("startY", startY);
                payload.put("startZ", startZ);

                payload.put("yaw", outYaw);
                payload.put("pitch", outPitch);

                return payload;
            }
        }

        class MetricsFacade {
            public List<Double> tps() {
                double[] values = Bukkit.getServer().getTPS();
                List<Double> list = new ArrayList<>(values.length);
                for (double value : values) {
                    list.add(value);
                }
                return list;
            }

            public double mspt() {
                return Bukkit.getServer().getAverageTickTime();
            }

            public double lastTickTime() {
                return plugin.getLastTickTimeMs();
            }

            public int queueLen() {
                return plugin.getQueueLen();
            }
        }

        class RefFacade {
            public Object call(String refType, String refId, String method, List<Object> args) throws Exception {
                return call(refType, refId, method, args, null);
            }

            public Object call(String refType, String refId, String method, List<Object> args, JsonObject kwargs) throws Exception {
                if ("player_name".equalsIgnoreCase(refType) && "getUniqueId".equals(method)) {
                    UUID uuid = plugin.resolvePlayerUuidByName(refId);
                    if (uuid != null) {
                        return uuid;
                    }
                    throw new EntityGoneException("player_name not found: " + refId);
                }
                Object target = resolveRef(refType, refId);
                if (target == null) {
                    throw new EntityGoneException(refType + " not found: " + refId);
                }
                if (target instanceof org.bukkit.entity.Player player && !player.isOnline()) {
                    throw new EntityGoneException("Player is no longer online");
                }
                if (target instanceof Block blockTarget && "getInventory".equals(method)) {
                    BlockState state = blockTarget.getState();
                    if (state instanceof InventoryHolder holder) {
                        return holder.getInventory();
                    }
                    return null;
                }
                if ("getUniqueId".equals(method) && target instanceof org.bukkit.entity.Entity entity) {
                    return entity.getUniqueId();
                }
                if (target instanceof org.bukkit.entity.Player playerTarget && "kick".equals(method)) {
                    String reason = args.isEmpty() ? "" : String.valueOf(args.get(0));
                    try {
                        Method kick = playerTarget.getClass().getMethod("kick", Component.class);
                        kick.invoke(playerTarget, Component.text(reason));
                        return null;
                    } catch (Exception ignored) {
                    }
                    try {
                        Method kick = playerTarget.getClass().getMethod("kick", String.class);
                        kick.invoke(playerTarget, reason);
                        return null;
                    } catch (Exception ignored) {
                    }
                    try {
                        Method kickPlayer = playerTarget.getClass().getMethod("kickPlayer", String.class);
                        kickPlayer.invoke(playerTarget, reason);
                    } catch (Exception ignored) {
                    }
                    return null;
                }
                if (target instanceof World worldTarget && args.size() == 2 && ("spawnEntity".equals(method) || "spawn".equals(method))) {
                    Object locationObj = args.get(0);
                    Object typeObj = args.get(1);

                    if ("spawn".equals(method)) {
                        if (!(typeObj instanceof EnumValue) && !(typeObj instanceof String) && !(typeObj instanceof EntityType)) {
                            typeObj = null;
                        }
                    }

                    if (typeObj == null && "spawn".equals(method)) {
                        // fall through to reflection
                    } else {
                        Map<String, Object> options = kwargs == null ? Collections.emptyMap() : deserializeArgsObject(kwargs);
                        return spawnEntityWithOptions(worldTarget, locationObj, typeObj, options);
                    }
                }
                Method[] methods = target.getClass().getMethods();
                for (Method candidate : methods) {
                    if (!candidate.getName().equals(method)) {
                        continue;
                    }
                    if (candidate.getParameterCount() != args.size()) {
                        continue;
                    }
                    Object[] converted = convertArgs(candidate.getParameterTypes(), args);
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

            public Object getAttr(String refType, String refId, String field) throws Exception {
                Object target = resolveRef(refType, refId);
                if (target == null) {
                    throw new EntityGoneException(refType + " not found: " + refId);
                }
                return getField(target, field);
            }

            public void setAttr(String refType, String refId, String field, Object value) throws Exception {
                Object target = resolveRef(refType, refId);
                if (target == null) {
                    throw new EntityGoneException(refType + " not found: " + refId);
                }
                setField(target, field, value);
            }

            private Object resolveRef(String refType, String refId) {
                return BridgeInstance.this.resolveRef(refType, refId);
            }
        }

        class PermissionsFacade {
            public boolean addPermission(org.bukkit.entity.Player player, String permission, boolean value) {
                if (player == null || permission == null) {
                    return false;
                }
                if (applyLuckPermsPermission(player, permission, value)) {
                    return true;
                }
                PermissionAttachment attachment = permissionAttachments.computeIfAbsent(player.getUniqueId(),
                        id -> player.addAttachment(plugin));
                attachment.setPermission(permission, value);
                return true;
            }

            public boolean removePermission(org.bukkit.entity.Player player, String permission) {
                if (player == null || permission == null) {
                    return false;
                }
                if (applyLuckPermsRemovePermission(player, permission)) {
                    return true;
                }
                PermissionAttachment attachment = permissionAttachments.get(player.getUniqueId());
                if (attachment == null) {
                    return false;
                }
                attachment.unsetPermission(permission);
                return true;
            }

            public List<String> groups(org.bukkit.entity.Player player) {
                if (player == null) {
                    return List.of();
                }
                List<String> result = luckPermsGroups(player);
                return result != null ? result : List.of();
            }

            public String primaryGroup(org.bukkit.entity.Player player) {
                if (player == null) {
                    return null;
                }
                return luckPermsPrimaryGroup(player);
            }

            public boolean hasGroup(org.bukkit.entity.Player player, String group) {
                if (player == null || group == null) {
                    return false;
                }
                List<String> groups = luckPermsGroups(player);
                if (groups == null) {
                    return false;
                }
                return groups.contains(group);
            }

            public boolean addGroup(org.bukkit.entity.Player player, String group) {
                if (player == null || group == null) {
                    return false;
                }
                return applyLuckPermsGroup(player, group, true);
            }

            public boolean removeGroup(org.bukkit.entity.Player player, String group) {
                if (player == null || group == null) {
                    return false;
                }
                return applyLuckPermsGroup(player, group, false);
            }

            private Object luckPermsApi() {
                try {
                    Class<?> apiClass = Class.forName("net.luckperms.api.LuckPerms");
                    Object registration = Bukkit.getServicesManager().getRegistration(apiClass);
                    if (registration == null) {
                        return null;
                    }
                    Method getProvider = registration.getClass().getMethod("getProvider");
                    return getProvider.invoke(registration);
                } catch (Exception ignored) {
                    return null;
                }
            }

            private Object luckPermsUser(Object api, UUID uuid) {
                try {
                    Object userManager = api.getClass().getMethod("getUserManager").invoke(api);
                    Method getUser = userManager.getClass().getMethod("getUser", UUID.class);
                    return getUser.invoke(userManager, uuid);
                } catch (Exception ignored) {
                    return null;
                }
            }

            private boolean saveLuckPermsUser(Object api, Object user) {
                try {
                    Object userManager = api.getClass().getMethod("getUserManager").invoke(api);
                    Class<?> userClass = Class.forName("net.luckperms.api.model.user.User");
                    Method saveUser = userManager.getClass().getMethod("saveUser", userClass);
                    saveUser.invoke(userManager, user);
                    return true;
                } catch (Exception ignored) {
                    return false;
                }
            }

            private boolean applyLuckPermsPermission(org.bukkit.entity.Player player, String permission,
                    boolean value) {
                Object api = luckPermsApi();
                if (api == null) {
                    return false;
                }
                Object user = luckPermsUser(api, player.getUniqueId());
                if (user == null) {
                    return false;
                }
                try {
                    Class<?> nodeClass = Class.forName("net.luckperms.api.node.Node");
                    Object builder = nodeClass.getMethod("builder", String.class).invoke(null, permission);
                    builder.getClass().getMethod("value", boolean.class).invoke(builder, value);
                    Object node = builder.getClass().getMethod("build").invoke(builder);
                    Object data = user.getClass().getMethod("data").invoke(user);
                    data.getClass().getMethod("add", nodeClass).invoke(data, node);
                    return saveLuckPermsUser(api, user);
                } catch (Exception ignored) {
                    return false;
                }
            }

            private boolean applyLuckPermsRemovePermission(org.bukkit.entity.Player player, String permission) {
                Object api = luckPermsApi();
                if (api == null) {
                    return false;
                }
                Object user = luckPermsUser(api, player.getUniqueId());
                if (user == null) {
                    return false;
                }
                try {
                    Class<?> nodeClass = Class.forName("net.luckperms.api.node.Node");
                    Object builder = nodeClass.getMethod("builder", String.class).invoke(null, permission);
                    Object node = builder.getClass().getMethod("build").invoke(builder);
                    Object data = user.getClass().getMethod("data").invoke(user);
                    data.getClass().getMethod("remove", nodeClass).invoke(data, node);
                    return saveLuckPermsUser(api, user);
                } catch (Exception ignored) {
                    return false;
                }
            }

            private boolean applyLuckPermsGroup(org.bukkit.entity.Player player, String group, boolean add) {
                Object api = luckPermsApi();
                if (api == null) {
                    return false;
                }
                Object user = luckPermsUser(api, player.getUniqueId());
                if (user == null) {
                    return false;
                }
                try {
                    Class<?> nodeClass = Class.forName("net.luckperms.api.node.types.InheritanceNode");
                    Object builder = nodeClass.getMethod("builder", String.class).invoke(null, group);
                    Object node = builder.getClass().getMethod("build").invoke(builder);
                    Object data = user.getClass().getMethod("data").invoke(user);
                    if (add) {
                        data.getClass().getMethod("add", nodeClass).invoke(data, node);
                    } else {
                        data.getClass().getMethod("remove", nodeClass).invoke(data, node);
                    }
                    return saveLuckPermsUser(api, user);
                } catch (Exception ignored) {
                    return false;
                }
            }

            private List<String> luckPermsGroups(org.bukkit.entity.Player player) {
                Object api = luckPermsApi();
                if (api == null) {
                    return null;
                }
                Object user = luckPermsUser(api, player.getUniqueId());
                if (user == null) {
                    return null;
                }
                try {
                    Class<?> inheritanceNodeClass = Class.forName("net.luckperms.api.node.types.InheritanceNode");
                    Object nodes = user.getClass().getMethod("getNodes").invoke(user);
                    if (!(nodes instanceof Iterable<?> iterable)) {
                        return List.of();
                    }
                    List<String> groups = new ArrayList<>();
                    for (Object node : iterable) {
                        if (inheritanceNodeClass.isInstance(node)) {
                            Object name = inheritanceNodeClass.getMethod("getGroupName").invoke(node);
                            if (name != null) {
                                groups.add(name.toString());
                            }
                        }
                    }
                    return groups;
                } catch (Exception ignored) {
                    return List.of();
                }
            }

            private String luckPermsPrimaryGroup(org.bukkit.entity.Player player) {
                Object api = luckPermsApi();
                if (api == null) {
                    return null;
                }
                Object user = luckPermsUser(api, player.getUniqueId());
                if (user == null) {
                    return null;
                }
                try {
                    Object group = user.getClass().getMethod("getPrimaryGroup").invoke(user);
                    return group != null ? group.toString() : null;
                } catch (Exception ignored) {
                    return null;
                }
            }
        }

        class ReflectFacade {
            public Class<?> clazz(String name) throws ClassNotFoundException {
                return Class.forName(name);
            }
        }

        class CommandsFacade {
            private final BridgeInstance instance;

            CommandsFacade(BridgeInstance instance) {
                this.instance = instance;
            }

            public void register(String name) {
                plugin.registerScriptCommand(name, instance);
            }
        }

        static class EntityGoneException extends RuntimeException {
            EntityGoneException(String message) {
                super(message);
            }
        }

        class EventSubscription implements Listener {
            private final PyJavaBridgePlugin pluginRef;
            private final Class<? extends Event> eventClass;
            private long lastTick = -1;
            private final EventExecutor executor;

            EventSubscription(PyJavaBridgePlugin plugin, BridgeInstance instance, String eventName, boolean oncePerTick)
                    throws ClassNotFoundException {
                this(plugin, instance, eventName, oncePerTick, null);
            }

            EventSubscription(PyJavaBridgePlugin plugin, BridgeInstance instance, String eventName, boolean oncePerTick,
                    Class<? extends Event> overrideClass) throws ClassNotFoundException {
                this.pluginRef = plugin;
                this.eventClass = overrideClass != null ? overrideClass : resolveEventClass(eventName);
                final BridgeInstance instanceRef = instance;
                final String eventNameRef = eventName;
                final boolean oncePerTickRef = oncePerTick;
                this.executor = (listener, event) -> {
                    if (!eventClass.isInstance(event)) {
                        return;
                    }
                    if (oncePerTickRef) {
                        long tick = pluginRef.getCurrentTick();
                        if (tick == lastTick) {
                            return;
                        }
                        lastTick = tick;
                    }
                    instanceRef.sendEvent(event, eventNameRef);
                    if (event instanceof org.bukkit.event.entity.EntityExplodeEvent
                            && instanceRef.hasSubscription("block_explode")) {
                        instanceRef.sendEvent(event, "block_explode");
                    }
                };
            }

            void register() {
                Bukkit.getPluginManager().registerEvent(eventClass, this, EventPriority.NORMAL, executor, pluginRef,
                        true);
            }

            void unregister() {
                HandlerList.unregisterAll(this);
            }

        }

        static class PendingEvent {
            java.util.concurrent.CountDownLatch latch = new java.util.concurrent.CountDownLatch(1);
            java.util.concurrent.atomic.AtomicBoolean cancelRequested = new java.util.concurrent.atomic.AtomicBoolean(
                    false);
            org.bukkit.event.Cancellable cancellable;
            org.bukkit.block.Block block;
            Event event;
            int id;
            String chatOverride;
            Double damageOverride;
        }

        private Class<? extends Event> resolveEventClass(String eventName) throws ClassNotFoundException {
            if (eventName.equalsIgnoreCase("server_boot")) {
                return org.bukkit.event.server.ServerLoadEvent.class;
            }
            String pascal = toPascalCase(eventName) + "Event";
            String[] packages = new String[] {
                    "org.bukkit.event.player.",
                    "org.bukkit.event.block.",
                    "org.bukkit.event.entity.",
                    "org.bukkit.event.inventory.",
                    "org.bukkit.event.server.",
                    "org.bukkit.event.world.",
                    "org.bukkit.event.weather.",
                    "org.bukkit.event.vehicle.",
                    "org.bukkit.event.hanging.",
                    "org.bukkit.event.enchantment.",
                    "org.bukkit.event.",
            };
            for (String pkg : packages) {
                try {
                    Class<?> clazz = Class.forName(pkg + pascal);
                    if (Event.class.isAssignableFrom(clazz)) {
                        @SuppressWarnings("unchecked")
                        Class<? extends Event> eventClass = (Class<? extends Event>) clazz;
                        return eventClass;
                    }
                } catch (ClassNotFoundException ignored) {
                }
            }
            throw new ClassNotFoundException("Event not found for " + eventName);
        }

        private String toPascalCase(String value) {
            StringBuilder builder = new StringBuilder();
            for (String part : value.split("_")) {
                if (part.isEmpty()) {
                    continue;
                }
                builder.append(part.substring(0, 1).toUpperCase()).append(part.substring(1));
            }
            return builder.toString();
        }
    }

    static class ObjectRegistry {
        private final Map<Integer, Object> objects = new ConcurrentHashMap<>();
        private final AtomicInteger counter = new AtomicInteger(1);

        int register(Object obj) {
            if (obj == null) {
                return 0;
            }
            int id = counter.getAndIncrement();
            objects.put(id, obj);
            return id;
        }

        Object get(int id) {
            return objects.get(id);
        }
    }

    static class EnumValue {
        final String type;
        final String name;

        EnumValue(String type, String name) {
            this.type = type;
            this.name = name;
        }
    }
}
