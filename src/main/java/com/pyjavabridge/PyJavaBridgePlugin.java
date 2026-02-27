package com.pyjavabridge;

import com.pyjavabridge.util.CallableTask;
import com.pyjavabridge.util.DebugManager;
import com.pyjavabridge.util.PlayerUuidResolver;

import org.bukkit.Bukkit;
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
import java.util.ArrayList;
import java.util.HashMap;
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

            drainMainThreadQueue();
        }, 1L, 1L);

        startScripts(scriptsDir, runtimeDir);
    }

    @Override
    public void onDisable() {
        stopFileWatcher();

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

        Runnable wrapped = () -> {
            try {
                Object result = task.call();
                future.complete(result);

            } catch (Exception ex) {
                future.completeExceptionally(ex);
                instance.logError("Main-thread call failed", ex);
            }
        };

        // Use MinecraftServer.execute() for immediate processing (wakes main thread between ticks)
        if (serverExecuteMethod != null) {
            try {
                serverExecuteMethod.invoke(minecraftServer, wrapped);
            } catch (Exception e) {
                // Fall back to queue
                mainThreadQueue.add(wrapped);
            }
        } else {
            mainThreadQueue.add(wrapped);
        }

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

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0) {
            sender.sendMessage("\u00a7eUsage: /bridge reload [<script>] | /bridge debug | /bridge plugins | /bridge watch");
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

        sender.sendMessage("\u00a7cUnknown subcommand.");
        return true;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 1) {
            return List.of("reload", "debug", "plugins", "watch");
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
}
