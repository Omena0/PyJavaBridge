package com.pyjavabridge;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.ConsoleCommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.plugin.EventExecutor;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.command.CommandMap;

import java.lang.reflect.Field;
import org.bukkit.event.block.BlockExplodeEvent;
import org.bukkit.event.entity.EntityExplodeEvent;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.lang.reflect.Method;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicInteger;

public class PyJavaBridgePlugin extends JavaPlugin {
    private final ConcurrentLinkedQueue<Runnable> mainThreadQueue = new ConcurrentLinkedQueue<>();
    private final Map<String, BridgeInstance> instances = new ConcurrentHashMap<>();
    private final Set<UUID> debugPlayers = Collections.synchronizedSet(new HashSet<>());
    private BukkitTask mainThreadPump;
    private long currentTick = 0L;
    private final java.util.concurrent.atomic.AtomicInteger eventCounter = new java.util.concurrent.atomic.AtomicInteger(1);

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
            copyRuntimeResource("python/bridge.py", runtimeDir.resolve("bridge.py"));
            copyRuntimeResource("python/runner.py", runtimeDir.resolve("runner.py"));
            copyRuntimeResource("python/bridge.pyi", runtimeDir.resolve("bridge.pyi"));
            copyRuntimeResource("python/bridge.py", scriptsDir.resolve("bridge.py"));
            copyRuntimeResource("python/bridge.pyi", scriptsDir.resolve("bridge.pyi"));
            getLogger().info("PyJavaBridge runtime initialized at " + runtimeDir);
        } catch (IOException e) {
            getLogger().severe("Failed to initialize runtime: " + e.getMessage());
            return;
        }

        mainThreadPump = Bukkit.getScheduler().runTaskTimer(this, () -> {
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
            startScript(scriptPath, getDataFolder().toPath().resolve("scripts"), getDataFolder().toPath().resolve("runtime"));
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
            return;
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
            sender.sendMessage("§eUsage: /bridge reload [<script>] | /bridge debug");
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
        sender.sendMessage("§cUnknown subcommand.");
        return true;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 1) {
            return List.of("reload", "debug");
        }
        if (args.length == 2 && args[0].equalsIgnoreCase("reload")) {
            return new ArrayList<>(instances.keySet());
        }
        return List.of();
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
                sender.sendMessage("§cPyJavaBridge command unavailable (script not running)." );
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
        @SuppressWarnings("unused")
        private final AtomicInteger requestId = new AtomicInteger(1);
        private final Map<Integer, PendingEvent> pendingEvents = new ConcurrentHashMap<>();

        private ServerSocket serverSocket;
        private Socket socket;
        private BufferedReader reader;
        private BufferedWriter writer;
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
                reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
                writer = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8));
                String line;
                while (running && (line = reader.readLine()) != null) {
                    JsonObject message = JsonParser.parseString(line).getAsJsonObject();
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
                case "ready" -> sendEvent("server_boot", new JsonObject());
                case "event_done" -> handleEventDone(message);
                case "event_cancel" -> handleEventCancel(message);
                case "register_command" -> handleRegisterCommand(message);
                default -> sendError(message, "Unknown message type: " + type, null);
            }
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

        private void handleSubscribe(JsonObject message) {
            String eventName = message.get("event").getAsString();
            boolean oncePerTick = message.has("once_per_tick") && message.get("once_per_tick").getAsBoolean();
            if (eventName.equalsIgnoreCase("server_boot")) {
                return;
            }
            try {
                plugin.getLogger().info("[" + name + "] Subscribing to event " + eventName + " (oncePerTick=" + oncePerTick + ")");
                if (eventName.equalsIgnoreCase("block_explode")) {
                    EventSubscription blockSub = new EventSubscription(plugin, this, eventName, oncePerTick, org.bukkit.event.block.BlockExplodeEvent.class);
                    blockSub.register();
                    subscriptions.put(eventName + "#block", blockSub);
                    EventSubscription entitySub = new EventSubscription(plugin, this, eventName, oncePerTick, org.bukkit.event.entity.EntityExplodeEvent.class);
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
                    sendError(id, error.getMessage(), error);
                } else {
                    JsonObject response = new JsonObject();
                    response.addProperty("type", "return");
                    response.addProperty("id", id);
                    response.add("result", serialize(result));
                    send(response);
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
                    return candidate.invoke(target, converted);
                }
            }
            throw new NoSuchMethodException("Method not found: " + method + " on " + target.getClass().getName());
        }

        private Object resolveTarget(String targetName, JsonObject argsObj) throws Exception {
            return switch (targetName) {
                case "server" -> Bukkit.getServer();
                case "chat" -> new ChatFacade();
                case "reflect" -> new ReflectFacade();
                case "commands" -> new CommandsFacade(this);
                default -> throw new IllegalArgumentException("Unknown target: " + targetName);
            };
        }

        private Object[] convertArgs(Class<?>[] parameterTypes, List<Object> args) {
            Object[] converted = new Object[parameterTypes.length];
            for (int i = 0; i < parameterTypes.length; i++) {
                Object arg = args.get(i);
                if (arg == null) {
                    converted[i] = null;
                    continue;
                }
                if (parameterTypes[i].isInstance(arg)) {
                    converted[i] = arg;
                    continue;
                }
                if (parameterTypes[i] == int.class || parameterTypes[i] == Integer.class) {
                    converted[i] = ((Number) arg).intValue();
                    continue;
                }
                if (parameterTypes[i] == double.class || parameterTypes[i] == Double.class) {
                    converted[i] = ((Number) arg).doubleValue();
                    continue;
                }
                if (parameterTypes[i] == float.class || parameterTypes[i] == Float.class) {
                    converted[i] = ((Number) arg).floatValue();
                    continue;
                }
                if (parameterTypes[i] == long.class || parameterTypes[i] == Long.class) {
                    converted[i] = ((Number) arg).longValue();
                    continue;
                }
                if (parameterTypes[i] == boolean.class || parameterTypes[i] == Boolean.class) {
                    converted[i] = arg;
                    continue;
                }
                if (parameterTypes[i].isEnum() && arg instanceof EnumValue enumValue) {
                    @SuppressWarnings("unchecked")
                    Class<? extends Enum<?>> enumClass = (Class<? extends Enum<?>>) parameterTypes[i];
                    @SuppressWarnings({"rawtypes", "unchecked"})
                    Enum<?> enumValueResolved = Enum.valueOf((Class) enumClass, enumValue.name);
                    converted[i] = enumValueResolved;
                    continue;
                }
                if (parameterTypes[i] == UUID.class && arg instanceof UUID uuid) {
                    converted[i] = uuid;
                    continue;
                }
                return null;
            }
            return converted;
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
            if (obj.has("__uuid__")) {
                return UUID.fromString(obj.get("__uuid__").getAsString());
            }
            if (obj.has("__enum__")) {
                return new EnumValue(obj.get("__enum__").getAsString(), obj.get("name").getAsString());
            }
            return obj;
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
                if (itemStack.hasItemMeta()) {
                    fields.add("meta", serialize(itemStack.getItemMeta(), seen));
                }
            }
            if (value instanceof org.bukkit.inventory.meta.ItemMeta itemMeta) {
                fields.addProperty("hasCustomModelData", itemMeta.hasCustomModelData());
                if (itemMeta.hasCustomModelData()) {
                    fields.addProperty("customModelData", itemMeta.getCustomModelData());
                }
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
            }
            if (value instanceof org.bukkit.Server server) {
                fields.addProperty("name", server.getName());
                fields.addProperty("version", server.getVersion());
            }
            obj.add("fields", fields);
            return obj;
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
            tryAddPayload(payload, event, "getPlayer", "player");
            tryAddPayload(payload, event, "getBlock", "block");
            tryAddPayload(payload, event, "getEntity", "entity");
            tryAddPayload(payload, event, "getLocation", "location");
            tryAddPayload(payload, event, "getWorld", "world");
            tryAddPayload(payload, event, "getItem", "item");
            tryAddPayload(payload, event, "getInventory", "inventory");
            tryAddPayload(payload, event, "getChunk", "chunk");
            return payload;
        }

        private boolean dispatchCancellableEvent(Event event, String eventName, JsonObject payload, CancelMode cancelMode, long timeoutMs) {
            boolean cancellable = event instanceof org.bukkit.event.Cancellable;
            int eventId = -1;
            if (cancellable) {
                eventId = plugin.eventCounter.getAndIncrement();
                payload.addProperty("id", eventId);
                PendingEvent pending = new PendingEvent();
                pending.cancellable = (org.bukkit.event.Cancellable) event;
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

        private void tryAddPayload(JsonObject payload, Event event, String methodName, String key) {
            try {
                Method method = event.getClass().getMethod(methodName);
                Object value = method.invoke(event);
                if (value != null) {
                    payload.add(key, serialize(value));
                }
            } catch (Exception ignored) {
            }
        }

        private void send(JsonObject response) {
            if (writer == null) {
                return;
            }
            try {
                writer.write(gson.toJson(response));
                writer.write("\n");
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
                writer.write(gson.toJson(message));
                writer.write("\n");
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
            JsonObject response = new JsonObject();
            response.addProperty("type", "error");
            response.addProperty("id", id);
            response.addProperty("message", error);
            if (ex != null) {
                response.addProperty("details", ex.toString());
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
                return venvPython.toString();
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

        class EventSubscription implements Listener {
            private final PyJavaBridgePlugin pluginRef;
            private final Class<? extends Event> eventClass;
            private long lastTick = -1;
            private final EventExecutor executor;

            EventSubscription(PyJavaBridgePlugin plugin, BridgeInstance instance, String eventName, boolean oncePerTick) throws ClassNotFoundException {
                this(plugin, instance, eventName, oncePerTick, null);
            }

            EventSubscription(PyJavaBridgePlugin plugin, BridgeInstance instance, String eventName, boolean oncePerTick, Class<? extends Event> overrideClass) throws ClassNotFoundException {
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
                    if (event instanceof org.bukkit.event.entity.EntityExplodeEvent && instanceRef.hasSubscription("block_explode")) {
                        instanceRef.sendEvent(event, "block_explode");
                    }
                };
            }

            void register() {
                Bukkit.getPluginManager().registerEvent(eventClass, this, EventPriority.NORMAL, executor, pluginRef, true);
            }

            void unregister() {
                HandlerList.unregisterAll(this);
            }

        }

        static class PendingEvent {
            java.util.concurrent.CountDownLatch latch = new java.util.concurrent.CountDownLatch(1);
            java.util.concurrent.atomic.AtomicBoolean cancelRequested = new java.util.concurrent.atomic.AtomicBoolean(false);
            org.bukkit.event.Cancellable cancellable;
            org.bukkit.block.Block block;
            int id;
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
