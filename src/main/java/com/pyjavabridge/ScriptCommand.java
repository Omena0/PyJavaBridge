package com.pyjavabridge;

import com.google.gson.JsonObject;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;

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
