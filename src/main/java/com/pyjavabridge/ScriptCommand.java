package com.pyjavabridge;

import com.google.gson.JsonObject;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandMap;
import org.bukkit.command.CommandSender;

import java.lang.reflect.Field;
import java.util.logging.Logger;

class ScriptCommand extends Command {
    private volatile BridgeInstance instance;
    private String permission;

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

    static void registerScriptCommand(String name, BridgeInstance instance, String permission, Logger logger) {
        CommandMap map = getCommandMap(logger);

        if (map == null) {
            logger.warning("Could not register command: " + name);
            return;
        }

        String commandName = name.toLowerCase();
        Command existing = map.getCommand(commandName);

        if (existing instanceof ScriptCommand scriptCommand) {
            scriptCommand.setInstance(instance);
            if (permission != null) {
                scriptCommand.setScriptPermission(permission);
            }
            return;
        }

        if (existing != null) {
            logger.warning("Command /" + commandName + " already registered by another plugin.");
        }

        ScriptCommand cmd = new ScriptCommand(commandName, instance);
        if (permission != null) {
            cmd.setScriptPermission(permission);
        }
        map.register("pyjavabridge", cmd);
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
}
