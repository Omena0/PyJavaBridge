package com.pyjavabridge;

import com.google.gson.JsonObject;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandMap;
import org.bukkit.command.CommandSender;
import org.bukkit.command.SimpleCommandMap;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.logging.Logger;

/**
 * A dynamically registered Bukkit command that forwards execution and
 * tab-completion to the connected Python script via the bridge.
 */
class ScriptCommand extends Command {
    private volatile BridgeInstance instance;
    private String permission;
    private final Map<Integer, List<String>> completions = new HashMap<>();
    private volatile boolean hasDynamicTabComplete = false;

    ScriptCommand(String name, BridgeInstance instance) {
        super(name);
        this.instance = instance;
    }

    void setInstance(BridgeInstance instance) {
        this.instance = instance;
    }

    String getScriptPermission() {
        return permission;
    }

    void setScriptPermission(String permission) {
        this.permission = permission;
    }

    void setCompletions(Map<Integer, List<String>> completions) {
        this.completions.clear();
        if (completions != null) {
            for (Map.Entry<Integer, List<String>> entry : completions.entrySet()) {
                List<String> copied = new ArrayList<>(entry.getValue().size());
                for (String s : entry.getValue()) {
                    copied.add(s);
                }
                this.completions.put(entry.getKey(), copied);
            }
        }
    }

    void setDynamicTabComplete(boolean dynamic) {
        this.hasDynamicTabComplete = dynamic;
    }

    static void registerScriptCommand(String name, BridgeInstance instance, String permission, Map<Integer, List<String>> completions, boolean hasDynamicTabComplete, Logger logger) {
        CommandMap map = getCommandMap(logger);

        if (map == null) {
            logger.warning("Could not register command: " + name);
            return;
        }

        String commandName = name.toLowerCase();
        boolean rebound = rebindExistingScriptCommands(map, commandName, instance, permission, completions,
                hasDynamicTabComplete, logger);
        if (rebound) {
            return;
        }

        Command existing = map.getCommand(commandName);

        if (existing != null) {
            logger.warning("Command /" + commandName + " already registered by another plugin.");
        }

        ScriptCommand cmd = new ScriptCommand(commandName, instance);
        cmd.setScriptPermission(permission);
        cmd.setCompletions(completions);
        cmd.setDynamicTabComplete(hasDynamicTabComplete);
        map.register("pyjavabridge", cmd);
    }

    @SuppressWarnings("unchecked")
    private static boolean rebindExistingScriptCommands(CommandMap map, String commandName,
            BridgeInstance instance, String permission, Map<Integer, List<String>> completions,
            boolean hasDynamicTabComplete, Logger logger) {
        boolean updated = false;

        Command direct = map.getCommand(commandName);
        if (direct instanceof ScriptCommand scriptCommand) {
            applyRegistration(scriptCommand, instance, permission, completions, hasDynamicTabComplete);
            updated = true;
        }

        if (!(map instanceof SimpleCommandMap simpleMap)) {
            return updated;
        }

        try {
            Field knownCommandsField = SimpleCommandMap.class.getDeclaredField("knownCommands");
            knownCommandsField.setAccessible(true);
            Map<String, Command> knownCommands = (Map<String, Command>) knownCommandsField.get(simpleMap);

            String namespacedKey = "pyjavabridge:" + commandName;
            for (Map.Entry<String, Command> entry : knownCommands.entrySet()) {
                String key = entry.getKey();
                if (!(commandName.equals(key) || namespacedKey.equals(key))) {
                    continue;
                }

                Command cmd = entry.getValue();
                if (cmd instanceof ScriptCommand scriptCommand) {
                    applyRegistration(scriptCommand, instance, permission, completions, hasDynamicTabComplete);
                    updated = true;
                }
            }
        } catch (Exception e) {
            logger.fine("Could not inspect knownCommands for /" + commandName + ": " + e.getMessage());
        }

        return updated;
    }

    private static void applyRegistration(ScriptCommand scriptCommand, BridgeInstance instance,
            String permission, Map<Integer, List<String>> completions, boolean hasDynamicTabComplete) {
        scriptCommand.setInstance(instance);
        scriptCommand.setScriptPermission(permission);
        scriptCommand.setCompletions(completions);
        scriptCommand.setDynamicTabComplete(hasDynamicTabComplete);
    }

    private static CommandMap getCommandMap(Logger logger) {
        try {
            Field field = Bukkit.getServer().getClass().getDeclaredField("commandMap");
            field.setAccessible(true);

            return (CommandMap) field.get(Bukkit.getServer());

        } catch (Exception e) {
            logger.warning("Failed to access commandMap: " + e.getMessage());
            return null;
        }
    }

    @SuppressWarnings("unchecked")
    static void unregisterAllScriptCommands(Logger logger) {
        CommandMap map = getCommandMap(logger);
        if (!(map instanceof SimpleCommandMap simpleMap)) {
            return;
        }

        try {
            Field knownCommandsField = SimpleCommandMap.class.getDeclaredField("knownCommands");
            knownCommandsField.setAccessible(true);
            Map<String, Command> knownCommands = (Map<String, Command>) knownCommandsField.get(simpleMap);

            Set<String> keysToRemove = new java.util.HashSet<>();
            for (Map.Entry<String, Command> entry : knownCommands.entrySet()) {
                if (entry.getValue() instanceof ScriptCommand) {
                    keysToRemove.add(entry.getKey());
                }
            }

            for (String key : keysToRemove) {
                Command command = knownCommands.get(key);
                if (command instanceof ScriptCommand scriptCommand) {
                    try {
                        scriptCommand.unregister(simpleMap);
                    } catch (Exception e) {
                        logger.fine("Failed to unregister script command '" + scriptCommand.getName() + "': " + e.getMessage());
                    }
                }
                try {
                    knownCommands.remove(key);
                } catch (UnsupportedOperationException ignored) {
                    // Some server implementations expose unmodifiable map views.
                }
            }
        } catch (Exception e) {
            logger.warning("Failed to unregister script commands: " + e.getMessage());
        }
    }

    @Override
    public boolean execute(CommandSender sender, String label, String[] args) {
        BridgeInstance current = this.instance;

        if (current == null || !current.isRunning()) {
            sender.sendMessage("\u00a7cScript is not running.");
            return true;
        }

        if (permission != null && !sender.hasPermission(permission)) {
            sender.sendMessage("\u00a7cYou don't have permission to use this command.");
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
        payload.add("args", current.getGson().toJsonTree(args));
        payload.addProperty("command", getName());

        current.sendEvent("command_" + getName(), payload);
        return true;
    }

    @Override
    public List<String> tabComplete(CommandSender sender, String alias, String[] args) {
        if (args.length == 0) return List.of();

        // Dynamic tab completion via Python callback
        if (hasDynamicTabComplete) {
            BridgeInstance current = this.instance;
            if (current != null && current.isRunning()) {
                return current.requestTabComplete(getName(), args, sender);
            }
            return List.of();
        }

        // Static tab completion from registered completions map
        int argIndex = args.length - 1;
        String partial = args[argIndex].toLowerCase();

        List<String> options = completions.get(argIndex);
        if (options == null) {
            options = completions.get(-1);
        }
        if (options == null) return List.of();

        List<String> results = new ArrayList<>(options.size());
        for (String option : options) {
            if (option.toLowerCase().startsWith(partial)) {
                results.add(option);
            }
        }
        return results;
    }
}
