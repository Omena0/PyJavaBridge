package com.pyjavabridge;

import com.pyjavabridge.util.CallableTask;
import com.pyjavabridge.util.DebugManager;
import com.pyjavabridge.util.PlayerUuidResolver;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.Container;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.ConsoleCommandSender;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;

import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicInteger;

public class PyJavaBridgePlugin extends JavaPlugin {
    private final ConcurrentLinkedQueue<Runnable> mainThreadQueue = new ConcurrentLinkedQueue<>();
    private final Map<String, BridgeInstance> instances = new ConcurrentHashMap<>();
    private final DebugManager debugManager = new DebugManager();
    private final PlayerUuidResolver uuidResolver = new PlayerUuidResolver();
    private Thread fileWatcherThread;
    private volatile boolean watchEnabled = false;

    private BukkitTask mainThreadPump;
    private Method serverExecuteMethod; // MinecraftServer.execute(Runnable) for sub-tick scheduling
    private Object minecraftServer;

    private long currentTick = 0L;
    private long lastTickNano = 0L;
    private double lastTickTimeMs = 0.0;

    private final AtomicInteger eventCounter = new AtomicInteger(1);
    private PacketBridge packetBridge;

    @Override
    public void onEnable() {
        debugManager.setLogger(getLogger());
        getCommand("bridge").setExecutor(this);
        getCommand("bridge").setTabCompleter(this);

        // Resolve MinecraftServer.execute() for sub-tick task scheduling
        try {
            Object craftServer = Bukkit.getServer();
            minecraftServer = craftServer.getClass().getMethod("getServer").invoke(craftServer);
            serverExecuteMethod = minecraftServer.getClass().getMethod("execute", Runnable.class);
            getLogger().info("Sub-tick scheduling enabled via MinecraftServer.execute()");
        } catch (Exception e) {
            getLogger().warning("Sub-tick scheduling unavailable, falling back to tick-based queue: " + e.getMessage());
            serverExecuteMethod = null;
            minecraftServer = null;
        }

        Path dataDir = getDataFolder().toPath();
        Path scriptsDir = dataDir.resolve("scripts");
        Path runtimeDir = dataDir.resolve("runtime");

        try {
            Files.createDirectories(scriptsDir);
            Files.createDirectories(runtimeDir);

            copyRuntimeResource("python/runner.py", runtimeDir.resolve("runner.py"));
            copyBridgePackage(scriptsDir);

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

            drainMainThreadQueue();
        }, 1L, 1L);

        // Initialize ProtocolLib packet bridge if available
        if (getServer().getPluginManager().getPlugin("ProtocolLib") != null) {
            try {
                packetBridge = new PacketBridge(this);
                getLogger().info("ProtocolLib detected — packet API enabled");
            } catch (Exception e) {
                getLogger().warning("ProtocolLib found but packet API could not be initialized: " + e.getMessage());
            }
        }

        startScripts(scriptsDir, runtimeDir);
    }

    @Override
    public void onDisable() {
        stopFileWatcher();

        if (packetBridge != null) {
            packetBridge.removeAllListeners();
        }

        if (mainThreadPump != null) {
            mainThreadPump.cancel();
        }

        // Send shutdown events and wait
        for (BridgeInstance instance : instances.values()) {
            instance.sendShutdownEvent();
        }

        // Then shut down
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
                    .filter(path -> !Files.isDirectory(path))
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

    public void registerScriptCommand(String name, BridgeInstance instance) {
        ScriptCommand.registerScriptCommand(name, instance, null, null, false, getLogger());
    }

    public void registerScriptCommand(String name, BridgeInstance instance, String permission) {
        ScriptCommand.registerScriptCommand(name, instance, permission, null, false, getLogger());
    }

    public void registerScriptCommand(String name, BridgeInstance instance, String permission, Map<Integer, List<String>> completions) {
        ScriptCommand.registerScriptCommand(name, instance, permission, completions, false, getLogger());
    }

    public void registerScriptCommand(String name, BridgeInstance instance, String permission, Map<Integer, List<String>> completions, boolean hasDynamicTabComplete) {
        ScriptCommand.registerScriptCommand(name, instance, permission, completions, hasDynamicTabComplete, getLogger());
    }

    public UUID resolvePlayerUuidByName(String name) {
        return uuidResolver.resolvePlayerUuidByName(name);
    }

    public void sendScriptMessage(String fromScript, String toScript, com.google.gson.JsonElement data) {
        if ("*".equals(toScript)) {
            // Broadcast to all other scripts
            for (var entry : instances.entrySet()) {
                if (!entry.getKey().equals(fromScript) && entry.getValue().isRunning()) {
                    deliverScriptMessage(entry.getValue(), fromScript, data);
                }
            }
        } else {
            BridgeInstance target = instances.get(toScript);
            if (target != null && target.isRunning()) {
                deliverScriptMessage(target, fromScript, data);
            }
        }
    }

    private void deliverScriptMessage(BridgeInstance target, String fromScript, com.google.gson.JsonElement data) {
        com.google.gson.JsonObject payload = new com.google.gson.JsonObject();
        payload.addProperty("from", fromScript);
        payload.add("data", data);
        target.sendEvent("script_message", payload);
    }

    public java.util.Collection<String> getScriptNames() {
        return instances.keySet();
    }

    private void copyRuntimeResource(String resourcePath, Path destination) throws IOException {
        try (InputStream input = getResource(resourcePath)) {
            if (input == null) {
                throw new IOException("Missing resource: " + resourcePath);
            }

            Files.copy(input, destination, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private void copyBridgePackage(Path scriptsDir) throws IOException {
        // Read the manifest listing all bridge package files
        try (InputStream manifest = getResource("python/bridge/MANIFEST")) {
            if (manifest == null) {
                throw new IOException("Missing bridge/MANIFEST");
            }
            java.io.BufferedReader reader = new java.io.BufferedReader(new java.io.InputStreamReader(manifest));
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;
                Path dest = scriptsDir.resolve("bridge").resolve(line);
                Files.createDirectories(dest.getParent());
                copyRuntimeResource("python/bridge/" + line, dest);
            }
        }
    }

    CompletableFuture<Object> runOnMainThread(BridgeInstance instance, CallableTask task) {
        CompletableFuture<Object> future = new CompletableFuture<>();

        Runnable wrapped = () -> {
            try {
                Object result = task.call();
                future.complete(result);

            } catch (Exception ex) {
                future.completeExceptionally(ex);
                instance.logError("Main-thread call failed", ex);
            }
        };

        // Always use mainThreadQueue so drainMainThreadQueue() can process
        // tasks during event dispatch wait loops (avoids deadlock).
        mainThreadQueue.add(wrapped);

        return future;
    }

    private static final long SPIN_WAIT_NS = 5_000_000; // 5ms spin to catch chained calls
    private static final long MAX_SPIN_NS = 20_000_000; // 20ms hard cap per drain cycle

    void drainMainThreadQueue() {
        long spinDeadline = 0;
        long hardDeadline = 0;

        while (true) {
            Runnable task = mainThreadQueue.poll();
            if (task != null) {
                try {
                    task.run();
                } catch (Exception ex) {
                    getLogger().severe("Main-thread task error: " + ex.getMessage());
                }
                long now = System.nanoTime();
                if (hardDeadline == 0) {
                    hardDeadline = now + MAX_SPIN_NS;
                }
                spinDeadline = now + SPIN_WAIT_NS;
                if (spinDeadline > hardDeadline) {
                    spinDeadline = hardDeadline;
                }
                continue;
            }
            if (spinDeadline == 0 || System.nanoTime() >= spinDeadline) {
                break;
            }
            Thread.onSpinWait();
        }
    }

    public long getCurrentTick() {
        return currentTick;
    }

    public double getLastTickTimeMs() {
        return lastTickTimeMs;
    }

    public int getQueueLen() {
        return mainThreadQueue.size();
    }

    private void startFileWatcher(Path scriptsDir) {
        if (fileWatcherThread != null && fileWatcherThread.isAlive()) {
            return;
        }
        watchEnabled = true;
        fileWatcherThread = new Thread(() -> {
            java.nio.file.WatchService watcher = null;
            try {
                watcher = java.nio.file.FileSystems.getDefault().newWatchService();
                scriptsDir.register(watcher,
                        java.nio.file.StandardWatchEventKinds.ENTRY_MODIFY,
                        java.nio.file.StandardWatchEventKinds.ENTRY_CREATE);
                Map<String, Long> pending = new HashMap<>();
                while (watchEnabled) {
                    java.nio.file.WatchKey key = watcher.poll(200, java.util.concurrent.TimeUnit.MILLISECONDS);
                    if (key != null) {
                        for (java.nio.file.WatchEvent<?> event : key.pollEvents()) {
                            Path changed = (Path) event.context();
                            if (changed == null) continue;
                            String filename = changed.getFileName().toString();
                            if (!filename.endsWith(".py")) continue;
                            if (filename.equals("bridge.py") || filename.equals("bridge.pyi") || filename.equals("runner.py")) continue;
                            pending.put(filename, System.currentTimeMillis());
                        }
                        key.reset();
                    }
                    long now = System.currentTimeMillis();
                    var it = pending.entrySet().iterator();
                    while (it.hasNext()) {
                        var entry = it.next();
                        if (now - entry.getValue() >= 1000) {
                            it.remove();
                            String scriptName = entry.getKey();
                            getLogger().info("[Watch] Auto-reloading: " + scriptName);
                            Bukkit.getScheduler().runTask(PyJavaBridgePlugin.this, () -> restartScript(scriptName));
                        }
                    }
                }
            } catch (Exception e) {
                if (watchEnabled) {
                    getLogger().warning("File watcher error: " + e.getMessage());
                }
            } finally {
                if (watcher != null) {
                    try {
                        watcher.close();
                    } catch (Exception ignored) {
                    }
                }
            }
        }, "PyJavaBridge-FileWatcher");
        fileWatcherThread.setDaemon(true);
        fileWatcherThread.start();
    }

    private void stopFileWatcher() {
        watchEnabled = false;
        if (fileWatcherThread != null) {
            fileWatcherThread.interrupt();
            fileWatcherThread = null;
        }
    }

    void addDebugPlayer(UUID playerId) {
        debugManager.addDebugPlayer(playerId);
    }

    void removeDebugPlayer(UUID playerId) {
        debugManager.removeDebugPlayer(playerId);
    }

    void broadcastErrorToDebugPlayers(String message) {
        debugManager.broadcastErrorToDebugPlayers(message);
    }

    void broadcastDebug(String message) {
        debugManager.broadcastDebug(message);
    }

    public Set<UUID> getDebugPlayerUuids() {
        return debugManager.getDebugPlayerUuids();
    }

    public boolean isDebugEnabled() {
        return debugManager.isDebugEnabled();
    }

    public int nextEventId() {
        return eventCounter.getAndIncrement();
    }

    public PacketBridge getPacketBridge() {
        return packetBridge;
    }

    public boolean hasPacketBridge() {
        return packetBridge != null;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0) {
            sender.sendMessage("\u00a7eUsage: /bridge reload [<script>] | debug | plugins | watch | schem <x> <y> <z> <w> <h> <d>");
            return true;
        }

        if (args[0].equalsIgnoreCase("reload")) {
            if (args.length >= 2) {
                restartScript(args[1]);
                sender.sendMessage("\u00a7aReloaded script: " + args[1]);

            } else {
                restartAllScripts();
                sender.sendMessage("\u00a7aReloaded all scripts.");
            }
            return true;
        }

        if (args[0].equalsIgnoreCase("debug")) {
            if (sender instanceof Player player) {
                if (debugManager.isDebugPlayer(player.getUniqueId())) {
                    removeDebugPlayer(player.getUniqueId());
                    player.sendMessage("\u00a7ePyJavaBridge debug disabled.");

                } else {
                    addDebugPlayer(player.getUniqueId());
                    player.sendMessage("\u00a7aPyJavaBridge debug enabled.");
                }

            } else if (sender instanceof ConsoleCommandSender) {
                boolean nowEnabled = !debugManager.isConsoleDebug();
                debugManager.setConsoleDebug(nowEnabled);
                sender.sendMessage(nowEnabled
                        ? "\u00a7aPyJavaBridge console debug enabled."
                        : "\u00a7ePyJavaBridge console debug disabled.");
            }

            return true;
        }

        if (args[0].equalsIgnoreCase("plugins")) {
            if (instances.isEmpty()) {
                sender.sendMessage("\u00a7eNo scripts loaded.");
                return true;
            }
            sender.sendMessage("\u00a7eLoaded scripts:");
            List<String> names = new ArrayList<>(instances.keySet());
            names.sort(String.CASE_INSENSITIVE_ORDER);
            for (String name : names) {
                BridgeInstance instance = instances.get(name);
                String description = instance != null ? getScriptDescription(instance.getScriptPath()) : "";
                if (description == null || description.isBlank()) {
                    description = "(no description)";
                }
                sender.sendMessage("\u00a77- " + name + ": \u00a7f" + description);
            }
            return true;
        }

        if (args[0].equalsIgnoreCase("watch")) {
            if (watchEnabled) {
                stopFileWatcher();
                sender.sendMessage("\u00a7eFile watching disabled.");
            } else {
                startFileWatcher(getDataFolder().toPath().resolve("scripts"));
                sender.sendMessage("\u00a7aFile watching enabled (1000ms debounce).");
            }
            return true;
        }

        if (args[0].equalsIgnoreCase("schem")) {
            if (!(sender instanceof Player player)) {
                sender.sendMessage("\u00a7cThis command can only be used by a player.");
                return true;
            }
            // /bridge schem <x> <y> <z> <width> <height> <depth>
            if (args.length < 7) {
                sender.sendMessage("\u00a7eUsage: /bridge schem <x> <y> <z> <width> <height> <depth>");
                return true;
            }
            try {
                int bx = Integer.parseInt(args[1]);
                int by = Integer.parseInt(args[2]);
                int bz = Integer.parseInt(args[3]);
                int width = Integer.parseInt(args[4]);
                int height = Integer.parseInt(args[5]);
                int depth = Integer.parseInt(args[6]);

                if (width <= 0 || height <= 0 || depth <= 0) {
                    sender.sendMessage("\u00a7cDimensions must be positive.");
                    return true;
                }
                long volume = (long) width * height * depth;
                if (volume > 100000) {
                    sender.sendMessage("\u00a7cRegion too large (max 100,000 blocks).");
                    return true;
                }

                World world = player.getWorld();

                // First pass: collect unique block strings and loot tags
                Map<String, String> lootTags = new HashMap<>();
                // blockDef -> key char (air is always ~)
                Map<String, Character> keyMap = new LinkedHashMap<>();
                // Track block data per position in Y->Z->X order
                List<String> blockDefs = new ArrayList<>();
                // Key pool: printable non-digit chars excluding ~
                String keyPool = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!@#$%^&*()_+-={}|[]:<>?,./";
                int nextKey = 0;

                // Track concrete positions for exit/marker auto-detection
                Set<Integer> limeConcretePos = new HashSet<>();
                Map<String, Set<Integer>> otherConcretePos = new LinkedHashMap<>();
                Map<String, Integer> blockCounts = new HashMap<>();

                for (int y = 0; y < height; y++) {
                    for (int z = 0; z < depth; z++) {
                        for (int x = 0; x < width; x++) {
                            Block block = world.getBlockAt(bx + x, by + y, bz + z);
                            Material mat = block.getType();

                            if (mat == Material.AIR) {
                                blockDefs.add("air");
                                continue;
                            }

                            // Detect concrete for exit/marker auto-detection
                            String matName = mat.name();
                            if (matName.endsWith("_CONCRETE")) {
                                int flatIdx = y * depth * width + z * width + x;
                                if (mat == Material.LIME_CONCRETE) {
                                    limeConcretePos.add(flatIdx);
                                    blockDefs.add("air");
                                } else {
                                    String color = matName.substring(0, matName.length() - 9).toLowerCase();
                                    otherConcretePos.computeIfAbsent(color, k -> new HashSet<>()).add(flatIdx);
                                    blockDefs.add(null);
                                }
                                continue;
                            }

                            String data = block.getBlockData().getAsString();
                            // Strip minecraft: prefix
                            String def = data;
                            if (def.startsWith("minecraft:")) {
                                def = def.substring("minecraft:".length());
                            }

                            // Check for named containers with loot tags
                            BlockState state = block.getState();
                            if (state instanceof Container container) {
                                String customName = null;
                                try {
                                    var displayName = container.customName();
                                    if (displayName != null) {
                                        customName = net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer.plainText().serialize(displayName);
                                    }
                                } catch (Exception e) {
                                    try {
                                        customName = container.getInventory().getType().name();
                                    } catch (Exception ignored) {}
                                }
                                if (customName != null && customName.contains("[loot:")) {
                                    java.util.regex.Matcher m = java.util.regex.Pattern.compile("\\[loot:(\\w+)\\]").matcher(customName);
                                    if (m.find()) {
                                        String tag = m.group(1);
                                        lootTags.put(tag, tag);
                                        // Append container name to block def
                                        if (def.contains("[")) {
                                            def = def.substring(0, def.length() - 1) + ",name=[loot:" + tag + "]]";
                                        } else {
                                            def = def + "[name=[loot:" + tag + "]]";
                                        }
                                    }
                                }
                            }

                            // Assign a key if we haven't seen this def before
                            if (!def.equals("air") && !keyMap.containsKey(def)) {
                                if (nextKey >= keyPool.length()) {
                                    sender.sendMessage("\u00a7cToo many unique block types (max " + keyPool.length() + ").");
                                    return true;
                                }
                                keyMap.put(def, keyPool.charAt(nextKey++));
                            }
                            if (!def.equals("air")) blockCounts.merge(def, 1, (a, b) -> a + b);
                            blockDefs.add(def);
                        }
                    }
                }

                // Compute main block(s) — most common non-air, non-concrete blocks
                int totalNonAir = blockCounts.values().stream().mapToInt(Integer::intValue).sum();
                List<String> mainBlockDefs = new ArrayList<>();
                List<Integer> mainBlockWeights = new ArrayList<>();
                if (totalNonAir > 0) {
                    List<Map.Entry<String, Integer>> sorted = blockCounts.entrySet().stream()
                        .sorted(Map.Entry.<String, Integer>comparingByValue().reversed())
                        .toList();
                    for (var entry : sorted) {
                        double pct = (double) entry.getValue() / totalNonAir * 100;
                        if (pct >= 35.0) {
                            mainBlockDefs.add(entry.getKey());
                            mainBlockWeights.add(entry.getValue());
                        }
                    }
                    if (mainBlockDefs.isEmpty()) {
                        mainBlockDefs.add(sorted.get(0).getKey());
                        mainBlockWeights.add(sorted.get(0).getValue());
                    }
                } else {
                    mainBlockDefs.add("stone");
                    mainBlockWeights.add(1);
                }

                // Ensure main blocks have key assignments
                for (String mainDef : mainBlockDefs) {
                    if (!mainDef.equals("air") && !keyMap.containsKey(mainDef)) {
                        if (nextKey >= keyPool.length()) {
                            sender.sendMessage("\u00a7cToo many unique block types.");
                            return true;
                        }
                        keyMap.put(mainDef, keyPool.charAt(nextKey++));
                    }
                }

                // Replace concrete marker placeholders with main block(s)
                if (!otherConcretePos.isEmpty()) {
                    int totalWeight = mainBlockWeights.stream().mapToInt(Integer::intValue).sum();
                    for (int i = 0; i < blockDefs.size(); i++) {
                        if (blockDefs.get(i) == null) {
                            if (mainBlockDefs.size() == 1) {
                                blockDefs.set(i, mainBlockDefs.get(0));
                            } else {
                                int px = i % width;
                                int pz = (i / width) % depth;
                                int py = i / (width * depth);
                                int hash = (px * 73856093) ^ (py * 19349669) ^ (pz * 83492791);
                                int pick = (hash & 0x7FFFFFFF) % totalWeight;
                                int cumulative = 0;
                                String chosen = mainBlockDefs.get(0);
                                for (int j = 0; j < mainBlockDefs.size(); j++) {
                                    cumulative += mainBlockWeights.get(j);
                                    if (pick < cumulative) {
                                        chosen = mainBlockDefs.get(j);
                                        break;
                                    }
                                }
                                blockDefs.set(i, chosen);
                            }
                        }
                    }
                }

                // Detect exits from lime concrete groups
                List<String> exitDefs = new ArrayList<>();
                if (!limeConcretePos.isEmpty()) {
                    for (Set<Integer> group : schemConnectedComponents(limeConcretePos, width, height, depth)) {
                        String exitDef = schemExitFromGroup(group, width, height, depth);
                        if (exitDef != null) exitDefs.add(exitDef);
                    }
                }

                // Detect markers from other concrete groups
                List<String> markerDefs = new ArrayList<>();
                for (var colorEntry : otherConcretePos.entrySet()) {
                    for (Set<Integer> group : schemConnectedComponents(colorEntry.getValue(), width, height, depth)) {
                        String mDef = schemMarkerFromGroup(colorEntry.getKey(), group, width, height, depth);
                        if (mDef != null) markerDefs.add(mDef);
                    }
                }

                // Build a 3-D key char array [y][z][x] for encoding
                char[][][] grid = new char[height][depth][width];
                int idx = 0;
                for (int y = 0; y < height; y++)
                    for (int z = 0; z < depth; z++)
                        for (int x = 0; x < width; x++)
                            grid[y][z][x] = blockDefs.get(idx++).equals("air") ? '~' : keyMap.get(blockDefs.get(idx - 1));

                // Encode with multi-phase algorithm (volumetric fills + greedy mesh)
                List<String> opsList = encodeSchemOps(grid, width, height, depth);
                StringBuilder ops = new StringBuilder();
                for (String op : opsList) ops.append(op).append('\n');

                // Build full .droom content
                StringBuilder droom = new StringBuilder();
                droom.append("type: generic\n");
                droom.append("width: ").append(width).append("\n");
                droom.append("height: ").append(height).append("\n");
                droom.append("depth: ").append(depth).append("\n");
                if (!lootTags.isEmpty()) {
                    droom.append("loot:");
                    for (var entry : lootTags.entrySet()) {
                        droom.append(" ").append(entry.getKey()).append("=").append(entry.getValue());
                    }
                    droom.append("\n");
                }
                droom.append("\n");

                // Exit definitions (auto-detected from lime concrete)
                for (String exitDef : exitDefs) {
                    droom.append("exit: ").append(exitDef).append("\n");
                }
                // Marker definitions (auto-detected from other concrete)
                for (String markerDef : markerDefs) {
                    droom.append("marker: ").append(markerDef).append("\n");
                }
                if (!exitDefs.isEmpty() || !markerDefs.isEmpty()) droom.append("\n");

                // Key definitions
                for (var entry : keyMap.entrySet()) {
                    droom.append(entry.getValue()).append(": ").append(entry.getKey()).append("\n");
                }
                droom.append("\n---\n");
                droom.append(ops);

                // Write to file
                Path outputDir = getDataFolder().toPath().resolve("schematics");
                Files.createDirectories(outputDir);
                String filename = "schem_" + bx + "_" + by + "_" + bz + ".droom";
                Path outputFile = outputDir.resolve(filename);
                Files.writeString(outputFile, droom.toString(), StandardCharsets.UTF_8);

                sender.sendMessage("\u00a7aSchematic saved to " + outputFile.toAbsolutePath());
                sender.sendMessage("\u00a77Size: " + width + "x" + height + "x" + depth + " (" + volume + " blocks, " + keyMap.size() + " unique types)");
                if (!lootTags.isEmpty()) {
                    sender.sendMessage("\u00a77Loot tags found: " + String.join(", ", lootTags.keySet()));
                }
                if (!exitDefs.isEmpty()) {
                    sender.sendMessage("\u00a77Exits detected: " + exitDefs.size());
                }
                if (!markerDefs.isEmpty()) {
                    sender.sendMessage("\u00a77Markers detected: " + markerDefs.size());
                }
                if (!mainBlockDefs.isEmpty() && !otherConcretePos.isEmpty()) {
                    sender.sendMessage("\u00a77Main block(s): " + String.join(", ", mainBlockDefs));
                }

            } catch (NumberFormatException e) {
                sender.sendMessage("\u00a7cCoordinates and dimensions must be integers.");
            } catch (Exception e) {
                sender.sendMessage("\u00a7cError: " + e.getMessage());
            }
            return true;
        }

        sender.sendMessage("\u00a7cUnknown subcommand.");
        return true;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 1) {
            return List.of("reload", "debug", "plugins", "watch", "schem");
        }

        if (args.length == 2 && args[0].equalsIgnoreCase("reload")) {
            return new ArrayList<>(instances.keySet());
        }

        if (args[0].equalsIgnoreCase("schem") && sender instanceof Player player) {
            Block target = player.getTargetBlockExact(5);
            if (target != null) {
                return switch (args.length) {
                    case 2 -> List.of(String.valueOf(target.getX()));
                    case 3 -> List.of(String.valueOf(target.getY()));
                    case 4 -> List.of(String.valueOf(target.getZ()));
                    default -> List.of();
                };
            }
        }

        return List.of();
    }

    private String getScriptDescription(Path scriptPath) {
        if (scriptPath == null) {
            return "";
        }
        try {
            List<String> lines = Files.readAllLines(scriptPath, StandardCharsets.UTF_8);
            int i = 0;
            // Skip blank lines and comment lines
            while (i < lines.size()) {
                String trimmed = lines.get(i).trim();
                if (trimmed.isEmpty() || trimmed.startsWith("#")) {
                    i++;
                } else {
                    break;
                }
            }
            if (i >= lines.size()) {
                return "";
            }
            String line = lines.get(i).trim();
            String delimiter = null;
            if (line.startsWith("\"\"\"")) {
                delimiter = "\"\"\"";
            } else if (line.startsWith("'''")) {
                delimiter = "'''";
            }
            if (delimiter == null) {
                return "";
            }
            String after = line.substring(delimiter.length());
            // Single-line docstring: """text"""
            if (after.endsWith(delimiter) && after.length() >= delimiter.length()) {
                return after.substring(0, after.length() - delimiter.length()).strip();
            }
            // Multi-line docstring
            StringBuilder sb = new StringBuilder(after);
            for (int j = i + 1; j < lines.size(); j++) {
                String l = lines.get(j);
                int end = l.indexOf(delimiter);
                if (end >= 0) {
                    sb.append(' ').append(l, 0, end);
                    return sb.toString().strip().replaceAll("\\s+", " ");
                }
                sb.append(' ').append(l.trim());
            }
        } catch (IOException e) {
            getLogger().fine("Could not read script description: " + e.getMessage());
        }
        return "";
    }

    // -- Schematic encoding helpers -----------------------------------------------

    /**
     * Encode a 3-D char grid into fill/set operations using a two-phase
     * algorithm: volumetric fills with overwriting, then greedy meshing.
     */
    private static List<String> encodeSchemOps(char[][][] target, int w, int h, int d) {
        char[][][] state = new char[h][d][w];
        for (int y = 0; y < h; y++)
            for (int z = 0; z < d; z++)
                java.util.Arrays.fill(state[y][z], '~');

        List<String> phase1 = new ArrayList<>();
        List<String> baseline = Objects.requireNonNull(schemGreedyMesh(target, state, w, h, d));

        // Phase 1: volumetric fills
        while (true) {
            List<Object[]> candidates = schemDiffCandidates(target, state, w, h, d);
            if (candidates.isEmpty()) break;

            int currentTotal = phase1.size() + baseline.size();
            String bestOp = null;
            char[][][] bestState = null;
            List<String> bestCorr = null;
            int bestTotal = currentTotal;

            for (Object[] cand : candidates) {
                char key = (char) cand[0];
                int[] b = (int[]) cand[1];
                int vol = (b[3]-b[0]+1) * (b[4]-b[1]+1) * (b[5]-b[2]+1);
                if (vol <= 1) continue;

                char[][][] trial = schemCopyState(state, h, d, w);
                for (int y = b[1]; y <= b[4]; y++)
                    for (int z = b[2]; z <= b[5]; z++)
                        for (int x = b[0]; x <= b[3]; x++)
                            trial[y][z][x] = key;

                List<String> trialCorr = schemGreedyMesh(target, trial, w, h, d);
                int trialTotal = phase1.size() + 1 + trialCorr.size();
                if (trialTotal < bestTotal) {
                    bestTotal = trialTotal;
                    bestOp = "fill " + b[0] + " " + b[1] + " " + b[2] + " " + b[3] + " " + b[4] + " " + b[5] + " " + key;
                    bestState = trial;
                    bestCorr = trialCorr;
                }
            }

            if (bestOp == null) break;
            phase1.add(bestOp);
            state = bestState;
            baseline = Objects.requireNonNull(bestCorr);
        }

        List<String> result = new ArrayList<>(phase1);
        result.addAll(baseline);
        return result;
    }

    private static List<Object[]> schemDiffCandidates(char[][][] target, char[][][] state, int w, int h, int d) {
        Map<Character, int[]> bboxes = new HashMap<>();
        for (int y = 0; y < h; y++)
            for (int z = 0; z < d; z++)
                for (int x = 0; x < w; x++) {
                    if (state[y][z][x] != target[y][z][x]) {
                        char k = target[y][z][x];
                        int[] b = bboxes.computeIfAbsent(k, c -> new int[]{w, h, d, -1, -1, -1});
                        if (x < b[0]) b[0] = x; if (y < b[1]) b[1] = y; if (z < b[2]) b[2] = z;
                        if (x > b[3]) b[3] = x; if (y > b[4]) b[4] = y; if (z > b[5]) b[5] = z;
                    }
                }
        List<Object[]> result = new ArrayList<>();
        java.util.Set<Long> seen = new java.util.HashSet<>();
        for (var entry : bboxes.entrySet()) {
            char k = entry.getKey();
            int[] b = entry.getValue();
            if (b[3] < 0) continue;
            int x1 = b[0], y1 = b[1], z1 = b[2], x2 = b[3], y2 = b[4], z2 = b[5];
            // Per-axis insets: xz symmetric, y_bot and y_top independent
            for (int xz = 0; xz < 3; xz++) {
                for (int yb = 0; yb < 3; yb++) {
                    for (int yt = 0; yt < 3; yt++) {
                        int nx1 = x1+xz, nz1 = z1+xz, nx2 = x2-xz, nz2 = z2-xz;
                        int ny1 = y1+yb, ny2 = y2-yt;
                        if (nx1 > nx2 || ny1 > ny2 || nz1 > nz2) continue;
                        // Pack into long for dedup: k(16) + coords(8 bits each × 6)
                        long key = ((long)k << 48) | ((long)nx1<<40) | ((long)ny1<<32) |
                                   ((long)nz1<<24) | ((long)nx2<<16) | ((long)ny2<<8) | nz2;
                        if (seen.add(key))
                            result.add(new Object[]{k, new int[]{nx1, ny1, nz1, nx2, ny2, nz2}});
                    }
                }
            }
        }
        return result;
    }

    private static final int[][] SWEEP_PERMS = {{1,2,0}, {0,2,1}, {2,0,1}};

    private static List<String> schemGreedyMesh(char[][][] target, char[][][] state, int w, int h, int d) {
        List<String> best = null;
        for (int[] perm : SWEEP_PERMS) {
            List<String> ops = schemGreedySweep(target, state, w, h, d, perm);
            if (best == null || ops.size() < best.size()) best = ops;
        }
        return best;
    }

    private static List<String> schemGreedySweep(char[][][] target, char[][][] state, int w, int h, int d, int[] perm) {
        int[] dims = {w, h, d};
        int s0 = dims[perm[0]], s1 = dims[perm[1]], s2 = dims[perm[2]];
        int p0 = perm[0], p1 = perm[1], p2 = perm[2];
        boolean[][][] visited = new boolean[s0][s1][s2];
        List<String> ops = new ArrayList<>();

        for (int a = 0; a < s0; a++) {
            for (int b = 0; b < s1; b++) {
                for (int c = 0; c < s2; c++) {
                    if (visited[a][b][c]) continue;
                    int[] r = new int[3];
                    r[p0] = a; r[p1] = b; r[p2] = c;
                    int cx = r[0], cy = r[1], cz = r[2];
                    if (state[cy][cz][cx] == target[cy][cz][cx]) continue;
                    char key = target[cy][cz][cx];

                    // Expand inner (c)
                    int ec = c;
                    while (ec+1 < s2) {
                        int[] r2 = new int[3]; r2[p0]=a; r2[p1]=b; r2[p2]=ec+1;
                        int nx=r2[0], ny=r2[1], nz=r2[2];
                        if (visited[a][b][ec+1] || state[ny][nz][nx]==target[ny][nz][nx] || target[ny][nz][nx]!=key) break;
                        ec++;
                    }
                    // Expand mid (b)
                    int eb = b;
                    boolean exp = true;
                    while (exp && eb+1 < s1) {
                        for (int jc = c; jc <= ec; jc++) {
                            int[] r2 = new int[3]; r2[p0]=a; r2[p1]=eb+1; r2[p2]=jc;
                            int nx=r2[0], ny=r2[1], nz=r2[2];
                            if (visited[a][eb+1][jc] || state[ny][nz][nx]==target[ny][nz][nx] || target[ny][nz][nx]!=key) { exp=false; break; }
                        }
                        if (exp) eb++;
                    }
                    // Expand outer (a)
                    int ea = a;
                    exp = true;
                    while (exp && ea+1 < s0) {
                        for (int jb = b; jb <= eb && exp; jb++)
                            for (int jc = c; jc <= ec; jc++) {
                                int[] r2 = new int[3]; r2[p0]=ea+1; r2[p1]=jb; r2[p2]=jc;
                                int nx=r2[0], ny=r2[1], nz=r2[2];
                                if (visited[ea+1][jb][jc] || state[ny][nz][nx]==target[ny][nz][nx] || target[ny][nz][nx]!=key) { exp=false; break; }
                            }
                        if (exp) ea++;
                    }

                    for (int ja = a; ja <= ea; ja++)
                        for (int jb = b; jb <= eb; jb++)
                            for (int jc = c; jc <= ec; jc++)
                                visited[ja][jb][jc] = true;

                    int[] rs = new int[3]; rs[p0]=a; rs[p1]=b; rs[p2]=c;
                    int[] re = new int[3]; re[p0]=ea; re[p1]=eb; re[p2]=ec;
                    int x1=rs[0], y1=rs[1], z1=rs[2], x2=re[0], y2=re[1], z2=re[2];

                    if (x1==x2 && y1==y2 && z1==z2)
                        ops.add("set " + x1 + " " + y1 + " " + z1 + " " + key);
                    else
                        ops.add("fill " + x1 + " " + y1 + " " + z1 + " " + x2 + " " + y2 + " " + z2 + " " + key);
                }
            }
        }
        return ops;
    }

    private static char[][][] schemCopyState(char[][][] state, int h, int d, int w) {
        char[][][] copy = new char[h][d][w];
        for (int y = 0; y < h; y++)
            for (int z = 0; z < d; z++)
                System.arraycopy(state[y][z], 0, copy[y][z], 0, w);
        return copy;
    }

    /** Find connected components via BFS in a set of flat-indexed positions. */
    private static List<Set<Integer>> schemConnectedComponents(Set<Integer> positions, int w, int h, int d) {
        List<Set<Integer>> components = new ArrayList<>();
        Set<Integer> remaining = new HashSet<>(positions);
        while (!remaining.isEmpty()) {
            int start = remaining.iterator().next();
            Set<Integer> comp = new HashSet<>();
            ArrayDeque<Integer> queue = new ArrayDeque<>();
            queue.add(start);
            remaining.remove(start);
            while (!queue.isEmpty()) {
                int pos = queue.poll();
                comp.add(pos);
                int px = pos % w, pz = (pos / w) % d, py = pos / (w * d);
                int[][] nbrs = {{px-1,py,pz},{px+1,py,pz},{px,py-1,pz},{px,py+1,pz},{px,py,pz-1},{px,py,pz+1}};
                for (int[] n : nbrs) {
                    if (n[0] >= 0 && n[0] < w && n[1] >= 0 && n[1] < h && n[2] >= 0 && n[2] < d) {
                        int nIdx = n[1] * d * w + n[2] * w + n[0];
                        if (remaining.remove(nIdx)) queue.add(nIdx);
                    }
                }
            }
            components.add(comp);
        }
        return components;
    }

    /** Determine an exit definition from a connected group of lime concrete positions. */
    private static String schemExitFromGroup(Set<Integer> group, int w, int h, int d) {
        int minX = w, maxX = -1, minY = h, maxY = -1, minZ = d, maxZ = -1;
        for (int pos : group) {
            int px = pos % w, pz = (pos / w) % d, py = pos / (w * d);
            if (px < minX) minX = px; if (px > maxX) maxX = px;
            if (py < minY) minY = py; if (py > maxY) maxY = py;
            if (pz < minZ) minZ = pz; if (pz > maxZ) maxZ = pz;
        }
        String facing; int ew, eh;
        if (minX == maxX) {
            facing = (minX == 0) ? "-x" : "+x";
            ew = maxZ - minZ + 1; eh = maxY - minY + 1;
        } else if (minZ == maxZ) {
            facing = (minZ == 0) ? "-z" : "+z";
            ew = maxX - minX + 1; eh = maxY - minY + 1;
        } else if (minY == maxY) {
            facing = (minY == 0) ? "-y" : "+y";
            ew = maxX - minX + 1; eh = maxZ - minZ + 1;
        } else {
            return null;
        }
        return minX + "," + minY + "," + minZ + " " + facing + " " + ew + "x" + eh;
    }

    /** Determine a marker definition from a connected group of concrete positions. */
    private static String schemMarkerFromGroup(String color, Set<Integer> group, int w, int h, int d) {
        int minX = w, maxX = -1, minY = h, maxY = -1, minZ = d, maxZ = -1;
        for (int pos : group) {
            int px = pos % w, pz = (pos / w) % d, py = pos / (w * d);
            if (px < minX) minX = px; if (px > maxX) maxX = px;
            if (py < minY) minY = py; if (py > maxY) maxY = py;
            if (pz < minZ) minZ = pz; if (pz > maxZ) maxZ = pz;
        }
        return color + " " + minX + "," + minY + "," + minZ + " " +
               (maxX - minX + 1) + "x" + (maxY - minY + 1) + "x" + (maxZ - minZ + 1);
    }
}
